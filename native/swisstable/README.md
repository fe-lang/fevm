# SwissTable hashing and probes

`hash_u256` implements XXH64 with seed zero over exactly 32 little-endian bytes.
The numeric key's least significant limb is the first input lane. The Fe
implementation specializes the [XXH64 specification][spec] to that fixed length;
it does not allocate or serialize a byte buffer. `SwissKey.hash` returns `u64`.
Equal keys must hash equally, and a custom implementation should mix all key bits.
The table still selects its initial 16-slot group from bits 4–7 and its seven-bit
fingerprint from bits 8–14. Equality resolves fingerprint collisions.

The previous mixer multiplied a whole `u256` and shifted by small amounts. High
limbs did not reach the bits consumed by the table: varying limb 2 or 3 produced
identical initial groups and fingerprints. Narrowing before mixing would discard
those limbs; the new hash consumes all four lanes before its final avalanche.

This deterministic, non-cryptographic hash does not provide hash-flood protection.
The table remains a scalar, fixed-capacity prototype with 256 entries. It has no
growth or tombstone cleanup policy. Deletion preserves probe chains, but a table
with no empty control bytes must scan all 256 slots on a miss even after most
entries have been removed. Production state storage needs those policies and an
explicit threat model before this table can be considered production ready.

[spec]: https://github.com/Cyan4973/xxHash/blob/v0.8.3/doc/xxhash_spec.md

## Reproduce

Use the compiler produced by `../bootstrap.py`. The baseline Git object must be
available locally (default `1a41c9609c95c884425c0f7262f9d914c71fcda2`).

```sh
python3 native/swisstable/run.py --fe /path/to/pinned/fe \
  --out /tmp/swisstable-check --check-only
python3 native/swisstable/run.py --fe /path/to/pinned/fe \
  --out /tmp/swisstable-timing --levels 2
```

Use a fresh output directory. The first command checks O0/O1/O2. The second runs
alternating baseline/candidate timing trials at O2; it still checks every scenario
before measuring. Baseline and candidate table sources, generated executables,
objects, IR, assembly, the complete input corpus, host/compiler identities, hashes,
build/relink times, and code sizes are retained. Build times include report emission
and linking, and are single diagnostic observations. Text size includes the driver.

The runner generates standalone roots from exact table source snapshots. Ingot
tests are also run through the actual workspace/dependency path by `../accept.py`.
The generated roots give the diagnostic executable access to private table fields
without adding counters or diagnostic methods to the production API.

## What is checked and measured

- Six key families: sequential values in each of the four limbs, repeated limbs,
  and deterministic random full-width keys.
- Occupancies of 64, 128, 224, and 256 entries. Each is tested fresh, after three
  complete replacement cycles, and after filling to capacity and deleting down
  to the requested occupancy. Hits and misses are measured separately.
- Dictionary-oracle traces include capacity failures, existing-key updates,
  unsuccessful removals, and 2,048 mixed operations. Runtime hash checks cover
  every single bit, complemented bit, adjacent pair, and random full-width keys.
- Separate diagnostic builds count actual visited groups, inspected control
  bytes, and equality checks for every operation and query. Every count is
  compared with an independent physical-table model. Histograms, means, p95,
  maxima, and retained tombstone counts are recorded.

Timed executables have no probe instrumentation. Runtime keys and values arrive
through stdin; setup, individual correctness queries, and output are outside the
CPU clock interval. Each lookup result influences the next query index, and a
checksum covers the returned values and presence bits. Even-valued inputs make
the traversal visit every query in order; every batch checksum is checked.
Each process discards a warmup batch. Baseline/candidate order alternates across
trials, and all sample values are retained. These are hot-table lookup costs,
including hashing and loop overhead, not whole-EVM throughput or insertion timings.

Run on an idle machine: CPU clocks exclude descheduling, but frequency, thermal
state, and other workloads still affect results. Linux execution requires a Linux
runner; a macOS result does not establish cross-platform acceptance.
