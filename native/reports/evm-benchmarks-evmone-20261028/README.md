# Closing evm-benchmarks gaps to evmone

A second round on [ipsilon/evm-benchmarks](https://github.com/ipsilon/evm-benchmarks)
`d8b88f4` brings FeVM from 1.87x to 1.25x evmone's time (geometric mean of 27
cases) and from 1.08x to 0.72x revm's. FeVM now beats evmone on four cases
and is within 1% of it on three more, and beats revm on 24. All three engines agree on every case's status,
gas used and logs hash. See [`after.jsonl`](after.jsonl); the starting point is
the [previous report's](../evm-benchmarks-gaps-20261028/README.md) `after.jsonl`.

| Cases | FeVM / revm before | after | FeVM / evmone before | after |
| --- | ---: | ---: | ---: | ---: |
| main (14) | 1.24 | 0.91 | 1.74 | 1.28 |
| micro (13) | 0.93 | 0.56 | 2.01 | 1.21 |
| all (27) | 1.08 | 0.72 | 1.87 | 1.25 |

## Changes

FeVM, in order:

- `ac9f14c` Arms that fault or halt leave the dispatch loop themselves, so the
  loop loads no status per opcode; MLOAD and MSTORE within memory run inline.
- `98073ae` CALLDATALOAD reads whole words (it took ~2,800 instructions).
- `1a7dfe0` Precompiles are warm without warm-set entries.
- `3cf0a62` Intrinsic gas counts nonzero calldata bytes eight at a time.
- `28c9e95` EVM memory size is tracked apart from a doubling, zeroed buffer.
- `84197ea` SIGNEXTEND works within the sign byte's limb (2x faster).
- `3890312` A warm SLOAD looks its slot up once for warmth.
- `43e02dc` swisstable `423b4c7` hashes u256 keys by folded multiplication
  instead of XXH64 (snailtracer -8.5%).
- `121063f` PUSH1, PUSH2, PUSH4 and PUSH32 read their width.
- `d1bee77` Common opcodes charge their constant base gas in their arms, the
  rest from the table before a second dispatch; the dispatch head drops from
  about 17 to 11 instructions.
- `42ab458` MLOAD and MSTORE grow memory inline when the buffer holds it.

Sonatina, used by the compiler that built the driver:

- `perf/freeze-guards` `5c204bdf`, `dc5b1ac4`: compare-subtract fusion only
  for differences used in four or more blocks; stack-depth and gas checks keep
  `cmp; jb` instead of `sub; setb; test; jne` (sha1_shifts -24%).
- `perf/bounded-shift-counts` `0068cd79`: i256 compares against powers of
  two test the shifted limbs against zero.
- `perf/word-divider` `7125fc53`: MULMOD skips the divider for products below
  the modulus; `7d6e4e54`: wide quotient digits by 3-by-2 division.

| Case | FeVM µs before | after | revm µs | evmone µs | FeVM / revm | FeVM / evmone |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| blake2b_huff/empty | 14.42 | 10.47 | 11.44 | 12.05 | 0.92 | 1.21 → 0.87 |
| blake2b_huff/8415nulls | 774.10 | 543.16 | 659.08 | 402.25 | 0.82 | 1.93 → 1.35 |
| blake2b_shifts/8415nulls | 6,696.91 | 4,842.92 | 6,336.49 | 3,626.80 | 0.76 | 1.87 → 1.33 |
| sha1_divs/empty | 28.59 | 22.79 | 29.43 | 26.57 | 0.77 | 1.08 → 0.86 |
| sha1_divs/5311 | 2,142.26 | 1,702.27 | 2,176.20 | 2,222.60 | 0.78 | 0.97 → 0.77 |
| sha1_shifts/empty | 26.51 | 18.73 | 25.37 | 13.35 | 0.74 | 2.00 → 1.40 |
| sha1_shifts/5311 | 2,019.35 | 1,434.95 | 1,935.15 | 1,029.64 | 0.74 | 1.97 → 1.39 |
| snailtracer/benchmark | 32,165.44 | 23,575.83 | 26,614.55 | 17,614.06 | 0.89 | 1.83 → 1.34 |
| structarray_alloc/nfts_rank | 543.69 | 350.16 | 476.46 | 175.58 | 0.73 | 3.10 → 1.99 |
| swap_math/spent | 4.40 | 3.05 | 3.16 | 1.95 | 0.96 | 2.27 → 1.56 |
| swap_math/received | 4.71 | 3.30 | 3.43 | 2.10 | 0.96 | 2.25 → 1.57 |
| swap_math/insufficient_liquidity | 3.69 | 2.52 | 2.38 | 1.68 | 1.06 | 2.18 → 1.50 |
| weierstrudel/1 | 143.80 | 130.87 | 87.26 | 98.02 | 1.50 | 1.48 → 1.33 |
| weierstrudel/15 | 1,355.85 | 1,189.77 | 839.80 | 963.12 | 1.42 | 1.41 → 1.24 |
| JUMPDEST_n0/empty | 523.78 | 303.33 | 798.56 | 301.04 | 0.38 | 1.75 → 1.01 |
| jump_around/empty | 18.40 | 12.70 | 25.38 | 15.20 | 0.50 | 1.21 → 0.84 |
| loop_with_many_jumpdests/empty | 7,827.89 | 4,535.00 | 12,063.96 | 4,482.18 | 0.38 | 1.74 → 1.01 |
| memory_grow_mload/nogrow | 35.99 | 25.88 | 42.80 | 18.88 | 0.60 | 1.90 → 1.37 |
| memory_grow_mload/by1 | 38.13 | 27.46 | 45.43 | 20.70 | 0.60 | 1.85 → 1.33 |
| memory_grow_mload/by16 | 46.51 | 31.42 | 53.72 | 23.38 | 0.58 | 2.01 → 1.34 |
| memory_grow_mload/by32 | 57.16 | 33.92 | 65.66 | 33.83 | 0.52 | 1.70 → 1.00 |
| memory_grow_mstore/nogrow | 41.48 | 28.20 | 46.32 | 20.28 | 0.61 | 2.06 → 1.39 |
| memory_grow_mstore/by1 | 43.23 | 29.95 | 49.09 | 21.69 | 0.61 | 2.02 → 1.38 |
| memory_grow_mstore/by16 | 51.01 | 33.03 | 52.23 | 23.22 | 0.63 | 2.19 → 1.42 |
| memory_grow_mstore/by32 | 59.84 | 35.81 | 57.76 | 30.21 | 0.62 | 1.99 → 1.19 |
| signextend/zero | 103.94 | 42.12 | 60.01 | 31.73 | 0.70 | 3.33 → 1.33 |
| signextend/one | 99.87 | 42.15 | 61.72 | 30.71 | 0.68 | 3.26 → 1.37 |

## What remains

- Dispatch: about 45 instructions per opcode on swap_math against evmone's
  20; the head is 11 instructions, and Cranelift's register allocator keeps
  the code pointer and sometimes gas or `self` in stack slots. Small source
  changes swing dispatch-bound cases by 20-30% at equal instruction counts
  when a loop-carried value moves to memory.
- structarray_alloc (1.99x): MSTORE growth past the buffer and the remaining
  dispatch cost.
- weierstrudel (1.24-1.33x evmone, the one case still behind revm): MULMOD's
  8-by-4-limb division is latency-bound in a stack-buffered divider.
- swap_math (1.5x): per-transaction state work (warm sets, journals, hash
  tables) outside the loop, about 24k of 66k instructions.
