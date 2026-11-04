# fevm session mode

`fevm serve` keeps one world in one process and answers requests on stdin,
one response each on stdout, until stdin ends. `fevm-client` is a Rust client
for it, with no dependencies:

```rust
use fevm_client::{Address, Block, Session, Tx, U256};

let mut session = Session::spawn("out/fevm")?;
session.set_block(&Block { gas_limit: U256::from(30_000_000u64), ..Block::default() })?;
session.set_balance(Address::from(0x1000), U256::from(10u128.pow(18)))?;
let receipt = session.transact(&Tx {
    sender: Address::from(0x1000),
    to: None,
    gas_limit: 1_000_000,
    data: initcode,
    ..Tx::default()
})?;
let contract = receipt.created.expect("deployed");
```

`transact` keeps a transaction's changes and `call` keeps none, as eth_call
does. `snapshot` copies the world and `revert` returns to a copy.
`configure` sets the code size limits, the gas cap and the checks a test may
skip (chain ID, nonce, base fee, EIP-3607). Receipts carry the status,
validity, gas used and refunded, created address, output and logs, and the
step and call traces that `set_tracing` asks for.

`fevm_tools client` builds fevm and runs the client's tests against it;
acceptance runs it as the `session` stage.

## Protocol

Every request and response is a frame: a big-endian u32 length, then that many
bytes. A request starts with its command byte; a response starts with its
status byte.

Fields are big endian. `word` is 32 bytes, `address` 20, `u64` 8, `count` 4,
`flag` and `byte` 1, and `bytes` a count followed by that many bytes.

| status | meaning |
|---|---|
| 0 | done; the response's fields follow |
| 1 | fevm could not allocate memory; nothing changed |
| 2 | malformed request or unknown command; nothing changed |
| 3 | no such snapshot |

| command | request fields | response fields |
|---|---|---|
| 1 configure | max_code_size u64, max_initcode_size u64, tx_gas_limit_cap u64, checks byte (bit 0 chain ID, 1 nonce, 2 base fee, 3 EIP-3607) | |
| 2 set block | coinbase address, number word, timestamp word, prevrandao word, gas_limit word, base_fee word, blob_base_fee word, chain_id word | |
| 3 set balance | address, value word | |
| 4 set nonce | address, value word | |
| 5 set code | address, code bytes | |
| 6 set storage | address, slot word, value word | |
| 7 set block hash | number word, hash word | |
| 8 account | address | exists flag, balance word, nonce word, code_hash word, code bytes |
| 9 storage | address, slot word | value word |
| 10 transact | flags byte (bit 0 commit, 1 trace calls, 2 trace steps), transaction | receipt |
| 11 snapshot | | id count |
| 12 revert | id count | |

A transaction is: kind byte (0 legacy, 1 access list, 2 fee market, 3 blob,
4 set code), signed chain ID flag and word, sender address, creates flag, to
address, nonce word, gas_limit u64, gas_price word (the EIP-1559 maximum fee),
max_priority_fee_per_gas word, max_fee_per_blob_gas word, value word, data
bytes; then a count of access-list entries, each an address and a count of
slot words; a count of blob-hash words; and a count of authorizations, each
chain_id word, address, nonce word, y_parity word, r word and s word. The
sender is recovered; fevm does not check signatures.

A receipt is: invalid byte (0 for a valid transaction, else the validity
code), status byte, gas_used u64, gas_refunded u64, created flag and address,
output bytes, and a count of logs, each an address, a topic-count byte, the
topic words and data bytes. Then the trace: a complete flag; a count of
steps, each pc as a count, op byte, call depth u16, gas u64, stack length u16
and memory size u64; and a count of call events, each an enter flag, kind
byte (the opcode, entering), depth u16, from address, to address, value word,
gas u64 (given entering, left leaving), status byte (leaving), the number of
steps before it as a count, and data bytes (input entering, output leaving).
Untraced receipts have empty lists. Codes and names are in
[`ingots/evm/src/status.fe`](../../ingots/evm/src/status.fe).

Snapshot ids count up from zero. Reverting to snapshot `n` restores the world
it copied and discards snapshots taken after it; `n` stays.
