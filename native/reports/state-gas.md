# Cancun state-access gas and refunds

The state-access gas milestone is accepted on x86_64 Linux with local Fe
`09aed1e8817d0be5a9340dc7d6ad3fd7fec43f50` and published Sonatina
`736c2be7fc7ae2258bb781213e2e6eae1903b6c0`. The exact source hashes, compiler checks
and eight-stage results are in
[the acceptance record](linux-x86_64-state-gas-acceptance.json); rebuild with
[state-gas-toolchain.json](state-gas-toolchain.json).

Transactions now track upfront and runtime account/slot warmness, immutable
original storage values, and signed refund counters. Warm additions and refunds
follow nested checkpoint rollback. SSTORE uses Cancun original/current/new-value
pricing and the 2,300-gas sentry; SLOAD and BALANCE distinguish cold and warm
access, and TLOAD/TSTORE cost 100 gas without the sentry. Account keys use their
low 160 bits.

`Transaction::finish(commit, gas_spent)` returns persistent state, capped refunds
and net gas used. Aborts undo writes and return no refund. Successful settlement
caps positive refunds at one fifth of pre-refund gas spent; refunds never refill
frame execution gas. Access-list setup is permitted only before runtime activity.
Transaction reuse starts fresh access, original-value, transient and refund state.

| Check | Passing coverage |
| --- | --- |
| Workspace | 37 tests at each of O0/O1/O2 |
| CLI and allocator failures | 14 checks at each level |
| Stateless Cancun frames | 1,729 frames at each level |
| Stateful Cancun sequences | 349 cases at each level |
| SwissTable matrix | 2,004 cases across 12 builds |
| Arithmetic matrix | 74,676 checks across 48 builds |
| Reference and contract | 5 Rust tests and 8 Python tests |

The stateful reference uses pinned revm's real journal. Comparisons cover
persistent/current/original and transient storage, account/slot warmness,
signed frame and cumulative refunds, nested commit/revert, transaction abort,
refund caps and net gas. Independent anchors check the reference results.
Host table exhaustion and allocation failure remain operational errors; they
are not converted into consensus halts.

The state driver exposed runtime String `AsBytes` lowering and enum-verifier
scaling blockers. [Fe PR1694](https://github.com/argotorg/fe/pull/1694) and
[Sonatina PR368–PR370](https://github.com/fe-lang/sonatina/pull/370)
(official stack371) fix
those causes. The adopted compiler passes 4,479 Fe tests and 1,816 Sonatina
tests, strict Clippy and formatting, plus 323 Sonatina filechecks and doctests.

This milestone builds on the separately recorded
[transaction journal](transaction-journal.md). Signed transaction envelopes,
intrinsic and access-list intrinsic charges, CALL/CREATE execution, the remaining
opcode families and full Cancun conformance remain separate work. World and
transaction caches retain their explicit 256-entry host limit. This compiler
and state-gas source still need an AArch64 macOS acceptance run.
