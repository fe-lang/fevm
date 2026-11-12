# Ethereum state tests

`fevm_tools conformance` ([`native/tools`](../tools/src/conformance.fe)) runs
the Osaka and Amsterdam cases of an
[execution-specs](https://github.com/ethereum/execution-specs) test fixture
release through FeVM's `transact`, each by its fork's rules. Each case starts a fresh native
`fevm_conformance` process, which reads one binary-encoded case from stdin and
prints the transaction outcome, the logs hash and the complete post-state. Run
it from the repository's root:

```sh
gh release download tests@v21.0.2 -R ethereum/execution-specs -p fixtures.tar.gz
tar -xzf fixtures.tar.gz fixtures/state_tests
native/out/toolchain/bin/fe build . --ingot fevm_tools --backend native -O 2 \
  --emit executable --out-dir native/out/tools
native/out/tools/fevm_tools conformance --fe native/out/toolchain/bin/fe \
  --fixtures fixtures/state_tests --out native/out/conformance-run
```

`--fe` builds the driver; `--executable` reuses an already built one instead.
`--fork` limits the run to the forks named after it (`Osaka`, `Amsterdam`).
`--select` limits the run to fixture paths containing any of the substrings
that follow it, `--level` picks the driver's optimization level (default O2),
`--jobs` sets the number of parallel cases (default: two fewer than the host's
processors) and `--timeout` the per-case limit in seconds (default 120). Each
output directory must be new. The runner reads one fixture file at a time, and
`results.json`'s `seconds` covers reading the fixtures as well as running the
cases.

Given `RUNS [TRANSACT]` arguments, the driver repeats the case RUNS times
before the reported run, skipping the transaction when TRANSACT is 0; the
[benchmark runner](../bench/README.md) times the difference.

A case passes when the transaction's validity matches `expectException`, the
receipt's logs hash matches, the gas used and success match the fixture's
receipt where it has one (`tests@v21.0.2` on), and every account's balance,
nonce, code and non-zero storage equals the fixture's post-state. Outcomes are:

- `passed`
- `signature`: the transaction's signature is malformed. FeVM takes a recovered
  sender, so rejecting the signature is the host's part of decoding it; the
  case is not run.
- `failed`: a validity, logs or state mismatch, listed in `cases.jsonl`
- `host_error`: FeVM stopped with a host status (allocation failure, balance
  overflow) instead of an EVM outcome
- `crash` and `timeout`

The runner encodes the environment, pre-state and the transaction selected by
the case's data/gas/value indexes; it derives the blob base fee from
`currentExcessBlobGas` with the fixture's blob schedule for the fork (BPO2's
update fraction when a fixture has none), the slot number from `slotNumber`, and the transaction type from its fields. As in other
state-test clients, `BLOCKHASH(n)` for the previous 256 blocks is the Keccak-256
hash of `n`'s decimal digits. The driver checks the post-state directly instead
of recomputing the state root.

All runnable cases of `tests@v21.0.2` pass: 14,640 Osaka and 16,883 Amsterdam;
25 of each are `signature`. `results.json` counts outcomes by fork
(`by_fork`) and by fixture group.

The driver prints one JSON object: `invalid` (null, or the validity code's
name), `status` (the status name), `host_failure`, `gas_used`, `logs_hash`
and the post-state accounts. Names come from `ingots/evm/src/status.fe`.
