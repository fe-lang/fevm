# Ethereum state and blockchain tests

`fevm_tools conformance` ([`native/tools`](../tools/src/conformance.fe)) runs
the Osaka and Amsterdam cases of an
[execution-specs](https://github.com/ethereum/execution-specs) test fixture
release through FeVM's `Evm::transact`, each by its fork's rules. Each case starts a fresh native
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
`--fork` limits the run to the forks or networks named after it (`Osaka`,
`Amsterdam`, and for blockchain tests the networks below, such as `BPO1` or
`OsakaToBPO1AtTime15k`).
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
25 of each are `signature`. `results.json` counts outcomes by fork or network
(`by_network`) and by fixture group.

The driver prints one JSON object: `invalid` (null, or the validity code's
name), `status` (the status name), `host_failure`, `gas_used`, `logs_hash`
and the post-state accounts. Names come from `ingots/evm/src/status.fe`.

## Blockchain tests

Given a release's `blockchain_tests`, the same command imports each test's
blocks through `fevm_chain`'s `Chain`, one driver process per test:

```sh
tar -xzf fixtures.tar.gz fixtures/blockchain_tests
native/out/tools/fevm_tools conformance --fe native/out/toolchain/bin/fe \
  --fixtures fixtures/blockchain_tests --out native/out/blocks-run
```

A test runs if fevm implements every fork of its `network`: a fork from
genesis, or for `XToYAtTime15k`, X and then Y from timestamp 15,000. Forks
whose names begin with `Amsterdam` have Amsterdam's rules and the others
(`Osaka`, `BPO1`, `BPO2`) Osaka's; a BPO fork after Amsterdam is Amsterdam's
(`AmsterdamToBPOIncreaseAtTime15k` is `Amsterdam`, then
`AmsterdamBPOIncrease`). The BPO forks take their blob schedule from the
fixture's `config.blobSchedule`. Networks with Prague or an earlier fork are
not run.

The driver gets only what a client would: the chain ID, the fork schedule,
the pre-state, the genesis block and each block's `rlp`. It checks that the
pre-state's root is the genesis header's, then imports each block with
`Chain::import`, which decodes it, validates its header against the head,
runs it and compares its roots and values with the header. A test passes
when each block's validity is the fixture's, the reason fevm gives for each
invalid block is one its `expectException` names, the head's hash after the
last block is `lastblockhash`, and the state then equals `postState`.

`native/tools/src/blocks.fe` maps each reason to the execution-spec-tests
exceptions it stands for. Where fevm draws fewer distinctions, a reason
stands for several: its intrinsic gas includes the calldata floor
(`INTRINSIC_GAS_TOO_LOW`, `INTRINSIC_GAS_BELOW_FLOOR_GAS_COST`), one code
covers a nonce above and below the sender's and a blob or set-code creation,
and a block access list is no part of the block, so a wrong, misordered or
repeated one shows only as a wrong hash (`INVALID_BAL_HASH`,
`INVALID_BLOCK_ACCESS_LIST`, `INCORRECT_BLOCK_FORMAT`).

All 44,842 tests of `tests@v21.0.2` pass, every block judged:

| network | tests |
|---|---|
| `Osaka` | 17,441 |
| `Amsterdam` | 26,349 |
| `BPO1`, `BPO2`, `AmsterdamBPOIncrease`, `AmsterdamBPODecrease` | 190 each |
| `OsakaToBPO1AtTime15k`, `BPO1ToBPO2AtTime15k` | 25, 24 |
| `BPO2ToAmsterdamAtTime15k` | 193 |
| `AmsterdamToBPOIncreaseAtTime15k`, `AmsterdamToBPODecreaseAtTime15k` | 26, 24 |

The driver prints `blocks`, each `valid` or with the `reason` it is invalid
(and the index of the `transaction` it concerns), the `head` block's hash and
the final accounts; or `genesis` if the pre-state is not the genesis
header's. A host failure (an allocation failure, a balance overflow) is no
verdict on a block: the driver prints only `host_error`, and the test's
outcome is `host_error`.
