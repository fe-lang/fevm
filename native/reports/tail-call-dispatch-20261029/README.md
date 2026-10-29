# Tail-call dispatch on Fe master `3587ff999`

FeVM's common opcodes run as handlers that tail-call the next opcode's handler
through a table, with `pc`, gas and the stack depth in argument registers.
Before, one ~60 KB dispatch loop kept that state live across ~160 arms, and
Cranelift's register allocator spilled a different part of it after each change.
The handlers need Sonatina's native tail calls, which Fe master
[`3587ff999`](https://github.com/argotorg/fe/tree/3587ff99982ca3dd5e0eaa93e8d143cacf64ee40)
pins (Sonatina `92df01a6`). Fe master replaces sbillig/fe's
`feat/generic-byte-order`, which FeVM main pins; it now carries that branch's
owned-value destruction, memory owners and byte-order reads.

On [ipsilon/evm-benchmarks](https://github.com/ipsilon/evm-benchmarks) `d8b88f4`
(27 cases), FeVM takes 0.57x main's time on x86_64 Linux and 0.52x on AArch64
macOS (geometric means). It beats revm on 25 cases on each host, and evmone on 17
on Linux and 20 on macOS.

| Host | Cases | FeVM / main | FeVM / revm: main | branch | FeVM / evmone: main | branch |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Linux x86_64 | main (14) | 0.65 | 1.16 | 0.75 | 1.41 | 0.91 |
| Linux x86_64 | all (27) | 0.57 | 1.03 | 0.59 | 1.33 | 0.76 |
| macOS AArch64 | main (14) | 0.57 | 1.07 | 0.61 | 1.69 | 0.96 |
| macOS AArch64 | all (27) | 0.52 | 1.14 | 0.59 | 1.58 | 0.81 |

"Main" cases are the full contracts: blake2b, sha1, snailtracer, structarray_alloc,
swap_math and weierstrudel. The rest are micro-benchmarks for jumps, memory
growth and SIGNEXTEND.

## Changes

- `dee19ce` Stack slots and memory, already checked by the interpreter, are
  accessed unchecked.
- `6ddd2c6` The stack, arithmetic, memory and jump opcodes run as tail-calling
  handlers; other opcodes return to `run_until_child`'s loop.
- `70a5a7d`, `52fef2b`, `35c4d16` Memory growth charges, binary results and
  out-of-buffer growth no longer give the hot handlers a stack frame.
- `59dd0f3` The stack depth is passed between handlers instead of stored to
  `Vm` and reloaded on every opcode.
- `704cbe7`, `df8f3b8` Division and modular opcodes, and each DUP and SWAP, get
  handlers of their own.
- `9bd35ce` Frames reuse their memory and stack buffers across transactions.
- `e490140` Pin Fe master `3587ff999`.
- `81c87f7` The soak ingot allows fevm's unsafe code. It sits outside the
  workspace, so Fe's unsafe trust rule rejected it, on main as well.

## Method

CPU µs per transaction from `native/bench/run.py`'s method
(`RUNS` applications minus `RUNS` setups, best of 3), O2 drivers. FeVM main is
`0027791` built with its pinned Fe `71ffd7ca4`; the branch is built with Fe
`3587ff999`. Both drivers produce the same output on every case. The revm and
evmone times are each host's last full `run.py` run, which also checked that
all three engines agree on every case's status, gas used and logs hash. revm
33.1.0 is built with fat LTO and `target-cpu=native` (on Linux with nightly
1.101.0, since stable 1.99.1's LLVM crashes compiling it for Zen 5); evmone v0.25.0 runs its
baseline interpreter, a Release build (with `-march=native` on Linux, where
its CMake still targets x86-64-v2).

- Linux: Ryzen 5 9600X (Zen 5), Ubuntu 26.04 ([results](linux-x86_64.jsonl)).
- macOS: Apple M1 Pro, macOS 15.6.1 ([results](macos-arm64.jsonl)).

On Zen 5, evmone's memory_grow cases stall on store-to-load forwarding (its ADD
stores four 8-byte limbs that DUP reloads with 16-byte loads), so FeVM's lead
there is larger than on AArch64.

### Linux x86_64

| Case | FeVM main µs | branch µs | revm µs | evmone µs | / main | / revm | / evmone |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| blake2b_huff/empty | 10.98 | 8.12 | 10.37 | 11.68 | 0.74 | 0.78 | 0.70 |
| blake2b_huff/8415nulls | 597.08 | 424.04 | 607.71 | 406.35 | 0.71 | 0.70 | 1.04 |
| blake2b_shifts/8415nulls | 5,459.31 | 3,922.30 | 5,885.10 | 3,876.29 | 0.72 | 0.67 | 1.01 |
| sha1_divs/empty | 43.50 | 18.24 | 26.75 | 29.50 | 0.42 | 0.68 | 0.62 |
| sha1_divs/5311 | 3,340.85 | 1,365.79 | 2,089.92 | 2,438.74 | 0.41 | 0.65 | 0.56 |
| sha1_shifts/empty | 20.92 | 14.31 | 23.87 | 15.55 | 0.68 | 0.60 | 0.92 |
| sha1_shifts/5311 | 1,609.53 | 1,068.84 | 1,906.32 | 1,230.49 | 0.66 | 0.56 | 0.87 |
| snailtracer/benchmark | 26,022.38 | 18,227.50 | 23,657.25 | 17,591.31 | 0.70 | 0.77 | 1.04 |
| structarray_alloc/nfts_rank | 413.44 | 223.13 | 444.57 | 239.29 | 0.54 | 0.50 | 0.93 |
| swap_math/spent | 3.24 | 2.34 | 2.72 | 2.04 | 0.72 | 0.86 | 1.15 |
| swap_math/received | 3.58 | 2.53 | 3.09 | 2.21 | 0.71 | 0.82 | 1.14 |
| swap_math/insufficient_liquidity | 2.65 | 1.98 | 2.22 | 1.75 | 0.75 | 0.89 | 1.13 |
| weierstrudel/1 | 132.73 | 95.25 | 83.35 | 96.77 | 0.72 | 1.14 | 0.98 |
| weierstrudel/15 | 1,260.16 | 889.13 | 804.16 | 933.79 | 0.71 | 1.11 | 0.95 |
| JUMPDEST_n0/empty | 586.55 | 292.77 | 679.23 | 292.30 | 0.50 | 0.43 | 1.00 |
| jump_around/empty | 17.18 | 8.20 | 17.26 | 14.87 | 0.48 | 0.48 | 0.55 |
| loop_with_many_jumpdests/empty | 8,848.09 | 4,425.31 | 10,301.18 | 4,421.30 | 0.50 | 0.43 | 1.00 |
| memory_grow_mload/nogrow | 33.23 | 16.38 | 37.60 | 34.46 | 0.49 | 0.44 | 0.48 |
| memory_grow_mload/by1 | 34.57 | 17.68 | 41.77 | 36.24 | 0.51 | 0.42 | 0.49 |
| memory_grow_mload/by16 | 37.77 | 18.62 | 47.84 | 42.25 | 0.49 | 0.39 | 0.44 |
| memory_grow_mload/by32 | 43.27 | 21.12 | 61.22 | 50.95 | 0.49 | 0.34 | 0.41 |
| memory_grow_mstore/nogrow | 33.65 | 17.32 | 43.58 | 36.26 | 0.51 | 0.40 | 0.48 |
| memory_grow_mstore/by1 | 35.28 | 20.91 | 39.69 | 38.78 | 0.59 | 0.53 | 0.54 |
| memory_grow_mstore/by16 | 40.13 | 22.25 | 47.26 | 41.59 | 0.55 | 0.47 | 0.53 |
| memory_grow_mstore/by32 | 45.60 | 23.01 | 50.74 | 45.05 | 0.50 | 0.45 | 0.51 |
| signextend/zero | 69.55 | 31.66 | 53.63 | 27.78 | 0.46 | 0.59 | 1.14 |
| signextend/one | 69.35 | 31.60 | 54.81 | 27.81 | 0.46 | 0.58 | 1.14 |

### macOS AArch64

| Case | FeVM main µs | branch µs | revm µs | evmone µs | / main | / revm | / evmone |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| blake2b_huff/empty | 17.63 | 10.64 | 18.16 | 15.06 | 0.60 | 0.59 | 0.71 |
| blake2b_huff/8415nulls | 1,002.68 | 578.07 | 1,088.94 | 547.91 | 0.58 | 0.53 | 1.06 |
| blake2b_shifts/8415nulls | 10,667.22 | 5,593.77 | 10,909.07 | 5,194.47 | 0.52 | 0.51 | 1.08 |
| sha1_divs/empty | 62.40 | 27.74 | 45.09 | 34.18 | 0.44 | 0.62 | 0.81 |
| sha1_divs/5311 | 4,818.76 | 2,110.81 | 3,558.13 | 2,618.70 | 0.44 | 0.59 | 0.81 |
| sha1_shifts/empty | 37.37 | 20.36 | 41.63 | 21.36 | 0.54 | 0.49 | 0.95 |
| sha1_shifts/5311 | 2,904.00 | 1,501.93 | 3,314.19 | 1,674.27 | 0.52 | 0.45 | 0.90 |
| snailtracer/benchmark | 39,160.25 | 24,900.75 | 42,341.50 | 22,146.23 | 0.64 | 0.59 | 1.12 |
| structarray_alloc/nfts_rank | 778.83 | 300.11 | 844.26 | 397.75 | 0.39 | 0.36 | 0.75 |
| swap_math/spent | 5.00 | 3.37 | 4.92 | 3.35 | 0.67 | 0.68 | 1.01 |
| swap_math/received | 5.45 | 3.50 | 5.40 | 3.61 | 0.64 | 0.65 | 0.97 |
| swap_math/insufficient_liquidity | 3.94 | 2.86 | 3.77 | 2.85 | 0.73 | 0.76 | 1.00 |
| weierstrudel/1 | 217.80 | 157.91 | 142.46 | 126.60 | 0.73 | 1.11 | 1.25 |
| weierstrudel/15 | 2,003.71 | 1,419.58 | 1,403.52 | 1,116.11 | 0.71 | 1.01 | 1.27 |
| JUMPDEST_n0/empty | 834.42 | 253.43 | 510.86 | 334.27 | 0.30 | 0.50 | 0.76 |
| jump_around/empty | 39.09 | 21.91 | 55.75 | 34.26 | 0.56 | 0.39 | 0.64 |
| loop_with_many_jumpdests/empty | 12,603.53 | 3,830.64 | 7,470.57 | 5,012.22 | 0.30 | 0.51 | 0.76 |
| memory_grow_mload/nogrow | 64.54 | 29.66 | 46.86 | 53.15 | 0.46 | 0.63 | 0.56 |
| memory_grow_mload/by1 | 67.97 | 30.67 | 49.77 | 54.36 | 0.45 | 0.62 | 0.56 |
| memory_grow_mload/by16 | 75.14 | 34.70 | 67.54 | 59.21 | 0.46 | 0.51 | 0.59 |
| memory_grow_mload/by32 | 77.98 | 36.00 | 82.27 | 70.15 | 0.46 | 0.44 | 0.51 |
| memory_grow_mstore/nogrow | 67.24 | 34.89 | 52.21 | 42.26 | 0.52 | 0.67 | 0.83 |
| memory_grow_mstore/by1 | 64.17 | 37.25 | 54.80 | 43.77 | 0.58 | 0.68 | 0.85 |
| memory_grow_mstore/by16 | 75.85 | 40.60 | 65.41 | 53.14 | 0.54 | 0.62 | 0.76 |
| memory_grow_mstore/by32 | 75.93 | 44.26 | 80.56 | 60.69 | 0.58 | 0.55 | 0.73 |
| signextend/zero | 97.43 | 42.97 | 65.23 | 63.87 | 0.44 | 0.66 | 0.67 |
| signextend/one | 97.80 | 43.67 | 69.03 | 64.59 | 0.45 | 0.63 | 0.68 |

## Acceptance

All seven stages pass on a clean `e490140` on both hosts
([Linux](linux-acceptance/acceptance.json), [macOS](macos-acceptance/acceptance.json)):

- 83 workspace tests at each of O0/O1/O2
- 38 CLI/allocator checks at each level
- 1,840 frame and 1,142 state comparisons at each level
- 74,676 arithmetic checks

Frames keep the three declared simultaneous-fault reason differences per level.
The Python harness's 13 tests and the Rust reference's nine tests also pass
(Linux).

## Cancun conformance

All 16,847 Cancun state tests of
[execution-spec-tests v5.4.0](https://github.com/ethereum/execution-spec-tests/releases/tag/v5.4.0)
pass with an O2 driver on Linux ([results](linux-conformance-results.json)).

## Resident memory

Peak RSS was 16.9 MB after 1,000 transactions and 17.0 MB after 40,000, at
`81c87f7` on Linux ([results](soak-results.json)).
