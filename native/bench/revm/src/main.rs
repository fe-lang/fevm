//! Runs one state-test case through revm, reading the binary case format of
//! FeVM's conformance driver (native/conformance/run.py) from stdin and taking
//! the driver's arguments: `RUNS [TRANSACT]` first decodes the case and builds
//! its pre-state RUNS more times, applying the transaction to each one unless
//! TRANSACT is 0. The last run prints its outcome.

use std::error::Error;
use std::hint::black_box;
use std::io::Read;

use revm::context::result::ExecutionResult;
use revm::context::{BlockEnv, TxEnv};
use revm::context_interface::block::BlobExcessGasAndPrice;
use revm::context_interface::transaction::{AccessList, AccessListItem};
use revm::database::{CacheDB, EmptyDB};
use revm::primitives::hardfork::SpecId;
use revm::primitives::{Address, B256, Bytes, Log, TxKind, U256, keccak256};
use revm::state::{AccountInfo, Bytecode};
use revm::{Context, ExecuteEvm, MainBuilder, MainContext};

struct Reader<'a> {
    data: &'a [u8],
    position: usize,
}

impl Reader<'_> {
    fn bytes(&mut self, len: usize) -> &[u8] {
        let bytes = &self.data[self.position..self.position + len];
        self.position += len;
        bytes
    }

    fn word(&mut self, len: usize) -> U256 {
        U256::from_be_slice(self.bytes(len))
    }

    fn address(&mut self) -> Address {
        Address::from_slice(self.bytes(20))
    }

    fn count(&mut self) -> usize {
        self.word(4).to()
    }
}

struct Account {
    address: Address,
    info: AccountInfo,
    storage: Vec<(U256, U256)>,
}

struct Case {
    block: BlockEnv,
    chain_id: u64,
    accounts: Vec<Account>,
    tx: TxEnv,
}

fn decode(data: &[u8]) -> Case {
    let mut reader = Reader { data, position: 0 };
    assert_eq!(reader.word(1), U256::from(1));
    let beneficiary = reader.address();
    let number = reader.word(32);
    let timestamp = reader.word(32);
    let prevrandao = B256::from(reader.word(32));
    let gas_limit = reader.word(32).to();
    let basefee = reader.word(32).to();
    let blob_gasprice = reader.word(32).to();
    let chain_id = reader.word(32).to();
    let block = BlockEnv {
        number,
        beneficiary,
        timestamp,
        gas_limit,
        basefee,
        difficulty: U256::ZERO,
        prevrandao: Some(prevrandao),
        blob_excess_gas_and_price: Some(BlobExcessGasAndPrice {
            excess_blob_gas: 0,
            blob_gasprice,
        }),
    };
    let accounts = (0..reader.count())
        .map(|_| {
            let address = reader.address();
            let balance = reader.word(32);
            let nonce = reader.word(32).to();
            let len = reader.count();
            let code = Bytecode::new_raw(Bytes::copy_from_slice(reader.bytes(len)));
            let info = AccountInfo::new(balance, nonce, code.hash_slow(), code);
            let storage = (0..reader.count())
                .map(|_| (reader.word(32), reader.word(32)))
                .collect();
            Account {
                address,
                info,
                storage,
            }
        })
        .collect();
    let tx_type = reader.word(1).to();
    let caller = reader.address();
    let creates = reader.word(1) == U256::from(1);
    let to = reader.address();
    let nonce = reader.word(32).to();
    let gas_limit = reader.word(8).to();
    let gas_price = reader.word(32).to();
    let priority_fee = reader.word(32).to();
    let max_fee_per_blob_gas = reader.word(32).to();
    let value = reader.word(32);
    let len = reader.count();
    let data = Bytes::copy_from_slice(reader.bytes(len));
    let access_list = AccessList(
        (0..reader.count())
            .map(|_| AccessListItem {
                address: reader.address(),
                storage_keys: (0..reader.count())
                    .map(|_| B256::from(reader.word(32)))
                    .collect(),
            })
            .collect(),
    );
    let blob_hashes = (0..reader.count())
        .map(|_| B256::from(reader.word(32)))
        .collect();
    assert_eq!(reader.position, reader.data.len());
    let tx = TxEnv {
        tx_type,
        caller,
        gas_limit,
        gas_price,
        kind: if creates {
            TxKind::Create
        } else {
            TxKind::Call(to)
        },
        value,
        data,
        nonce,
        chain_id: Some(chain_id),
        access_list,
        gas_priority_fee: (tx_type >= 2).then_some(priority_fee),
        blob_hashes,
        max_fee_per_blob_gas,
        ..Default::default()
    };
    Case {
        block,
        chain_id,
        accounts,
        tx,
    }
}

/// Decodes the case, builds its pre-state and applies the transaction if
/// `execute`; `None` stands for an invalid transaction.
fn run(data: &[u8], execute: bool) -> Option<Option<ExecutionResult>> {
    let case = decode(data);
    let mut db = CacheDB::new(EmptyDB::default());
    for account in case.accounts {
        db.insert_account_info(account.address, account.info);
        for (slot, value) in account.storage {
            db.insert_account_storage(account.address, slot, value)
                .unwrap();
        }
    }
    let mut evm = Context::mainnet()
        .with_db(db)
        .with_block(case.block)
        .modify_cfg_chained(|cfg| {
            cfg.spec = SpecId::CANCUN;
            cfg.chain_id = case.chain_id;
        })
        .build_mainnet();
    if !execute {
        black_box(&mut evm);
        return None;
    }
    Some(evm.transact(case.tx).ok().map(|outcome| outcome.result))
}

fn rlp_header(out: &mut Vec<u8>, len: usize, base: u8) {
    if len <= 55 {
        out.push(base + len as u8);
    } else {
        let bytes = len.to_be_bytes();
        let skip = bytes.iter().take_while(|byte| **byte == 0).count();
        out.push(base + 55 + (bytes.len() - skip) as u8);
        out.extend_from_slice(&bytes[skip..]);
    }
}

fn rlp_bytes(out: &mut Vec<u8>, bytes: &[u8]) {
    if !(bytes.len() == 1 && bytes[0] < 0x80) {
        rlp_header(out, bytes.len(), 0x80);
    }
    out.extend_from_slice(bytes);
}

/// keccak256(rlp([[address, [topics...], data], ...])), the receipt logs hash.
fn logs_hash(logs: &[Log]) -> B256 {
    let mut items = Vec::new();
    for log in logs {
        let mut topics = Vec::new();
        for topic in log.data.topics() {
            rlp_bytes(&mut topics, topic.as_slice());
        }
        let mut payload = Vec::new();
        rlp_bytes(&mut payload, log.address.as_slice());
        rlp_header(&mut payload, topics.len(), 0xc0);
        payload.extend(topics);
        rlp_bytes(&mut payload, &log.data.data);
        rlp_header(&mut items, payload.len(), 0xc0);
        items.extend(payload);
    }
    let mut out = Vec::new();
    rlp_header(&mut out, items.len(), 0xc0);
    out.extend(items);
    keccak256(out)
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().collect();
    let runs: u64 = args.get(1).map_or(Ok(0), |arg| arg.parse())?;
    let execute = args.get(2).map_or(Ok(1), |arg| arg.parse::<u64>())? != 0;
    let mut data = Vec::new();
    std::io::stdin().read_to_end(&mut data)?;
    // Every repeated application must use the gas the reported one does.
    let mut repeated_gas = None;
    for _ in 0..runs {
        if let Some(outcome) = run(&data, execute) {
            let gas = outcome.map(|result| result.gas_used());
            assert!(repeated_gas.is_none_or(|repeated| repeated == gas));
            repeated_gas = Some(gas);
        }
    }
    let Some(result) = run(&data, true).unwrap() else {
        assert!(repeated_gas.is_none_or(|repeated| repeated.is_none()));
        println!("{{\"invalid\":1}}");
        return Ok(());
    };
    assert!(repeated_gas.is_none_or(|repeated| repeated == Some(result.gas_used())));
    let status = match &result {
        ExecutionResult::Success { .. } => "success".to_string(),
        ExecutionResult::Revert { .. } => "revert".to_string(),
        ExecutionResult::Halt { reason, .. } => format!("halt {reason:?}"),
    };
    println!(
        "{{\"invalid\":0,\"status\":\"{status}\",\"gas_used\":{},\"logs_hash\":\"{:#x}\"}}",
        result.gas_used(),
        logs_hash(result.logs())
    );
    Ok(())
}
