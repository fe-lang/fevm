# Cancun frame differential corpus

This runner compares FeVM's single-frame execution with `revm-interpreter`
**31.1.0** with a pinned [DUP/SWAP halt-classification correction](https://github.com/sbillig/revm/commit/d613ef5735b9beb17acd53a5a1802ebc2198a18d),
explicitly configured for **Cancun**. Cargo.lock pins the reference and its
dependencies. The corpus includes 1,602 terminating frames: arithmetic batches,
all PUSH widths and truncation positions, valid and invalid jumps, stack limits,
and returned/reverted bytes. Specification-derived anchors, including all stack cases, also check the
reference independently.

Current status: all **1,602 frames pass at O0/O1/O2 on AArch64 macOS**. Fe's
escape-decoding fix supplies valid JSON, and the pinned reference correction
distinguishes DUP/SWAP underflow from genuine overflow. The reference's successful
instruction paths and gas charging remain unchanged. No cases or halt categories
were removed. See the [acceptance report](../reports/cancun-frames.md).
The earlier native baseline passed on Linux; this expanded frame gate still
needs its own Linux run.

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

The Fe driver accepts `<hex-bytecode> <hex-calldata>` and emits one JSON object:

```json
{"status":"success","stack":["0x0000000000000000000000000000000000000000000000000000000000000001"],"output":"0x"}
```

Stack order is bottom to top. Successful and reverted frames expose the complete
final stack. Exceptional halts expose `null`: operand consumption after a fault is
an engine diagnostic, not a successful frame result. Process errors, malformed
JSON and timeouts fail the harness. They are not normalized into EVM halt codes.
Each FeVM frame runs in its own process; arithmetic operations are batched within
bounded EVM programs, preserving every arithmetic result on the stack.

## Scope and references

This slice compares halt status, successful/reverted stacks and output. It does
not establish gas accounting, memory accounting, external state/rollback, nested
calls, full Cancun conformance or performance. The reference has a 1,000,000-gas
frame limit and a default host; the corpus avoids external-state operations and
gas-dependent results. The Fe process timeout bounds harness failures while
proper FeVM gas metering remains pending.

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
