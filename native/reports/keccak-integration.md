# Native Keccak and BLOCKHASH integration

The library is published at [fe-lang/keccak](https://github.com/fe-lang/keccak),
pinned in FeVM to `7f32a75b9426f68fd3d44c2d09207386c481355d`. The local Keccak
implementation and reference harness have moved there. The standalone repository
owns known-answer, chunking, subrange and randomized differential tests against
both `tiny-keccak` and RustCrypto, plus reproducible benchmark/compiler artifacts.

FeVM now implements SHA3 using that library. It charges Cancun's 30 gas plus
six per input word and memory expansion before allocating, handles zero-length
input without narrowing its offset, hashes borrowed memory without changing it,
and pushes the digest as a big-endian EVM word. BLOCKHASH now checks the previous
256-block window before consulting host history, preserving full-width operands.

The compiler pin advances from the local transaction integration to published
Fe master `04d34410582e4ddac3f516c6ded1a0fdb4a31b3c`, with Sonatina
`9c35018759aff07516025684fea0be784b0cf6df`. The immutable x86_64 Linux binary
has SHA-256 `0a0254cd83b74eabc85b48706afaa45e397a0e6f5dd1aef2d406351aa596f92e`.
FeVM needs no unpublished compiler changes. The standalone timing harness needs
a new native scalar-barrier API; Keccak ships its independently verified Fe
patch and build instructions.

## Coverage

- 35 native FeVM tests, including exact SHA3 gas boundaries, allocation ordering,
  full-width offsets/lengths, borrowed memory, static execution and BLOCKHASH.
- 16 CLI/allocator/journal checks at each optimization level, including empty
  Keccak and the `abc` known answer.
- 1,835 Cancun frame cases, including 106 Keccak cases covering unaligned input,
  padding/rate boundaries, empty ranges, zero-filled expansion, gas and faults.
- 383 state sequences, including 34 block-history and gas cases. State wire
  format version 2 carries explicit block history and a per-transaction number.
- Existing arithmetic differential kernels and protocol/reference tests.

The rollback fixture's former SHA3 TODO example now uses LOG0, preserving its
operational-failure rollback assertions. Independent reference anchors pass for
all frame and state cases. Standalone Keccak passes all three library tests and
600 differential cases per implementation at O0/O1/O2; its published-master
library tests also pass without the benchmark compiler patch.

## Acceptance

All seven stages pass on x86_64 Linux: 35 workspace tests, 16 CLI checks,
1,835 frame cases and 383 state sequences at each of O0/O1/O2, plus 74,676
arithmetic checks across 48 generated builds. The frame corpus retains three
previously declared RETURNDATACOPY simultaneous-fault reason differences at each
level; all 106 Keccak cases match. All ten Python harness tests and five Rust
reference tests pass, as do nightly Rust formatting and strict Clippy.

The [machine-readable record](linux-x86_64-keccak-acceptance.json) includes
compiler identity, Git dependency pins, source hashes, per-stage results and
build metadata. Source hashes were rechecked against the final tree. Workspace
logs and [the compiler manifest](keccak-toolchain.json) are retained alongside it.
Full local artifacts live under `native/out/keccak-acceptance-20261002-r2`, with
the immutable compiler under `native/out/keccak-resume-20261002/toolchain`.

Acceptance runs every workspace suite with `--jobs 1`. The initial run found
and corrected the obsolete rollback fixture; its partial result is retained
separately. Explicit 3- and 6-GiB scopes were too small for compilation. The
successful run used a 12-GiB scope and reached about 9.55 GiB, without recorded
memory-limit or OOM events. These settings retain every optimizer level and
verifier check. Total acceptance wall time was approximately 70 minutes on
this shared host.

This checkpoint does not establish complete Cancun conformance or AArch64 macOS
acceptance. Account-code opcodes, calls/creation, logs and the remaining families
remain subsequent interpreter work.
