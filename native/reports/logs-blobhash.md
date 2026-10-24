# Logs and blob hashes

The implementation adds LOG0–LOG4 and BLOBHASH to the native interpreter.
Logs own copies of memory and ordered topics, follow nested checkpoint rollback,
and move into transaction receipts. Blob hashes are transaction inputs and remain
available across frame rollback. Static frames reject logs; zero-length LOG
ranges ignore full-width offsets; BLOBHASH compares full-width indices before
narrowing. Buffer growth failures preserve prior logical contents.

The state protocol is version 4. Its 1,142 deterministic cases include 405 new
log/blob cases, and compare logs after each step and at transaction settlement.
The revm reference reads real journal logs and derives the blob transaction type.
Protocol tests reject malformed logs and compare address, topic order and data.

## Current development compiler

[`logs-blobhash-toolchain.json`](logs-blobhash-toolchain.json) pins clean committed
Fe `c5dd6603d` and Sonatina `8d822fc3`, Rust 1.98.1. This includes final PR #1718
`2db9a38fa`, native reference/ownership/recursive-summary repairs, workspace and
root/callee analysis reuse, and indexed object-store invalidation. The local
integration commits require local repositories when bootstrapping.

An immutable all-feature compiler has SHA-256
`81aba7d928185bf579477bf391cbfe3f799e95d78c6208b7e75bb2faaadeb523`.
Five focused O1 native regressions for account/log buffers, local clobbers,
reference layouts and recursive unused effects pass with this binary.
The reduced real checkpoint probe also builds and executes successfully:
44.86 seconds wall, 44.80 seconds CPU, 1,669,316,608 bytes peak RSS on x86_64 Linux.
It verifies nested commit/rollback and final log ownership. This is one workload
measurement without a matched baseline, not a speedup claim.

## Acceptance status

The six focused Rust state-reference tests and nine Python state-contract/runner
tests pass, as do strict reference Clippy and nightly Rust formatting. A runner
regression reproduces and fixes a duplicate `timeout` keyword that prevented the
CLI build deadline from reaching subprocess execution. Source-only bootstrap
also verifies the current manifest's exact Fe/Sonatina revisions and lock hash.

The previous immutable Fe `2e2bc79c9` / Sonatina `ad45e18fb` compiler passed all
44 core native tests at O0 and O1. The O0 workspace check completed; the remaining
O1 workspace checks were stopped when testing was narrowed to targeted checks.
The full expanded CLI, 1,835-frame, 1,142-state and arithmetic matrix has not
completed for this milestone. O2 work is deferred. A separate full state-driver
O2 build exceeded an 8 GiB limit before executing any state cases.

Local evidence lives under `native/out/logs-blobhash-20261003/`: `acceptance-r4/`,
`candidate-o1-perf-r1/identity.json`, `o1-focused-native-r1/results.json`,
`checkpoints-o1-candidate-r1/result.json`, and `logs-commit-*.log`. Historical
acceptance records retain their original compiler identities. The default
`native/toolchain.json` still identifies the prior published-master checkpoint.

Call frames, contract creation/destruction, precompiles, complete transaction
processing, removal of remaining host table/input bounds and full Cancun
conformance remain subsequent work. This report does not mark FeVM complete.
