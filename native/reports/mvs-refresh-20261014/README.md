# Latest MVS refresh — 2026-10-14

This is the accepted pre-performance baseline. The [final performance compiler](../mvs-compile-perf-20261014/README.md) retains these prerequisites and adds the verified traversal fix.

Fetched `sbillig/fe:mvs` at `1b4e287c65a0981b385a18c9d49195c92f8f2197`.
Compiler prerequisite refresh `6f496843b0d4192670e1f2a19bf4ae75c51a6499`
is directly based on that revision. It retains the published Sonatina fix
`6f4b0397cfa77165a0ff4fafadc0a003fb72dc59` and the owned native frame stack.
The full FeVM workspace passes semantic checking without runtime-source changes.
All seven native acceptance stages pass on x86_64 Linux; see [acceptance.json](acceptance.json).

The native `FixedStack` holds owned CALL frames in one fallible heap allocation.
Slots start as `None`; push and pop move values, a full push returns its supplied
owner, and release consumes empty storage. Mutable top access reserves the
owner through its last use. This supports large frames with owned byte buffers.
Latest MVS does not provide this native helper. Its implementation and allocator
fixtures apply unchanged. The old complete commit conflicts in the Rust native
test harness because upstream replaced the obsolete effect-provider regression.
The merge retains upstream's test and both stack regressions; the stack source
is byte-for-byte unchanged. See [applicability.json](applicability.json) and
[compiler-prerequisite.patch](compiler-prerequisite.patch).

Sonatina previously classified pure `enum.extract` as unconditionally safe to
speculate. LICM then hoisted a log-buffer payload extraction before its required
active-variant proof. The fix excludes extraction from speculation, retaining
pure value semantics and unused-result removal. Latest MVS still pins the older
Sonatina revision, so the existing published dependency update is retained.
That update applies cleanly. The earlier [port report](../mvs-port-20261012/README.md)
records the isolated LICM reproducer, independent regression and Sonatina suite.

All 3,789 compiler release workspace/all-feature tests pass, with one configured
skip. This includes controlled stack and buffer allocation/ownership tests at
O0/O1/O2, and rejection of pop/release while top access remains live. Strict
all-target/all-feature Clippy, nightly formatting and release-note validation
pass. The Python harness's 13 tests and Rust reference's nine tests pass, with
reference Clippy and formatting clean.

A clean detached bootstrap verifies committed sources, Rust 1.99.0 and Cargo.lock
before freezing compiler SHA256
`82d1c2112d94ea87098c99d5b7eaa344d5552cc76640cd2df1575218481aa75a`.
[compiler-build.json](compiler-build.json) records the build. Acceptance uses
this binary, a fresh published-library cache, one suite at a time, shared-memory
active temporaries and disk-backed idle Cargo artifacts. Runtime sources,
harnesses and original CALL work are frozen and checked by content hash.

The baseline compiler remains local as an ancestor of the final performance
compiler. Publication review uses the descendant's two refs in
[the final publication record](../mvs-compile-perf-20261014/publication.json).
The original baseline tip and patch remain in [publication.json](publication.json).

Compilation is CPU-bound during preparation. Two 30-second live O1 samples
(5,904 samples total) attribute 77.93% and 69.48% of their CPU time to named
Sonatina enum-proof verifier functions and typed containers. Hot work traverses
value-state trees, updates overlapping children, collects captured references
and merges reference sets. These sampled windows establish a live hotspot,
not whole-run phase percentages or a measured optimization benefit. Test
modules each repeat runtime code generation and Full verification, while cases
within a module share one object. See [compilation-cost.json](compilation-cost.json).
No verification checks were removed and no performance change was made.

An extended 49 Hz O2 profile covers 1,185 seconds (~93% of that stage) and
confirms the larger observation: 55.37% of sampled CPU is in named enum-proof
verifier functions/containers; named Cranelift functions account for 3.46%.
`ValueState::captured` takes 8.82%, persistent child-map range iteration 7.64%,
and `References::join` 6.31%. Generic allocation and type-query costs are not
attributed to callers. See [perf-O2-extended-summary.json](perf-O2-extended-summary.json).
The earlier short-window percentages describe verifier-heavy intervals.

Acceptance passes all 52 workspace tests, 35 CLI/allocator checks, 1,840 frame
comparisons and 1,142 state comparisons at each of O0/O1/O2, plus 74,676
arithmetic checks across 48 builds. The three previously recorded simultaneous-
fault reason differences per frame level are unchanged; the compared outcomes,
gas, output, stack and active memory pass. The state corpus excludes CALL/CREATE;
this is not full Cancun conformance and AArch64 macOS remains unexecuted.

All 68 frozen input files and the 14 original dirty/untracked files retain their
recorded hashes. The acceptance workspace includes the user's existing CALL
changes. This refresh changes the compiler pin and evidence only; it leaves that
work uncommitted and byte-for-byte intact. See
[source-verification.json](source-verification.json).
