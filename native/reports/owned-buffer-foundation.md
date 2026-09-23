# Owned-buffer and memory-cost foundation

Status: **PASS on AArch64 macOS** for all seven native acceptance stages, the
memory-cost unit tests, and a reusable owned-buffer frame probe. The interpreter
still uses its existing fixed memory and output arrays; this checkpoint supplies
the compiler and range calculations for replacing them.

## Compiler and sources

- Fe: `bde32240b93090d15b7139bab05e8ec660035882`, published on `argotorg/fe:fevm-native-memory-integration`.
- Sonatina: `5374ab32a35d41a39ca82c138797ab9b033caf80`, published on `sbillig/sonatina:fevm-native-enum-integration`.
- [Saved compiler manifest](memory-toolchain.json); Rust 1.98.1, `cranelift`.
- Compiler SHA-256: `0fac504b3e7aa043323e924a969e646d344ad3d7f617111ac06b3fb37b552c82`.
- Host: Apple M1 Pro, AArch64 macOS 15.6.1.

Fresh exact-revision checkouts and locked dependencies produced the immutable
compiler. Its build reused the retained Cargo cache but copied the finished
executable outside that cache. The integration includes native memory copying,
enum layout, owned `ByteBuffer`, string escapes, and shared field receivers.
Their review branches remain separate:
[Fe #1579](https://github.com/argotorg/fe/pull/1579),
[Sonatina #328](https://github.com/fe-lang/sonatina/pull/328),
[Fe #1580](https://github.com/argotorg/fe/pull/1580),
[Fe #1563](https://github.com/argotorg/fe/pull/1563), and
[Fe #1581](https://github.com/argotorg/fe/pull/1581).

The field-receiver fix passes the complete standalone Fe suite (3,381 passed,
one skip). The combined native compiler passes its complete suite (3,448 passed,
one skip). Both pass strict Clippy and nightly formatting. Shared calls borrow
the original projected storage before an ownership transfer can occur; explicit
moves and conflicting mutable access retain their checks.

FeVM was based on `a078672e4d17611b40000692aba49dd34dd831c3` during acceptance,
with the memory module and reusable-buffer fixture uncommitted. The frame record
includes the new module's source hash; all recorded source hashes were checked
again after acceptance. The reference revision, corpus, and comparison contract
are unchanged from the [previous checkpoint](cancun-frames.md).

## Results

| Check | Result |
| --- | --- |
| FeVM workspace | 16 passed at each of O0/O1/O2, including four memory-cost tests |
| CLI smoke | 10 passed at each of O0/O1/O2 |
| Existing Cancun frame corpus | 1,602 passed at each of O0/O1/O2 |
| SwissTable matrix | 2,004 scenarios across 12 builds passed |
| Arithmetic matrix | 74,676 cases across 48 builds passed |
| Separate owned-buffer frame probe | Built and exited successfully at O0/O1/O2 |

The new [memory module](../../ingots/evm/src/memory.fe) computes word-rounded
extents, incremental quadratic expansion costs and copy-word charges without
allocating. Empty ranges ignore their offsets. Nonempty ranges reject extents
proven unpayable with a `u64` gas budget before narrowing EVM words. MCOPY planning
combines both ranges. Tests include word/quadratic boundaries, maximal offsets,
and the exact largest expansion and copy charges that fit `u64`.

The separate [frame probe](../fixtures/owned_buffer_frame.fe) grows memory to
9,000 bytes, resets and reuses capacity, checks regrowth zeroing, transfers output
ownership, and explicitly releases buffers. Its recorded source hash matches
the published fixture. It is additional evidence, not an eighth acceptance stage.

## Evidence and reproduction

- [Acceptance and compiler provenance](macos-arm64-memory-acceptance.json).
- [Frame results and source hashes](macos-arm64-memory-frames.json).
- [CLI results](macos-arm64-memory-cli.json).
- [Arithmetic results](macos-arm64-memory-arithmetic.json).
- [SwissTable results](macos-arm64-memory-swisstable.json.gz), deterministic gzip.
- [Owned-buffer frame results](macos-arm64-memory-frame-owner.json).
- Workspace logs: [O0](macos-arm64-memory-workspace-O0.log), [O1](macos-arm64-memory-workspace-O1.log), [O2](macos-arm64-memory-workspace-O2.log).

```sh
python3 native/bootstrap.py --out native/out/memory-toolchain \
  --manifest native/reports/memory-toolchain.json
python3 native/accept.py --build native/out/memory-toolchain/build.json \
  --out native/out/memory-foundation-acceptance --check-only
```

Use fresh output directories for a repeat run. The original generated artifacts
remain under `native/out/memory-foundation-acceptance/`. Timing was omitted;
these results make no throughput claim. The retained owned-bytes Cargo cache
remains at `/Users/sean/code/fe/fevm-native-owned-bytes/target`.

## Remaining work

Wire owned buffers and charging into the VM, make active memory and gas observable,
and expand the memory differential corpus. Existing memory/range defects are
not resolved by adding the unused planning module. The expanded corpus also needs
an explicit contract for simultaneous exceptional faults: the reference and
execution specification can report different diagnostic reasons for the same
exceptional outcome. Existing comparisons have not been relaxed.

Compiler reference-descriptor reclamation remains a separate prerequisite for
resident memory-lifetime claims. The new compiler and expanded gate still need
Linux execution; the [older Linux baseline](linux-baseline-2026-09-22/README.md)
does not cover this checkpoint.
