# fevm

`fevm` is a native Fe implementation of the EVM. The project is intended to drive Fe native compilation, standard library, and language development with a real systems program.

The repo is a Fe workspace:

- `ingots/evm`: the interpreter library and CLI executable
- `ingots/precompiles`: the Cancun precompiled contracts
- `native/differential/driver`: a structured frame runner for the pinned Cancun corpus
- `native/differential/state_driver`: transaction/checkpoint sequences for the stateful corpus
- `native/conformance/driver`: runs one Ethereum state test transaction through `transact`
- `native/fixtures/journal`, `native/fixtures/accounts`, `native/fixtures/logs`, and `native/fixtures/calls`: allocation-failure fixtures run by the native harness

The interpreter depends on [swisstable](https://github.com/fe-lang/swisstable)
for fixed-capacity hash tables and [keccak](https://github.com/fe-lang/keccak)
for Keccak-256. `ingots/evm/fe.toml` pins both to immutable Git revisions; Fe
fetches them when resolving the workspace.

The executable accepts one hex bytecode argument and optional calldata, interprets a bounded EVM subset, and writes either returned bytes or the final top-of-stack as a 32-byte hex word.

```sh
python3 native/bootstrap.py --out native/out/toolchain --toolchain 1.99.0
native/out/toolchain/bin/fe build . --backend native --ingot fevm --out-dir out
./out/fevm 0x600260030100
```

The compiler target is upstream [Fe master](https://github.com/argotorg/fe/tree/fa06c6cd5ba19cbf15da718fad80b84d79a569b9)
at `fa06c6cd5ba19cbf15da718fad80b84d79a569b9`, pinned with its Sonatina revision,
Rust version and Cargo lock hash in [`native/toolchain.json`](native/toolchain.json).
Sources use MVS mutable value bindings and explicit unsafe boundaries. See
[native build instructions](native/README.md) for reproducible compiler builds and
the acceptance matrix. All seven native acceptance stages pass at O0/O1/O2 on
x86_64 Linux and AArch64 macOS ([evidence](native/reports/fe-master-20261024/README.md)).
Earlier
reports describe their historical compilers; the
[fork performance work](native/reports/mvs-next3-20261015/README.md) they measured
is now part of Fe master.

Sample output:

```text
0x0000000000000000000000000000000000000000000000000000000000000005
```

Library entry point:

```fe
let call = fevm::default_call_env()
let block = fevm::default_block_env()
var transaction = fevm::Transaction::new(
    world, sender: call.origin, destination: call.address, coinbase: block.coinbase,
)
let result = fevm::execute(program, calldata, call, block, mut transaction)
let commit = result.status == fevm::OK
let gas_spent = call.gas_limit - result.gas_remaining
let settled = transaction.finish(commit, gas_spent)
// Read settled.logs, then take the world for the next transaction.
let world = settled.state
```

Every owner, from results and logs to the world, frees its memory when it goes
out of scope or is overwritten; nothing is released by hand.

Complete Cancun transactions go through `fevm::transact(world, request, block)`.
A `TxRequest` holds a `TxEnv` (envelope kind, sender, recipient or creation flag,
nonce, gas limit and fee fields, value) together with owned calldata or initcode,
access-list entries and versioned blob hashes. Only blob transactions may carry
blob hashes. `transact` applies the
specification's includability checks; an invalid transaction returns the
untouched state and a receipt whose `invalid` field names the reason. A valid one
buys its gas, increments the sender nonce, warms the sender, recipient, coinbase,
precompiles and access list, and runs the call or creation. It then refunds unused
gas and the capped refund to the sender, pays the priority fee to the coinbase,
deletes self-destructed new accounts and touched accounts left empty, together
with their storage, and returns the receipt's status, gas used, output and logs.
Host failures (allocation), including during fee payment, return the pre-state
with that status.
The [Ethereum state-test runner](native/conformance/README.md) drives `transact`.

The reusable API exposes `Program`, `InputData`, `CallEnv`, `BlockEnv`, `WorldState`, `Transaction`, `Checkpoint`, `TransactionResult`, `LogBuffer`, `LogEntry`, and `ExecutionResult`. Code, calldata and output use owned growable buffers. Construct code with `Program::copy_from(source, len)`, move an `InputData` into `Program::new(input)`, or use `parse_hex_program`. Code remains immutable with its precomputed instruction-boundary jumpdest map. Truncated PUSH immediates are zero-padded while CODESIZE and CODECOPY retain the original code length. There is no fixed 4 KiB code/calldata cap; allocation failure is an operational error.

`execute`, `execute_vm` and `Vm::run` borrow their code and calldata, so a caller
can reuse them or pass temporaries. `InputData::copy_from(source, offset, len)`
copies a byte-source range, `InputData::copy_bytes(span)` copies a memory span, and
`InputData::new(bytes, status)` takes a `core::MemBuffer`. Inputs expose `len()`,
`byte_at(index)` and `bytes()`. Failed inputs are rejected before opening a
transaction checkpoint. `vm::Vm` retains memory capacity across runs; each run
clears the logical extent and zeroes newly exposed bytes. `into_result()` consumes
the VM and transfers its output to the `ExecutionResult`.

A `Transaction` owns the world state while execution is active. Each `Vm::run`
opens a frame checkpoint: success commits it, while REVERT and every exceptional
or operational failure undo that frame's writes. Explicit nested checkpoints
support child commit and rollback; a committed child remains reversible by its
parent. Close checkpoints once in reverse order. Static mode is inherited.
Checkpoints are journal scopes only; they do not count toward EVM call depth.

`CALL`, `CALLCODE`, `DELEGATECALL` and `STATICCALL` run child frames on an
explicit frame stack rather than native recursion, so the 1,024-frame depth limit
does not depend on native stack size. Each child frame is allocated separately,
so frame storage grows with the actual call depth. Each child runs under its own
checkpoint. Every call touches its target, even without value; a failed call
undoes the touch.
Calls charge Cancun warm/cold access, value-transfer and new-account costs,
forward at most all but one 64th of the remaining gas plus the 2,300-gas stipend,
and fail without executing on insufficient balance or at the depth limit.
Children write their output prefix into the caller's memory and replace its
return data; RETURNDATASIZE and RETURNDATACOPY read that buffer. Host failures
and unimplemented features in a child abort the whole execution rather than being
reported to EVM code as a failed call.

`CREATE` and `CREATE2` charge initcode words (EIP-3860) and, for CREATE2, the
hashing words; derive the address from the sender's nonce or salt and initcode
hash; and run the initcode as a child frame under its own checkpoint. A target
with a nonce, code or storage collides (EIP-684/EIP-7610) and consumes the
forwarded gas. Successful initcode output is deposited as code after the
EIP-3541 prefix check, 200 gas per byte and the EIP-170 size limit; a failed
deposit is an exceptional halt. `SELFDESTRUCT` (EIP-6780) moves the balance to
its beneficiary and deletes the account only if this transaction created it.

All ten Cancun precompiles live in the separate `fevm_precompiles` workspace
ingot: ECRECOVER (secp256k1), SHA-256, RIPEMD-160, IDENTITY, MODEXP (EIP-198 with
EIP-2565 gas), BN254 ECADD/ECMUL/ECPAIRING (EIP-196/197 with EIP-1108 gas),
BLAKE2F (EIP-152) and KZG point evaluation (EIP-4844, BLS12-381 with the mainnet
trusted setup's `[τ]G2`). Each charges its gas before doing work; invalid input
or insufficient gas is an exceptional halt. MODEXP works on limb arrays sized for
each call's modulus, so any affordable modulus is evaluated; failing to allocate
them is a host error.

`finish(commit, gas_spent)` consumes the transaction and returns persistent state,
owned logs, capped `gas_refunded`, and net `gas_used`. Aborting first undoes all
writes and discards logs and refunds. Both paths discard transient storage, blob
hashes and the journal; every frame must already be closed. Move the public
`state` and `logs` fields out to keep them, for example the world for the next
transaction. Journal and log growth are fallible: allocation failure leaves the
operation unapplied, and rollback only pops the journal.

LOG0 through LOG4 copy frame memory and ordered topics into transaction-owned
storage. `transaction.logs()` and `receipt.logs` expose `entry(index)`, which
copies `LogEntry` header metadata: address, topics, topic count and `len()`.
Read payload bytes through `logs.byte_at(entry: index, index: byte)`, which
checks both indices against the current log buffer. Headers store no references.
Nested rollback truncates logs, including
logs from committed children. Static frames reject log emission. Add versioned
blob hashes with `add_blob_hash(hash)` before execution; this returns false on
allocation failure. BLOBHASH costs 3 gas and returns zero for any full-width
index outside that transaction's list. Blob hashes survive checkpoint rollback.

The transaction warms its sender, destination, coinbase, and Cancun precompiles
upfront. Add access-list entries with `access_list_account(address)` and
`access_list_slot(address, slot)` before opening any checkpoint or changing runtime
state. These calls return false on allocation failure. Runtime warming follows
checkpoint rollback; original storage values remain fixed for the transaction.
Account keys use their low 160 bits.

BALANCE, EXTCODESIZE, EXTCODECOPY, EXTCODEHASH, SLOAD and SSTORE use Cancun warm/cold pricing. SSTORE tracks original,
current and new values, enforces the 2,300-gas sentry, and updates signed refunds.
TLOAD/TSTORE cost 100 gas and do not use that sentry. `ExecutionResult.refund_delta`
is the successful frame's signed contribution; unsuccessful frames contribute
zero. Refunds never refill a frame's executable gas. At transaction completion,
positive refunds are capped to one fifth of the supplied pre-refund `gas_spent`.
The caller supplies the transaction's total gas spent; signed-envelope and
intrinsic-gas processing remain outside this frame API.

Initialize accounts before opening a transaction with `ensure_account(address)`,
`set_balance(address, value)`, `set_nonce(address, value)` and
`set_code(address, code)`. Code accepts the Keccak library's `ByteSource` trait
(including arrays, `core::MemBuffer` and `core::MemSpan`) and is copied into
world-owned storage; its caller retains ownership of the input. `set_code` returns
an operational status and preserves the account on allocation failure. Replacing
or clearing code compacts the arena; its capacity tracks the peak live code extent.
Code storage has no frame-input size limit.

`exists(address)` distinguishes an explicitly present empty account from absence.
Zero balance/nonce writes preserve an existing account and do not create an absent
one. Transaction undo restores prior existence as well as values. EXTCODEHASH
returns zero for absent accounts and EIP-161 empty accounts (zero balance, nonce
and code), and the empty Keccak digest for nonempty accounts without code.
EXTCODECOPY zero-fills beyond stored code and charges memory expansion, three gas
per copied word, and the shared warm/cold account access cost, including access
cost for an empty copy. Contract creation is the only code write during a
transaction; it is journaled and undone with its frame.
The [account-code checkpoint](native/reports/account-code.md) passes all seven
native acceptance stages at O0/O1/O2 on x86_64 Linux using local Fe `4c03313f1`.

The world and transaction caches are growable
[SwissTables](https://github.com/fe-lang/swisstable). Allocation failures are
explicit host resource errors, distinct from EVM halts.
The [state-gas checkpoint](native/reports/state-gas.md) passes full native
acceptance at O0/O1/O2 on x86_64 Linux. It builds on the separately recorded
[transaction journal](native/reports/transaction-journal.md).

SHA3 uses the separately tested [Fe Keccak library](https://github.com/fe-lang/keccak),
pinned to an immutable Git revision. It charges 30 gas plus six per input word
and memory expansion before allocating, and borrows the selected memory range.
Zero-length input ignores the offset. BLOCKHASH exposes only the previous
256 blocks, including when the host supplies entries outside that window.
The [Keccak integration checkpoint](native/reports/keccak-integration.md) passes
all seven native acceptance stages at O0/O1/O2 on x86_64 Linux.

Implemented opcode slice:

- `STOP`
- `SHA3` (Ethereum Keccak-256)
- `PUSH0`, `PUSH1` through `PUSH32`
- `POP`, `DUP1` through `DUP16`, `SWAP1` through `SWAP16`
- `ADD`, `MUL`, `SUB`, `DIV`, `SDIV`, `MOD`, `SMOD`, `ADDMOD`, `MULMOD`, `EXP`
- `SIGNEXTEND`, `LT`, `GT`, `SLT`, `SGT`, `EQ`, `ISZERO`
- `AND`, `OR`, `XOR`, `NOT`, `BYTE`, `SHL`, `SHR`, `SAR`
- `ADDRESS`, `ORIGIN`, `CALLER`, `CALLVALUE`, `CALLDATALOAD`, `CALLDATASIZE`, `CALLDATACOPY`
- `CODESIZE`, `CODECOPY`, `EXTCODESIZE`, `EXTCODECOPY`, `EXTCODEHASH`, `GASPRICE`, `RETURNDATASIZE`, `RETURNDATACOPY`
- `BALANCE`, `BLOCKHASH`, `COINBASE`, `TIMESTAMP`, `NUMBER`, `PREVRANDAO`, `GASLIMIT`, `CHAINID`, `SELFBALANCE`, `BASEFEE`, `BLOBBASEFEE`, `BLOBHASH`
- `MLOAD`, `MSTORE`, `MSTORE8`, `SLOAD`, `SSTORE`, `MSIZE`, `TLOAD`, `TSTORE`, `MCOPY`
- validated `JUMP`, `JUMPI`, `PC`, `GAS`, `JUMPDEST`
- `LOG0` through `LOG4`
- `CREATE`, `CALL`, `CALLCODE`, `DELEGATECALL`, `CREATE2`, `STATICCALL`, `SELFDESTRUCT`
- `RETURN`, `REVERT`
- `INVALID` as an explicit execution fault

`INVALID` (0xfe) and every undefined byte are exceptional halts that consume all
frame gas.

Smoke samples:

```sh
./out/fevm 0x600260030100   # PUSH1 2; PUSH1 3; ADD; STOP
./out/fevm 0x600260030200   # PUSH1 2; PUSH1 3; MUL; STOP
./out/fevm 0x5f1560021b00   # PUSH0; ISZERO; PUSH1 2; SHL; STOP
./out/fevm 0x602a5f525f5100 # MSTORE then MLOAD
./out/fevm 0x6003565b600700 # JUMP to JUMPDEST; PUSH1 7; STOP
./out/fevm 0x5f3500 0x1234  # CALLDATALOAD
./out/fevm 0x602a5f5260205ff3 # RETURN 32 bytes
./out/fevm 0x600160005560005400 # SSTORE then SLOAD
./out/fevm 0x0c             # undefined opcode: invalid
```

The [Cancun frame corpus](native/differential/README.md) compares selected frame
results against pinned revm. FeVM passes all 16,847 Cancun state tests of
execution-spec-tests v5.4.0
([report](native/reports/owned-memory-restack-20261024/README.md)).
Performance comparisons with other EVMs remain future work.

Native compiler arithmetic checks, performance measurements, and reproducible
build instructions are documented in [native/README.md](native/README.md).
