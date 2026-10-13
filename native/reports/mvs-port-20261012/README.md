# MVS port — 2026-10-12, verified 2026-10-13

All seven native acceptance stages pass on x86_64 Linux with the clean pinned
compiler Fe `1c8e2c20d` and Sonatina `6f4b0397`. The existing uncommitted CALL
work is preserved. Prerequisite commits remain local; remote reproducibility
requires their publication and a cold dependency-resolution check.

| Acceptance | Result |
| --- | --- |
| Native workspace | 52 tests at each O0/O1/O2 |
| CLI and controlled allocators | 35 checks at each O0/O1/O2 |
| Cancun frame comparisons | 1,840 cases at each O0/O1/O2 |
| Cancun state comparisons | 1,142 cases at each O0/O1/O2 |
| Arithmetic | 74,676 checks across 48 builds |

See [acceptance-final.json](acceptance-final.json), the accompanying logs and
individual `*-final.json` results. The frame comparison retains three known
simultaneous-fault reason differences at each level; its scope compares outcomes,
gas, output, completed stack and active memory. This acceptance covers the
recorded bounded corpora; full Cancun conformance and AArch64 macOS verification
remain outside this result. Timing measurements were omitted.

The fresh detached bootstrap verifies exact source revisions, Rust 1.99.0 and
Cargo.lock SHA256 before compiling. [compiler-build.json](compiler-build.json)
records the frozen binary SHA256
`e45b3315ebd67d6b01fdc103cc17bcf2839dd00fc193ef795488cfebaf62b896`.
All consumer source hashes still match the snapshot exercised by acceptance.

Fe derives from `sbillig/fe:mvs` at `fe5c32c1`. Commit `c4b5c2a` migrates the
obsolete effect-provider regression to owned native storage. Commit `2c114c8a`
adds the owned native `FixedStack` required by the CALL scheduler. Commit
`1c8e2c20` pins the Sonatina enum extraction fix. The complete locked release
Fe workspace/all-feature suite passes 3,782 tests (one configured skip), with
strict all-target/all-feature Clippy and nightly formatting clean. See
[compiler-enum-nextest.log](compiler-enum-nextest.log) and
[compiler-enum-clippy.log](compiler-enum-clippy.log).

The original O1 log allocator fixture exposed LICM moving pure `enum.extract`
above its required active-variant proof. Isolated replay of the actual FeVM IR
established LICM as the first invalidating pass. Sonatina `6f4b0397` excludes
payload extraction from unconditional speculation, preserving value semantics
and unused-result removal. An independent regression verifies isolated LICM
and both optimization pipelines. Full Sonatina tests pass 1,952 cases (three
configured skips), all 353 filechecks, strict Clippy and doctests. The original
log fixture and every allocator check pass in final acceptance. No verifier
relaxation or consumer workaround was used. Before/after IR and pass traces
remain in this directory.

FeVM now uses MVS mutable value bindings, explicit native argument safety
boundaries and move/refill ownership. `LogEntry` copies header metadata;
payload reads use `LogBuffer.byte_at(entry, index)` through the current owner.
The full tested working tree includes the five pre-existing CALL tests. The
separate migration commit excludes that original CALL implementation; its
reconstructed workspace passes semantic checking on the final compiler.
[preserved-CALL-work.json](preserved-CALL-work.json) verifies all 12 original
tracked and untracked CALL files differ only by the intended migration edits.
Unrelated root logs remain untouched.

Keccak's three and SwissTable's six library tests pass at O0/O1/O2. SwissTable's
historical benchmark baseline `60017e7f` changes only eleven mutable binding
spellings. Runner `770372e5` pins it, and all 2,004 dictionary/probe scenarios
across 12 builds pass. The production SwissTable pin remains `7e275c4`.
Keccak's separate benchmark requires its documented experimental compiler
barrier and is outside this runtime acceptance. The Python harness tests and
Rust reference tests pass; reference Clippy and nightly formatting are clean.

The exact five prerequisite branch tips and patches are reviewable in
[publication.json](publication.json). Manifests use portable Git URLs and
immutable revisions. Local verification uses process-scoped Git transport
overrides, recorded in [progress.json](progress.json); global Git configuration
was not changed. No prerequisite or FeVM branch has been pushed.

Historical failures are retained: the missing stack, obsolete effect-provider
fixture and pre-fix O1 enum extraction failure each have logs and reproductions.
A later O1 run timed out under severe memory pressure while idle Cargo and old
acceptance artifacts occupied shared RAM. Moving those artifacts to disk with
original-path symlinks preserved every file and recovered about 7.3 GiB of RAM.
The unchanged seven-stage retry passed with the same timeouts; O1 completed in
1,276 seconds. Resource samples and [memory-recovery.json](memory-recovery.json)
record the environment correction. The user-authorized deletion of exactly
47 obsolete test executables is separately audited in the cleanup records.
