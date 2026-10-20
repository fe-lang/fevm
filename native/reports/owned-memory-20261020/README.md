# Owned memory on Fe `999ff9562`

FeVM `7ad8b0e` ports the interpreter to Fe's owned-value destruction and
core memory owners, built with Fe [`999ff9562`](https://github.com/sbillig/fe/tree/999ff9562353ab381f7cafe389f7e86499ade918)
(branch `feat/owned-value-destruction`, on Fe master `c33d070d6`; Sonatina
`30e45b25`) with `--features cranelift` on x86_64 Linux ([build record](linux-build.json)).

- Every owner frees its memory where its lifetime ends. The 15 `release` methods
  and all 272 `.release()` calls are gone, as are `Vm::run_owned` and
  `TransactionResult::into_state`.
- `core::MemBuffer` and `core::MemVec` replace `std::native::ByteBuffer` and
  `FixedStack`. Frames live on a growable `MemVec<Frame>`; the journal, log
  entries, blob hashes and access lists are typed vectors instead of hand-packed
  byte records; memory copies go through slices (`copy_from`, `copy_within`,
  `zero`), and MLOAD/MSTORE use word reads and writes.
- [SwissTable](https://github.com/fe-lang/swisstable) `ba7c923` grows over owned
  arrays, so the state tables have no 256-entry limit and `ERR_STATE_LIMIT` is gone.
- MODEXP limbs are allocated for each modulus, so any affordable modulus is
  evaluated and `ERR_UNSUPPORTED_PRECOMPILE` is gone.
- [Keccak](https://github.com/fe-lang/keccak) `2b80ec9` reads `MemBuffer` and
  `MemSpan` sources.

The runs below used `7ad8b0e`'s sources before it was committed. The only
difference is that the dependency manifests named the same Keccak and SwissTable
commits by local path; the frame and state records' 62 other source hashes match.

## Acceptance

All seven stages pass on x86_64 Linux
([acceptance.json](linux-acceptance/acceptance.json)): 76 workspace tests, 35
CLI/allocator checks, 1,840 frame and 1,142 state comparisons at each of
O0/O1/O2, and 74,676 arithmetic checks. Frames keep the three declared
simultaneous-fault reason differences per level. The Python harness's 13 tests,
the Rust reference's nine tests and the four reduced O1 probes (`checkpoints`,
`inputs`, `calls`, `vm_inputs`) also pass. This compiler has not run on AArch64
macOS.

## Cancun conformance

All 16,847 Cancun state tests of
[execution-spec-tests v5.4.0](https://github.com/ethereum/execution-spec-tests/releases/tag/v5.4.0)
(`fixtures_stable.tar.gz`, SHA-256 `92cf1b47…`) pass with an O2 driver
([results](linux-conformance-results.json)). That includes the 47 cases that
used to stop with a host status because they exceeded the 256-entry state tables.

With eight parallel cases the run took 24 s; the summed case time was 193 s and
the slowest case was `ContractCreationSpam` at 13 s. The
[bulk-copy run](../bulk-copy-20261019/README.md) on the same host took 46 s and
363 s, but host load was not controlled for either run, so this is not a
measured speedup.

## Resident memory

`native/soak` runs Cancun transactions that expand a caller's and a callee's
memory, emit a log, set and clear a slot and return data, all in one process.
Peak RSS was 13.7 MB after 1,000 transactions and 14.0 MB after 40,000
([results](soak-results.json)). Counting allocations through `LD_PRELOAD`, 1,000
transactions made 64,019 allocations and 64,018 frees; the survivor, 96 bytes,
is independent of the transaction count. The transaction path therefore reaches
none of the compiler-internal native allocations that are never freed.

## Compiler fixes found by this port

- Runtime drops were looked up by the checked body's statement ids, but runtime
  code is lowered from the constant-folded body, whose statements are
  renumbered; a drop could destroy another's value (a double free in
  `transact_charges_fees_and_rejects_bad_nonces`). Fixed in Fe `a77de3760`.
- Native `read_word`/`write_word` used the target's little-endian order instead
  of the documented big-endian one. Fixed in Fe `999ff9562` with
  `core::num::{to_be, from_be}`.
