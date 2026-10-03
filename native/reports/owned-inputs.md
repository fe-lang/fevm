# Owned code and calldata

`Program` and `InputData` now own growable byte buffers, removing their 4 KiB
limits. Code stays immutable with its instruction-boundary jump map. `Vm::run`
borrows reusable inputs; `run_owned`, `execute` and `execute_vm` consume and
release one-shot inputs. Parsing failures and allocation failures release their
buffers, and the VM rejects failed inputs before opening a checkpoint.

The CLI and differential drivers use the new API. State protocol v4 keeps its
two-byte field lengths but no longer imposes a 4 KiB total packet limit. Five
large-input cases bring the stateless corpus to 1,840 frames.

## Targeted O1 evidence

The input/parser probe passes 14 execution checks: 50,000-byte parsing,
independent copies, PUSH/jump boundaries, malformed hex, and controlled code
and jump-map allocation failures with exact release checks. Its build takes
2.17 seconds and peaks at 221.4 MB RSS.

The production-module VM probe executes three integration tests successfully:

- Reuse owned 9,001-byte calldata across two borrowed-input runs.
- Reject failed code or calldata before checkpointing and preserve transaction setup.
- Execute code beyond 8 KiB, including valid jumps and rejection of PUSH data as a destination.

That build takes 174.09 seconds wall / 174.06 seconds CPU and peaks at
2,415,714,304 bytes RSS on x86_64 Linux, with profiling disabled and one Rayon
thread. The preceding compiler timed out at 180 seconds before execution;
that censored result does not establish a percentage speedup.

Three selected Rust reference tests, 13 Python harness tests, and five
specification-derived large-input reference anchors pass. Nightly Rust
formatting and strict all-target release reference Clippy pass. The five anchors
were checked against revm; they have not been run through the updated FeVM
differential driver. The focused VM tests above exercise the corresponding code,
calldata and jump behavior directly.

## Compiler identity

[`owned-inputs-toolchain.json`](owned-inputs-toolchain.json) pins committed Fe
`78710ce5e4c0dfb199abbc1b586c5665cc6ff07d` and Sonatina
`8d822fc38bbed86c5b5646eba6d713521e2ff2c9`, Rust 1.98.1. These local integration
revisions require local repositories when bootstrapping. Source-only bootstrap
verifies both revisions and the Cargo lock hash.

The measured immutable compiler has SHA-256
`6621adaa679a00bb14f769064cd77753e99e926f425ac49770419bacbca56316`.
It was built from Fe `9d5f6bb9dff9df2b220ae1b8eac6b33aac5b2c6f` plus patch
`5086f3e2d78651d4f6aec8447baf90a230da9532627e2bd234d6f049039cf083`,
which exactly matches the subsequent commit `78710ce5e`. Its version banner
therefore identifies `9d5f6bb9d`. The build enables all CLI features; the manifest
selects the same set through default features plus `cranelift,borrowck-profile`.

Local artifacts are under `native/out/owned-inputs-20261003/`:
`inputs-feedback-clause-cache-r1/result.json`,
`vm-feedback-clause-cache-r1/result.json`, `owned-input-reference.json`,
`reference-tests.log`, `python-tests.log`, and
`scaling/feedback-clause-cache-candidate/identity.json`. Probe records include
source, runner, compiler and executable hashes.

The full workspace, CLI and differential suites remain deferred; O2 and macOS
have not been checked for this change. Historical acceptance records retain their
original pins. CALL-family execution, creation/destruction, precompiles and full
transaction processing remain subsequent milestones.
