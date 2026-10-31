# fevm

`fevm` is an EVM written in [Fe](https://github.com/argotorg/fe) and compiled
to native code by Fe's native backend (Sonatina and Cranelift). It implements
Osaka, the current mainnet fork: every Osaka opcode and precompile, and the
state transition of one transaction. It passes all 14,693 runnable Osaka state
tests of execution-spec-tests `tests@v21.0.1`. It also drives Fe's native
compiler, standard library and language development with a real systems
program.

## Layout

The repo is a Fe workspace:

- `ingots/evm`: the interpreter library and the `fevm` CLI
- `ingots/precompiles`: the Osaka precompiled contracts
- `native/conformance`: the Ethereum state-test runner and its driver
- `native/differential`: frame and state comparisons against revm
- `native/bench`: state-test benchmarks against revm and evmone
- `native/soak`, `native/fixtures`, `native/arith`: resident-memory,
  allocation-failure and compiler arithmetic checks
- `native/accept.py`, `native/bootstrap.py`: the acceptance suite and the
  pinned compiler build

The interpreter depends on [swisstable](https://github.com/fe-lang/swisstable)
for growable hash tables and [keccak](https://github.com/fe-lang/keccak) for
Keccak-256; `ingots/evm/fe.toml` pins both to Git revisions.

## Building

fevm needs Fe [argotorg/fe#1895](https://github.com/argotorg/fe/pull/1895)
(`5e882e0a2`, on master `e572b31ac`) with its pinned Sonatina and Rust 1.99.0.
[`native/toolchain.json`](native/toolchain.json) records the revisions and lock
hash, and bootstrap builds that compiler. Native hosts are x86_64 Linux and
AArch64 macOS.

```sh
python3 native/bootstrap.py --out native/out/toolchain --toolchain 1.99.0
native/out/toolchain/bin/fe build . --backend native --ingot fevm -O 2 --out-dir out
```

## CLI

`fevm <hex-bytecode> [hex-calldata]` runs the code once in an empty world with
default call and block values. It prints the returned bytes, or the top of the
stack as a 32-byte word, or `empty`. On failure it prints the status name
(`revert` with the revert data) and exits with the status code.

```sh
./out/fevm 0x600260030100        # PUSH1 2; PUSH1 3; ADD; STOP
0x0000000000000000000000000000000000000000000000000000000000000005
./out/fevm 0x602a5f5260205ff3    # RETURN 32 bytes
./out/fevm 0x5f3500 0x1234       # CALLDATALOAD
./out/fevm 0x01                  # stack_underflow, exit 10
```

## Library

### Transactions

`transact(world, request, block, config, buffers)` runs one transaction and
returns `Applied { state, receipt }`.

- `WorldState` holds accounts, code, storage and block hashes. Set up accounts
  with `set_balance`, `set_nonce`, `set_code` and `storage_store`, and block
  hashes with `set_block_hash`. `try_clone` copies the world, so a host can
  keep a snapshot and return to it.
- A `TxRequest` holds a `TxEnv` (envelope kind, signed chain ID, recovered
  sender, recipient or creation flag, nonce, gas limit, fee fields, value) with
  owned calldata or initcode, access-list entries, blob hashes and EIP-7702
  authorizations. fevm takes the recovered sender; decoding and checking
  signed envelopes belongs to the host.
- `BlockEnv` holds the block's values and the chain ID.
- `Config` holds the host's settings. `Config::osaka()` is mainnet's rules: the
  EIP-170 and EIP-3860 code size limits, EIP-7825's 2^24 gas cap, and the
  chain ID, nonce, base fee and EIP-3607 sender checks. A test harness may
  raise the limits or skip the checks; a transaction priced below the base fee
  then pays its own price and no priority fee.
- `FrameBuffers` is a pool of frame memory, stacks and child frames that
  repeated transactions reuse.

An invalid transaction returns the untouched state and a receipt whose
`invalid` field names the reason. A valid one buys its gas, increments the
sender's nonce, warms the sender, recipient, coinbase, precompiles and access
list, applies its authorizations, runs the call or creation, charges at least
the EIP-7623 calldata floor, refunds unused gas and the capped refund, pays the
priority fee, and deletes self-destructed new accounts and touched empty
accounts. The receipt has the status, gas used and refunded, the created
contract's address, the output and the logs. A host failure (allocation,
balance overflow) returns the pre-state with that status.

### Statuses

`ingots/evm/src/status.fe` defines every status with its name
(`write_status_name`, `write_invalid_name`):

| code | name | kind |
|---|---|---|
| 0 | `success` | EVM outcome |
| 19 | `revert` | EVM outcome |
| 10, 11 | `stack_underflow`, `stack_overflow` | exceptional halt |
| 15, 16, 17, 18 | `out_of_gas`, `invalid_jump`, `invalid_opcode`, `return_data_oob` | exceptional halt |
| 23, 24, 25 | `static_write`, `code_prefix`, `precompile_failure` | exceptional halt |
| 27 | `address_collision` | exceptional halt (creation transactions) |
| 21, 26 | `host_allocation`, `balance_overflow` | host failure |

Exceptional halts consume all of a frame's gas. Host failures abort the whole
execution; EVM code never sees them. Validity codes (`VALID` and
`INVALID_*`, such as `nonce`, `intrinsic_gas`, `chain_id`) are in the same
file.

### Frames

`execute` and `execute_vm` run one frame's code against a `Transaction`, the
journaled view of a `WorldState` during a transaction. `Transaction`
checkpoints nest: a child commit stays reversible by its parent, and every
frame runs under its own. `finish(commit, gas_spent)` returns the state, logs,
capped refund and net gas used. CALL and CREATE children run on an explicit
frame stack, so the 1,024-frame depth limit does not depend on the native
stack.

Every owner, from results and logs to the world, frees its memory when it goes
out of scope or is overwritten. Allocation failure is a host failure, distinct
from an EVM halt.

## Testing

```sh
python3 native/accept.py --build native/out/toolchain/build.json \
  --out native/out/acceptance --check-only
python3 native/conformance/run.py --fe native/out/toolchain/bin/fe \
  --fixtures <execution-spec-tests>/fixtures/state_tests --out native/out/conformance
```

Acceptance runs seven stages: the workspace tests at O0, O1 and O2, CLI and
allocation-failure checks, the Osaka frame and state comparisons against revm,
and the arithmetic matrix ([native/README.md](native/README.md)). The
[state-test runner](native/conformance/README.md) is separate; the 23 Osaka
state tests it does not count have malformed signatures, which fevm, given a
recovered sender, never sees. [Benchmarks](native/bench/README.md) time the
evm-benchmarks state tests against revm and evmone.
