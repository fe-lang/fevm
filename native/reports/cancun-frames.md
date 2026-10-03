# Cancun frame acceptance

Historical status: **PASS on x86_64 Linux at FeVM `7f8f550`** for the
1,602-frame slice and all seven native acceptance stages of that revision.
**AArch64 macOS acceptance applies to `a078672`**, before the reference-build
reproducibility fixes. These records cover their stated revisions and older
compiler pin. The later frame/state suite is documented in the
[state-gas report](state-gas.md). These results do not establish full Cancun
conformance or acceptance of the current runner.

## Historical Linux acceptance — 2026-10-02

The complete suite was rerun using the updated reference runner and the same
pinned Fe `e51aebfc7027aa37eb81c7fc92046387a01998e2` and Sonatina
`61fa661c23bbeeeab024c4e9936656b7a73bd8f4` sources. The fresh bootstrap used local
Git repositories containing those exact commits and `native/toolchain.json`.
Host: x86_64 Linux, kernel 7.0.0-1014-azure, glibc 2.39.
Compiler SHA-256: `25350af4194360883785971978bc978175c5d8d322fa1e8149af4d1db04066cb`.

The frame record identifies clean FeVM commit
`7f8f55013d9d5354122bd83aec0a42c3f19d9e08`. Every recorded source hash matches
that revision, including runner SHA-256
`bacd2a3a80c8b91c28cb43163d0203d13df1595a453005d821ae4b44a9b4e07c`.
The interpreter, driver, corpus and reference sources also match the historical
macOS run; the runner, its regression tests and recorded toolchain manifest
identify the updated build procedure.

The reference record includes the selected `toolchain` (`1.98.1`), Rust/Cargo
versions, `target_directory` under the fresh run's `cancun-frames/reference-target`,
resolved revm Git identities and executable hash. Build and metadata commands
use `rustup run 1.98.1 cargo`; the build explicitly selects its target directory.
All seven acceptance stages exit zero and the report records `complete: true`.
The result totals are listed below; `--check-only` omits timing measurements.

- [Acceptance and compiler provenance](linux-x86_64-cancun-acceptance.json).
- [Frame results, reference identities and source hashes](linux-x86_64-cancun-frames.json).
- [CLI results](linux-x86_64-cancun-cli.json).
- [Arithmetic results](linux-x86_64-cancun-arithmetic.json).
- [SwissTable results](linux-x86_64-cancun-swisstable.json.gz), deterministic gzip.
- Workspace logs: [O0](linux-x86_64-cancun-workspace-O0.log), [O1](linux-x86_64-cancun-workspace-O1.log), [O2](linux-x86_64-cancun-workspace-O2.log).

```sh
python3 native/bootstrap.py --out native/out/cancun-linux-toolchain \
  --toolchain 1.98.1 --manifest native/toolchain.json \
  --fe-repository /path/to/fe --sonatina-repository /path/to/sonatina
python3 native/accept.py --build native/out/cancun-linux-toolchain/build.json \
  --out native/out/cancun-linux-acceptance --check-only
```

Check out `7f8f550` to reproduce this historical runner and its
`native/toolchain.json`; the current branch uses a later compiler and corpus.
Choose fresh output directories. The published records retain the literal paths
from this run; complete generated cases, compiler reports, IR, executables and
logs remain under `/tmp/fevm-pr1-review-checks/acceptance/`.

## Historical macOS sources and compiler

- Fe: `e51aebfc7027aa37eb81c7fc92046387a01998e2`, published as `argotorg/fe:fevm-native-acceptance-pinned`.
- Sonatina: `61fa661c23bbeeeab024c4e9936656b7a73bd8f4`.
- [Saved compiler manifest](cancun-toolchain.json); Rust 1.98.1, `cranelift`.
- Compiler SHA-256: `46798d53619da19404cf86afd25c1b676687c25c4f1c27204701fd014114bcc6`.
- Host: Apple M1 Pro, AArch64 macOS 15.6.1.
- Reference: [revm d613ef5735b9beb17acd53a5a1802ebc2198a18d](https://github.com/sbillig/revm/commit/d613ef5735b9beb17acd53a5a1802ebc2198a18d), based on the exact revm-interpreter 31.1.0 release source, explicitly configured for Cancun.
- Execution specification: `c335bc4e9e99f7b91024d9033bdc89ce54394848`.

The compiler was built from fresh exact-revision checkouts and copied to an
immutable executable. Its source and binary are unchanged from the preceding
checkpoint. At that checkpoint, Fe's standalone
[escape-decoding PR1563](https://github.com/argotorg/fe/pull/1563) targeted master;
the accepted native integration was separately published.
The manifest's historical publication branch describes its original build.

FeVM was based on `f32a238` with the reference pin, explicit stack anchors and
reference-provenance recording uncommitted during this run. The frame record
retains source hashes for the interpreter, driver, corpus, reference and lockfile;
all match FeVM `a078672e4d17611b40000692aba49dd34dd831c3`, which committed those
changes after the run. In particular, the recorded runner hash is
`aa94ab6e769630c91ea2459c0509e8befea7f25761b7d0d6e9705e691fe7e454`.
This historical record predates `7f8f550` and does not verify its explicit Rust
selection or target-directory handling; its reference metadata lacks those new
fields. Resolved reference package versions and Git identities are recorded
directly from Cargo metadata. To reproduce this historical runner, check out
`a078672` before running the command below.

## Results

Both the historical Linux run at `7f8f550` and macOS run at `a078672`
pass the following matrix.

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
charging. During the historical macOS acceptance, its full default workspace suite
passed 340 tests with one skip; the all-feature interpreter passed 31 tests,
and workspace documentation tests and strict interpreter Clippy passed.
The additional no-default-feature test build exposed two pre-existing missing-import errors in unchanged files. Per user
direction, those errors are recorded separately and left unchanged; FeVM uses
the default standard-library feature.

The acceptance command exits zero and records `complete: true`. Timing
measurements were omitted (`--check-only`); these results make no throughput claim.

## Historical macOS evidence and reproduction

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
The historical seven-stage gate is covered by the Linux run above.
The [Cloud handoff](../cloud-linux.md) retains instructions for the earlier baseline.
