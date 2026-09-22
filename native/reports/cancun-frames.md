# Cancun frame acceptance

Status: **PASS on AArch64 macOS** for the bounded frame slice and all seven
native acceptance stages. This does not establish full Cancun conformance.

## Sources and compiler

- Fe: `e51aebfc7027aa37eb81c7fc92046387a01998e2`, published as `argotorg/fe:fevm-native-acceptance-pinned`.
- Sonatina: `61fa661c23bbeeeab024c4e9936656b7a73bd8f4`.
- [Saved compiler manifest](cancun-toolchain.json); Rust 1.98.1, `cranelift`.
- Compiler SHA-256: `46798d53619da19404cf86afd25c1b676687c25c4f1c27204701fd014114bcc6`.
- Host: Apple M1 Pro, AArch64 macOS 15.6.1.
- Reference: [revm d613ef5735b9beb17acd53a5a1802ebc2198a18d](https://github.com/sbillig/revm/commit/d613ef5735b9beb17acd53a5a1802ebc2198a18d), based on the exact revm-interpreter 31.1.0 release source, explicitly configured for Cancun.
- Execution specification: `c335bc4e9e99f7b91024d9033bdc89ce54394848`.

The compiler was built from fresh exact-revision checkouts and copied to an
immutable executable. Its source and binary are unchanged from the preceding
checkpoint. Fe's standalone [escape-decoding PR1563](https://github.com/argotorg/fe/pull/1563)
now targets master; the accepted native integration remains separately published.
The manifest's historical publication branch describes its original build.

FeVM was based on `f32a238` with the reference pin, explicit stack anchors and
reference-provenance recording uncommitted during this run. The frame record
retains source hashes for the interpreter, driver, corpus, reference and lockfile;
all match the committed implementation. Resolved reference package versions and
Git identities are recorded directly from Cargo metadata.

## Results

| Gate | Result |
| --- | --- |
| FeVM workspace | 12 passed at each of O0/O1/O2 |
| CLI smoke | 10 passed at each of O0/O1/O2 |
| Cancun frame corpus | 1,602 passed at each of O0/O1/O2; 4,806 comparisons |
| Arithmetic matrix | 74,676 cases across 48 builds passed |
| SwissTable matrix | 2,004 scenarios across 12 builds passed |

The frame corpus includes 9 initial specification anchors, 167 packed arithmetic
frames, 593 PUSH cases, 704 jump cases, 121 stack cases and 8 frame/output cases.
All stack cases now have independent expected results, including successful
DUP/SWAP values, insufficient depth, full-capacity DUP and genuine PUSH overflow.
The reference must agree with those anchors before any FeVM comparison runs.

The isolated reference correction preserves successful instruction paths and gas
charging. Its full default workspace suite passes 340 tests with one skip; the
all-feature interpreter passes 31 tests, and workspace documentation tests and
strict interpreter Clippy pass. The additional no-default-feature test build
exposes two pre-existing missing-import errors in unchanged files. Per user
direction, those errors are recorded separately and left unchanged; FeVM uses
the default standard-library feature.

The acceptance command exits zero and records `complete: true`. Timing
measurements were omitted (`--check-only`); these results make no throughput claim.

## Retained evidence and reproduction

- [Acceptance and compiler provenance](macos-arm64-cancun-acceptance.json).
- [Frame results, reference identities and source hashes](macos-arm64-cancun-frames.json).
- [CLI results](macos-arm64-cancun-cli.json).
- [Arithmetic results](macos-arm64-cancun-arithmetic.json).
- [SwissTable results](macos-arm64-cancun-swisstable.json.gz), deterministic gzip.
- Workspace logs: [O0](macos-arm64-cancun-workspace-O0.log), [O1](macos-arm64-cancun-workspace-O1.log), [O2](macos-arm64-cancun-workspace-O2.log).

```sh
python3 native/accept.py --build native/out/escape-toolchain/build.json \
  --out native/out/cancun-reference-acceptance --check-only
```

Choose a fresh output directory when repeating the command. Complete generated
cases, compiler reports, IR, executables and logs remain under
`/Users/sean/code/fevm/native/out/cancun-reference-acceptance/`.
The original failure remains under `native/out/cancun-escape-acceptance/`: 1,475
O0 frames matched before revm misclassified DUP/SWAP underflow as overflow.
The earlier JSON-escape failure remains under `native/out/cancun-frames/`.
No adapter error normalization or case removal was used to pass either gate.

## Remaining scope

The frame runner compares halt categories, successful/reverted stacks and output.
Memory/range semantics, gas accounting, external state, rollback and nested
execution remain subsequent work. The next memory slice has separate retained
probes for the already known MSIZE, source-offset and zero-length-copy gaps;
those cases are outside this accepted corpus.

The original six-stage native baseline has [passed on x86_64 Linux](linux-baseline-2026-09-22/README.md).
That run used Fe 85e64e840 and predates the escape fix and expanded frame corpus.
The expanded gate still requires a separate Linux run; see [the Cloud handoff](../cloud-linux.md).
