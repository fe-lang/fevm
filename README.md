# fevm

`fevm` is a native Fe implementation of the EVM. The project is intended to drive Fe native compilation, standard library, and language development with a real systems program.

The repo is a Fe workspace:

- `ingots/evm`: the interpreter library and CLI executable
- `native/differential/driver`: a structured frame runner for the pinned Cancun corpus
- `native/differential/state_driver`: transaction/checkpoint sequences for the stateful corpus
- `native/fixtures/journal`: an allocation-failure fixture run by the native harness

The interpreter depends on [swisstable](https://github.com/fe-lang/swisstable)
for fixed-capacity hash tables and [keccak](https://github.com/fe-lang/keccak)
for Keccak-256. `ingots/evm/fe.toml` pins both to immutable Git revisions; Fe
fetches them when resolving the workspace.

The executable accepts one hex bytecode argument and optional calldata, interprets a bounded EVM subset, and writes either returned bytes or the final top-of-stack as a 32-byte hex word.

```sh
python3 native/bootstrap.py --out native/out/toolchain \
  --toolchain 1.98.1
native/out/toolchain/bin/fe build . --backend native --ingot fevm --out-dir out
./out/fevm 0x600260030100
```

The compiler pin uses published Fe master and Sonatina revisions. See
[native build instructions](native/README.md) for prerequisites and reproducible
acceptance commands.

Sample output:

```text
0x0000000000000000000000000000000000000000000000000000000000000005
```

Library entry point:

```fe
let call = fevm::default_call_env()
let block = fevm::default_block_env()
let mut transaction = fevm::Transaction::new(
    world, sender: call.origin, destination: call.address, coinbase: block.coinbase,
)
let result = fevm::execute(program, calldata, call, block, mut transaction)
let commit = result.status == fevm::OK
let gas_spent = call.gas_limit - result.gas_remaining
// Consume the result after using it to release its owned output buffer.
result.release()
let settled = transaction.finish(commit, gas_spent)
let world = settled.state
```

The reusable API exposes `Program`, `InputData`, `CallEnv`, `BlockEnv`, `WorldState`, `Transaction`, `Checkpoint`, `TransactionResult`, and `ExecutionResult`. Results own their output and require explicit `release()`. `vm::Vm` can retain memory capacity across `run` calls; each run clears the logical extent and zeroes newly exposed bytes. Release the VM after its final run, or consume it with `into_result()` to transfer its output. Construct code with `Program::new(bytes, len, status)` or `parse_hex_program`; its immutable bytes share a precomputed instruction-boundary jumpdest map. Truncated PUSH immediates are zero-padded while CODESIZE and CODECOPY retain the original code length.

A `Transaction` owns the world state while execution is active. Each `Vm::run`
opens a frame checkpoint: success commits it, while REVERT and every exceptional
or operational failure undo that frame's writes. Explicit nested checkpoints
support child commit and rollback; a committed child remains reversible by its
parent. Close checkpoints once in reverse order. Static mode is inherited, and
opening a frame beyond depth 1,024 fails without closing its parent.

`finish(commit, gas_spent)` consumes the transaction and returns persistent state,
capped `gas_refunded`, and net `gas_used`. Aborting first undoes all writes and
returns no refund. Both paths discard transient storage and release the journal;
every frame must already be closed. Journal growth is fallible: allocation failure
leaves the write unapplied, and rollback uses existing storage.

The transaction warms its sender, destination, coinbase, and Cancun precompiles
upfront. Add access-list entries with `access_list_account(address)` and
`access_list_slot(address, slot)` before opening any checkpoint or changing runtime
state. These calls return false on host table exhaustion. Runtime warming follows
checkpoint rollback; original storage values remain fixed for the transaction.
Account keys use their low 160 bits.

BALANCE, SLOAD and SSTORE use Cancun warm/cold pricing. SSTORE tracks original,
current and new values, enforces the 2,300-gas sentry, and updates signed refunds.
TLOAD/TSTORE cost 100 gas and do not use that sentry. `ExecutionResult.refund_delta`
is the successful frame's signed contribution; unsuccessful frames contribute
zero. Refunds never refill a frame's executable gas. At transaction completion,
positive refunds are capped to one fifth of the supplied pre-refund `gas_spent`.
The caller supplies the transaction's total gas spent; signed-envelope and
intrinsic-gas processing remain outside this frame API.

The world and transaction caches currently use 256-entry tables. Exhaustion and
allocation failures are explicit host resource errors, distinct from EVM halts.
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
- `CODESIZE`, `CODECOPY`, `GASPRICE`, `RETURNDATASIZE`, `RETURNDATACOPY`
- `BALANCE`, `BLOCKHASH`, `COINBASE`, `TIMESTAMP`, `NUMBER`, `PREVRANDAO`, `GASLIMIT`, `CHAINID`, `SELFBALANCE`, `BASEFEE`, `BLOBBASEFEE`
- `MLOAD`, `MSTORE`, `MSTORE8`, `SLOAD`, `SSTORE`, `MSIZE`, `TLOAD`, `TSTORE`, `MCOPY`
- validated `JUMP`, `JUMPI`, `PC`, `GAS`, `JUMPDEST`
- `RETURN`, `REVERT`
- `INVALID` as an explicit execution fault

Recognized TODO opcodes:

- account and history opcodes: `EXTCODESIZE`, `EXTCODECOPY`, `EXTCODEHASH`, `BLOBHASH`
- logs: `LOG0` through `LOG4`
- create/call opcodes: `CREATE`, `CALL`, `CALLCODE`, `DELEGATECALL`, `CREATE2`, `STATICCALL`, `SELFDESTRUCT`

Undefined byte values still fail as unsupported opcodes.

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
./out/fevm 0x0c             # unsupported undefined opcode
```

Near-term expansion:

- Account code tables for external code opcodes.
- Direct runtime-code deployment before exact `CREATE`/`CREATE2` address derivation.
- Environment fixtures for logs, calls, and nested execution.
The [Cancun frame corpus](native/differential/README.md) compares selected frame
results against pinned revm. Full Cancun conformance and performance comparisons
remain future work.

Native compiler arithmetic checks, performance measurements, and reproducible
build instructions are documented in [native/README.md](native/README.md).
