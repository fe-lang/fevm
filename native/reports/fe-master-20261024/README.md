# Fe master `fa06c6cd5`

Fe master [`fa06c6cd5`](https://github.com/argotorg/fe/tree/fa06c6cd5ba19cbf15da718fad80b84d79a569b9)
stores whole aggregate values and constants into objects
([argotorg/fe#1868](https://github.com/argotorg/fe/pull/1868),
[argotorg/fe#1869](https://github.com/argotorg/fe/pull/1869)) and pins Sonatina
[`fcdbdc4d`](https://github.com/fe-lang/sonatina/tree/fcdbdc4d8706f7b93415d605ed8e9aa277179f98)
([fe-lang/sonatina#435](https://github.com/fe-lang/sonatina/pull/435),
[fe-lang/sonatina#436](https://github.com/fe-lang/sonatina/pull/436)). Earlier
compilers copied aggregates into objects one leaf at a time; with `f69b911ce` the
evm test module's verification needed more than 14 GB at -O0 with default
threads. Both
compilers were built by `native/bootstrap.py` with Rust 1.99.0 and
`--features cranelift` ([Linux](linux-build.json), [macOS](macos-build.json)).

FeVM `f777822` includes the CALL frame-stack and transaction review fixes. All
seven acceptance stages pass on x86_64 Linux and AArch64 macOS 15.6.1
(`native/accept.py --check-only`): 80 workspace tests at each of O0/O1/O2, 39
CLI/allocator checks, 1,840 frame and 1,142 state comparisons per level, and
74,676 arithmetic checks ([Linux](linux-acceptance/acceptance.json),
[macOS](macos-acceptance/acceptance.json)). The Python harness's 13 tests and the
Rust reference's nine tests pass on Linux.

The workspace stages take 31-34 s per level on macOS, down from 305-312 s with
`21db8bc23` ([bulk-copy report](../bulk-copy-20261019/README.md)), and 24-30 s on
Linux. Building and running the evm ingot's 62 tests with default threads peaks at
1.0-1.3 GB of memory at each level on Linux.

The execution-spec-tests v5.4.0 Cancun state tests give the same result as before
on both hosts: 16,800 of 16,847 pass and the other 47 exceed the 256-entry state
tables ([Linux](linux-conformance-results.json),
[macOS](macos-conformance-results.json)). With eight parallel cases the run takes
46 s on Linux and 93 s on macOS.
