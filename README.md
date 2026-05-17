# fevm

`fevm` is a native Fe implementation of the EVM. The project is intended to drive Fe native compilation, standard library, and language development with a real systems program.

The executable accepts one hex bytecode argument, interprets a bounded EVM subset, and writes the final top-of-stack as a 32-byte hex word.

```sh
cargo run -p fe --features cranelift -- build --backend native --out-dir /Users/sean/code/fevm/out /Users/sean/code/fevm
/Users/sean/code/fevm/out/fevm 0x600260030100
```

Sample output:

```text
0x0000000000000000000000000000000000000000000000000000000000000005
```

Implemented opcode slice:

- `STOP`
- `PUSH0`, `PUSH1` through `PUSH32`
- `POP`, `DUP1` through `DUP16`, `SWAP1` through `SWAP16`
- `ADD`, `MUL`, `SUB`, `DIV`, `SDIV`, `MOD`, `SMOD`, `ADDMOD`, `MULMOD`, `EXP`
- `SIGNEXTEND`, `LT`, `GT`, `SLT`, `SGT`, `EQ`, `ISZERO`
- `AND`, `OR`, `XOR`, `NOT`, `BYTE`, `SHL`, `SHR`, `SAR`
- `CODESIZE`, `CODECOPY`
- `MLOAD`, `MSTORE`, `MSTORE8`, `MSIZE`, `MCOPY`
- validated `JUMP`, `JUMPI`, `PC`, `JUMPDEST`
- `INVALID` as an explicit execution fault

Recognized TODO opcodes:

- `SHA3`
- environment and block context opcodes: `ADDRESS` through `BLOBBASEFEE`
- transient storage: `TLOAD`, `TSTORE`
- logs: `LOG0` through `LOG4`
- create/call/return opcodes: `CREATE`, `CALL`, `CALLCODE`, `RETURN`, `DELEGATECALL`, `CREATE2`, `STATICCALL`, `REVERT`, `SELFDESTRUCT`

Undefined byte values still fail as unsupported opcodes.

Smoke samples:

```sh
/Users/sean/code/fevm/out/fevm 0x600260030100   # PUSH1 2; PUSH1 3; ADD; STOP
/Users/sean/code/fevm/out/fevm 0x600260030200   # PUSH1 2; PUSH1 3; MUL; STOP
/Users/sean/code/fevm/out/fevm 0x5f1560021b00   # PUSH0; ISZERO; PUSH1 2; SHL; STOP
/Users/sean/code/fevm/out/fevm 0x602a5f525f5100 # MSTORE then MLOAD
/Users/sean/code/fevm/out/fevm 0x6003565b600700 # JUMP to JUMPDEST; PUSH1 7; STOP
/Users/sean/code/fevm/out/fevm 0x30             # TODO ADDRESS
/Users/sean/code/fevm/out/fevm 0x0c             # unsupported undefined opcode
```

Near-term expansion:

- Return/revert data and executable-state reporting.
- Optional calldata CLI input so `CALLDATALOAD`, `CALLDATASIZE`, and `CALLDATACOPY` can be implemented without a fake execution environment.
- Keccak support for `SHA3` in native Fe.
- Environment fixtures for context, block, call, log, and storage opcodes.
- A test corpus that compares selected programs against a reference EVM.
