# Native arithmetic evidence: AArch64 macOS

Measured on an Apple M1 Pro with macOS 15.6.1 and Apple Clang 17.0.0.
These are diagnostic microbenchmarks collected during concurrent compiler and
Lean workloads. They establish the benefit of specific division paths, not EVM
throughput or competitiveness with production implementations. Linux has not run.

## Revisions and verification

The baseline source matches Fe `1750a181810cb503aee1ff471edf3eeb2f9e1427`,
using Sonatina `6592ff4c8bf3559d5a7e3ec83f26cb0caa69a0da`.
The candidate source matches Fe `e923c4a0d97f9fbfea0480a843389f3b025ae5bd`,
using Sonatina `8f5f6bccee3fe968fd6a6c4855433e4a84ccbb8f`.
Both binaries were built while their pin changes were uncommitted, so their
embedded version strings identify the parent commits. The JSON records retain
those literal strings and binary hashes. The harness was also uncommitted during
measurement; generated source hashes identify the exact matched inputs.
Both measured compilers came from release all-feature workspace test builds with
Rust 1.98.1. `baseline-toolchain.json` pins the baseline source and lockfile for
the bootstrap; the candidate uses `../toolchain.json`.

The baseline includes the separately verified aggregate loop-lifetime fix, which
allows the value-only four-limb division control to compile while continuing to
reject references that survive reuse of their stack storage.

- Both Fe integrations passed the full all-feature release suite: 2,849 tests,
  one skipped; strict workspace Clippy and nightly formatting passed.
- Sonatina lifetime fix: 1,493 tests passed, one skipped; 296 filechecks.
- Sonatina division optimization: 1,494 tests passed, one skipped; 296 filechecks.
  Strict workspace Clippy and nightly formatting passed for both commits.
- The complete baseline matrix passes 74,676 differential cases across 48
  operation/representation/optimization combinations. The candidate division
  run passes the same 1,421 cases per operation before timing.
- The final clean-source bootstrap passes all 74,676 arithmetic cases and all
  three SwissTable tests at O0/O1/O2. Its embedded version is `e923c4a0d`.
  Stale reports, a mismatched compiler hash, and comparison source mismatches
  were also checked to fail without replacing a completed acceptance record.

## Alternating comparison

Three trials alternate baseline/candidate order. Each trial discards a warmup
and retains seven CPU-time samples per operand class. Every batch result is
checked against Python arbitrary-precision arithmetic. The table gives medians
over the 21 retained samples, in CPU nanoseconds per dependent operation/XOR
iteration at O2. Operand labels describe initial inputs; subsequent inputs follow
the recurrence documented in the suite README.

| Operation / initial operands | Baseline ns | Candidate ns | Ratio |
|---|---:|---:|---:|
| Division, wide / wide | 2340.1 | 2343.0 | 1.00x |
| Division, wide / 7 | 2342.0 | 2341.6 | 1.00x |
| Division, both fit u64 | 2335.8 | 7.94 | 294x |
| Division, numerator smaller | 2340.2 | 6.74 | 347x |
| Remainder, wide / wide | 2338.6 | 2330.0 | 1.00x |
| Remainder, wide / 7 | 2338.9 | 2344.1 | 1.00x |
| Remainder, both fit u64 | 2341.6 | 9.02 | 260x |
| Remainder, numerator smaller | 2336.4 | 6.96 | 336x |

The generated AArch64 scalar path contains `udiv` and `msub`. The general
restoring divider is unchanged. The entire division/remainder object's text,
including the common driver, grows from 5,368 to 5,628 bytes (+260, 4.8%).
Signed i128/i256 boundary matrices are covered by upstream tests, including
minimum values and overflow; the Fe timing corpus is unsigned u256.

Raw build and relink times are retained, but changing host contention prevents
a credible compiler-time speedup claim. Process CPU timing also remains sensitive
to CPU frequency and thermal state. Rerun on an idle host before setting gates.

## Further work supported by the evidence

The built-in O2 addition, multiplication, shifts and comparison outperform this
four-u64 diagnostic control. Final multiplication assembly already drops the
unused high product: it contains ten low multiplications and six high halves.
No multiplication change was justified by the source-level full-product concern.

Wide numerators with small divisors still use the slow general divider. A measured
short-divisor algorithm is the next arithmetic candidate. Register/ABI changes
should wait for profiles of meaningful interpreter kernels. Neither production
EVM comparisons nor whole-interpreter performance conclusions follow from this suite.

## Raw records and reproduction

- `macos-arm64-baseline.json`: complete 48-combination baseline and all samples.
- `macos-arm64-division-candidate.json`: candidate build, size and runtime data.
- `macos-arm64-division-comparison.json`: alternating trials and summary values.
- `macos-arm64-acceptance.json`: final bootstrap provenance and acceptance status.
- `macos-arm64-acceptance-arithmetic.json`: all final compiler correctness results.

Original generated sources, objects, IR and assembly remain under
`/private/tmp/fevm-native-lifetime-matrix` and
`/private/tmp/fevm-native-division-candidate-final` on the development machine.
Recreate them with `arith/run.py` using the respective pinned compilers, then run
`arith/compare.py` against their retained `results.json` files. The acceptance
record from the final clean-source bootstrap is separate from these measurements.
