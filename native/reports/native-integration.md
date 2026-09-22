# Native integration acceptance: AArch64 macOS

The pinned native compiler passes all current FeVM acceptance checks at O0/O1/O2:

- 12 workspace tests at each level, including EVM state and SwissTable tests.
- 10 CLI smoke cases at each level, including the formerly crashing empty input.
- 74,676 arithmetic differential cases across 48 builds.
- 2,004 SwissTable differential scenarios across 12 builds.

This establishes native execution for the current application and corpora.
Linux execution and Cancun conformance remain pending; these checks do not
measure production EVM throughput.

## Provenance

Fe `85e64e8404642eaddcdd1ec8d275d7c26ab7ac31` pins Sonatina
`61fa661c23bbeeeab024c4e9936656b7a73bd8f4`
([PR #321](https://github.com/fe-lang/sonatina/pull/321)). The compiler was built
from fresh, detached source checkouts with the locked dependencies and generated
parser. Only Cargo build artifacts were reused. Its version is
`fe 26.3.0 (85e64e840)` and SHA-256 is
`8f6d4def9bcc5d093b7f898b17863246c275e7b36df86c3a9f9af5781d446789`.
The [saved manifest](integration-toolchain.json) and
[acceptance record](macos-arm64-integration-acceptance.json) retain exact inputs,
host tools, compiler build time, and each acceptance stage's result.

FeVM's program and harness sources match `35201718e401481d1cbe5bf378089527ad2f8027`.
The manifest and report files were uncommitted during acceptance, so the corpus
records correctly retain their dirty-worktree flags. The recorded source hashes
identify the tested inputs; no FeVM program or harness source changed for this fix.

Sonatina's all-feature release suite passed 1,609 tests with one configured skip,
plus 296 filechecks and doctests. Fe's all-feature release suite passed 3,406 tests
with one configured skip. Nightly formatting and strict workspace/all-target
Clippy passed; Fe was checked with defaults and all features.

## Aggregate construction fix

Previously, each native `insert_value` allocated and copied an entire aggregate.
A 4,096-byte initialization consequently required roughly 16 MiB of stack at O0.
The fix continues construction in the preceding insert's storage only when it
has one consumer in the same block. Other readers, arguments, and extracted views
retain independent snapshots. Object lifetime and escape checks are unchanged.

The [pre-fix developer-build record](macos-arm64-aggregate-construction-before.json)
retains the original binary hash and failing empty-input result. Comparing that
build with the pinned compiler on the unchanged FeVM source gives:

| O0 artifact | Before | After |
|---|---:|---:|
| Executable text | 142,412,840 bytes | 8,547,508 bytes |
| `parse_hex_program` stack subtraction | `0x10336b0` (16.2 MiB) | `0x2e590` (185 KiB) |
| Empty-bytecode CLI | SIGSEGV | Pass |

The process stack limit and FeVM capacities were unchanged. The original standalone
4,096-byte reproduction also passes O0/O1/O2, with retained development artifacts
in `/private/tmp/fevm-native-array-stack-fixed`.

## Current CLI artifacts

| Level | Build seconds | Text bytes | Executable bytes |
|---|---:|---:|---:|
| O0 | 84.79 | 8,547,508 | 8,747,992 |
| O1 | 138.75 | 6,532,532 | 6,707,592 |
| O2 | 174.63 | 6,532,532 | 6,707,592 |

These are single build observations, including report emission, on a shared
development machine. They are not controlled compiler-speed measurements.
The acceptance run used `--check-only`; no runtime timing comparison was made.

## Records and reproduction

- [CLI cases, artifact sizes, and hashes](macos-arm64-integration-cli.json).
- [Arithmetic cases and source hashes](macos-arm64-integration-arithmetic.json).
- [SwissTable cases, probes, and source hashes](macos-arm64-integration-swisstable.json.gz).
- Workspace output at [O0](macos-arm64-integration-workspace-O0.log),
  [O1](macos-arm64-integration-workspace-O1.log), and
  [O2](macos-arm64-integration-workspace-O2.log).

The clean compiler and build record remain in
`/private/tmp/fevm-native-construction-bootstrap`; generated sources, IR, objects,
assembly, binaries, and logs remain in
`/private/tmp/fevm-native-construction-acceptance`.
Use `native/bootstrap.py --manifest native/reports/integration-toolchain.json`
and `native/accept.py --check-only` as documented in the [native README](../README.md).
Unpublished Fe commits must be supplied through a local repository or Git bundle.
