# Cancun frame correctness checkpoint

Status: **blocked on the pinned reference's stack-underflow classification**.
This is a draft checkpoint, not complete frame acceptance or Cancun conformance.

## Sources and compiler

- Fe: `e51aebfc7027aa37eb81c7fc92046387a01998e2`, [escape fix PR1563](https://github.com/argotorg/fe/pull/1563).
- Sonatina: `61fa661c23bbeeeab024c4e9936656b7a73bd8f4`.
- [Saved toolchain manifest](cancun-toolchain.json); Rust 1.98.1, `cranelift`.
- Compiler SHA-256: `46798d53619da19404cf86afd25c1b676687c25c4f1c27204701fd014114bcc6`.
- Host: Apple M1 Pro, AArch64 macOS 15.6.1.
- Reference: revm-interpreter 31.1.0, revm-bytecode 7.1.1, revm-primitives 21.0.2, with Cargo.lock and explicit Cancun configuration.
- Execution specification: `c335bc4e9e99f7b91024d9033bdc89ce54394848`.

The compiler was built from fresh remote-source checkouts. FeVM was based on
`3518736` with the correctness slice uncommitted during execution. The frame
record retains hashes for every interpreter, driver, corpus and reference source;
those hashes still match this checkpoint. The original failing escape report at
`native/out/cancun-frames` is retained separately.

## Results

| Gate | Result |
| --- | --- |
| Fe full all-feature release suite | 3,414 passed, one configured skip |
| Fe strict Clippy and nightly formatting | Passed, defaults and all features |
| FeVM workspace | 12 passed at each of O0/O1/O2 |
| CLI smoke | 10 passed at each of O0/O1/O2 |
| Arithmetic matrix | 74,676 cases across 48 builds passed |
| SwissTable matrix | 2,004 scenarios across 12 builds passed |
| Cancun frame corpus | 1,475 O0 frames matched; next frame disagrees; O1/O2 not run |

The frame prefix includes all arithmetic, PUSH and jump cases. The failure is
`dup-underflow-1`, bytecode `80`, with empty calldata. FeVM returns
`stack_underflow`; revm returns `stack_overflow`. Direct reference runs of `90`
and `5f90` reproduce the corresponding SWAP issue. The reference's stack methods
return false for insufficient depth, and its DUP/SWAP instruction handlers map
that false result to StackOverflow. The execution-spec stack instructions require
StackUnderflowError. The adapter passes through the reference classification.
This is a halt-category discrepancy, not a demonstrated consensus-state failure.

No output repair, error normalization, case removal or dependency patch was used.
The complete acceptance command exits 1 and records complete=false. User direction
was requested before addressing a newly discovered dependency bug. Timing
comparisons were omitted (`--check-only`); these results make no throughput claim.

## Durable artifacts

All artifacts are under `/Users/sean/code/fevm/native/out/`:

- `escape-toolchain/`: clean compiler sources, executable and build.json.
- `cancun-escape-acceptance/`: acceptance.json, all stage logs and result records.
- `cancun-escape-acceptance/cancun-frames/`: exact cases, first mismatch, source and binary hashes, O0 executable/IR/compiler report.
- `retained/escape-*`: full compiler checks and bootstrap logs.

The compiler and interpreter branches are published for review. The frame runner
compares halt categories, successful/reverted stacks and output. Gas/memory
accounting, external state, rollback and nested frames remain later milestones.
Linux acceptance remains blocked by Cloud Git smart-HTTP access; the baseline
attempts and exact inputs are in [the Cloud handoff](../cloud-linux.md).
