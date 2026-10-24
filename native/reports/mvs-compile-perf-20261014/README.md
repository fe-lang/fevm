# MVS native compilation performance — 2026-10-14

All seven native acceptance stages pass on x86_64 Linux with the fixed compiler.
Workspace compile/test preparation is approximately twice as fast:

| Level | Baseline | Fixed |
| --- | ---: | ---: |
| O0 | 20.29 min | 10.24 min |
| O1 | 21.37 min | 11.49 min |
| O2 | 21.29 min | 11.43 min |

The complete matrix takes 43.72 minutes versus 78.44 minutes (~44% less wall time).
These are single-run integration observations; see
[native-comparison.json](native-comparison.json) for exact times and profiling
coverage. Small independent scaling measurements below use repeated paired runs.


The unchanged latest-MVS baseline is Fe `6f496843b`, directly based on fork MVS
`1b4e287c`, with Sonatina `6f4b0397`. It passes all seven native acceptance stages.
Workspace preparation takes 1,217 / 1,282 / 1,278 seconds at O0/O1/O2.
Its [extended O2 profile](../mvs-refresh-20261014/perf-O2-extended-summary.json)
covers 1,185 seconds: named enum-proof verifier functions and typed containers
account for 55.37% of sampled CPU; named Cranelift functions account for 3.46%.
The earlier short O1 windows show 69–78% verifier work. Those are sampled CPU
costs, not inclusive caller costs or whole-run percentages.

Sonatina `159c00d6576757adc48c816d501a14386b12a902` fixes repeated work in
`ValueState`:

- Constant array writes visit only symbolic children that can overlap the index.
- Captured-reference unions accumulate in place, avoiding repeated set cloning.
- Immutable snapshots retain a separate proof that capture returns empty.
  Mutation invalidates that proof. It includes implicit and inactive payloads.
- Empty aggregate construction seeds absence proofs so retained SSA prefixes
  reuse them; fully initialized scalar arrays establish implicit capture absence
  before the first insertion.

Full verification, reference alternatives, weak updates, sparse implicit cells,
inactive enum payloads and snapshot isolation remain required. No proof level or
test case is removed. Two new semantic tests and extended snapshot/absence
regressions accompany the implementation.

All 1,954 Sonatina release workspace/all-feature tests pass, with three configured
skips. All 353 filechecks, doctests, strict all-target/all-feature Clippy and nightly
formatting pass. [sonatina-checks.json](sonatina-checks.json) records the commands.

Independent generated IR inputs exercise construction, repeated capture, and
distinct reference-bearing arrays through the generic Full verifier. These
isolated fixtures use the EVM target. Both immutable CLI binaries use Rust 1.99.0
and default features. Measurements include parsing and process startup, with one
warmup pair and five alternating measured pairs, one Rayon worker and no
concurrent task builds or tests. All 26 valid cases pass.

| Case | Baseline | Fixed | Speedup |
| --- | ---: | ---: | ---: |
| 4,096-element construction | 222.04 ms | 32.40 ms | 6.85× |
| 4,096 elements, 1,024 capture calls | 972.63 ms | 59.85 ms | 16.25× |
| 1,024-reference return | 56.36 ms | 17.54 ms | 3.21× |

Small-case peak RSS is approximately unchanged. These numbers do not establish
the end-to-end FeVM speedup. [comparison.json](comparison.json) and
[comparison-samples.json](comparison-samples.json) retain input hashes, binary
hashes and individual samples. [compare.py](compare.py) records the measurement
procedure; [fixtures.tar.gz](fixtures.tar.gz) contains the valid inputs. An initial
extra fixture used `obj.proj` for an array; the baseline correctly rejected it.
The corrected `obj.index` fixtures are the measured reference cases. That failed
setup is excluded, and [fixture-correction.json](fixture-correction.json) records it.

Fe `ed4ec1d4c3eb5fe4090caedf1235f6c6df375d08` passes all 3,789 release
workspace/all-feature tests (one configured skip), strict Clippy, nightly
formatting and release-note checks. A clean pinned bootstrap freezes compiler
SHA256 `9b1efb263b1f2bf7bb85be49a23979ecaff7ecbb5d1fed128169be3daafd8814`.
[compiler-build.json](compiler-build.json) records the exact sources and toolchain.

Fe's integration retains every other dependency input exactly. The Cargo lockfile
diff changes only the six Sonatina package revisions; locked metadata validates
the graph. [fe-pin-update.json](fe-pin-update.json) records the lock hash and the
unrelated resolver changes that were prevented. Existing FeVM CALL edits and all
runtime sources remain unchanged. Both prerequisite branches are published.


Acceptance retains all 52 workspace tests, 35 CLI/allocator checks, 1,840 frame
comparisons and 1,142 state comparisons at each of O0/O1/O2, plus 74,676 arithmetic
checks across 48 builds. All nine CLI/frame/state executables have identical
SHA256 hashes to the baseline. The Python harness's 13 tests, Rust reference's
nine tests, reference Clippy and nightly formatting also pass.

The fixed extended O2 profile covers 678 seconds of the 686-second stage.
Named enum-proof work accounts for 34.69% of sampled CPU versus the baseline's
55.37%. The named captured-reference function falls from 8.82% to 0.06%; full
child-map range iteration from 7.64% to 1.72%. Coverage differs between profiles,
so percentages are descriptive rather than exact paired phase estimates.
[perf-fixed-O2-summary.json](perf-fixed-O2-summary.json) records the details.

All 68 frozen input files and all 14 original dirty/untracked files retain their
recorded hashes. The toolchain manifest is the only input change from baseline;
existing CALL work remains unchanged and uncommitted. See
[source-verification.json](source-verification.json). The three existing
simultaneous-fault reason differences per frame level remain unchanged. The
state corpus excludes CALL/CREATE, full Cancun conformance remains pending, and
AArch64 macOS was not executed.

The native `FixedStack` implementation and allocator fixtures carry unchanged
onto MVS `1b4e287c`; upstream's test-harness changes required a small merge.
The earlier enum-extraction speculation repair remains in the backend's history.
[The baseline report](../mvs-refresh-20261014/README.md) records applicability.
[fe-prerequisite.patch](fe-prerequisite.patch) and
[sonatina-performance.patch](sonatina-performance.patch) contain the exact changes.

The [merge inventory](merge-summary.md) describes all four Fe/Sonatina commits,
their dependency order and the upstream changes that supersede older patches.

Both prerequisite branches are published after explicit user authorization:

- [Fe `fevm-mvs-compile-perf-20261014`](https://github.com/sbillig/fe/tree/fevm-mvs-compile-perf-20261014) at `ed4ec1d4c`.
- [Sonatina `perf/fevm-enum-proof-traversal-20261014`](https://github.com/fe-lang/sonatina/tree/perf/fevm-enum-proof-traversal-20261014) at `159c00d6`.

[publication.json](publication.json) and [publication-push.json](publication-push.json)
record the exact remote tips. Fresh default-URL bootstrap source preparation
uses no repository overrides. All 4,462 tracked Fe files and 1,224 Sonatina files
match the accepted clean bootstrap sources byte-for-byte, and the Cargo lock
hash matches. [published-verification.json](published-verification.json) records
that comparison. Prepare-only does not rebuild the compiler; its `build.json`
retains `complete: false` by design. The complete compiler and native acceptance
results above apply to these identical sources.

Only the toolchain manifest's publication description changed after acceptance;
[progress.json](progress.json) preserves the accepted input hashes and separately
records this metadata change. Existing published library pins remain unchanged.
The FeVM branch was not pushed.
