# Closing evm-benchmarks gaps to revm

Three changes, chosen by profiling the cases where FeVM trailed revm and
evmone on [ipsilon/evm-benchmarks](https://github.com/ipsilon/evm-benchmarks)
`d8b88f4`, bring FeVM from 1.35x to 1.08x revm's time (geometric mean of 27
cases) and from 2.34x to 1.87x evmone's. FeVM is now faster than revm on 12
cases, and on the micro suite as a whole. All three engines agree on every
case's status, gas used and logs hash.

1. Memory growth (`90a6bc0`). MLOAD and MSTORE grew memory through the
   general planner, which computes the quadratic cost in u128 and returns an
   `Option` through memory; below 2^32 bytes the cost now takes u64
   arithmetic. structarray_alloc and the memory_grow cases.
2. Division (Sonatina `perf/word-divider` `728b0938`). Wide divisions by a
   power of two (every wide DIV of sha1_divs) and by a one-limb divisor (most
   of snailtracer's SDIVs) called the out-of-line Knuth divider; they now
   shift and mask, or take four inline 128/64-bit digits.
3. Code analysis (`ee52d18`). Every call copied the callee's code and scanned
   it for JUMPDESTs; `set_code` now stores the bitmap beside the code in the
   arena and calls copy both. Small transactions and code-heavy micro cases.

The run used `native/bench/run.py` defaults on the host, engines and fixtures
of the [first report](../evm-benchmarks-20261027/README.md), after `896ff85`
kept large allocations on the heap. Both runs build the driver at O2 with the
same scratch Fe compiler, the second with change 2. See
[`before.jsonl`](before.jsonl) and [`after.jsonl`](after.jsonl).

| Cases | FeVM / revm before | after | FeVM / evmone before | after |
| --- | ---: | ---: | ---: | ---: |
| main (14) | 1.48 | 1.24 | 2.09 | 1.74 |
| micro (13) | 1.22 | 0.93 | 2.65 | 2.01 |
| all (27) | 1.35 | 1.08 | 2.34 | 1.87 |

| Case | FeVM µs before | after | revm µs | evmone µs | FeVM / revm | FeVM / evmone |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| blake2b_huff/empty | 21.76 | 14.42 | 11.39 | 11.90 | 1.87 → 1.27 | 1.21 |
| blake2b_huff/8415nulls | 805.13 | 774.10 | 657.66 | 401.78 | 1.22 → 1.18 | 1.93 |
| blake2b_shifts/8415nulls | 6,731.18 | 6,696.91 | 6,240.38 | 3,585.37 | 1.08 → 1.07 | 1.87 |
| sha1_divs/empty | 47.70 | 28.59 | 29.03 | 26.54 | 1.62 → 0.98 | 1.08 |
| sha1_divs/5311 | 3,555.87 | 2,142.26 | 2,197.39 | 2,214.81 | 1.63 → 0.97 | 0.97 |
| sha1_shifts/empty | 27.39 | 26.51 | 24.83 | 13.24 | 1.10 → 1.07 | 2.00 |
| sha1_shifts/5311 | 2,032.65 | 2,019.35 | 1,919.39 | 1,024.05 | 1.06 → 1.05 | 1.97 |
| snailtracer/benchmark | 33,822.00 | 32,165.44 | 26,467.82 | 17,573.76 | 1.28 → 1.22 | 1.83 |
| structarray_alloc/nfts_rank | 654.57 | 543.69 | 473.92 | 175.40 | 1.37 → 1.15 | 3.10 |
| swap_math/spent | 5.61 | 4.40 | 3.03 | 1.94 | 1.83 → 1.45 | 2.27 |
| swap_math/received | 6.00 | 4.71 | 3.36 | 2.09 | 1.76 → 1.40 | 2.25 |
| swap_math/insufficient_liquidity | 4.84 | 3.69 | 2.38 | 1.69 | 1.98 → 1.55 | 2.18 |
| weierstrudel/1 | 152.85 | 143.80 | 86.90 | 97.18 | 1.75 → 1.66 | 1.48 |
| weierstrudel/15 | 1,376.31 | 1,355.85 | 819.37 | 960.18 | 1.68 → 1.66 | 1.41 |
| JUMPDEST_n0/empty | 501.84 | 523.78 | 794.33 | 299.65 | 0.63 → 0.66 | 1.75 |
| jump_around/empty | 27.75 | 18.40 | 25.21 | 15.16 | 1.10 → 0.73 | 1.21 |
| loop_with_many_jumpdests/empty | 7,447.60 | 7,827.89 | 12,013.79 | 4,499.83 | 0.62 → 0.65 | 1.74 |
| memory_grow_mload/nogrow | 49.55 | 35.99 | 42.55 | 18.92 | 1.16 → 0.85 | 1.90 |
| memory_grow_mload/by1 | 51.36 | 38.13 | 45.02 | 20.62 | 1.12 → 0.85 | 1.85 |
| memory_grow_mload/by16 | 69.08 | 46.51 | 53.17 | 23.17 | 1.29 → 0.88 | 2.01 |
| memory_grow_mload/by32 | 93.35 | 57.16 | 65.31 | 33.70 | 1.39 → 0.88 | 1.70 |
| memory_grow_mstore/nogrow | 53.98 | 41.48 | 46.44 | 20.15 | 1.17 → 0.89 | 2.06 |
| memory_grow_mstore/by1 | 57.04 | 43.23 | 48.85 | 21.45 | 1.15 → 0.89 | 2.02 |
| memory_grow_mstore/by16 | 80.03 | 51.01 | 52.71 | 23.24 | 1.51 → 0.97 | 2.19 |
| memory_grow_mstore/by32 | 99.16 | 59.84 | 57.01 | 30.06 | 1.74 → 1.05 | 1.99 |
| signextend/zero | 123.31 | 103.94 | 59.56 | 31.21 | 2.05 → 1.75 | 3.33 |
| signextend/one | 118.60 | 99.87 | 61.27 | 30.60 | 1.93 → 1.63 | 3.26 |

The two JUMPDEST-only cases slowed by 4-5%. Built with the previous compiler,
changes 1 and 3 alone make them faster (JUMPDEST_n0 501 -> 431 us,
loop_with_many_jumpdests 7,472 -> 6,470 us); the compiler with the inline
division paths then costs them about 20%, while snailtracer, blake2b, sha1,
structarray_alloc, swap_math and weierstrudel stay level or improve. The
division paths enlarge the dispatch function; the cause is not yet confirmed.

The largest remaining gaps to revm are MULMOD (weierstrudel, 1.66x: its
8-by-4-limb division works on limbs in a stack buffer), SIGNEXTEND (1.7x),
per-transaction cost (swap_math, 1.4-1.6x) and snailtracer (1.22x), whose
time is spread over dispatch, storage hashing and SDIV.
