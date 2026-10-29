use std::error::Error;

use revm_bytecode::Bytecode;
use revm_context::{BlockEnv, CfgEnv, Context, Host, JournalTr, TxEnv};
use revm_database::{DatabaseCommit, InMemoryDB};
use revm_interpreter::interpreter::{EthInterpreter, ExtBytecode};
use revm_interpreter::{CallInput, InputsImpl, Interpreter, SharedMemory, instruction_table};
use revm_primitives::{
    Address, B256, Bytes, HashMap, HashSet, Log, TxKind, U256, hardfork::SpecId, hex,
};
use serde::{Deserialize, Serialize};

use super::{Frame, frame_from_result};

type StateHost = Context<BlockEnv, TxEnv, CfgEnv, InMemoryDB>;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Case {
    block_hashes: Vec<BlockHash>,
    accounts: Vec<Account>,
    storage: Vec<Storage>,
    watch_accounts: Vec<Address>,
    watch_slots: Vec<Slot>,
    transactions: Vec<Transaction>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct BlockHash {
    number: U256,
    hash: U256,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Account {
    address: Address,
    balance: U256,
    nonce: u64,
    code: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Slot {
    address: Address,
    slot: U256,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Storage {
    address: Address,
    slot: U256,
    value: U256,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Transaction {
    block_number: U256,
    blob_hashes: Vec<B256>,
    sender: Address,
    destination: Address,
    coinbase: Address,
    access_accounts: Vec<Address>,
    access_slots: Vec<Slot>,
    commit: bool,
    actions: Vec<Action>,
}

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Action {
    Frame {
        code: String,
        calldata: String,
        gas_limit: u64,
        is_static: bool,
    },
    Scope {
        is_static: bool,
        commit: bool,
        actions: Vec<Action>,
    },
}

#[derive(Serialize)]
struct AccountObservation {
    balance: String,
    warm: bool,
}

#[derive(Serialize)]
struct SlotObservation {
    value: String,
    original: String,
    transient: String,
    warm: bool,
}

#[derive(Serialize)]
struct LogObservation {
    address: String,
    topics: Vec<String>,
    data: String,
}

impl From<&Log> for LogObservation {
    fn from(log: &Log) -> Self {
        Self {
            address: format!("{:#x}", log.address),
            topics: log
                .data
                .topics()
                .iter()
                .map(|topic| format!("{topic:#x}"))
                .collect(),
            data: format!("0x{}", hex::encode(&log.data.data)),
        }
    }
}

#[derive(Serialize)]
struct Step {
    frame: Option<Frame>,
    refund_delta: i128,
    refund_counter: i128,
    accounts: Vec<AccountObservation>,
    storage: Vec<SlotObservation>,
    logs: Vec<LogObservation>,
}

#[derive(Serialize)]
pub struct TransactionResult {
    steps: Vec<Step>,
    refund_counter: i128,
    gas_refunded: u64,
    gas_used: u64,
    balances: Vec<String>,
    storage: Vec<String>,
    logs: Vec<LogObservation>,
}

struct Runner<'a> {
    host: StateHost,
    transaction: &'a Transaction,
    accounts: &'a [Address],
    slots: &'a [Slot],
    refund: i128,
    gas_spent: u64,
    steps: Vec<Step>,
}

fn database_storage(database: &InMemoryDB, address: Address, slot: U256) -> U256 {
    database
        .cache
        .accounts
        .get(&address)
        .and_then(|account| account.storage.get(&slot))
        .copied()
        .unwrap_or_default()
}

impl Runner<'_> {
    fn observe(&mut self, frame: Option<Frame>, refund_delta: i128) {
        // Observe the journal directly: querying Host would itself warm the keys.
        let journal = &self.host.journaled_state;
        let accounts = self
            .accounts
            .iter()
            .map(|address| {
                let account = journal.state.get(address);
                let balance = account
                    .map(|account| account.info.balance)
                    .unwrap_or_else(|| {
                        self.host
                            .journaled_state
                            .database
                            .cache
                            .accounts
                            .get(address)
                            .map(|account| account.info.balance)
                            .unwrap_or_default()
                    });
                AccountObservation {
                    balance: format!("0x{balance:064x}"),
                    warm: journal.warm_addresses.is_warm(address)
                        || account.is_some_and(|account| {
                            !account.is_cold_transaction_id(journal.transaction_id)
                        }),
                }
            })
            .collect();
        let storage = self
            .slots
            .iter()
            .map(|key| {
                let slot = journal
                    .state
                    .get(&key.address)
                    .and_then(|account| account.storage.get(&key.slot));
                let original =
                    database_storage(&self.host.journaled_state.database, key.address, key.slot);
                let current = slot.map_or(original, |slot| slot.present_value());
                let transient = journal
                    .transient_storage
                    .get(&(key.address, key.slot))
                    .copied()
                    .unwrap_or_default();
                SlotObservation {
                    value: format!("0x{current:064x}"),
                    original: format!("0x{original:064x}"),
                    transient: format!("0x{transient:064x}"),
                    warm: journal
                        .warm_addresses
                        .is_storage_warm(&key.address, &key.slot)
                        || slot.is_some_and(|slot| {
                            !slot.is_cold_transaction_id(journal.transaction_id)
                        }),
                }
            })
            .collect();
        self.steps.push(Step {
            frame,
            refund_delta,
            refund_counter: self.refund,
            accounts,
            storage,
            logs: journal.logs().iter().map(LogObservation::from).collect(),
        });
    }

    fn actions(
        &mut self,
        actions: &[Action],
        inherited_static: bool,
    ) -> Result<(), Box<dyn Error>> {
        for action in actions {
            match action {
                Action::Frame {
                    code,
                    calldata,
                    gas_limit,
                    is_static,
                } => {
                    let code = hex::decode(code)?;
                    let calldata = hex::decode(calldata)?;
                    if code.len() > 4096 || calldata.len() > 4096 {
                        return Err("case exceeds the current FeVM input capacities".into());
                    }
                    let checkpoint = self.host.journaled_state.checkpoint();
                    let mut interpreter = Interpreter::<EthInterpreter>::new(
                        SharedMemory::new(),
                        ExtBytecode::new(Bytecode::new_legacy(Bytes::from(code))),
                        InputsImpl {
                            target_address: self.transaction.destination,
                            caller_address: self.transaction.sender,
                            input: CallInput::Bytes(Bytes::from(calldata)),
                            ..InputsImpl::default()
                        },
                        inherited_static || *is_static,
                        SpecId::OSAKA,
                        *gas_limit,
                    );
                    let result = interpreter
                        .run_plain(
                            &instruction_table::<EthInterpreter, StateHost>(),
                            &mut self.host,
                        )
                        .into_result_return()
                        .ok_or("CALL/CREATE opcodes are outside this corpus")?;
                    let frame = frame_from_result(&interpreter, &result)?;
                    self.gas_spent = self
                        .gas_spent
                        .checked_add(gas_limit - frame.gas_remaining)
                        .ok_or("aggregate frame gas exceeds u64")?;
                    let refund_delta = if frame.outcome == "success" {
                        self.host.journaled_state.checkpoint_commit();
                        i128::from(result.gas.refunded())
                    } else {
                        self.host.journaled_state.checkpoint_revert(checkpoint);
                        0
                    };
                    self.refund += refund_delta;
                    self.observe(Some(frame), refund_delta);
                }
                Action::Scope {
                    is_static,
                    commit,
                    actions,
                } => {
                    let checkpoint = self.host.journaled_state.checkpoint();
                    let refund_before = self.refund;
                    self.actions(actions, inherited_static || *is_static)?;
                    if *commit {
                        self.host.journaled_state.checkpoint_commit();
                    } else {
                        self.host.journaled_state.checkpoint_revert(checkpoint);
                        self.refund = refund_before;
                    }
                    self.observe(None, 0);
                }
            }
        }
        Ok(())
    }
}

pub fn execute(case: Case) -> Result<Vec<TransactionResult>, Box<dyn Error>> {
    let mut database = InMemoryDB::default();
    for block in case.block_hashes {
        database
            .cache
            .block_hashes
            .insert(block.number, block.hash.into());
    }
    for account in case.accounts {
        let code = Bytecode::new_legacy(Bytes::from(hex::decode(&account.code)?));
        let mut info = database.load_account(account.address)?.info.clone();
        info.balance = account.balance;
        info.nonce = account.nonce;
        info.code_hash = code.hash_slow();
        info.code = Some(code);
        database.insert_account_info(account.address, info);
    }
    for storage in case.storage {
        database.insert_account_storage(storage.address, storage.slot, storage.value)?;
    }
    let mut results = Vec::new();
    for transaction in &case.transactions {
        let mut host = StateHost::new(database, SpecId::OSAKA);
        host.block.beneficiary = transaction.coinbase;
        host.block.number = transaction.block_number;
        host.tx.caller = transaction.sender;
        host.tx.blob_hashes = transaction.blob_hashes.clone();
        host.tx.kind = TxKind::Call(transaction.destination);
        host.tx
            .derive_tx_type()
            .map_err(|error| format!("invalid reference transaction environment: {error:?}"))?;
        let mut access_list: HashMap<Address, HashSet<U256>> = HashMap::default();
        for address in &transaction.access_accounts {
            access_list.entry(*address).or_default();
        }
        for slot in &transaction.access_slots {
            access_list
                .entry(slot.address)
                .or_default()
                .insert(slot.slot);
        }
        host.journaled_state.warm_access_list(access_list);
        host.journaled_state
            .warm_coinbase_account(transaction.coinbase);
        host.journaled_state.warm_precompiles(
            (1_u64..=10)
                .chain([0x100])
                .map(|value| Address::from_word(U256::from(value).into()))
                .collect(),
        );
        // Transaction sender/destination loads occur before any frame checkpoint.
        host.balance(transaction.sender)
            .ok_or("sender load failed")?;
        host.balance(transaction.destination)
            .ok_or("destination load failed")?;
        host.journaled_state.touch(transaction.destination);
        let checkpoint = host.journaled_state.checkpoint();
        let mut runner = Runner {
            host,
            transaction,
            accounts: &case.watch_accounts,
            slots: &case.watch_slots,
            refund: 0,
            gas_spent: 0,
            steps: Vec::new(),
        };
        runner.actions(&transaction.actions, false)?;
        if transaction.commit {
            runner.host.journaled_state.checkpoint_commit();
        } else {
            runner.host.journaled_state.checkpoint_revert(checkpoint);
            runner.refund = 0;
        }
        let gas_refunded =
            u64::try_from(runner.refund.max(0).min(i128::from(runner.gas_spent / 5)))?;
        let logs = runner
            .host
            .journaled_state
            .logs()
            .iter()
            .map(LogObservation::from)
            .collect();
        let state = runner.host.journaled_state.finalize();
        database = runner.host.journaled_state.database;
        database.commit(state);
        let balances = case
            .watch_accounts
            .iter()
            .map(|address| {
                let value = database
                    .cache
                    .accounts
                    .get(address)
                    .map(|account| account.info.balance)
                    .unwrap_or_default();
                format!("0x{value:064x}")
            })
            .collect();
        let storage = case
            .watch_slots
            .iter()
            .map(|key| {
                let value = database_storage(&database, key.address, key.slot);
                format!("0x{value:064x}")
            })
            .collect();
        results.push(TransactionResult {
            steps: runner.steps,
            refund_counter: runner.refund,
            gas_refunded,
            gas_used: runner.gas_spent - gas_refunded,
            balances,
            storage,
            logs,
        });
    }
    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::{Case, execute};
    use revm_primitives::{B256, U256};
    use serde_json::{Value, json};

    fn case(original: u64, transactions: Value) -> Case {
        serde_json::from_value(json!({
            "block_hashes": [],
            "accounts": [{"address": "0x0000000000000000000000000000000000000044", "balance": "0x63", "nonce": 0, "code": ""}],
            "storage": [{"address": "0x0000000000000000000000000000000000000000", "slot": "0x0", "value": format!("0x{original:x}")}],
            "watch_accounts": ["0x0000000000000000000000000000000000000044"],
            "watch_slots": [{"address": "0x0000000000000000000000000000000000000000", "slot": "0x0"}],
            "transactions": transactions,
        })).unwrap()
    }

    fn transaction(actions: Value) -> Value {
        json!({
            "block_number": "0x0", "blob_hashes": [],
            "sender": "0x0000000000000000000000000000000000000000",
            "destination": "0x0000000000000000000000000000000000000000",
            "coinbase": "0x0000000000000000000000000000000000000000",
            "access_accounts": [], "access_slots": [], "commit": true, "actions": actions,
        })
    }

    fn frame(code: &str) -> Value {
        json!({"kind": "frame", "code": code, "calldata": "", "gas_limit": 1_000_000, "is_static": false})
    }

    #[test]
    fn blob_hashes_use_the_blob_transaction_host_path() {
        let mut input = case(0, json!([transaction(json!([frame("5f49600149")]))]));
        let hash = B256::from([1; 32]);
        input.transactions[0].blob_hashes = vec![hash];
        let results = execute(input).unwrap();
        assert_eq!(
            results[0].steps[0]
                .frame
                .as_ref()
                .unwrap()
                .stack
                .as_ref()
                .unwrap(),
            &[format!("{hash:#x}"), format!("0x{:064x}", 0)]
        );
    }

    #[test]
    fn log_observations_follow_real_journal_rollback_and_finalization() {
        let input = case(
            0,
            json!([transaction(json!([
                frame("60aa5f53600560015fa1"),
                {"kind": "scope", "is_static": false, "commit": false, "actions": [frame("5f5fa0")]},
                frame("5f5fa0fe"),
            ]))]),
        );
        let results = execute(input).unwrap();
        assert_eq!(results[0].steps[1].logs.len(), 2);
        assert_eq!(results[0].steps[2].logs.len(), 1);
        assert_eq!(results[0].steps[3].logs.len(), 1);
        assert_eq!(results[0].logs.len(), 1);
        assert_eq!(results[0].logs[0].data, "0xaa");
        assert_eq!(results[0].logs[0].topics, [format!("0x{:064x}", 5)]);
    }

    #[test]
    fn account_code_hash_distinguishes_empty_accounts_and_empty_code() {
        let empty = "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470";
        let abc = "0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45";
        for (balance, nonce, code, expected) in [
            (0_u64, 0, "", format!("0x{:064x}", 0)),
            (1, 0, "", empty.to_string()),
            (0, 1, "", empty.to_string()),
            (0, 0, "616263", abc.to_string()),
        ] {
            let mut input = case(0, json!([transaction(json!([frame("60443b60443f")]))]));
            input.accounts[0].balance = U256::from(balance);
            input.accounts[0].nonce = nonce;
            input.accounts[0].code = code.to_string();
            let results = execute(input).unwrap();
            let frame = results[0].steps[0].frame.as_ref().unwrap();
            assert_eq!(
                frame.stack.as_ref().unwrap(),
                &[format!("0x{:064x}", code.len() / 2), expected,]
            );
            assert_eq!(frame.gas_remaining, 997294);
        }
    }

    #[test]
    fn cancun_net_storage_metering_vectors() {
        // EIP-2200 sequence vectors with Osaka's cold charge and refund schedule.
        for (original, values, spent, refund) in [
            (0, &[0, 0][..], 2312, 0),
            (0, &[0, 1], 22212, 0),
            (0, &[1, 0], 22212, 19900),
            (0, &[1, 2], 22212, 0),
            (0, &[1, 1], 22212, 0),
            (1, &[0, 0], 5112, 4800),
            (1, &[0, 1], 5112, 2800),
            (1, &[0, 2], 5112, 0),
            (1, &[2, 0], 5112, 4800),
            (1, &[2, 3], 5112, 0),
            (1, &[2, 1], 5112, 2800),
            (1, &[2, 2], 5112, 0),
            (1, &[1, 0], 5112, 4800),
            (1, &[1, 2], 5112, 0),
            (1, &[1, 1], 2312, 0),
            (0, &[1, 0, 1], 42218, 19900),
            (1, &[0, 1, 0], 8018, 7600),
        ] {
            let code: String = values
                .iter()
                .map(|value| format!("60{value:02x}600055"))
                .collect();
            let results =
                execute(case(original, json!([transaction(json!([frame(&code)]))]))).unwrap();
            let result = &results[0];
            assert_eq!(
                result.steps[0].frame.as_ref().unwrap().gas_remaining,
                1_000_000 - spent
            );
            assert_eq!(result.refund_counter, refund);
            assert_eq!(
                result.gas_refunded,
                u64::try_from(refund).unwrap().min(spent / 5)
            );
            assert_eq!(
                result.storage[0],
                format!("0x{:064x}", values.last().unwrap())
            );
        }
    }

    #[test]
    fn real_journal_reverts_warmness_storage_and_refunds() {
        let actions = json!([
            {"kind": "scope", "is_static": false, "commit": false, "actions": [
                frame("5f5f5560443160095f5d"),
                {"kind": "scope", "is_static": false, "commit": true, "actions": [frame("60015f55")]}
            ]}, frame("5f545f5c")
        ]);
        let results = execute(case(1, json!([transaction(actions)]))).unwrap();
        let steps = &results[0].steps;
        assert_eq!(steps[0].refund_delta, 4800);
        assert_eq!(steps[1].refund_delta, -2000);
        assert_eq!(steps[3].refund_counter, 0);
        assert!(!steps[3].accounts[0].warm);
        assert!(!steps[3].storage[0].warm);
        assert_eq!(steps[3].storage[0].transient, format!("0x{:064x}", 0));
        assert_eq!(steps[4].frame.as_ref().unwrap().gas_remaining, 997796);
        assert_eq!(steps[0].accounts[0].balance, format!("0x{:064x}", 99));
    }

    #[test]
    fn transaction_boundaries_commit_storage_and_reset_original_and_transient() {
        let first = transaction(json!([frame("60075f5560095f5d")]));
        let second = transaction(json!([frame("5f5c5f5f55")]));
        let results = execute(case(0, json!([first, second]))).unwrap();
        assert_eq!(results[0].storage[0], format!("0x{:064x}", 7));
        let second = &results[1];
        assert_eq!(second.refund_counter, 4800);
        assert_eq!(second.steps[0].storage[0].original, format!("0x{:064x}", 7));
        assert_eq!(
            second.steps[0].storage[0].transient,
            format!("0x{:064x}", 0)
        );
        assert_eq!(
            second.steps[0]
                .frame
                .as_ref()
                .unwrap()
                .stack
                .as_ref()
                .unwrap()[0],
            format!("0x{:064x}", 0)
        );
        assert_eq!(second.storage[0], format!("0x{:064x}", 0));
    }
}
