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

`--lazy` builds and runs [`fevm_lazy`](lazy/src/lib.fe) instead, which shares
`fevm_conformance`'s case reading and output and runs each state test's
transaction a second time, over a world that starts empty and reads the
pre-state from a `WorldSource` as the transaction needs it. It adds `lazy`,
each way that run disagrees with the complete one: its receipt; an account
or slot the lazy world holds but did not load, or that differs from the
complete post-state (code too, where read, and storage the complete account
has); or an account or slot the complete run changed that the lazy world
did not load, unless the slot's account was loaded and is gone. A case with
any of them, or without `lazy`, fails, and a load the lazy world missed
fails fevm's assertions and crashes the driver. `fevm_conformance` itself
instantiates only the complete world, so the benchmark runner times it
unchanged. Blockchain tests run as without `--lazy`; `--stateless` and
`--paths`, below, run them statelessly or over a store of trie nodes too.

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

### Stateless

`--stateless` builds and runs `fevm_lazy`, and has it validate each block of
a blockchain test statelessly beside the import, with the complete `Chain`
as the oracle. It implies `--lazy`, so state tests in the same run run
lazily. Before importing a block the driver takes the chain's state as a
witness: every node of its trie (`Chain::write_nodes`), every code of its
world, and the headers of the head and the 255 blocks before it, which the
driver keeps itself. After the import, `validate` runs over:

1. the whole witness, and must give the chain's verdict: `Valid` with the
   same block hash, receipts and output (gas used, blob gas used, logs
   bloom, requests and their hash, access list), or `Invalid` with the same
   reason;
2. only what the first run used, and must give the same;
3. that without one used node, without one used code, and without one used
   header, each in its own run, and must give `Verdict::Witness` lacking
   just that item. Each is the one at the position the keccak256 of the
   block's RLP gives, modulo the count used, so a run is reproducible. The
   headers used are the parent's and the ancestors' a BLOCKHASH reached; a
   run with none used, such as for a block whose header is invalid, is
   skipped and counted.

The driver adds `stateless`: the blocks validated, which must be every block
it judged, those that read an ancestor's header, the removal runs made and
skipped, each by kind (node, code, header), and each disagreement, which
fails the test, as does a missing `stateless`. `results.json` sums the
counts in `stateless_runs`. The witnesses come from fevm's own reads, so the
run cannot find a load that asks for more than other clients' witnesses
give; it finds a missed or misplaced load, a trie or chain fault, and a lack
classified as a verdict. All 44,932 tests of `tests@v21.0.3` pass: 56,165
blocks validated, of which 72 read an ancestor's header; 51,602 runs without
a node and as many without a code (4,563 of each skipped), and 56,163
without a header (2 skipped).

### Over a store of trie nodes

`--paths` builds and runs `fevm_lazy` too, and has it validate each block of
a blockchain test as a client that keeps the state trie on disk would, with
the complete `Chain` as the oracle. It excludes `--stateless`. The driver
keeps a store of trie nodes keyed by where each stands (`NodePath`: the
owner account's key for a storage trie, the depth and the path), as a
client's tables hold them. It fills the store with the genesis state's
nodes by a reading of their RLP of its own, from the root by hash, not
`StateTrie`'s. For each block, before the import, it validates the block
through `fevm_chain`'s steps (`decode_block`, `checked_env`, `run`,
`write_changes`, `root`, `mismatch`) as a client does: the block runs over
a state that reads accounts and slots through a partial `StateTrie` whose
source is the store, which checks the hash of each node it gives, and code
and block hashes from the chain's world before the block; the store is
taken back from that state (`Evm::into_parts`, `into_source`), and the
block's changes go into a new partial trie over it. A second run sets the
changes in the trie the block was read through, as `validate` does, from a
copy of the store, and its changed nodes must be the same. The verdict must be
the chain's, with the same block hash, receipts and output if valid. For a
valid block the driver applies `StateTrie::changed_nodes` to the store: the
storage tries cleared, then the deletes, then the puts. It also reads each
account the block's changes name from the trie after the root, by its hashed
key (`account_keyed`), as a client writes it with its new storage root, and
that must be the account a new complete trie of the chain's world holds;
then it takes the store back out of the trie (`into_source`). Each header
that decodes, the genesis's and each block's, must encode back to its RLP
(`Header::encode`). After every block,
valid or not, the store must equal, place by place and byte by byte, the
nodes of a new complete trie of the chain's world as the same reading gives
them, and no node read from it may have had another hash than the one
asked for.

The driver adds `paths`: the blocks validated, which must be every block it
judged, the nodes the store held at the genesis, the nodes read from it,
the puts, deletes and storage tries cleared applied, the headers encoded
again, and each problem, which fails the test, as does a missing `paths`.
`results.json` sums the counts in `paths_runs`. All 44,932 tests of
`tests@v21.0.3` pass: 56,165 blocks; 2,918,619 nodes stored at the
genesis, 1,141,289 read, 662,803 puts, 11,661 deletes and no storage trie
cleared, which no test of these forks does (a storage trie is cleared only
when settlement deletes an empty account with storage, which only a
pre-state can hold); 101,097 headers, every genesis's and block's, encoded
again.

## Blocks from another client's witness

`fevm_tools witness` validates blocks with `validate` from what another
client gives: a block directory of
[fevm-replay](https://github.com/PugarHuda/fevm-replay)'s `fetch-block` and
`fetch-proofs`, such as the two in its `fixtures/proven`:

```sh
mkdir -p native/out/replay && tar -xzf <fevm-replay>/fixtures/proven/0x19335e5.tar.gz -C native/out/replay
native/out/tools/fevm_tools witness --fe native/out/toolchain/bin/fe \
  --replay native/out/replay/0x19335e5 --out native/out/witness-run
```

or a directory of a block and its execution witness, below. `--replay`
takes one or more fevm-replay directories; `--fe` builds `fevm_lazy`, or
`--executable` reuses a built one, `--level` sets its optimization level
and `--jobs` how many blocks run at once (default: two fewer than the
host's processors). For each fevm-replay directory the runner builds a
witness case:

- the block's RLP, rebuilt from `block.json` (`eth_getBlockByNumber` with
  its transactions): the header, each transaction in its block form
  (legacy, and EIP-2930, EIP-1559, blob and EIP-7702 ones as their type
  byte and payload), no ommers and the withdrawals. The header must hash to
  the block's hash and each transaction to its own; `validate` then checks
  the transactions and withdrawals roots;
- the parent's header, rebuilt from `proofs.json`'s `parent` and checked by
  its hash, the only header, as the directory holds no ancestors;
- as trie nodes, every node of the parent's account and storage proofs
  (`pre`, EIP-1186), and the nodes derived from the block's own proofs
  (`post`), below, whose own nodes are left out;
- as codes, the system contracts' code in `proofs.json`, and every code in
  the traces (`prestate.json`) and of the EIP-7702 delegates
  (`delegates.json`);
- the fork schedule of its chain (`chain.json`) from Osaka on. Mainnet's
  is go-ethereum's `params/chainspecs/mainnet.json`: Osaka from
  1,764,798,551 with Prague's blobs (6, 9, 5,007,716), BPO1 from
  1,765,290,071 (10, 15, 8,346,193) and BPO2 from 1,767,747,671 (14, 21,
  11,684,671). Hoodi's (chain 560,048) is reth v2.11.0's: Osaka from
  1,761,677,592, BPO1 from 1,762,365,720 and BPO2 from 1,762,955,544, with
  the same blobs. A chain without a schedule, or a block before its
  chain's Osaka, is refused.

The case (version 9) is the chain ID, the fork schedule as a blockchain
test has it, the parent's hash, the block's RLP, and the nodes, codes and
headers, each a count and then each item with its length. `fevm_lazy` runs
`validate` once on it and prints the verdict: `valid` with the block's
`hash`, `invalid` with its `reason` (and `transaction`), or `witness` with
what it `lacks` (`header`, `node`, `malformed_node`, `code`) and its `hash`;
then `nodes`, `codes` and `headers`, each how many the witness held and how
many the validation read. A host failure prints only `host_error`.
`results.json` lists each block with its verdict, and `totals` the count of
each verdict and, over the valid blocks, how many nodes, codes and headers
their witnesses held and their validation read; the runner fails unless
every block is valid.

With `--paths` the case is version 11, and `fevm_lazy` also puts the
witness's nodes reached from the parent's state root in a store keyed by
where each stands, by the same reading as for blockchain tests, and
validates the block again through `fevm_chain`'s steps over a partial trie
whose source is that store, with the witness's codes and headers. The
verdict must be the witness's, and no node read may have had another hash.
The witness holds only part of the state, so after a valid block the store
cannot be compared with a whole state; instead every node in it, once the
block's changed nodes are applied, must be reached from the block's state
root through nodes it holds, each with the hash its parent names. It adds
`paths` with the counts, and `totals` sums them; any problem fails the run.

`--execution-witness` takes directories of a block on the chain `--chain`
names and its witness as a node gives them: the block's RLP (`raw.json`,
`debug_getRawBlock`), its hash (`block.json`, `eth_getBlockByNumber`) and an
execution witness (`witness.json`, `debug_executionWitness`). The case is
the block as given, its header checked against the hash, the parent's hash
from that header, and the witness's `state` nodes, `codes` and `headers` as
they are. Such a witness carries the nodes a collapse needs, so none are
derived, and one it lacks is a finding:

```sh
native/out/tools/fevm_tools witness --fe native/out/toolchain/bin/fe --chain 560048 \
  --execution-witness native/out/witness-hoodi/* --out native/out/witness-hoodi-run
```

Over 96 consecutive Hoodi blocks, 4,078,315 to 4,078,410, with the
witnesses ethrex v31.0.0 serves through ethpandaops' public endpoint
(`native/out/scripts/fetch_witnesses.py` fetched them; they are not in the
repository), all 96 are valid. Their validation read every node (41,286)
and code (1,119) of their witnesses, and of 245 headers 237: each of the 8
blocks whose BLOCKHASH reaches back holds the header of the oldest block it
asks for, whose hash its child's header already gives. The run found that
`Chain`'s trie updates set the slots in the order the block first changed
them: block 4,078,344 clears three slots under a storage root's branch and
sets a fourth, so the branch keeps two children, but after the three
clearings the trie collapsed the branch onto its last child, which it had
to read, before the fourth slot gave it a second child again; the witness,
minimal for the end state, did not hold that child. `write_changes` now
sets before it removes.

A deletion that leaves a branch with one child moves that child up into
its place, and when the child is a leaf or an extension under keys no
transaction touched, `eth_getProof` cannot name it: the parent's proofs
lack it, and the block's own proof of the deleted key ends at it as it
moved up, its path longer by the nibbles it rose. So from each leaf and
extension of the `post` proofs the runner derives the same node with one up
to all of its path's leading nibbles removed (an extension keeps one), its
path re-encoded with its hex-prefix flag and its value or child unchanged,
and adds those that are no `pre` node; `results.json` counts them as
`derived`. That is sound whatever the derived nodes are: a witness's nodes
are read by their hash, from the parent's state root down, so a string that
is no node of the parent's state is never read. A sibling that is a branch
cannot be derived: it stays where it is, under a new or longer extension,
so the proof of the deleted key stops at that extension and never holds the
branch. The trie must still read it to learn that it is a branch, so such a
block lacks it (`Lack::Node`).

Block `0x19335e5` of fevm-replay's `fixtures/proven` is valid this way, its
hash `0x633b9cae…2ccd6`: of 39,462 nodes (2,969 from `pre`, 36,493
derived) the validation read 2,973, all of `pre` and 4 derived, the
siblings of the block's collapses, such as a USDC storage leaf the block's
clearing of a slot pulls up; and 77 of 83 codes and the parent's header.
Without the derived nodes it lacks that leaf as the changes go into the
trie. Block `0x192f56b` cannot be validated from its directory: its proofs,
fetched before fevm-replay proved the system contracts, hold none of them,
so its first system call lacks the beacon roots contract's account.
