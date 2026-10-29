# Osaka

FeVM now implements one fork, the current mainnet one: Osaka (Fusaka, mainnet
2025-12-03). The blob-parameter-only forks after it (BPO1, BPO2) change only the
blob schedule, which reaches FeVM as the block's blob base fee, and six blobs per
transaction fit every schedule since Prague. The cutover from Cancun is complete;
nothing selects an earlier fork.

The work sits on FeVM main `1f8f525` (tail-call dispatch), whose compiler it
keeps: Fe master `3587ff999` with Sonatina `92df01a6`, bootstrapped from
`toolchain.json` on x86_64 Linux ([build record](linux-build.json)). CLZ has a
dispatch handler like the other unary opcodes, at 5 gas.

## Changes

- `CLZ` (EIP-7939).
- Transactions: the EIP-7623 calldata floor, the EIP-7825 gas limit cap (2^24,
  which a host may raise through `BlockEnv.tx_gas_limit_cap`), six blobs per
  transaction (EIP-7594), and the signed chain ID.
- MODEXP: EIP-7883 pricing and EIP-7823's 1,024-byte length bounds.
- P256VERIFY at 0x100 (EIP-7951), on a four-limb Montgomery field generic over
  its modulus, which BN254 now shares.
- EIP-7702 set-code transactions. FeVM recovers each authority from its
  signature, applies the delegations before the call's checkpoint, and runs a
  delegated account's delegate code at the top level and in the CALL family.
- The seven BLS12-381 precompiles at 0x0b through 0x11 (EIP-2537), including the
  RFC 9380 maps to G1 and G2.
- Block-level EIPs (system contracts, requests, EIP-7918's excess blob gas) are
  outside FeVM's single-transaction scope.

## Conformance

All 14,693 Osaka state tests of execution-specs
[`tests@v21.0.1`](https://github.com/ethereum/execution-specs/releases/tag/tests%40v21.0.1)
that FeVM can run pass with an O2 driver on a clean `80e0ec7`
([results](linux-conformance-results.json)). The other 23 cases have malformed
transaction signatures; FeVM takes a recovered sender, so the runner reports
them as `signature` without running them. The fixtures use Osaka's blob
schedule, whose update fraction prices the blob base fee. With six parallel
cases, beside the acceptance run, the run took 4 s.

## Acceptance

All seven stages pass on a clean `80e0ec7`
([acceptance.json](linux-acceptance/acceptance.json)):

- 101 workspace tests at each of O0/O1/O2
- 38 CLI/allocator checks at each level
- 1,845 frame and 1,149 state comparisons with revm at Osaka, at each level
- 74,676 arithmetic checks

Frames keep the three declared simultaneous-fault reason differences per level.
The Python harness's 13 tests and the Rust reference's nine tests also pass. The
Osaka work has not run on AArch64 macOS. Peak RSS in the soak stays flat: 17.0 MB
after 1,000 transactions and 17.1 MB after 40,000. A sample of 315 EIP-7702 cases also
matched revm at Osaka in validity and gas, except a type-4 creation the fixture
rejects and revm's runner accepts.

## Benchmarks

Every transaction in [ipsilon/evm-benchmarks](https://github.com/ipsilon/evm-benchmarks)
sets a gas limit above the EIP-7825 cap (snailtracer uses 161 million gas), so
the bench runner lifts the cap. Under Osaka rules all 27 cases use the gas the
stored revm and evmone results record; those runners still execute Cancun rules.
Nothing was timed.
