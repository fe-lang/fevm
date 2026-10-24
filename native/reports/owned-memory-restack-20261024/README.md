# Owned memory on Fe `0f2218d38`, restacked onto FeVM main

Fe [`0f2218d38`](https://github.com/sbillig/fe/tree/0f2218d38091eefc9034e7bb91bb76ecda122252)
is branch `feat/owned-value-destruction` rebased onto Fe master `fa06c6cd5`, the
compiler FeVM main pins. It replaces
[`a353e3cb1`](../owned-memory-rebase-20261020/README.md). Its Cargo.lock pins
Sonatina `fcdbdc4d`, as master's does. The compiler was bootstrapped from
`toolchain.json` with `--features cranelift` on x86_64 Linux, from a local Fe
repository holding the pinned commit ([build record](linux-build.json)).

`owned-memory` is restacked onto FeVM main `43d58c4`. Main's changes since
`2209cb0` are carried into the port:

- Child frames are boxed, as in `37d1a08`, now in a `MemVec<Box<Frame>>`: frame
  storage grows with call depth and a frame never moves. The calls fixture's
  controlled allocator sees one box per child (the slot list stays far below its
  32,769-byte threshold), so it fails each of the two boxes in turn.
- Blob hashes outside blob transactions are rejected, call targets are touched
  without value, removed accounts lose their storage, and a failed fee payment
  returns the pre-state (`7b645df`..`234a1ca`). Tables grow, so fee payment fails
  only on allocation; main's full-account-table test becomes a growth test in
  which the absent coinbase is added and paid.

Compiler changes since `a353e3cb1`, besides Fe master's own: fixes from two more
reviews of the branch. Product parameters and value patterns destroy exactly
their unbound owned parts, an effect-free EVM `drop` still destroys its fields,
an irrefutable `if let` or `while let` over an owner compiles, and Sonatina
fe-lang/sonatina#432 stops a reference packed beside an owner from counting as
an escape.

## Acceptance

All seven stages pass on a clean `52d9d91`
([acceptance.json](linux-acceptance/acceptance.json)):

- 80 workspace tests at each of O0/O1/O2
- 38 CLI/allocator checks at each level
- 1,840 frame and 1,142 state comparisons at each level
- 74,676 arithmetic checks

Frames keep the three declared simultaneous-fault reason differences per level.
The Python harness's 13 tests and the Rust reference's nine tests also pass. This
compiler has not run on AArch64 macOS.

## Cancun conformance

All 16,847 Cancun state tests of
[execution-spec-tests v5.4.0](https://github.com/ethereum/execution-spec-tests/releases/tag/v5.4.0)
pass with an O2 driver ([results](linux-conformance-results.json)). FeVM main on
Fe master passes 16,800; the other 47 fill a fixed-capacity table. With eight
parallel cases the run took 25 s. Host load was not controlled.

## Resident memory

Peak RSS was 13.8 MB after 1,000 transactions and 14.0 MB after 40,000
([results](soak-results.json)). Counting allocations through `LD_PRELOAD`,
1,000 transactions made 27,009 allocations and 27,008 frees. With `a353e3cb1`
they made 25,009 and 25,008; each transaction's one CALL now also allocates its
frame box and the frame list's slots. The survivor is the same 96 bytes as
before.
