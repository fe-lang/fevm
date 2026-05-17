# fevm

`fevm` is a native Fe implementation of the EVM. The project is intended to drive Fe native compilation, standard library, and language development with a real systems program.

The executable accepts one hex bytecode argument and optional calldata, interprets a bounded EVM subset, and writes either returned bytes or the final top-of-stack as a 32-byte hex word.

```sh
cargo run -p fe --features cranelift -- build --backend native --out-dir /Users/sean/code/fevm/out /Users/sean/code/fevm
/Users/sean/code/fevm/out/fevm 0x600260030100
```

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
)
```

The reusable API exposes `Program`, `ByteBuffer`, `CallEnv`, `BlockEnv`, and `ExecutionResult`. `main` is only a CLI wrapper around that API.

Implemented opcode slice:

- `STOP`
- `PUSH0`, `PUSH1` through `PUSH32`
- `POP`, `DUP1` through `DUP16`, `SWAP1` through `SWAP16`
- `ADD`, `MUL`, `SUB`, `DIV`, `SDIV`, `MOD`, `SMOD`, `ADDMOD`, `MULMOD`, `EXP`
- `SIGNEXTEND`, `LT`, `GT`, `SLT`, `SGT`, `EQ`, `ISZERO`
- `AND`, `OR`, `XOR`, `NOT`, `BYTE`, `SHL`, `SHR`, `SAR`
- `ADDRESS`, `ORIGIN`, `CALLER`, `CALLVALUE`, `CALLDATALOAD`, `CALLDATASIZE`, `CALLDATACOPY`
- `CODESIZE`, `CODECOPY`, `GASPRICE`, `RETURNDATASIZE`, `RETURNDATACOPY`
- `COINBASE`, `TIMESTAMP`, `NUMBER`, `PREVRANDAO`, `GASLIMIT`, `CHAINID`, `SELFBALANCE`, `BASEFEE`, `BLOBBASEFEE`
- `MLOAD`, `MSTORE`, `MSTORE8`, `MSIZE`, `MCOPY`
- validated `JUMP`, `JUMPI`, `PC`, `GAS`, `JUMPDEST`
- `RETURN`, `REVERT`
- `INVALID` as an explicit execution fault

Recognized TODO opcodes:

- `SHA3`
- account and history opcodes: `BALANCE`, `EXTCODESIZE`, `EXTCODECOPY`, `EXTCODEHASH`, `BLOCKHASH`, `BLOBHASH`
- transient storage: `TLOAD`, `TSTORE`
- logs: `LOG0` through `LOG4`
- create/call opcodes: `CREATE`, `CALL`, `CALLCODE`, `DELEGATECALL`, `CREATE2`, `STATICCALL`, `SELFDESTRUCT`

Undefined byte values still fail as unsupported opcodes.

Smoke samples:

```sh
/Users/sean/code/fevm/out/fevm 0x600260030100   # PUSH1 2; PUSH1 3; ADD; STOP
/Users/sean/code/fevm/out/fevm 0x600260030200   # PUSH1 2; PUSH1 3; MUL; STOP
/Users/sean/code/fevm/out/fevm 0x5f1560021b00   # PUSH0; ISZERO; PUSH1 2; SHL; STOP
/Users/sean/code/fevm/out/fevm 0x602a5f525f5100 # MSTORE then MLOAD
/Users/sean/code/fevm/out/fevm 0x6003565b600700 # JUMP to JUMPDEST; PUSH1 7; STOP
/Users/sean/code/fevm/out/fevm 0x5f3500 0x1234  # CALLDATALOAD
/Users/sean/code/fevm/out/fevm 0x602a5f5260205ff3 # RETURN 32 bytes
/Users/sean/code/fevm/out/fevm 0x31             # TODO BALANCE
/Users/sean/code/fevm/out/fevm 0x0c             # unsupported undefined opcode
```

Near-term expansion:

- Keccak support for `SHA3` in native Fe.
- In-memory account/storage tables for `BALANCE`, `SLOAD`, `SSTORE`, and external code opcodes.
- Direct runtime-code deployment before exact `CREATE`/`CREATE2` address derivation.
- Environment fixtures for logs, calls, and nested execution.
- A test corpus that compares selected programs against a reference EVM.
