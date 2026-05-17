# fevm

`fevm` is a native Fe implementation of the EVM. The project is intended to drive Fe native compilation, standard library, and language development with a real systems program.

The initial executable accepts one hex bytecode argument, interprets a small stack/arithmetic subset, and writes the final top-of-stack as a 32-byte hex word.

```sh
cargo run -p fe --features cranelift -- build --backend native --out-dir /Users/sean/code/fevm/out /Users/sean/code/fevm
/Users/sean/code/fevm/out/fevm 0x600260030100
```

Sample output:

```text
0x0000000000000000000000000000000000000000000000000000000000000005
```

Current opcode slice:

- `STOP`
- `PUSH0`, `PUSH1` through `PUSH32`
- `POP`, `DUP1` through `DUP16`, `SWAP1` through `SWAP16`
- `ADD`, `MUL`, `SUB`, `DIV`, `MOD`
- `LT`, `GT`, `EQ`, `ISZERO`
- `AND`, `OR`, `XOR`, `NOT`
- `SHL`, `SHR`

Smoke samples:

```sh
/Users/sean/code/fevm/out/fevm 0x600260030100   # PUSH1 2; PUSH1 3; ADD; STOP
/Users/sean/code/fevm/out/fevm 0x600260030200   # PUSH1 2; PUSH1 3; MUL; STOP
/Users/sean/code/fevm/out/fevm 0x5f1560021b00   # PUSH0; ISZERO; PUSH1 2; SHL; STOP
/Users/sean/code/fevm/out/fevm 0x56             # unsupported JUMP
```

Near-term expansion:

- Program counter and jumpdest validation for `JUMP`/`JUMPI`.
- Linear memory and `MLOAD`/`MSTORE`/`MSTORE8`.
- Return/revert data and executable-state reporting.
- A test corpus that compares selected programs against a reference EVM.
