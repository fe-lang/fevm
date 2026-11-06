# State-test benchmarks

`run.py` times FeVM, revm and, optionally, evmone on the transactions of
state-test benchmark fixtures, such as
[ipsilon/evm-benchmarks](https://github.com/ipsilon/evm-benchmarks) (evmone's
suite): snailtracer, blake2b, sha1, weierstrudel, swap_math and
structarray_alloc, plus micro-benchmarks for jumps, memory growth and
SIGNEXTEND.

```sh
git clone https://github.com/ipsilon/evm-benchmarks
python3 native/bench/run.py --fe native/out/toolchain/bin/fe --benchmarks evm-benchmarks/benchmarks
```

Each engine runs one case in the binary format of FeVM's conformance driver
(see `encode` in `run.py`) and takes the same arguments: `RUNS
[TRANSACT]` decodes the case and builds its pre-state RUNS more times,
applying the transaction to each one unless TRANSACT is 0, then applies it once
more and prints the outcome. The time of a transaction is the CPU time of RUNS
applications minus that of RUNS setups, divided by RUNS. `--target` sets the
CPU seconds RUNS aims for and `--repeat` how many timed runs of each mode to
take the least of. The runner disables glibc heap trimming, which would charge
setup-only runs for regrowing the heap, and serves allocations up to 32 MiB
from the heap rather than fresh mappings, as a long-running process would.

A case matches when every engine reports the same validity, status (success,
revert or halt), gas used and logs hash, and the logs hash equals the
fixture's. The fixtures were filled for London, and nothing checks the
post-state root. Every fixture's gas limit exceeds EIP-7825's cap, so the runner
encodes cases with the cap lifted (`BlockEnv.tx_gas_limit_cap`). FeVM executes
Osaka rules and the revm and evmone runners Cancun rules; all 27 cases use the
same gas under both.

The timed work is transaction validation, execution and the result's state
changes. evmone analyzes code for jump destinations on every call; FeVM and
revm analyze it when the code enters their state, which the setup covers.

A result also reports `<engine>_setup_us`, the time to build the pre-state once.
It is left out of the transaction time, so a slower setup, such as code analysis
or Keccak, shows only there.

## Precompiles and Keccak

The benchmark suite runs no precompiles and little Keccak. `fixtures.py` writes
state tests that loop `KECCAK256` and each precompile on an input that does its
full work; a call that fails or returns nothing halts the transaction, which
shows in its `status`:

```sh
python3 native/bench/fixtures.py native/out/bench-fixtures
python3 native/bench/run.py --benchmarks native/out/bench-fixtures --fe native/out/toolchain/bin/fe --fevm-only
```

`--fevm-only` times FeVM alone: these fixtures use Osaka's precompiles and gas,
and the revm and evmone runners run Cancun.

## Engines

- FeVM: the conformance driver, built by `--fe` at `--level` (default O2), or
  `--executable`.
- revm: `revm/`, revm 33.1.0 at the same `sbillig/revm` revision as the
  differential reference, with fat LTO and `target-cpu=native`. `run.py`
  builds it unless `--revm` names a binary.
- evmone: `evmone/runner.cpp` drives evmone's state transition with its
  baseline interpreter. Build evmone with its test utilities, then the runner,
  and pass it with `--evmone`:

```sh
git clone --recursive -b v0.25.0 https://github.com/ipsilon/evmone
cmake -S evmone -B evmone/build -DCMAKE_BUILD_TYPE=Release -DEVMONE_TESTING=ON \
  -DEVMONE_X86_64_ARCH_LEVEL=1 -DCMAKE_C_FLAGS=-march=native -DCMAKE_CXX_FLAGS=-march=native
cmake --build evmone/build --target evmone evmone.testutils -j8
native/bench/evmone/build.sh evmone evmone/build native/out/bench/evmone-runner
```
