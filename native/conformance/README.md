# Ethereum state tests

`run.py` runs the Cancun cases of an
[execution-spec-tests](https://github.com/ethereum/execution-spec-tests) fixture
release through FeVM's `transact`. Each case starts a fresh native
`fevm_conformance` process, which reads one binary-encoded case from stdin and
prints the transaction outcome, the logs hash and the complete post-state.

```sh
gh release download v5.4.0 -R ethereum/execution-spec-tests -p fixtures_stable.tar.gz
tar -xzf fixtures_stable.tar.gz
python3 native/conformance/run.py --fe native/out/toolchain/bin/fe \
  --fixtures fixtures/state_tests --out native/out/conformance-run
```

`--select` limits the run to fixture paths containing any given substring,
`--level` picks the driver's optimization level (default O2), `--jobs` sets the
number of parallel cases and `--timeout` the per-case limit in seconds.
`--executable` reuses an already built driver. Each output directory must be new.

A case passes when the transaction's validity matches `expectException`, the
receipt's logs hash matches, and every account's balance, nonce, code and
non-zero storage equals the fixture's post-state. Outcomes are:

- `passed`
- `failed`: a validity, logs or state mismatch, listed in `cases.jsonl`
- `host_error`: FeVM stopped with a host status (unimplemented precompile,
  state table capacity, allocation failure) instead of an EVM outcome
- `crash` and `timeout`

The runner encodes the environment, pre-state and the transaction selected by
the case's data/gas/value indexes; it derives the blob base fee from
`currentExcessBlobGas` and the transaction type from its fields. As in other
state-test clients, `BLOCKHASH(n)` for the previous 256 blocks is the Keccak-256
hash of `n`'s decimal digits. The driver checks the post-state directly instead
of recomputing the state root.
