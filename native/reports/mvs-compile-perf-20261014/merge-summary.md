# FeVM MVS prerequisite merge inventory

Published branches contain four commits to merge, in dependency order:

| Repository | Commit | Change |
| --- | --- | --- |
| Sonatina | [`6f4b0397`](https://github.com/fe-lang/sonatina/commit/6f4b0397cfa77165a0ff4fafadc0a003fb72dc59) | Keep enum extraction under its active-variant proof |
| Sonatina | [`159c00d6`](https://github.com/fe-lang/sonatina/commit/159c00d6576757adc48c816d501a14386b12a902) | Avoid repeated enum-proof array and capture scans |
| Fe | [`6f496843b`](https://github.com/sbillig/fe/commit/6f496843b0d4192670e1f2a19bf4ae75c51a6499) | Native fixed stack, allocator/ownership regressions, initial correctness pin |
| Fe | [`ed4ec1d4c`](https://github.com/sbillig/fe/commit/ed4ec1d4c3eb5fe4090caedf1235f6c6df375d08) | Pin the complete Sonatina correctness/performance series |

## Sonatina

Branch: [`perf/fevm-enum-proof-traversal-20261014`](https://github.com/fe-lang/sonatina/tree/perf/fevm-enum-proof-traversal-20261014).
The two commits are directly atop `11722eac`. The earlier correctness commit is
also published separately on `fix/enum-extract-speculation` and is an ancestor of
the performance branch.

1. **Enum-extraction correctness.** `EnumExtract` remains a pure value operation,
   but `DataFlowGraph::can_speculate` rejects it because its payload requires an
   active-variant proof at the use site. LICM previously hoisted FeVM log-buffer
   payload extraction ahead of that proof. A loop regression checks Full
   verification before/after LICM and through speed/size pipelines; the enum
   verification documentation records the distinction.
2. **Enum-proof verifier performance.** In `ValueState`, constant-index writes
   traverse only potentially overlapping symbolic children; symbolic/unknown
   writes retain the required weak updates. Captured-reference unions accumulate
   in place. An exact empty-capture certificate avoids repeated subtree scans,
   remains separate from stored-reference absence, and is invalidated when facts
   mutate. Aggregate initialization propagates absence proofs through retained
   SSA prefixes. Semantic regressions preserve reference alternatives, sparse
   implicit cells, inactive payloads, overlapping writes and snapshot isolation.
   Full proof verification remains enabled.

The CPU bottleneck was repeated verifier traversal and reference-set copying.
Named enum-proof functions/containers occupied 55.37% of the extended baseline
O2 CPU profile, versus 3.46% in named Cranelift functions. Repeated isolated
measurements show 6.85x faster 4,096-element construction and 16.25x faster the
4,096-element/1,024-call capture case. These microbenchmarks include process
startup and parsing and do not represent whole-compiler speedups.

## Fe

Branch: [`fevm-mvs-compile-perf-20261014`](https://github.com/sbillig/fe/tree/fevm-mvs-compile-perf-20261014).
Its two commits are directly atop the refreshed fork MVS revision
`1b4e287c65a0981b385a18c9d49195c92f8f2197`.

1. **Owned native frame storage.** Add exported `std::native::FixedStack<T, CAPACITY>`
   backed by one fallible heap allocation, initialized in place. Push/pop move
   owned values, a full push returns the supplied owner, `top_mut` reserves the
   stack while its result is live, and `release` consumes empty storage. This
   keeps large frame aggregates off the host stack. Expose the existing native
   allocator helpers within the ingot. Add Fe/C fixtures covering allocation
   failure, owned buffers, slot reuse and reclamation at O0/O1/O2, plus access
   conflict checks for pop/release with a live top borrow. Share the native-object
   extraction helper between allocator tests.
2. **Backend dependency integration.** Update Cargo.toml/Cargo.lock to Sonatina
   `159c00d6`, including both fixes. The final pin update changes only the six
   Sonatina lockfile source revisions; unrelated dependencies remain unchanged.
   Include the feature, correctness and performance release notes.

The stack implementation and allocator fixtures apply unchanged to this MVS
base. Only the Rust test harness required a small merge with upstream's replaced
effect-provider fixture. That merge is already included. The older standalone
owned-effect fixture migration is superseded upstream and should not be carried
forward. Use this refreshed branch rather than merging the old FeVM prerequisite
branch wholesale.

## Verification and boundaries

- Fe: 3,789 release workspace/all-feature tests pass, one configured skip.
- Sonatina: 1,954 tests pass, three configured skips; 353 filechecks and doctests pass.
- Strict Clippy, nightly formatting and Fe release-note checks pass.
- FeVM: all seven native gates pass; each O0/O1/O2 run covers 52 workspace tests,
  35 CLI/allocator checks, 1,840 frame comparisons and 1,142 state comparisons,
  plus 74,676 arithmetic checks across the matrix.
- Workspace preparation improves from 20.3/21.4/21.3 to 10.2/11.5/11.4 minutes;
  the full matrix improves from 78.44 to 43.72 minutes. These are single-run
  integration observations. All nine CLI/frame/state executables are identical.
- Published remote tips are verified. Fresh default-URL checkouts match every
  tracked source byte used for acceptance; the lockfile hash also matches.
- No additional FeVM runtime migration was needed for the compiler refresh or
  performance fix. The original CALL edits remain unchanged and uncommitted.
- Acceptance is x86_64 Linux; AArch64 macOS was not run. State differential cases
  exclude CALL/CREATE, and three existing simultaneous-fault reason differences
  per frame level remain unchanged. This is not full Cancun conformance.
- Remaining alias/map retention and repeated per-module runtime compilation are
  recorded follow-up opportunities; they are outside these four merge commits.

See [acceptance and profiles](README.md), [exact Fe patches](fe-prerequisite.patch),
[Sonatina performance patch](sonatina-performance.patch), and
[published source verification](published-verification.json).
