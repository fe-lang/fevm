# Owned memory on Fe `a353e3cb1`

Fe [`a353e3cb1`](https://github.com/sbillig/fe/tree/a353e3cb1b68e42c7fc3cc80c3de60691be1e72d)
is branch `feat/owned-value-destruction` rebased onto Fe master `b89180311`. It
replaces [`999ff9562`](../owned-memory-20261020/README.md), which is no longer
on `sbillig/fe`. Its Cargo.lock pins Sonatina `73c7e0e2`, which adds a `bswap`
instruction (fe-lang/sonatina#418). FeVM `86bd0de` builds with it unchanged:
the compiler was bootstrapped from `toolchain.json` with `--features cranelift`
on x86_64 Linux ([build record](linux-build.json)).

Compiler changes since `999ff9562`:

- Native zero-size allocations take no host memory (Fe `5ce19f8b5`).
- `core::num::{to_be, from_be}` lower to Sonatina's `bswap` (Fe `e4a9bc4b9`). A
  u256 byte swap, which every native MLOAD/MSTORE and ABI word access pays, goes
  from 1,065 to 28 x86-64 instructions at O2.
- Fixes from two reviews of the branch. Destruction is now correct for deferred
  initialization, `zero()` on collections, zero-sized types, stores at dynamic
  indices and recursive owners on EVM. `Drop` is now rejected for any `Copy`
  type, and effects on `drop` are rejected.

Acceptance ran on FeVM `ae57454` with `toolchain.json` already changed to
`86bd0de`'s; the README is the only other difference. Conformance and the soak
ran on a clean `86bd0de`.

## Acceptance

All seven stages pass ([acceptance.json](linux-acceptance/acceptance.json)):

- 76 workspace tests at each of O0/O1/O2
- 35 CLI/allocator checks at each level
- 1,840 frame and 1,142 state comparisons at each level
- 74,676 arithmetic checks

Frames keep the three declared simultaneous-fault reason differences per level.
The Python harness's 13 tests and the Rust reference's nine tests also pass. This
compiler has not run on AArch64 macOS.

## Cancun conformance

All 16,847 Cancun state tests of
[execution-spec-tests v5.4.0](https://github.com/ethereum/execution-spec-tests/releases/tag/v5.4.0)
pass with an O2 driver ([results](linux-conformance-results.json)). With eight
parallel cases the run took 27 s. Host load was not controlled.

## Resident memory

Peak RSS was 13.8 MB after 1,000 transactions and 14.0 MB after 40,000
([results](soak-results.json)). Counting allocations through `LD_PRELOAD`,
1,000 transactions made 25,009 allocations and 25,008 frees. With `999ff9562`
they made 64,019 and 64,018; the difference is the zero-size allocations, which
no longer reach the host. The survivor is the same 96 bytes as before.
