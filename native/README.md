# Native FeVM and arithmetic acceptance tooling

This suite checks the native FeVM workspace and CLI, Cancun frame results,
and arithmetic differential kernels. Select the compiler manifest for the
milestone being verified.
CLI smoke coverage is not Cancun conformance; gas and opcode semantics remain
separate interpreter milestones.

The [state-gas checkpoint](reports/state-gas.md) passes all eight stages on
x86_64 Linux: 37 workspace tests, 14 CLI/allocator checks, 1,729 Cancun frames
and 349 stateful sequences at each of O0/O1/O2, plus arithmetic and SwissTable
matrices. It adds Cancun warm/cold access, original storage and signed refunds
to the accepted [transaction journal](reports/transaction-journal.md).
That historical checkpoint retains its own compiler pin. The current pin and
expanded corpus still need an AArch64 macOS acceptance run.
The earlier [1,602-frame evidence](reports/cancun-frames.md) is explicitly scoped
to its historical FeVM revisions and compiler pin.

The preceding [Keccak integration](reports/keccak-integration.md) passes all seven
stages on published Fe master: 35 workspace tests, 16 CLI checks, 1,835 frames
and 383 state sequences at O0/O1/O2, plus the arithmetic matrix. Keccak and
SwissTable now own their standalone test suites in their respective repositories.

The earlier [owned-memory checkpoint](reports/memory-integration-draft.md) and
[owned-buffer foundation](reports/owned-buffer-foundation.md) retain their own
compiler manifests and historical platform evidence.

The [account-code milestone](reports/account-code.md) passes all seven stages on
local Fe `4c03313f1`: 39 workspace tests, 22 CLI/allocator checks, 1,835 frames
and 737 state sequences at O0/O1/O2, plus 74,676 arithmetic checks.

## Hosts and prerequisites

Supported execution hosts are **AArch64 macOS** and **x86_64 Linux**. Install Git,
Python 3.10 or newer, Node/npm, Rust via rustup, CMake, and the host C toolchain. On macOS,
use the Xcode command-line tools (`cc`, `size`, `otool`); on Linux install a C
compiler/linker and binutils (`cc`, `size`, `objdump`). Install the exact Rust
version recorded in the manifest. No third-party Python packages are required.

The current compiler is upstream Fe master
[`f69b911ce544c4fe72b2481adcafabf1d967a278`](https://github.com/argotorg/fe/tree/f69b911ce544c4fe72b2481adcafabf1d967a278).
Its Cargo.lock pins Sonatina `6bef907f7e5854d0c77cf18624b7042213526960`. Master
includes MVS, native `FixedStack` and the FeVM compile-time work previously pinned
from forks (enum-proof indexes, borrowed native layouts and one shared native test
runtime per ingot). It uses Rust 1.99.0; the default [`toolchain.json`](toolchain.json)
records the exact revisions and lock hash, and bootstrap fetches both from their
upstream repositories.

All seven native acceptance stages pass on x86_64 Linux: 47 workspace tests,
35 CLI/allocator checks, 1,840 frame comparisons and 1,142 state comparisons at
each of O0/O1/O2, plus 74,676 arithmetic checks. Frames retain the three declared
simultaneous-fault reason differences per level. The Python harness's 13 tests and
the Rust reference's nine tests pass. See the
[Fe master acceptance report](reports/fe-master-20261019/README.md).

The earlier [initialization-join repair](reports/mvs-compile-perf-20261015/README.md),
[enum-proof repair](reports/mvs-compile-perf-20261014/README.md),
[MVS refresh](reports/mvs-refresh-20261014/README.md) and
[MVS port](reports/mvs-port-20261012/README.md) retain their historical compilers,
measurements and publication evidence.

Earlier [owned-input results](reports/owned-inputs.md), the
[logs/BLOBHASH report](reports/logs-blobhash.md), and the
[#1718 integration](reports/keccak-pr1718.md) retain their own historical compiler
manifests and verification scope. They do not establish MVS acceptance. Keccak's
standalone differential and timing suite lives in
[fe-lang/keccak](https://github.com/fe-lang/keccak); FeVM does not use the
experimental compiler barrier required by that benchmark.

Bootstrap verifies exact commits and builds their committed sources. Native
acceptance defaults to one test suite at a time (`--jobs` overrides it), because
preparing the optimized interpreter tests can use substantial memory.

```sh
python3 native/bootstrap.py --out native/out/toolchain --toolchain 1.99.0
python3 native/accept.py --build native/out/toolchain/build.json \
  --out native/out/acceptance --check-only
```

For slower compiler candidates, `--build-timeout SECONDS` overrides each CLI/frame/state
Fe build deadline, and `--stage-timeout SECONDS` overrides the deadline for a complete
acceptance stage. Reports record both settings; a timeout still fails acceptance.
Standalone CLI and differential runners also accept `--build-timeout`.

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

The acceptance command checks the compiler hash, runs every workspace test,
CLI smoke cases, and the Cancun frame/state and arithmetic corpora
at O0/O1/O2. State cases compare refunds and checkpoint/transaction boundaries
against revm's real journal.
Both frame and state runners build their reference with the bootstrap record's
Rust version and an explicit output directory. Their reports record the selected
toolchain, Rust/Cargo versions and reference target directory.
It writes JSON plus per-command logs. CLI checks cover arguments, parsing, basic
execution, calldata return, and exit status; they retain build/link times and
artifact sizes. An incomplete or failing suite exits nonzero. Run the same
commands on each supported host; an unexecuted platform is not a passing result.
Use `--check-only` on shared CI machines. Full Fe/Sonatina project verification
is additional to this downstream suite.

## Reduced O1 development check

The checkpoint probe compiles the real transaction, journal, state and log modules
with a small entry point, then checks nested log commit/rollback and receipt
ownership. It avoids compiling the full interpreter and differential drivers.

```sh
python3 native/perf/run.py --probe checkpoints --fe /path/to/fe \
  --out native/out/checkpoints-o1
python3 native/perf/run.py --probe inputs --fe /path/to/fe \
  --out native/out/inputs-o1
python3 native/perf/run.py --probe vm_inputs --fe /path/to/fe \
  --out native/out/vm-inputs-o1
```

Each run requires a fresh output directory and records source/compiler hashes,
one-thread O1 build wall/CPU time, peak RSS and checked execution output. The
default build deadline is 180 seconds (`--build-timeout` overrides it). Use CPU
time for shared-host comparisons and compare identical source hashes. This probe
does not establish full interpreter conformance or an end-to-end speedup.

The input probe compiles only the real code/input types and hex parser. It checks
50,000-byte inputs, copy ownership, PUSH/jump boundaries, malformed hex, and
allocation/release behavior when code or jump-map allocation fails. Its controlled
allocator is relinked against the same native object, avoiding another Fe build.

`--probe vm_inputs` compiles the VM production modules and calls three owned-input
integration tests. They pass at O1 with the current development compiler: reusable
9,001-byte calldata, failed inputs before checkpointing, and large code with valid
and invalid jump boundaries. The build took 174.09 seconds and peaked at 2.42 GB RSS
on x86_64 Linux. This focused result does not establish full VM acceptance; the
whole-ingot suite and CLI/differential matrices remain deferred.

The [Cancun frame suite](differential/README.md) compares 1,840 deterministic
frames against a pinned revm interpreter. It checks outcomes, remaining gas,
output, and completed stacks and active memory, covering arithmetic operand
roles, PUSH padding, jump destinations, stack limits, and memory/copy boundaries.
The additional 1,142-case state suite checks current/original/transient storage,
account code and hashes, copy semantics, account/slot warmness, signed refunds,
logs, blob hashes and nested checkpoints. Signed transaction
envelopes, intrinsic charges and CALL/CREATE opcodes remain separate work.

SwissTable unit tests, differential checks, and benchmarks live in the
[standalone library repository](https://github.com/fe-lang/swisstable/tree/main/native).
FeVM workspace tests exercise its pinned git dependency through interpreter and
transaction behavior.

## Arithmetic correctness and measurement

```sh
python3 native/arith/run.py --fe native/out/toolchain/bin/fe \
  --out native/out/arithmetic
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

Inputs arrive at runtime through the trusted `std::io` host capabilities. The kernel is kept out of
line and each iteration consumes the preceding result (`a = result XOR seed`),
so the operation cannot be replaced with a compile-time constant. Each batch's
final result is checked against the reference computation. Comparison and some
operand classes can have short recurrence periods; this is not a random-input
throughput benchmark or a complete EVM performance measurement.

Timing uses `std::native::cpu_clock_ticks()` around the kernel, excluding process
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
python3 native/arith/run.py --fe /path/to/fe --out native/out/div-check \
  --operations div rem --levels 0 2 --check-only
python3 native/arith/run.py --fe /path/to/fe --out native/out/mul-profile \
  --operations mul --samples 9 --batch-ms 50 --build-samples 5
```

A failure keeps the generated source and available compiler reports. Fix the
root cause; do not remove a failing representation or optimization level from
acceptance to obtain a passing report.

After producing baseline and candidate runs, remeasure their common combinations
in alternating order on the same host:

```sh
python3 native/arith/compare.py --baseline native/out/baseline/results.json \
  --candidate native/out/candidate/results.json --out native/out/comparison
```

The comparison verifies artifact hashes and matching source hashes before running,
retains every trial, and checks all batch results against the same independent
oracle. Start with a focused selection such as `div rem` at O2 when measuring a
specific change. See `reports/` for the recorded local evidence and its limits.


## Offline Linux handoff

For a runner without repository access, create local Git bundles after completing
a bootstrap:

```sh
python3 native/handoff.py --build native/out/toolchain/build.json \
  --out native/out/linux-handoff
```

The handoff contains only the three committed histories needed for the pinned
FeVM, Fe and Sonatina revisions, their hashes, and exact Linux instructions.
It does not push branches or claim Linux verification. Transfer the directory
to a Linux runner and return the generated JSON records and logs.
