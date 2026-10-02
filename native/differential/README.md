# Cancun frame differential corpus

This runner compares FeVM's single-frame execution with `revm-interpreter`
**31.1.0** with a pinned [DUP/SWAP halt-classification correction](https://github.com/sbillig/revm/commit/d613ef5735b9beb17acd53a5a1802ebc2198a18d),
explicitly configured for **Cancun**. Cargo.lock pins the reference and its
dependencies. The corpus includes 1,729 frames: arithmetic batches, all PUSH
widths and truncation positions, jumps, stack limits, memory/copy boundaries,
remaining gas, and returned/reverted bytes. A looping program checks gas exhaustion.
Specification-derived anchors also check the reference independently.

Current checkpoint: **1,729 frames pass at O0/O1/O2 on x86_64 Linux**, including
96 memory and 31 gas cases. The three explicitly declared simultaneous-fault
reason differences per level match the agreed contract below. See the
[state-gas acceptance report](../reports/state-gas.md).

The historical [macOS and Linux checkpoints](../reports/cancun-frames.md) covered
1,602 frames at their explicitly recorded revisions with a separate compiler pin. The new compiler/corpus still needs a macOS run.
The pinned reference correction distinguishes DUP/SWAP underflow from genuine
overflow without changing successful instruction paths or gas charging.

## Running

Use the pinned native compiler and install the Rust version in
`native/toolchain.json` with rustup. Both frame and state runners select that
version explicitly; `--toolchain` selects another installed toolchain for a
diagnostic run. `native/accept.py` forwards its bootstrap record's Rust version
to both runners. Keep outputs outside temporary storage:

```sh
python3 native/differential/run.py --fe native/out/toolchain/bin/fe \
  --out native/out/cancun-frames
```

The default builds and runs O0/O1/O2. `--levels 0` selects a focused run. Each
output directory must be fresh. Both runners build the reference into
`<out>/reference-target` with an explicit Cargo `--target-dir`, overriding
`CARGO_TARGET_DIR` and `build.target-dir`. The result record includes
compiler/reference hashes, selected Rust toolchain, Rust/Cargo versions,
reference target directory, resolved reference package versions and Git sources, source hashes,
optimization levels and the first failure; generated
`cases.jsonl` retains every input and expected frame. Sources must remain unchanged
throughout a run. Compiler reports, IR, binaries and build logs are retained.

Run the harness regressions with
`python3 -m unittest discover -s native/differential -p 'test_*.py'`. They build
a small dependency-free Rust fixture using the pinned toolchain and retain
their temporary artifacts under `/tmp`.

The Fe driver now requires `<hex-bytecode> <hex-calldata> <u64-gas-limit>` and emits
one JSON object. This replaces the previous wire format:

```json
{"outcome":"success","reason":null,"gas_remaining":97,"stack":["0x0000000000000000000000000000000000000000000000000000000000000001"],"memory":"0x","output":"0x"}
```

Consensus outcomes are `success`, `revert`, and `exceptional`; remaining gas and
output must agree. Completed frames additionally compare the entire stack (bottom
to top) and word-rounded active memory. Exceptional frames consume all frame gas
and expose no output, stack or memory. Partial machine state after a fault depends
on engine fault ordering and is outside this comparison.

Reasons are retained separately in the reference record and each optimization
level's `frames.jsonl`. Only cases explicitly marked with simultaneous faults may
differ in reason, and both reasons must belong to that case's declared fault set.
The summary retains every such difference. Single-fault reasons, including the
independent DUP/SWAP anchors, remain checked. A bounds-plus-gas RETURNDATACOPY case
can therefore report bounds in revm and gas exhaustion in FeVM while agreeing on
the exceptional result and complete gas consumption.

Process errors, malformed JSON, unsupported instructions and host allocation
failures fail the harness. They are not normalized
into EVM halt codes.
Each FeVM frame runs in its own process; arithmetic operations are batched within
bounded EVM programs, preserving every arithmetic result on the stack.

## Scope and references

The expanded slice adds gas and active-memory accounting for implemented stateless
frame instructions. Each case supplies its gas limit; the usual budget is
1,000,000. Inputs remain bounded to 4,096 bytes by the parser. The stateless corpus excludes external state and nested calls. The additional
stateful corpus below covers implemented state access, refunds and checkpoint
rollback. Neither corpus establishes full Cancun conformance, CALL/CREATE
execution, resident allocation reclamation or performance.

The specification pin is
[`c335bc4e9e99f7b91024d9033bdc89ce54394848`](https://github.com/ethereum/execution-specs/tree/c335bc4e9e99f7b91024d9033bdc89ce54394848).
The arithmetic anchors follow
[Cancun arithmetic](https://github.com/ethereum/execution-specs/blob/c335bc4e9e99f7b91024d9033bdc89ce54394848/src/ethereum/forks/cancun/vm/instructions/arithmetic.py);
PUSH cases follow
[stack instructions](https://github.com/ethereum/execution-specs/blob/c335bc4e9e99f7b91024d9033bdc89ce54394848/src/ethereum/forks/cancun/vm/instructions/stack.py);
jump analysis follows
[valid jump destinations](https://github.com/ethereum/execution-specs/blob/c335bc4e9e99f7b91024d9033bdc89ce54394848/src/ethereum/forks/cancun/vm/runtime.py).
These are local, specification-derived cases, not the Ethereum execution-spec
test distribution. The reference crate was released from revm commit
[`0d424ba11fd59d2a2a13988d61381e5b5cfccd22`](https://github.com/bluealloy/revm/tree/0d424ba11fd59d2a2a13988d61381e5b5cfccd22).


## Stateful transaction sequences

```sh
python3 native/differential/state_run.py --fe native/out/toolchain/bin/fe \
  --out native/out/cancun-state
```

The stateful corpus has 349 deterministic cases. Its reference uses the pinned
revm Context and real Journal over InMemoryDB. Both engines run the same recursive
sequence of frames and explicit checkpoint scopes. Snapshots after each frame or
scope compare balances, persistent/current/original storage, transient storage,
account/slot warmness, signed refund deltas and cumulative refunds. Transaction
results also compare committed state, capped refunds and net gas used. Repeated
transactions share persistent state but start fresh transient/access/refund state.
The reference observes its journal directly so inspection does not warm a key.

Cases include the EIP-2200 storage sequences adjusted to Cancun, cold/warm gas
boundaries, upfront sender/destination/coinbase/precompile warming, duplicate
access lists, high-bit BALANCE aliases, negative frame refund contributions,
static writes, child commit/revert, parent rollback, and transaction abort/reuse.
The Python contract checks field shapes and accounting invariants; independent
anchors check the reference's gas, refund and value results. Operational failures
fail the comparison. Unlike the stateless simultaneous-fault controls, these
state cases require exact diagnostic reasons as well as exact results.

The native state driver takes one versioned binary case encoded as hex. Integers
and lengths use big endian; the encoder lives in `state_corpus.py`. Its current
4,096-byte input limit is a harness limit. JSON lines remain the reference input
and retained corpus format. Each case starts a fresh native process, while all
frames and transactions in that case execute in that process. The scope models
journal boundaries directly; it does not implement CALL/CREATE, transaction
signatures, intrinsic gas or access-list intrinsic charges.

All 349 stateful cases pass at O0/O1/O2 on x86_64 Linux with the
[state-gas compiler pin](../reports/state-gas-toolchain.json). AArch64 macOS
acceptance remains pending. The full native acceptance command includes this
corpus as its own stage.
