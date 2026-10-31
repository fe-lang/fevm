//! Drives a real `fevm serve`; set `FEVM_BIN` to the fevm executable.

use fevm_client::{Address, Block, Config, Error, Invalid, Session, Status, Tx, U256};

const SENDER: u64 = 0x1000;

fn session() -> Session {
    let fevm = std::env::var("FEVM_BIN").expect("set FEVM_BIN to a built fevm executable");
    let mut session = Session::spawn(fevm).expect("fevm serve starts");
    session
        .set_block(&Block {
            coinbase: Address::from(0xc0),
            gas_limit: U256::from(30_000_000u64),
            chain_id: U256::from(1u64),
            ..Block::default()
        })
        .unwrap();
    session
        .set_balance(
            Address::from(SENDER),
            U256::from(1_000_000_000_000_000_000u128),
        )
        .unwrap();
    session
}

fn tx(to: Option<Address>, nonce: u64, data: &[u8]) -> Tx {
    Tx {
        sender: Address::from(SENDER),
        to,
        nonce: U256::from(nonce),
        gas_limit: 1_000_000,
        gas_price: U256::from(1u64),
        data: data.to_vec(),
        ..Tx::default()
    }
}

/// Initcode that deploys `runtime`: CODECOPY it to memory and RETURN it.
fn deployer(runtime: &[u8]) -> Vec<u8> {
    let len = u8::try_from(runtime.len()).unwrap();
    [
        &[0x60, len, 0x80, 0x60, 0x09, 0x5f, 0x39, 0x5f, 0xf3],
        runtime,
    ]
    .concat()
}

/// Increments slot 0 and returns the new count as a word.
const COUNTER: [u8; 15] = [
    0x5f, 0x54, 0x60, 0x01, 0x01, 0x80, 0x5f, 0x55, 0x5f, 0x52, 0x60, 0x20, 0x5f, 0xf3, 0x00,
];

fn word(value: u64) -> Vec<u8> {
    U256::from(value).0.to_vec()
}

#[test]
fn deploys_calls_and_simulates() {
    let mut session = session();
    let created = session.transact(&tx(None, 0, &deployer(&COUNTER))).unwrap();
    assert!(created.succeeded(), "{created:?}");
    let counter = created.created.expect("a created address");
    assert_eq!(session.account(counter).unwrap().code, COUNTER);

    let first = session.transact(&tx(Some(counter), 1, &[])).unwrap();
    assert_eq!(first.output, word(1));
    // A call returns what the transaction would but keeps nothing.
    let simulated = session.call(&tx(Some(counter), 2, &[])).unwrap();
    assert_eq!(simulated.output, word(2));
    assert_eq!(
        session.storage(counter, U256::default()).unwrap(),
        U256::from(1u64)
    );
    assert_eq!(
        session.account(Address::from(SENDER)).unwrap().nonce,
        U256::from(2u64)
    );
    let second = session.transact(&tx(Some(counter), 2, &[])).unwrap();
    assert_eq!(second.output, word(2));
    assert_eq!(second.gas_used, simulated.gas_used);
}

#[test]
fn snapshots_restore_the_world() {
    let mut session = session();
    let target = Address::from(0xbb);
    session.set_code(target, &COUNTER).unwrap();
    let before = session.snapshot().unwrap();
    session.transact(&tx(Some(target), 0, &[])).unwrap();
    let after = session.snapshot().unwrap();
    session.transact(&tx(Some(target), 1, &[])).unwrap();
    assert_eq!(
        session.storage(target, U256::default()).unwrap(),
        U256::from(2u64)
    );

    session.revert(after).unwrap();
    assert_eq!(
        session.storage(target, U256::default()).unwrap(),
        U256::from(1u64)
    );
    session.revert(before).unwrap();
    assert_eq!(
        session.storage(target, U256::default()).unwrap(),
        U256::default()
    );
    assert_eq!(
        session.account(Address::from(SENDER)).unwrap().nonce,
        U256::default()
    );
    // Reverting to `before` discarded `after`, but `before` stays.
    assert!(matches!(session.revert(after), Err(Error::NoSnapshot)));
    session.revert(before).unwrap();
}

#[test]
fn reports_logs_reverts_and_invalid_transactions() {
    let mut session = session();
    // MSTORE(0, 0xab); LOG2(31, 1, 7, 9); then REVERT(31, 1) when called with data.
    let code = [
        0x60, 0xab, 0x5f, 0x52, 0x60, 0x09, 0x60, 0x07, 0x60, 0x01, 0x60, 0x1f, 0xa2, 0x36, 0x60,
        0x13, 0x57, 0x00, 0x00, 0x5b, 0x60, 0x01, 0x60, 0x1f, 0xfd,
    ];
    let target = Address::from(0xbb);
    session.set_code(target, &code).unwrap();
    let logged = session.transact(&tx(Some(target), 0, &[])).unwrap();
    assert!(logged.succeeded(), "{logged:?}");
    assert_eq!(logged.logs.len(), 1);
    assert_eq!(logged.logs[0].address, target);
    assert_eq!(logged.logs[0].topics, [U256::from(7u64), U256::from(9u64)]);
    assert_eq!(logged.logs[0].data, [0xab]);

    let reverted = session.transact(&tx(Some(target), 1, &[1])).unwrap();
    assert_eq!(reverted.status, Status::Revert);
    assert_eq!(reverted.output, [0xab]);
    assert!(reverted.logs.is_empty());

    let replayed = session.transact(&tx(Some(target), 0, &[])).unwrap();
    assert_eq!(replayed.invalid, Some(Invalid::Nonce));
    session
        .configure(&Config {
            check_nonce: false,
            ..Config::osaka()
        })
        .unwrap();
    assert!(
        session
            .transact(&tx(Some(target), 0, &[]))
            .unwrap()
            .succeeded()
    );
}

#[test]
fn configure_raises_the_code_size_limit() {
    let mut session = session();
    // PUSH2 30,000; PUSH0; RETURN: deploys 30,000 zero bytes.
    let initcode = [0x61, 0x75, 0x30, 0x5f, 0xf3];
    let mut create = tx(None, 0, &initcode);
    create.gas_limit = 10_000_000;
    let limited = session.transact(&create).unwrap();
    assert_eq!(limited.status, Status::OutOfGas);
    assert_eq!(limited.created, None);

    session
        .configure(&Config {
            max_code_size: 1 << 20,
            ..Config::osaka()
        })
        .unwrap();
    create.nonce = U256::from(1u64);
    let raised = session.transact(&create).unwrap();
    assert!(raised.succeeded(), "{raised:?}");
    let code = session.account(raised.created.unwrap()).unwrap().code;
    assert_eq!(code.len(), 30_000);
}
