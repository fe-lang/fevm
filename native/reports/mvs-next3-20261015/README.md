# Next three native compilation leads

The three-lead repair is complete locally. Compiler suites, all five
report-enabled O1 observations, the full native matrix and Python/Rust harness
checks pass. The accepted manifest matches the exact tested clean bootstrap.
No new compiler refs or PRs have been published; use the documented local
repository overrides until publication.

The fork MVS baseline is `8de35117e3de35c2f92967ec260e124db87c85bb`.
The previous accepted compiler is Fe `d7fdfbb73956b2f3d41e7f4b8101a5a49de46509`
with Sonatina `498ce58134505992ccd1146dcbdb94a11483fcf0`, which includes the
[previous aggregate-initialization repair](../mvs-compile-perf-20261015/README.md).
The new compiler is Fe `d1ccff352971945e4a9cd326fe5dc0b106a016ac` with
Sonatina `325114276de157cde38f5833ed8413166ef9741a`, Rust 1.99.0 and Cranelift.

Three leads were implemented: persistent enum-proof view-index snapshots with
incremental index updates at CFG joins; native layout queries that borrow type
definitions under one read guard; and one reachable runtime package across all
selected test source modules in an ingot. Each test still executes in its own
process. Native artifacts cut over to `<suite>.native.test.sona`/`.rmir` and
`artifacts/native/test-<index>/`; old module artifact paths are not emitted.

| Configuration | Wall seconds | User CPU seconds | Peak RSS KiB |
| --- | ---: | ---: | ---: |
| Previous compiler | 636.903 | 620.78 | 7,240,176 |
| Initial persistent index (rejected alone) | 685.596 | 671.50 | 7,390,940 |
| Add borrowed native layouts | 678.341 | 665.72 | 7,376,064 |
| Add incremental index joins | 534.836 | 525.24 | 4,440,956 |
| Add shared native test runtime | 401.405 | 393.72 | 4,648,812 |

Each row is one complete 52-test O1 workspace observation with reports enabled,
identical 68 input hashes, one suite/Rayon worker and no overlapping task builds
or tests. These are observations, not statistical estimates. All retain Full
verification. Intermediate compilers use Fe d7fdfbb73 plus recorded pin-only
patches. The final row uses the clean exact-commit bootstrap in `build.json`.

The combined change reduces wall time 36.98% and peak RSS 35.79%. The backend
repairs alone reduce wall time 16.03% and peak RSS 38.66%. Shared ingot compilation
adds a 24.95% wall reduction against that backend. Reports show 3,382 runtime
function entries across 12 objects before sharing, and 653 entries in one object
afterward. Within-suite owner/body summaries confirm 2,729 duplicate entries
before and none afterward. Display symbols are excluded from that comparison
because package-specific collision resolution can rename them.

The initial persistent-index prototype regressed despite its isolated snapshot
win. CFG joins rebuilt the full derived index; retaining unchanged paths and
updating changed/missing references is required. Do not adopt the initial index
commit without its join refinement. The layout increment is a 7.25-second/1.06%
observation in one pair and does not establish a precise whole-program gain.

All 12 linked test executables and 12 native objects are byte-identical in the
backend-only comparison with the previous compiler (`backend-artifact-comparison.json`).
The shared test executable necessarily has a different dispatcher and root set.
Source-module sharing applies to native tests; standalone executable builds use
their existing entry graph and receive the backend improvements.

Sonatina's final gates pass 1,961 tests (three configured skips), 355 filechecks,
docs/doctests, strict Clippy and nightly formatting. Fe passes 3,827 tests (one
configured skip), doctests, strict Clippy, release-note checks and formatting.
The new regressions cover snapshot isolation, mutable/forked native type stores,
join reference/binding/cache changes, duplicate test names, matching extern ABI
declarations, filters, empty selections and shared report artifacts. Temporary
ignored probes are absent from production sources.

Probe results include one warmup and five alternating measured pairs. The
snapshot probe compares 512 clones plus sparse removals; the layout probe keeps
both production-equivalent algorithms in one binary; the join probe compares
the eager persistent-index join with incremental updates in one binary and
checks state equality outside its timers. Their scoped gains are not predictions
of whole-program speedups. Frozen binaries and raw archives remain in
`/tmp/fevm-mvs-next3-20261015-r1`; hashes, commands, source patches and logs are
recorded here. The experimental `fe-ablation` checkout retains its recorded
pin-only diff. The production Fe and Sonatina branches are clean.

All seven native stages pass: 52 workspace tests / 35 CLI-allocator checks /
1,840 frames / 1,142 state cases at each of O0/O1/O2, plus 74,676 arithmetic
cases in 48 builds. Stage seconds are 472.894, 394.070, 393.065, 177.666, 77.925,
257.350 and 11.790; their sum is 29.746 minutes. These are verification timings;
no fresh paired whole-matrix baseline is claimed. All 57 standalone executables
(three main CLI, six differential drivers, 48 arithmetic kernels) are byte-identical
to the previous accepted compiler. Python's 13 tests and Rust reference's nine
tests, Clippy and formatting pass. Existing three simultaneous-fault frame reason
differences per level are unchanged; other compared observables match. State
coverage excludes CALL/CREATE, full Cancun conformance remains pending, and no
AArch64 execution was performed.

The final O1 profile contains 18,484 user-CPU self samples at 49 Hz, zero lost
samples, starting at 7.15 compiler CPU seconds. Capture stopped with controlled
SIGINT after compiler exit; `perf report` parses it successfully. Named enum-proof
signatures remain the largest category at 40.66%, with initialization 2.89%,
Cranelift 4.98% and aggregate-shape signatures 4.86%. Generic allocator costs are
unattributed and caller chains are incomplete. View-set clones, value-child
iteration/lookups, value joins and reference comparisons remain follow-ups.
An EVM layout clone closure appears at 2.17%; its calling phase is not identified.
No fourth optimization is included. Leaf postprocessing overlaps O2 verification
only, after all comparative observations and the O1 capture have ended.

All 68 frozen inputs matched before adoption. The tested manifest is then adopted
with its explicit hash delta recorded in `source-verification.json`; all 67 runtime
and harness inputs retain their hashes. The 14 original user files retain their
literal hashes and remain uncommitted. `publication.json` records the local-only
scope. `sonatina-complete.patch` includes the prior initialization repair plus the
three new backend commits, and `fe-complete.patch` includes all work atop fork
MVS8de35117e. Individual patches preserve the measured history.
