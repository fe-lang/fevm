# SwissTable full-key hash: AArch64 macOS

The full-key XXH64 correction and `u64` hash/probe interface improve distribution
and native lookup cost. They leave the table's 256-entry capacity, sequential
group probing, and tombstone behavior intact. This is a hot-table benchmark,
not a whole-EVM performance result.

## Inputs and method

Measured on Apple M1 Pro / macOS with the historical compiler pinned in
[candidate-toolchain.json](candidate-toolchain.json):
Fe `e923c4a0d97f9fbfea0480a843389f3b025ae5bd`, Sonatina
`8f5f6bccee3fe968fd6a6c4855433e4a84ccbb8f`; compiler SHA-256
`b878f1ea582669b69db859cbf3e7c137626d8bf22eb2ea3772c71913a1825616`.
The table baseline is FeVM `1a41c9609c95c884425c0f7262f9d914c71fcda2`.
The candidate was measured before commit and is now `08491ff`; exact table and
generated-source hashes identify it in the records.

Three trials alternate baseline/candidate order, retaining five samples each
after a discarded warmup. Inputs, setup, individual correctness checks, and I/O
are outside the CPU clock interval. Each runtime lookup result feeds the next
query index, and every batch checksum is checked. Probe counts come from separate
instrumented executables and are checked against a physical model. Table behavior
is independently checked against a Python dictionary. See the
[suite documentation](../swisstable/README.md) for the corpus and protocol.

Concurrent Rust and Lean builds heavily loaded this host (a process sample showed
two rustc processes consuming roughly seven cores between them). These timings
are diagnostic; frequency and contention prevent treating them as stable gates.
Build/relink observations are retained without compiler-speed claims. Linux has
not been executed.

## Selected O2 results

Each timing is the median of 15 CPU nanosecond samples per lookup. All 144 measured
cases are retained, including full and drained tables where probe scans dominate.

| Workload | Baseline ns | Candidate ns | Ratio |
|---|---:|---:|---:|
| Low-limb sequential, 128 entries, fresh hits | 2691.2 | 272.1 | 9.89x |
| Limb 2 sequential, 224 entries, fresh hits | 4715.8 | 353.3 | 13.35x |
| Limb 2 sequential, 224 entries, fresh misses | 6891.6 | 629.3 | 10.95x |
| Limb 3 sequential, 224 entries, fresh hits | 4717.8 | 322.7 | 14.62x |
| Random, 224 entries, fresh hits | 2772.9 | 325.0 | 8.53x |
| Random, 224 entries, fresh misses | 2985.1 | 508.9 | 5.87x |
| Random, filled then drained to 64 entries, misses | 7164.3 | 4755.4 | 1.51x |

For limb-2 keys at 224 entries, mean hit scans fall from **111 to 9.484375**
control bytes, and mean equality checks from **111 to 1.0625**. Mean miss scans
fall from **225 to 25.8125**, with equality checks falling from **224 to 0.0625**.
These counts are deterministic and do not depend on host contention.

The runtime improvement includes both distribution and arithmetic changes.
The old optimized native IR retains `umod <hash> 256.i256` in `search`; the
candidate uses a bounded 64-bit mask. The source change also replaces wide
mixing with four explicit 64-bit input lanes. The experiment does not isolate
XXH64's arithmetic cost from the narrower probe path. This supplies another
concrete compiler workload for future power-of-two strength reduction.

Uninstrumented O2 object text, including the common driver, shrinks from 158,308
to 146,420 bytes (11,888 bytes, 7.5%). At O0 the same objects are about 13 MB,
indicating substantial remaining code-size work in this aggregate-heavy program;
this change makes no attempt to diagnose or fix that compiler behavior.

## Coverage and remaining limits

Six ingot tests pass at O0/O1/O2, including independent xxhsum reference vectors,
each-limb distribution, deliberate same-hash collisions with wraparound, full-table
failure, updates past tombstones, and repeated deletion/reinsertion. The new
distribution regression fails against the old hash. The Python reference was
also compared with installed xxhsum 0.8.3 on 770 keys, including every single bit.

All 167 differential scenarios pass across baseline/candidate, O0/O1/O2, and
ordinary/instrumented builds: **2,004 scenario executions**, **1,059,840 map
operations**, and **173,580 individual queries**, plus checked lookup batches.
These are repeated checks across configurations, not counts of unique inputs.
The runner also verifies relinked objects and refuses nonempty output directories.

The updated native acceptance entrypoint passes all three SwissTable optimization
levels, the full new differential/probe matrix, and all 74,676 existing arithmetic
cases across 48 configurations. Fe formatting, Python compilation, and diff checks
pass. This repository has no Cargo manifest or Rust changes; the requested
`cargo +nightly fmt --all` invocation reports that absence, so Cargo formatting,
Clippy, and nextest do not apply to this Fe/Python-only change.

A temporary ingot containing the exact `ingots/evm/src/state.fe` consumer with a
real path dependency on SwissTable passes its three tests at O2 after the hash
interface cutover. The full FeVM workspace command still fails on the known
missing `std::native::Args/Arg` imports; no full-interpreter acceptance is claimed.

Hashing does not fix tombstone accumulation. Filling and then deleting down to
64 live entries leaves 192 tombstones, so misses still visit **all 256 slots**.
The fresh candidate random-key table at that occupancy averages **4.734375 slots**
per miss. Capacity/growth and reclamation policies remain separate work, as does
hash-flood protection for a deterministic unkeyed hash.

## Records

- [Correctness and probe matrix](macos-arm64-swisstable-checks.json.gz)
- [Alternating timing trials](macos-arm64-swisstable-timing.json.gz)
- [Updated native acceptance](macos-arm64-swisstable-acceptance.json)

These gzip files contain the complete JSON records without dropping histograms
or samples. Decompress with `gzip -dc <file>`. Original sources, corpus, objects,
IR, and assembly remain under `native/out/swisstable-check-2` and
`native/out/swisstable-timing`. Reproduce with the suite commands.

The driver template was formatted after timing; regenerating and formatting it
produces all four measured O2 source files byte-for-byte. The records preserve
the template hash that was present when each run started.

To rerun this compiler, use the pre-migration FeVM harness at `4c7a9b1`.
The current drivers use newer trusted standard-library I/O and timing APIs.
