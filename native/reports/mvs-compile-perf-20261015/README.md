# Latest-MVS FeVM compilation investigation — 2026-10-15

Compiler implementation and full Fe/Sonatina verification are complete locally.
**All seven native acceptance stages pass on x86_64 Linux.**

| Stage | Result | Wall time |
| --- | --- | ---: |
| Workspace O0 | 52 passed | 614.14 s |
| Workspace O1 | 52 passed | 620.67 s |
| Workspace O2 | 52 passed | 617.32 s |
| CLI/allocator | 35 passed per level | 194.91 s |
| Cancun frames | 1,840 passed per level | 80.24 s |
| Cancun state | 1,142 passed per level | 319.06 s |
| Arithmetic | 74,676 cases, 48 builds | 11.79 s |

The complete candidate matrix takes **40.97 minutes**. Only O1 has a fresh
matched baseline in this investigation; no whole-matrix comparative speedup is
claimed. All three main CLI executables are byte-for-byte identical to the
latest-MVS baseline ([CLI comparison](cli-comparison.json)). Baseline CLI timings
are excluded because that correctness/hash run overlapped Rust bootstrap.
The Python harness passes 13 tests; the Rust reference passes nine tests, strict
Clippy and nightly formatting. The three existing simultaneous-fault reason
differences per frame level remain unchanged. State cases exclude CALL/CREATE;
this is not full Cancun conformance, and AArch64 macOS was not run.

The unchanged-input O1 comparison improves **690.43 → 620.67 seconds**,
saving 69.76 seconds (**10.10% less wall time**). Both runs pass all 52 tests
with one suite worker and one Rayon worker. This is one integration observation
per compiler, not a statistical speedup estimate. See [workspace-comparison.json](workspace-comparison.json).

The candidate profile covers almost the whole stage (attachment at 5.95 compiler
CPU seconds). Named initialization-state work falls **7.79% → 2.37%**, and
aggregate-shape helpers **6.52% → 4.27%**. Named enum-proof work remains the
largest category (**34.25% → 38.28%** as other work shrinks). Coverage differs,
so these are descriptive self-sample shares, not exact paired phase timings.

The exact fork MVS baseline is Fe `8de35117e` with Sonatina `1544e570`.
It already includes native FixedStack and the preceding enum-proof repair.
The baseline passes all 52 O1 workspace tests in **690.43 seconds** (672.93 user,
14.77 system), with 7,246,332 KiB peak RSS. The profile wrapper's extra completion
poll interval is excluded from that compiler time.

Whole-run 49Hz user-CPU self samples attribute 34.25% to named enum-proof
functions/containers, 7.79% to initialization-state functions/containers,
6.48% to named Cranelift functions, and 6.52% to aggregate shape helpers.
These categories do not assign generic allocator work to callers. DWARF stacks
unwind incompletely, so no inclusive phase estimates are used. Two additional
30-second diagnostic windows were recorded during the baseline run.

The repair is Sonatina `498ce58134505992ccd1146dcbdb94a11483fcf0`, directly atop
`1544e570`. Initialization-state joins reuse exact shared snapshots, test variant
difference before walking definedness, visit each child key once, and retain
unchanged persistent-map entries. Full verification remains enabled, with no
new cache or dependency. Two regressions cover all 1,024 pairs of sparse
four-coordinate states, default definedness, enum metadata and snapshot isolation.

A private-operation scaling probe uses valid nested single-child aggregates,
256 joins per case, one warmup pair and five alternating measured pairs. At
depth 12, changed-state joins fall from **391.835 ms to 0.7204 ms (543.9x)**.
Identical shared-state joins become constant-time. These isolated operation
timings exclude parsing/construction and do not establish a FeVM speedup.
The first synthetic fixture used invalid one-line IR blocks; it was corrected,
preserved and excluded. The temporary ignored probe is absent from the commits.

Sonatina passes **1,958 tests, 355 filechecks**, docs/doctests, strict Clippy and
nightly formatting. Fe integration `d7fdfbb73956b2f3d41e7f4b8101a5a49de46509`
is directly atop latest fork MVS `8de35117e` and passes **3,826 tests**, strict
Clippy, formatting and release-note checks. Fe changes only the backend pin and
one release note. Its lockfile changes only six Sonatina package source revisions;
full locked metadata validates the graph. Configured skips remain unchanged:
three Sonatina, one Fe.

Both compiler branches remain local:

- Fe `perf/fevm-native-compile-20261015` at `d7fdfbb73956b2f3d41e7f4b8101a5a49de46509`.
- Sonatina `perf/fevm-verifier-20261015` at `498ce58134505992ccd1146dcbdb94a11483fcf0`.

[publication.json](publication.json) records exact proposed refs and patches.
No new compiler refs or FeVM changes were pushed. Bootstrap currently needs
local repository overrides containing the pinned commits; see the
[native build instructions](../../README.md).

All 68 frozen input hashes matched throughout acceptance, including all 14
original user work files. After the matrix passed, the project toolchain manifest
adopted the exact tested compiler from its separate bootstrap manifest. All 67
runtime/harness inputs remain unchanged; historical accepted input hashes and
the pin-adoption delta are preserved in [source-verification.json](source-verification.json).
Existing CALL edits remain unchanged and uncommitted. Compiler worktrees and
clean bootstrap tracked sources are unchanged, and the frozen compiler hash
still matches `c9ffe9ef6d74f3acd62ba76dc19db17769f66c58eadb26d124a21aa1fb1435ff`.

Raw profiles and immutable binaries remain under
`/tmp/fevm-mvs-compile-perf-20261015-r1`. The checked-in probe source is injected
into the existing private `object_initialization::tests` module for measurement;
it is absent from the production commits. [join-comparison.json](join-comparison.json)
records all warmup/measured samples and immutable test-binary hashes are recorded
separately. [sonatina-performance.patch](sonatina-performance.patch) and
[fe-performance.patch](fe-performance.patch) contain the complete local changes.
Remaining enum-proof retention/alias-map costs and per-module runtime-package
compilation are tracked follow-ups; neither is changed by this repair.
