# Transaction journal — Linux checkpoint

The transaction lifecycle passes the complete native acceptance suite on
x86_64 Linux using local Fe `2d39de82dc981d52ff02a184a0f4eefa47b208e8` and
published Sonatina `f8a9fe5ab832b718dbef57309c88c4290dd66232`. The compiler's
local branch is `integrate/fevm-transactions-20261001`; the exact integration
inputs are recorded in [its manifest](transaction-toolchain.json).

Transactions own persistent state and a growable undo journal. Frame success
commits a checkpoint; REVERT, exceptional halts and operational failures roll it
back. A committed child remains reversible by its parent. Transient storage is
shared across frames and discarded when the transaction finishes. Static mode
is inherited and call depth is bounded at 1,024. Journal allocation failure
leaves the write unapplied; undo never allocates.

The [acceptance record](linux-x86_64-transaction-acceptance.json) retains source
hashes, the clean bootstrap identity, command results and corpus identities:

- 27 workspace tests and 14 CLI/allocator checks at each of O0/O1/O2.
- 1,729 Cancun frames per level, with the three previously declared simultaneous
  fault diagnostic differences retained.
- 2,004 SwissTable cases across 12 builds and 74,676 arithmetic checks across
  48 builds.
- All 4,478 compiler release/all-feature tests passed, one skipped. Strict
  Clippy and nightly formatting passed for the compiler and Rust reference.
- Four Python contract tests and both Rust reference tests passed.

The compiler adds input separation, call-effect precision and recursive buffer
summary fixes in Fe PRs #1681, #1683, #1685, #1686, #1687, #1689 and #1693 on top
of the previously accepted performance integration. The integration itself is
local; bootstrap it from a checkout or bundle as described in the
[native instructions](../README.md).

The depth regression executes all 1,024 checkpoints on the normal 8 MiB host
stack. Its one-time VM probe stays outside recursive activations; the O0
recursive frame is 192 bytes. The allocator fixture forces journal growth to
fail and checks prior undo entries, later reuse, rollback and exact release.

This accepts the journal milestone on Linux. State-access gas and refunds,
CALL/CREATE opcodes, full Cancun conformance, and an AArch64 macOS run of this
pin remain pending. The existing 256-entry state-table capacity is an explicit
host resource limit, not an EVM consensus limit. Gate timings on a shared host
are not performance measurements.
