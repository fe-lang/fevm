# Cancun state-test conformance

FeVM runs every Cancun state test of
[execution-spec-tests v5.4.0](https://github.com/ethereum/execution-spec-tests/releases/tag/v5.4.0)
(`fixtures_stable.tar.gz`, SHA-256
`92cf1b47ad12fb27163261fc3c1cea5df72439cab507983d06b56c94f8741909`) through
`transact`, using `native/conformance/run.py` with an O2 driver built by Fe master
`f69b911ce` on x86_64 Linux. The interpreter sources are those of FeVM `cf091df`
(the run's tree differed only in README text).

**16,800 of 16,847 cases pass (99.72%).** Each passing case matches the fixture's
transaction validity, receipt logs hash, and every account's balance, nonce,
code and storage. The 47 others stop with a host status, not a wrong result:
45 exceed a 256-entry state table during execution (storage, transient storage
or warm-account sets) and 2 have pre-states larger than the tables. There are no
failures, crashes or timeouts. See [`non-passing.jsonl`](non-passing.jsonl) and
[`results.json`](results.json).

| Fixture group | Passed | Cases |
| --- | ---: | ---: |
| static/state_tests (ported ethereum/tests) | 13,756 | 13,769 |
| cancun/eip4844_blobs | 1,092 | 1,092 |
| berlin/eip2930_access_list | 533 | 533 |
| frontier/opcodes | 511 | 512 |
| osaka/eip7883_modexp_gas_increase (Cancun cases) | 151 | 151 |
| cancun/eip1153_tstore | 120 | 123 |
| istanbul/eip152_blake2 | 117 | 117 |
| cancun/eip6780_selfdestruct | 115 | 115 |
| cancun/eip5656_mcopy | 93 | 93 |
| frontier/precompiles | 70 | 73 |
| shanghai/eip3860_initcode | 40 | 62 |
| paris/eip7610_create_collision | 45 | 45 |
| byzantium/eip198_modexp_precompile | 39 | 39 |
| 16 smaller groups | 118 | 123 |

The run took 149 s with eight parallel cases. The slowest cases are the
`static_Call50000*` and `static_Return50000_2` tests (52–69 s each), which copy
50,000-byte call inputs or outputs 50,000 times through per-byte loops; see the
`ByteBuffer::copy_from` work in argotorg/fe#1830.
