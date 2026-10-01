# fevm

`fevm` is a native Fe implementation of the EVM. The project is intended to drive Fe native compilation, standard library, and language development with a real systems program.

The repo is a Fe workspace with three ingots:

- `ingots/evm`: the interpreter library and CLI executable
- `ingots/swisstable`: a generic fixed-capacity SwissTable-style hash table
- `native/differential/driver`: a structured frame runner for the pinned Cancun corpus

The executable accepts one hex bytecode argument and optional calldata, interprets a bounded EVM subset, and writes either returned bytes or the final top-of-stack as a 32-byte hex word.

```sh
python3 native/bootstrap.py --out native/out/toolchain \
  --toolchain 1.98.1 --fe-repository ../fe
native/out/toolchain/bin/fe build . --backend native --ingot fevm --out-dir out
./out/fevm 0x600260030100
```

The current compiler pin uses the local Fe branch
`integrate/fevm-development-20261001`; `../fe` must contain that branch's commit.
See [native build instructions](native/README.md) for the integrated PRs and
rebuilding from another checkout or a Git bundle.

Sample output:

```text
0x0000000000000000000000000000000000000000000000000000000000000005
```

Library entry point:

```fe
let result = fevm::execute(
    program,
    calldata,
    fevm::default_call_env(),
    fevm::default_block_env(),
    mut state,
)
// Consume the result after using it to release its owned output buffer.
result.release()
```

The reusable API exposes `Program`, `InputData`, `CallEnv`, `BlockEnv`, `WorldState`, and `ExecutionResult`. Results own their output and require explicit `release()`. `vm::Vm` can retain memory capacity across `run` calls; each run clears the logical extent and zeroes newly exposed bytes. Release the VM after its final run, or consume it with `into_result()` to transfer its output. Construct code with `Program::new(bytes, len, status)` or `parse_hex_program`; its immutable bytes share a precomputed instruction-boundary jumpdest map. Truncated PUSH immediates are zero-padded while CODESIZE and CODECOPY retain the original code length.

Implemented opcode slice:

- `STOP`
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

- `SHA3`
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

- Transaction context, journaled state rollback, and warm/cold storage gas/refunds.
- Keccak support for `SHA3` in native Fe.
- Account code tables for external code opcodes.
- Direct runtime-code deployment before exact `CREATE`/`CREATE2` address derivation.
- Environment fixtures for logs, calls, and nested execution.
The [Cancun frame corpus](native/differential/README.md) compares selected frame
results against pinned revm. Full Cancun conformance and performance comparisons
remain future work.

Native compiler arithmetic checks, performance measurements, and reproducible
build instructions are documented in [native/README.md](native/README.md).
