# Native account-code milestone

Implementation commit: `b9debd9f9b17a5232e0c1b1b3bd6a0d13bd4c710`.

FeVM implements EXTCODESIZE, EXTCODECOPY and EXTCODEHASH with Cancun gas and
shared transaction account warming. Account metadata now records explicit
existence, balance, nonce and cached code hashes in one table. Code lives in a
world-owned byte arena; host initialization copies borrowed input and compacts
replaced records. Allocation or table exhaustion preserves the old account.
World owners must be released after their final transaction.

EXTCODEHASH follows [EIP-1052](https://eips.ethereum.org/EIPS/eip-1052): absent
and [EIP-161 empty](https://eips.ethereum.org/EIPS/eip-161) accounts return zero;
nonempty accounts without code return Keccak of empty bytes. Storage is excluded
from the empty-account predicate. EXTCODECOPY pads beyond the source with zeroes,
preserves full-width source operands, and handles empty copies without narrowing
offsets. [EIP-2929](https://eips.ethereum.org/EIPS/eip-2929) account warmth is shared
with BALANCE and rolls back with failed frames and enclosing checkpoints.

Transaction journal records retain prior account existence, allowing undo to
remove newly created accounts while preserving explicitly present empty ones.
Code initialization is host-only in this milestone. CREATE and SELFDESTRUCT
account lifecycle rules remain pending, as do calls, logs and other unimplemented
opcodes. The account table retains its explicit 256-entry host limit; code storage
is independent of the frame harness's input limit.

## Compiler

This checkpoint requires local Fe `4c03313f1602dbe0cace235e9a32548cc907d551`,
based on master `04d344105` plus corrected PR #1718 head `cfe41afdf`. It repairs a
borrow-checker false positive exposed by reading account code after journal
allocation while writing a fresh frame buffer. The checker now carries the
physical separation obligation that excludes conditional raw-pointer corruption;
concrete aliasing remains rejected. Semantic, recursive native execution and
crash regressions accompany the repair. All 4,488 release compiler tests pass
with all features (one configured skip), along with strict Clippy and nightly
formatting.

The fresh production compiler uses default features plus `cranelift`, Rust
1.98.1 and Sonatina `9c35018759aff07516025684fea0be784b0cf6df`. Its SHA-256 is
`4d4e724e76b86487f05845f9a6368f68e2590743f6cecd0756b73692afa05a28`.
The immutable binary and clean bootstrap sources are under
`native/out/account-code-20261002/toolchain-r2`.

The compiler commit is local. The [milestone manifest](account-code-toolchain.json)
requires a repository or bundle containing that commit:

```sh
python3 native/bootstrap.py --manifest native/reports/account-code-toolchain.json \
  --fe-repository /home/sean/code/fe \
  --out native/out/account-code-rebuild --toolchain 1.98.1
python3 native/accept.py --build native/out/account-code-rebuild/build.json \
  --out native/out/account-code-acceptance --check-only --jobs 1
```

The default `native/toolchain.json` retains the preceding published-master
checkpoint. Keccak remains pinned to public `fe-lang/keccak` commit `7f32a75`.

## Coverage and acceptance

Four new native tests cover code replacement/compaction, low-160-bit aliases,
empty-account hash semantics, 24,576-byte code, table-capacity failures and
existence-aware rollback. A controlled allocator fixture checks two separate
world owners, first/second allocation failure, preservation of old code/hash and
exact release of the watched large arena allocations. State protocol version 3
carries explicit balance, nonce and code fixtures; earlier versions are rejected.

The state corpus adds 354 account-code cases, reaching 737. Cases cover exact
cold/warm gas boundaries, static reads, full-width operands, copy padding and
overwrite, shared access sets, failure rollback and transaction reuse. Independent
reference anchors and all six Rust reference tests pass, with strict Clippy and
nightly formatting. All ten Python harness tests pass. Native state differential
execution matches exactly at O0/O1/O2.

All seven acceptance stages pass on Linux x86_64:

| Check | Result |
| --- | --- |
| Workspace tests | 39 passed at each of O0/O1/O2 |
| CLI and allocator checks | 22 passed at each of O0/O1/O2 |
| Cancun frames | 1,835 passed at each of O0/O1/O2 |
| Cancun state sequences | 737 exact matches at each of O0/O1/O2 |
| Arithmetic | 74,676 checks across 48 builds |

The frame corpus retains the same three declared RETURNDATACOPY simultaneous-fault
reason differences per level. No new discrepancies appeared. All runtime and
harness source hashes were rechecked after acceptance, together with the immutable
compiler hash and clean compiler/Sonatina source revisions.

The [machine-readable record](linux-x86_64-account-code.json) includes per-stage
results, compiler identity, source hashes, reference versions, allocator results
and resource accounting. Workspace logs accompany it. Full artifacts remain under
`native/out/account-code-acceptance-20261002`.

The sequential run took approximately 106 minutes on this shared host
and peaked at 11.37 GiB. Its memory ceiling was raised from
12 to 16 GiB before O2, with zero swap allowance and no memory-limit or OOM events.
This is correctness acceptance, not a runtime performance comparison. Complete
Cancun conformance and current-toolchain macOS acceptance remain outside this
milestone.
