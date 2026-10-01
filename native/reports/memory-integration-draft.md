# Owned VM memory integration — Linux checkpoint

The owned-memory slice passes the complete native acceptance suite on x86_64
Linux with the local Fe integration `f6eed783cad9f437b5b1efb6b1fd59368d17ab55`
and published Sonatina `f8a9fe5ab832b718dbef57309c88c4290dd66232`.
The Fe branch is `integrate/fevm-development-20261001`; it includes performance
PRs #1661–#1667, pointer-analysis PR #1628, and LSP PR #1674 on master `2cd823883`.
Sonatina includes the merged verifier and initialization-sharing PRs #356/#357.
The exact source/lock pins are in [the toolchain manifest](../toolchain.json).
Fe remains local; rebuilding requires a local Fe repository or bundle containing
the integration commit, as described in [the native README](../README.md).

The [retained acceptance record](linux-x86_64-memory-acceptance.json) records:

- 19 workspace tests at each of O0/O1/O2, including frame reuse, zeroing,
  output ownership transfer, and gas exhaustion before allocation.
- 13 CLI checks at each level, including poisoned fresh allocations, memory and
  output allocation failures, and exact releases of owned buffers.
- 1,729 Cancun frames at each level, including 96 memory and 31 gas cases.
  The three declared simultaneous-fault reason differences per level are retained.
- 2,004 SwissTable scenarios across 12 builds and 74,676 arithmetic checks
  across 48 builds.
- 4,415 Fe release/all-feature tests passed, one skipped; strict Clippy and
  nightly formatting passed. Two cost snapshots were refreshed for the adopted
  Sonatina EVM optimizations after their execution/state assertions passed.

Acceptance used an immutable compiler built before the integration commit, whose
version string names parent `2cd823883`. The source audit verifies that the only
subsequent source differences are those two test snapshots; compiler code and
Cargo.lock are identical. The retained record includes its exact binary and patch
hashes. A clean-source bootstrap of the committed pin succeeds and its O1 FeVM
executable is byte-identical to the accepted build; all ten CLI smoke cases pass
again. Concurrent verification timings are not performance measurements.

This closes the memory integration slice on Linux. The current compiler/corpus
still needs an AArch64 macOS run. The next interpreter work is a transaction
context and journal with explicit commit/revert boundaries, transient-storage
cleanup, and state-access gas/refunds. Full Cancun conformance remains pending.

The approved comparison policy is implemented: portable frame outcomes, gas and
output must agree; completed frames additionally compare stack and active memory.
Only explicitly marked simultaneous faults may differ diagnostically, and both
reasons are retained. Single-fault anchors remain checked. Operational failures
are never converted into EVM exceptional results.

The interpreter draft adopts owned native memory/output, reset and explicit
release, word-rounded expansion, gas charging before allocation, overlap-safe
MCOPY and overflow-safe source zero-fill. GAS uses the remaining frame budget.
State operations that lack transaction-dependent pricing explicitly mark gas
accounting incomplete. Host resource failures remain separate from EVM halts.

## Historical draft checks

- Four Python contract tests pass, including rejection of altered gas, output,
  machine state, unmarked reason differences and operational errors.
- Both Rust adapter tests pass; nightly formatting and strict Clippy pass.
- All 1,729 reference frames satisfy the protocol and independent specification
  anchors: the existing 1,602 frames plus 96 memory and 31 gas cases. See the
  [source identities and reference result](memory-reference-draft.json).

## Historical compiler prerequisite

Fe `bde32240b` spends substantial time and memory in semantic borrow checking on
the new VM. Its workspace check was stopped after 259 seconds. RSS samples were
11,708,144 KiB and 8,044,464 KiB. A CPU sample concentrates in
`BorrowState::invalidate_memory`, structural capability joins and decision-graph
interning. This occurs before native backend compilation. It is a scaling
observation, not proof of nontermination or a complete root-cause attribution.

The [small reproducer](../fixtures/buffer-borrow-scaling/two_buffers.fe) contains
two owned buffers, a writing loop, and a copying loop. It exceeds a 45-second
check timeout. Controls complete: a single-buffer loop in about 0.6 seconds,
two buffers without loops in about 8.6 seconds, and one copying loop with two
buffers in about 12.4 seconds. These are bounded diagnostic runs, not uncontended
performance measurements. [Exact records and hashes](memory-borrow-scaling-draft.json).

```sh
native/out/memory-toolchain/bin/fe check \
  native/fixtures/buffer-borrow-scaling/two_buffers.fe
```

The full sample and logs remain under `native/out/retained/`. The compiler fix is
authorized and in progress in [Fe PR #1585](https://github.com/argotorg/fe/pull/1585).
The published changes reduce enum guard growth across summaries, reuse canonical
values and guards for identity operations, visit control-flow blocks in reverse
postorder, classify overlap without constructing unused intersections, and batch
capability-region unions. Projection before substitution and call-local source
reuse are also published; source reuse invalidates when loan or storage facts
change. Batched availability summaries are published and pass both full compiler
suites; their regression previously processed 33,408 clauses for 256 alternatives.
The complete VM still exceeds the unchanged 600-second frontend limit.

One-traversal guard quantification and batched call-effect regions are also
published. Both full compiler suites pass (3,390 standalone and 3,464 native,
one skipped each), as do strict Clippy checks. Their pre-fix regressions required
99,455 node-interning attempts for a 258-node graph and 67,587 clause-processing
steps for 256 call-effect alternatives. No guard condition or ownership check
is removed.

Per-function profiling shows that `Vm::run` converges in seven sweeps but spends
substantial time resolving call effects and invalidating memory. Another caller
context triggers another analysis. Call-local guard reuse is now published in
standalone `c4856b4fb` and native `bc0b27aa0`: the 256-region regression substitutes
two distinct guards twice instead of 512 times, with unchanged regions and
authority. Full suites pass (3,391 standalone and 3,465 native, one skipped each),
as do strict Clippy checks. The complete VM again times out at the unchanged 600-second limit (600.07
seconds). At 9m24s it had used 8m32s CPU and 3,619,072 KiB RSS. Small controls
all pass; their timings do not establish a full-VM speedup.

A separate minimal probe shows that a plain, non-generic callee receives distinct
semantic instance keys when reached from different callers. Canonicalizing those
keys requires preserving necessary trait assumptions and provider identities;
no instance-construction change has been made. Full VM acceptance remains pending.

Actual VM reuse/failure tests and the full O0/O1/O2 acceptance gate remain pending.
The compiler pin and [last accepted foundation](owned-buffer-foundation.md)
remain unchanged until those checks pass.
