# Cancun frame differential corpus

This runner compares FeVM's single-frame execution with `revm-interpreter`
**31.1.0** with a pinned [DUP/SWAP halt-classification correction](https://github.com/sbillig/revm/commit/d613ef5735b9beb17acd53a5a1802ebc2198a18d),
explicitly configured for **Cancun**. Cargo.lock pins the reference and its
dependencies. The draft corpus includes 1,729 frames: arithmetic batches, all PUSH
widths and truncation positions, jumps, stack limits, memory/copy boundaries,
remaining gas, and returned/reverted bytes. A looping program checks gas exhaustion.
Specification-derived anchors also check the reference independently.

Last accepted checkpoint: **1,602 frames pass at O0/O1/O2 on AArch64 macOS**. Fe's
escape-decoding fix supplies valid JSON, and the pinned reference correction
distinguishes DUP/SWAP underflow from genuine overflow. The reference's successful
instruction paths and gas charging remain unchanged. No cases or halt categories
were removed. See the [acceptance report](../reports/cancun-frames.md).
The earlier native baseline passed on Linux; this expanded frame gate still
needs its own Linux run.

The new contract and all 1,729 reference frames pass their checks, but FeVM memory
execution is **not accepted yet**: borrow-analysis scaling blocks compilation.
See the [draft report](../reports/memory-integration-draft.md).

## Running

Use the pinned native compiler and a Rust toolchain capable of building the
locked reference. Keep outputs outside temporary storage:

```sh
python3 native/differential/run.py --fe native/out/toolchain/bin/fe \
  --out native/out/cancun-frames
```

The default builds and runs O0/O1/O2. `--levels 0` selects a focused run. Each
output directory must be fresh. The result record includes compiler/reference
hashes, resolved reference package versions and Git sources, source hashes,
optimization levels and the first failure; generated
`cases.jsonl` retains every input and expected frame. Sources must remain unchanged
throughout a run. Compiler reports, IR, binaries and build logs are retained.

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

Process errors, malformed JSON, unsupported instructions, inexact transaction-gas
accounting and host allocation failures fail the harness. They are not normalized
into EVM halt codes.
Each FeVM frame runs in its own process; arithmetic operations are batched within
bounded EVM programs, preserving every arithmetic result on the stack.

## Scope and references

The expanded slice adds gas and active-memory accounting for implemented stateless
frame instructions. Each case supplies its gas limit; the usual budget is
1,000,000. Inputs remain bounded to 4,096 bytes by the parser. Existing state
operations remain prototype functionality; BALANCE/SLOAD/SSTORE mark gas as
inexact because warm/cold access and original-storage/refund pricing are absent.
The corpus excludes external state and nested calls. It does not establish full
Cancun conformance, rollback, resident allocation reclamation or performance.

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
