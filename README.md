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
- `native/client`: a Rust client for `fevm serve`, the session mode
- `native/conformance`: the Ethereum state-test driver
- `native/differential`: frame and state comparisons against revm
- `native/bench`: state-test benchmarks against revm and evmone
- `native/soak`, `native/fixtures`, `native/arith`: resident-memory,
  allocation-failure and compiler arithmetic checks
- `native/tools`: the acceptance suite, the state-test and benchmark runners and
  fevm's other checks written in Fe
- `native/bootstrap.py`: the pinned compiler build

The interpreter depends on [swisstable](https://github.com/fe-lang/swisstable)
for growable hash tables and [keccak](https://github.com/fe-lang/keccak) for
Keccak-256; `ingots/evm/fe.toml` pins both to Git revisions.

## Building

fevm needs Fe master `4608e5fdf`
([argotorg/fe#1977](https://github.com/argotorg/fe/pull/1977)) with its pinned
Sonatina and Rust 1.99.0.
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

`fevm serve` keeps one world and answers binary requests on stdin: settings,
block values, account and storage writes and reads, transactions that commit
or only simulate, snapshots and reverts. It is how programs not written in Fe
use fevm; [`native/client`](native/client/README.md) has a Rust client and
the protocol.

## Library

### Transactions

`transact(mut world, request, block, config, mut buffers, mut tracer)` runs
one transaction on `world` and returns its `Receipt`. `simulate` takes the same
arguments and returns the same receipt, but leaves `world` as it was.

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
- `Buffers` holds allocations that repeated transactions reuse: frame memory,
  stacks and child frames, and the journal.
- `tracer` watches the transaction run (below); `()` traces nothing.

An invalid transaction leaves the world untouched, and its receipt's
`invalid` field names the reason. A valid one buys its gas, increments the
sender's nonce, warms the sender, recipient, coinbase, precompiles and access
list, applies its authorizations, runs the call or creation, charges at least
the EIP-7623 calldata floor, refunds unused gas and the capped refund, pays the
priority fee, and deletes self-destructed new accounts and touched empty
accounts. The receipt has the status, gas used and refunded, the created
contract's address, the output and the logs. A host failure (allocation,
balance overflow) leaves the pre-state, with that status.

### Tracing

A tracer is any type that implements `Tracer`, whose hooks do nothing by
default:

```fe
pub trait Tracer {
    fn step(mut self, _ step: Step) {}
    fn enter(mut self, _ call: CallStart, input: MemSpan) {}
    fn leave(mut self, _ call: CallEnd, output: MemSpan) {}
}
```

`step` runs before every opcode with its pc, the gas, stack depth and memory
size, and the call depth. `enter` runs when a call or creation enters its frame
(opcode, caller, target, value, gas, input) and `leave` when it leaves (status,
gas left, output), the transaction's own message included. `transact` is
generic over the tracer, so `()` compiles to the same code as an interpreter
without hooks. `Trace` is a tracer that records the steps, the calls or both;
`fevm serve` uses it.

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

`execute` and `execute_vm` run one frame's code in a `Transaction`, which
holds a transaction's own state: its logs, refund, checkpoint depth and
endpoints. The world and buffers it works on are lent as effects, so code that
runs a frame provides them:

```fe
var tx = Transaction::new(sender, destination, coinbase, config: Config::osaka())
with (mut world, mut buffers) {
    let result = execute(program, calldata, call, block, mut tx)
    tx.finish(commit: result.status == OK, gas_spent)
}
```

Every write to the world passes the journal in the buffers, so `Transaction`
checkpoints nest: a child commit stays reversible by its parent, and every
frame runs under its own. `finish(commit, gas_spent)` undoes the transaction
unless `commit`, and returns its logs, capped refund and net gas used. CALL and CREATE children run on an explicit
frame stack, so the 1,024-frame depth limit does not depend on the native
stack.

Every owner, from results and logs to the world, frees its memory when it goes
out of scope or is overwritten. Allocation failure is a host failure, distinct
from an EVM halt.

## Testing

```sh
native/out/toolchain/bin/fe build . --ingot fevm_tools --backend native -O 2 \
  --emit executable --out-dir native/out/tools
native/out/tools/fevm_tools accept --build native/out/toolchain/build.json \
  --out native/out/acceptance --check-only
native/out/tools/fevm_tools conformance --fe native/out/toolchain/bin/fe \
  --fixtures <execution-spec-tests>/fixtures/state_tests --out native/out/conformance
```

Acceptance runs nine stages: the workspace tests at O0, O1 and O2, CLI and
allocation-failure checks, the Osaka frame and state comparisons against revm,
a build of `fevm_tools`, the session client's tests and the arithmetic matrix
([native/README.md](native/README.md)). The
[state-test runner](native/conformance/README.md) is separate; the 23 Osaka
state tests it does not count have malformed signatures, which fevm, given a
recovered sender, never sees. [Benchmarks](native/bench/README.md) time the
evm-benchmarks state tests against revm and evmone.
