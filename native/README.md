# Native tooling

Build the pinned compiler, then run acceptance, the state tests and the other
checks against it.

## Hosts and prerequisites

Native hosts are **AArch64 macOS** and **x86_64 Linux**. Install Git, Python
3.10 or newer, Node/npm, Rust via rustup, CMake and the host C toolchain (the
Xcode command-line tools on macOS; a C compiler and binutils on Linux). Install
the Rust version recorded in the manifest. No third-party Python packages are
needed.

## Compiler

[`toolchain.json`](toolchain.json) pins Fe master
[`6ccb3ca8e`](https://github.com/argotorg/fe/tree/6ccb3ca8e9ee95d255f86954980aa2e56e09acd9)
([argotorg/fe#1992](https://github.com/argotorg/fe/pull/1992)), its
Cargo.lock's Sonatina revision and hash, and Rust 1.99.0.

```sh
python3 native/bootstrap.py --out native/out/toolchain --toolchain 1.99.0
```

Bootstrap checks out the exact commits, verifies the lock hash, generates the
tree-sitter parser from npm's lockfile, builds the compiler and records its
identity, hash, host and build time in `<out>/build.json`. The compiler is
copied to `<out>/bin/fe`. Use a fresh output directory each time;
`--target-dir` reuses Cargo artifacts, and `--prepare-only` materializes the
sources without building. Cargo dependencies need network access or a
populated cache.

## Tools

`native/tools` holds fevm's checks written in Fe, as subcommands of one program
that runs from the repository's root:

```sh
native/out/toolchain/bin/fe build . --ingot fevm_tools --backend native -O 2 \
  --emit executable --out-dir native/out/tools
```

## Acceptance

```sh
native/out/tools/fevm_tools accept --build native/out/toolchain/build.json \
  --out native/out/acceptance --check-only
```

Acceptance checks the compiler hash and runs nine stages:

1. `workspace-O0`, `workspace-O1`, `workspace-O2`: every workspace test.
2. `cli-smoke`: CLI arguments, parsing, execution, return data and exit
   statuses, plus allocation-failure fixtures that relink the interpreter
   object against a controlled allocator (`fixtures/vm_allocator.c`).
3. `osaka-frames`: 1,845 frames against revm ([differential](differential/README.md)).
4. `osaka-state`: 1,149 transaction and checkpoint sequences against revm's
   journal.
5. `tools`: [`fevm_tools`](tools) builds.
6. `session`: the [Rust client](client/README.md)'s tests against `fevm serve`.
7. `arithmetic`: the compiler arithmetic matrix (below).

It writes JSON and per-command logs, and exits nonzero if any stage fails.
`--jobs` runs test suites concurrently (the default is one, since optimized
interpreter tests use substantial memory); `--build-timeout` and
`--stage-timeout` override the deadlines. Use `--check-only` on shared
machines, which skips timing measurements. Run it on each host: an unexecuted
platform is not a passing result.

[CI](../.github/workflows/ci.yml) runs acceptance and the state tests on both
hosts for every pull request and push to `main`.

## State tests

The [state-test runner](conformance/README.md) runs execution-spec-tests
Osaka and Amsterdam state tests through `transact`. It is not part of
acceptance.

## Resident memory

`native/soak` runs repeated Osaka transactions against one world in one
process. Each expands a caller's and a callee's memory, emits a log, sets and
clears a storage slot and returns data. Peak RSS must stay flat: the runner
fails if it grows by more than 1 MiB between 1,000 and 40,000 transactions.

```sh
native/out/tools/fevm_tools soak --fe native/out/toolchain/bin/fe --out native/out/soak
```

## Arithmetic

```sh
python3 native/arith/run.py --fe native/out/toolchain/bin/fe \
  --out native/out/arithmetic
```

The runner checks the compiler's 256-bit arithmetic: one standalone Fe
executable per operation, representation and optimization level, against
Python's arbitrary-precision results. Operations are addition, wrapping
multiplication, unsigned division and remainder, shifts, comparison and
wrapping exponentiation, with boundary cases across every limb and
deterministic random cases. The representations are built-in `u256` and a
four-`u64` struct with limb arithmetic, a control for the compiler rather than
an optimal implementation.

Without `--check-only` it also times each kernel with
`std::native::cpu_clock_ticks()`, keeping every sample, build times and
artifact sizes. `--operations` and `--levels` select a subset, and
`arith/compare.py` remeasures a baseline and a candidate in alternating order:

```sh
python3 native/arith/compare.py --baseline native/out/baseline/results.json \
  --candidate native/out/candidate/results.json --out native/out/comparison
```

Measure on an idle machine. A failure keeps the generated source and compiler
reports; fix the root cause rather than dropping a representation or level.
