# FeVM on Fe master

FeVM now builds with upstream Fe master
[`f69b911ce544c4fe72b2481adcafabf1d967a278`](https://github.com/argotorg/fe/tree/f69b911ce544c4fe72b2481adcafabf1d967a278),
whose Cargo.lock pins Sonatina `6bef907f7e5854d0c77cf18624b7042213526960`.
Master contains MVS, native `FixedStack`, and the FeVM compile-time work that
earlier milestones pinned from forks ([Fe #1799](https://github.com/argotorg/fe/pull/1799),
[Sonatina #412](https://github.com/fe-lang/sonatina/pull/412)). The committed
FeVM sources needed no changes; only [`toolchain.json`](toolchain.json) moves.

The compiler was built by `native/bootstrap.py` from fresh upstream checkouts with
Rust 1.99.0 and `--features cranelift` ([build record](build.json); compiler
SHA-256 `f6d5d7db4c07f4563ae7e604ac6958f82a61f190aa241e37eea2eedc3cf6ff00`).
Acceptance ran on an exact export of FeVM `bc4dfff` plus the new manifest, with
`native/accept.py --check-only`, one test suite and two Rayon workers.

| Stage | Result | Seconds |
| --- | --- | ---: |
| workspace O0 | 47 passed | 208.9 |
| workspace O1 | 47 passed | 200.2 |
| workspace O2 | 47 passed | 198.9 |
| CLI/allocator | 35 passed at each of O0/O1/O2 | 119.5 |
| Cancun frames | 1,840 passed at each of O0/O1/O2 | 42.6 |
| Cancun state | 1,142 passed at each of O0/O1/O2 | 219.0 |
| arithmetic | 74,676 checks across 48 builds | 12.0 |

Frames keep the three declared simultaneous-fault reason differences per level.
The Python harness's 13 tests and the Rust reference's nine tests also pass.
The standalone [Keccak](https://github.com/fe-lang/keccak) and
[SwissTable](https://github.com/fe-lang/swisstable) libraries pass their native
suites on the same compiler; both `main` branches now carry their MVS ports.

Scope is unchanged from earlier checkpoints: these corpora exclude CALL/CREATE
execution, full Cancun conformance and AArch64 macOS execution.
Stage logs, per-stage `results.json` and the acceptance record are in
[`acceptance/`](acceptance/).
