# Native arithmetic and acceptance tooling

This suite tests Fe's host-native arithmetic independently of the unfinished
FeVM interpreter integration. It uses the pinned compiler in `toolchain.json`.
The full FeVM CLI and Cancun acceptance remain separate milestones.

## Hosts and prerequisites

Supported execution hosts are **AArch64 macOS** and **x86_64 Linux**. Install Git,
Python 3.10 or newer, Node/npm, Rust via rustup, CMake, and the host C toolchain. On macOS,
use the Xcode command-line tools (`cc`, `size`, `otool`); on Linux install a C
compiler/linker and binutils (`cc`, `size`, `objdump`). Install the exact Rust
version recorded in the manifest. No third-party Python packages are required.

Compiler revisions currently include **local, unpublished commits**. Until they
are published, supply local repositories or Git bundles containing those exact
commits. The bootstrap does not substitute a branch tip or patch compiler sources.

```sh
python3 native/bootstrap.py --out /tmp/fevm-native-toolchain \
  --toolchain 1.98.1 \
  --fe-repository /path/to/fe \
  --sonatina-repository /path/to/sonatina
python3 native/accept.py --build /tmp/fevm-native-toolchain/build.json \
  --out /tmp/fevm-native-acceptance --check-only
```

Choose a fresh output directory for each bootstrap and arithmetic run.
`--target-dir /path/to/cache` can reuse Cargo artifacts while checking out clean
sources; the build record identifies that cache. The finished compiler is copied
to `<out>/bin/fe` so later cache reuse cannot replace it. `--prepare-only` verifies and
materializes the pinned sources without building; it does not produce a compiler.
The build uses `Cargo.lock`, verifies its hash, generates the tree-sitter parser
using npm's lockfile, and records compiler identity, hash, host and build time.
Dependency URL redirection is scoped to the build process, not global Git config.
The compiler's Cargo dependencies still require network access or a populated
Cargo cache. These are reproducible source/dependency inputs, not a promise of
byte-identical executables across different host linkers or SDKs.

The acceptance command checks the compiler hash, runs all SwissTable tests and
the SwissTable/arithmetic differential corpora at O0/O1/O2, and writes JSON plus
per-command logs. An incomplete or failing suite exits nonzero. Run the same
commands on each supported host; an unexecuted platform is not a passing result.
Use `--check-only` on shared CI machines. Full Fe/Sonatina project verification
is additional to this downstream suite.

The [SwissTable suite](swisstable/README.md) compares full-key hashing against
the original table, checks dictionary behavior and native probe counts, and
measures uninstrumented lookups across key distributions, occupancy, and deletion
histories. Acceptance runs its correctness matrix; timing is a separate command.
Its baseline Git revision must be available locally.

## Arithmetic correctness and measurement

```sh
python3 native/arith/run.py --fe /tmp/fevm-native-toolchain/bin/fe \
  --out /tmp/fevm-native-arithmetic
```

The runner generates one standalone Fe executable per operation, representation
and optimization level. It checks addition, wrapping multiplication, unsigned
division/remainder, shifts, comparison and wrapping exponentiation against
Python arbitrary-precision integer results. Boundary cases cross every limb and
include full-width values, overshifts, and large exponents; deterministic random
cases and repeated dependent calculations supplement them. Zero divisors are
excluded from successful-operation vectors; compiler trap tests remain part of
the upstream suite.

The two representations are built-in `u256` and a four-`u64` value struct. The
latter uses limb arithmetic (with `u128` products/carries), restoring division,
and exponentiation by squaring. It is a compiler diagnostic control, not a claim
that a handwritten limb implementation is optimal. Conversion between the wire
format and either representation happens outside the repeated kernel loop.

Inputs arrive at runtime through scalar libc imports. The kernel is kept out of
line and each iteration consumes the preceding result (`a = result XOR seed`),
so the operation cannot be replaced with a compile-time constant. Each batch's
final result is checked against the reference computation. Comparison and some
operand classes can have short recurrence periods; this is not a random-input
throughput benchmark or a complete EVM performance measurement.

Timing uses the host process CPU clock around the kernel, excluding process
startup, parsing and output. A compiled C probe verifies `clock_t` width and
`CLOCKS_PER_SEC`. A warmup batch is discarded, batch size adapts to timer
resolution, and all sample values are retained. CPU time is not wall latency;
CPU frequency, thermal state and other workloads still affect it. Measure on an
idle machine and alternate baseline/candidate runs before claiming a speedup.

Each result records compiler/source hashes, host, correctness case counts,
CPU nanoseconds per dependent iteration, complete build times, separate relink
time, object/executable sizes, and executable-text size. Build time includes
compiler startup, linking and debugging-report emission; it is not an isolated
backend compile measurement. Text size includes the driver as well as the kernel.
The object, emitted IR and disassembly are retained for attribution and review.

Useful selections:

```sh
python3 native/arith/run.py --fe /path/to/fe --out /tmp/div-check \
  --operations div rem --levels 0 2 --check-only
python3 native/arith/run.py --fe /path/to/fe --out /tmp/mul-profile \
  --operations mul --samples 9 --batch-ms 50 --build-samples 5
```

A failure keeps the generated source and available compiler reports. Fix the
root cause; do not remove a failing representation or optimization level from
acceptance to obtain a passing report.

After producing baseline and candidate runs, remeasure their common combinations
in alternating order on the same host:

```sh
python3 native/arith/compare.py --baseline /tmp/baseline/results.json \
  --candidate /tmp/candidate/results.json --out /tmp/comparison
```

The comparison verifies artifact hashes and matching source hashes before running,
retains every trial, and checks all batch results against the same independent
oracle. Start with a focused selection such as `div rem` at O2 when measuring a
specific change. See `reports/` for the recorded local evidence and its limits.


## Linux handoff while compiler commits are unpublished

After committing the tooling and completing a bootstrap, create local Git bundles:

```sh
python3 native/handoff.py --build /tmp/fevm-native-toolchain/build.json \
  --out /tmp/fevm-native-linux-handoff
```

The handoff contains only the three committed histories needed for the pinned
FeVM, Fe and Sonatina revisions, their hashes, and exact Linux instructions.
It does not push branches or claim Linux verification. Transfer the directory
to a Linux runner and return the generated JSON records and logs.
