use std::error::Error;

use revm_bytecode::Bytecode;
use revm_context::{BlockEnv, CfgEnv, Context, Host, JournalTr, TxEnv};
use revm_database::{DatabaseCommit, InMemoryDB};
use revm_interpreter::interpreter::{EthInterpreter, ExtBytecode};
use revm_interpreter::{CallInput, InputsImpl, Interpreter, SharedMemory, instruction_table};
use revm_primitives::{Address, Bytes, HashMap, HashSet, U256, hardfork::SpecId, hex};
use serde::{Deserialize, Serialize};

use super::{Frame, frame_from_result};

type StateHost = Context<BlockEnv, TxEnv, CfgEnv, InMemoryDB>;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Case {
    balances: Vec<Balance>,
    storage: Vec<Storage>,
    watch_accounts: Vec<Address>,
    watch_slots: Vec<Slot>,
    transactions: Vec<Transaction>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Balance {
    address: Address,
    value: U256,
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
struct Step {
    frame: Option<Frame>,
    refund_delta: i128,
    refund_counter: i128,
    accounts: Vec<AccountObservation>,
    storage: Vec<SlotObservation>,
}

#[derive(Serialize)]
pub struct TransactionResult {
    steps: Vec<Step>,
    refund_counter: i128,
    gas_refunded: u64,
    gas_used: u64,
    balances: Vec<String>,
    storage: Vec<String>,
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
                        SpecId::CANCUN,
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
    for balance in case.balances {
        let mut info = database.load_account(balance.address)?.info.clone();
        info.balance = balance.value;
        database.insert_account_info(balance.address, info);
    }
    for storage in case.storage {
        database.insert_account_storage(storage.address, storage.slot, storage.value)?;
    }
    let mut results = Vec::new();
    for transaction in &case.transactions {
        let mut host = StateHost::new(database, SpecId::CANCUN);
        host.block.beneficiary = transaction.coinbase;
        host.tx.caller = transaction.sender;
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
        });
    }
    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::{Case, execute};
    use serde_json::{Value, json};

    fn case(original: u64, transactions: Value) -> Case {
        serde_json::from_value(json!({
            "balances": [{"address": "0x0000000000000000000000000000000000000044", "value": "0x63"}],
            "storage": [{"address": "0x0000000000000000000000000000000000000000", "slot": "0x0", "value": format!("0x{original:x}")}],
            "watch_accounts": ["0x0000000000000000000000000000000000000044"],
            "watch_slots": [{"address": "0x0000000000000000000000000000000000000000", "slot": "0x0"}],
            "transactions": transactions,
        })).unwrap()
    }

    fn transaction(actions: Value) -> Value {
        json!({
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
    fn cancun_net_storage_metering_vectors() {
        // EIP-2200 sequence vectors with Cancun's cold charge and refund schedule.
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
