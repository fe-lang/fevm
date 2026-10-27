# evmone's benchmark suite: FeVM vs revm and evmone

`native/bench/run.py` timed one transaction of each case of
[ipsilon/evm-benchmarks](https://github.com/ipsilon/evm-benchmarks) `d8b88f4`
(14 main and 13 micro cases) on an AMD Ryzen 5 9600X (10 CPUs) under x86_64
Linux, with the defaults `--target 0.3 --repeat 3`. Every case matched: all
three engines report the same status, gas used and logs hash, and the logs hash
equals the fixture's. See [`results.jsonl`](results.jsonl).

- FeVM: this branch's conformance driver at O2, built by a scratch Fe that
  combines Fe `feat/generic-byte-order` (`71ffd7ca4`) with Sonatina
  `perf/freeze-guards`, `perf/word-divider` and `perf/bounded-shift-counts`.
- revm 33.1.0 (`sbillig/revm` `d613ef5`), fat LTO, `target-cpu=native`, rustc 1.98.1.
- evmone v0.25.0 baseline interpreter, GCC 13.3 `-O3 -march=native`. Its own
  `evmone-bench` agrees with `native/bench/evmone`: snailtracer 17.7 ms,
  structarray_alloc 174 µs and sha1_divs/5311 2,223 µs per call.

Geometric means of FeVM's time over the others':

| Cases | FeVM / revm | FeVM / evmone |
| --- | ---: | ---: |
| main (14) | 1.51 | 2.22 |
| micro (13) | 1.25 | 2.68 |
| all (27) | 1.38 | 2.43 |

| Case | Gas used | FeVM µs | revm µs | evmone µs | FeVM / revm | FeVM / evmone |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| blake2b_huff/empty | 35,252 | 21.53 | 11.82 | 11.88 | 1.82 | 1.81 |
| blake2b_huff/8415nulls | 934,875 | 803.04 | 667.96 | 403.25 | 1.20 | 1.99 |
| blake2b_shifts/8415nulls | 12,098,401 | 7,785.08 | 6,727.11 | 3,591.43 | 1.16 | 2.17 |
| sha1_divs/empty | 57,786 | 47.66 | 29.34 | 26.58 | 1.62 | 1.79 |
| sha1_divs/5311 | 3,042,886 | 3,544.17 | 2,183.01 | 2,226.10 | 1.62 | 1.59 |
| sha1_shifts/empty | 56,566 | 27.34 | 25.24 | 13.33 | 1.08 | 2.05 |
| sha1_shifts/5311 | 2,941,073 | 2,030.14 | 1,912.28 | 1,031.58 | 1.06 | 1.97 |
| snailtracer/benchmark | 161,088,532 | 39,140.88 | 29,299.40 | 17,818.12 | 1.34 | 2.20 |
| structarray_alloc/nfts_rank | 1,758,892 | 1,162.13 | 727.45 | 174.18 | 1.60 | 6.67 |
| swap_math/spent | 25,219 | 5.64 | 3.07 | 1.93 | 1.84 | 2.92 |
| swap_math/received | 25,689 | 6.03 | 3.37 | 2.08 | 1.79 | 2.90 |
| swap_math/insufficient_liquidity | 24,536 | 4.85 | 2.44 | 1.68 | 1.99 | 2.89 |
| weierstrudel/1 | 69,353 | 152.30 | 86.18 | 97.61 | 1.77 | 1.56 |
| weierstrudel/15 | 631,153 | 1,370.72 | 813.47 | 961.18 | 1.69 | 1.43 |
| JUMPDEST_n0/empty | 548,598 | 500.26 | 751.59 | 300.21 | 0.67 | 1.67 |
| jump_around/empty | 70,153 | 27.75 | 24.75 | 15.14 | 1.12 | 1.83 |
| loop_with_many_jumpdests/empty | 8,008,882 | 7,351.45 | 11,851.96 | 4,481.61 | 0.62 | 1.64 |
| memory_grow_mload/nogrow | 78,484 | 49.26 | 42.81 | 18.90 | 1.15 | 2.61 |
| memory_grow_mload/by1 | 78,912 | 52.49 | 44.99 | 20.65 | 1.17 | 2.54 |
| memory_grow_mload/by16 | 92,840 | 73.39 | 53.34 | 23.08 | 1.38 | 3.18 |
| memory_grow_mload/by32 | 123,549 | 94.64 | 66.13 | 33.83 | 1.43 | 2.80 |
| memory_grow_mstore/nogrow | 82,580 | 53.81 | 46.38 | 19.75 | 1.16 | 2.73 |
| memory_grow_mstore/by1 | 83,008 | 57.22 | 49.38 | 21.58 | 1.16 | 2.65 |
| memory_grow_mstore/by16 | 96,936 | 80.62 | 52.44 | 23.10 | 1.54 | 3.49 |
| memory_grow_mstore/by32 | 127,645 | 99.90 | 56.80 | 29.92 | 1.76 | 3.34 |
| signextend/zero | 117,194 | 123.32 | 59.19 | 31.81 | 2.08 | 3.88 |
| signextend/one | 117,206 | 117.38 | 60.48 | 30.96 | 1.94 | 3.79 |

FeVM beats revm only on code dense with JUMPDESTs, where revm is slower than
on any other case per unit of gas. The largest gaps to revm are SIGNEXTEND,
the three ~25,000-gas swap_math transactions (per-transaction cost), MULMOD
and ADDMOD in weierstrudel, DIV in sha1_divs, structarray_alloc and memory
growth by 16 or 32 words.
