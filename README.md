# fevm

`fevm` is an EVM written in [Fe](https://github.com/argotorg/fe) and compiled
to native code by Fe's native backend (Sonatina and Cranelift). It implements
Osaka, the current mainnet fork, and Amsterdam, the next: every opcode and
precompile, and the state transition of one transaction, by the rules of the
fork a host selects. It passes all 14,640 runnable Osaka and 16,883 runnable
Amsterdam state tests of execution-spec-tests `tests@v21.0.2`. It also drives
Fe's native compiler, standard library and language development with a real
systems program.

## Layout

The repo is a Fe workspace:

- `ingots/evm`: the interpreter library and the `fevm` CLI
- `ingots/precompiles`: the precompiled contracts, which Amsterdam keeps
- `ingots/rlp`: RLP encoding and strict decoding
- `ingots/chain`: the chain layer, which will decode, validate and import
  blocks; empty so far
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

fevm needs Fe master `6ccb3ca8e`
([argotorg/fe#1992](https://github.com/argotorg/fe/pull/1992)) with its pinned
Sonatina and Rust 1.99.0.
[`native/toolchain.json`](native/toolchain.json) records the revisions and lock
hash, and bootstrap builds that compiler. Native hosts are x86_64 Linux and
AArch64 macOS.

```sh
python3 native/bootstrap.py --out native/out/toolchain --toolchain 1.99.0
native/out/toolchain/bin/fe build . --backend native --ingot fevm -O 2 --out-dir out
```

## CLI

`fevm [--fork osaka|amsterdam] <hex-bytecode> [hex-calldata]` runs the code
once in an empty world with default call and block values, by the rules of
the fork it names (Osaka without `--fork`). It prints the returned bytes, or
the top of the stack as a 32-byte word, or `empty`. On failure it prints the
status name (`revert` with the revert data) and exits with the status code.

```sh
./out/fevm 0x600260030100        # PUSH1 2; PUSH1 3; ADD; STOP
0x0000000000000000000000000000000000000000000000000000000000000005
./out/fevm 0x602a5f5260205ff3    # RETURN 32 bytes
./out/fevm 0x5f3500 0x1234       # CALLDATALOAD
./out/fevm 0x01                  # stack_underflow, exit 10
./out/fevm --fork amsterdam 0x600160026003e88e50   # EXCHANGE, then POP: 1
```

`fevm serve` keeps one world and answers binary requests on stdin: settings,
block values, account and storage writes and reads, transactions that commit
or only simulate, snapshots and reverts. It is how programs not written in Fe
use fevm; [`native/client`](native/client/README.md) has a Rust client and
the protocol.

## Library

### Transactions

An `Evm` holds a world across transactions, with the allocations they
reuse (frame memory, stacks and child frames, the journal and a transaction's
tables):

```fe
var evm = Evm::new(world, Config::osaka())
let receipt = evm.transact(request, block, mut tracer)
let balance = evm.world().balance(address)
```

`transact` runs one transaction and keeps its changes; `simulate` runs it the
same way and keeps none; `validate` only checks that it could be included.
Between transactions a host reads the world with `world()` and writes it with
`world_mut()`; `set_world` and `into_world` replace it and take it back.

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
- `Config` holds the host's settings, which `set_config` changes between
  transactions: the fork, the EIP-170 and EIP-3860 code
  size limits, EIP-7825's 2^24 gas cap, and the chain ID, nonce, base fee and
  EIP-3607 sender checks. `Config::osaka()` and `Config::amsterdam()` are
  mainnet's; Amsterdam raises the code size limits (EIP-7954), and from it
  the cap bounds a transaction's execution gas, the gas past it being state
  gas (EIP-8037). A test harness may raise the limits or skip the checks; a
  transaction priced below the base fee then pays its own price and no
  priority fee.
- `tracer` watches the transaction run (below); `()` traces nothing.

An invalid transaction changes nothing and returns a receipt whose
`invalid` field names the reason. A valid one buys its gas, increments the
sender's nonce, warms the sender, recipient, coinbase, precompiles and access
list, applies its authorizations, runs the call or creation, charges at least
the EIP-7623 calldata floor, refunds unused gas and the capped refund, pays the
priority fee, and deletes self-destructed new accounts and touched empty
accounts. The receipt has the status, gas used and refunded, the gas it adds
to the block's totals (from Amsterdam, execution gas before refunds and state
gas apart), the created contract's address, the output and the logs. A host failure (allocation,
balance overflow) undoes the transaction and reports that status.

### Blocks

A `Block` runs a block's transactions on an `Evm`'s world, which it holds
from `begin` to `finish`:

```fe
var block = Block::begin(evm, env, parent_hash, parent_beacon_block_root)
let receipt = block.transact(request, mut tracer)
let (evm, finished) = block.finish(withdrawals)
```

`begin` records the parent hash for BLOCKHASH and makes the system calls
that store the parent beacon block root (EIP-4788) and the parent hash
(EIP-2935), except for the genesis block, which has no parent. `transact`
runs a transaction if the block has the gas and blob gas left for it
(`Config` has the fork's blob limit), and its receipt has the cumulative gas
used; `simulate` tries one without counting it. `finish`
credits the withdrawals (EIP-4895), collects the block's requests (EIP-7685):
the deposits its transactions logged (EIP-6110) and those the withdrawal and
consolidation request contracts return to their system calls (EIP-7002,
EIP-7251; from Amsterdam the builder request contracts too, EIP-8282). It
returns the `Evm`, and a `BlockOutput` with what the header commits to apart
from its Merkle roots: gas used (from Amsterdam the larger of execution and
state gas, EIP-7778), blob gas used, the logs bloom, the requests with their
hash, and from Amsterdam the block's access list (EIP-7928) with its hash. A
block whose request contract is missing or fails, whose deposit contract
logged a malformed deposit, or whose access list is too large for its gas
limit gives a `BlockError` instead.

The access list is built as the block runs. A read is noted where its gas has
been paid, the point at which an account or slot is warmed, and stays through
reverts. Changes are not tracked as they are written: when a transaction
ends, the journal's surviving entries name what it changed with the values it
began with, so a write that restored a value counts as a read. Outside a
block, and in a simulation, nothing is recorded.

fevm does not check a header against its parent, decode transactions or
compute Merkle roots; a host that validates blocks compares the output with
the header, and rejects a block with an invalid transaction. An invalid
block's changes are not undone: a host that may need the world before it
keeps a `try_clone` of it.

### Forks

The fork is a type. `Rules` gives a fork's rules as constants, each defined
once from the fork it begins in, so a fork is one line:

```fe
pub trait Rules {
    const FORK: Fork
    // EIP-7843: SLOTNUM pushes the slot number.
    const SLOTNUM: bool = Self::FORK.since(Fork::Amsterdam)
    // EIP-2929 and EIP-8038: the first access of an account in a transaction.
    const COLD_ACCOUNT_ACCESS: u64 = if Self::FORK.since(Fork::Amsterdam) { 3000 } else { 2600 }
    // ...
}

pub struct Amsterdam {}
impl Rules for Amsterdam { const FORK: Fork = Fork::Amsterdam }
```

`Evm`'s `transact`, `simulate` and `validate`, and `Vm::run`, match `Config.fork` once and
run code generic over its `Rules` type, as they are over the tracer. Each fork
compiles to its own interpreter, with its rules folded into its code: Osaka's
dispatch table sends SLOTNUM and DUPN to the invalid opcode path, and its code
has no state gas in it. A host may switch forks between transactions; the
world and the `Evm`'s allocations are the same for every fork.

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
[state-test runner](native/conformance/README.md) is separate; the 25 state
tests of each fork it does not count have malformed signatures, which fevm,
given a recovered sender, never sees. [Benchmarks](native/bench/README.md) time the
evm-benchmarks state tests against revm and evmone.

## License

fevm is licensed under the [Apache License, Version 2.0](LICENSE).
