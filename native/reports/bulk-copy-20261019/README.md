# Bulk byte copies on Fe master `21db8bc23`

Fe master [`21db8bc23`](https://github.com/argotorg/fe/tree/21db8bc23f3e52dc9b4e037f11dfb64f2cf73fda)
adds `ByteBuffer::copy_from` ([argotorg/fe#1830](https://github.com/argotorg/fe/pull/1830)).
FeVM `c358704` uses it for call inputs and initcode, child output, RETURN/REVERT
data, CODECOPY, CALLDATACOPY, RETURNDATACOPY, EXTCODECOPY, code loading and log
data, instead of per-byte loops. Both compilers were built by `native/bootstrap.py`
with Rust 1.99.0 and `--features cranelift`
([Linux](linux-build.json), [macOS](macos-build.json)).

All seven acceptance stages pass on x86_64 Linux and AArch64 macOS 15.6.1
(`native/accept.py --check-only`): 76 workspace tests at each of O0/O1/O2, 35
CLI/allocator checks, 1,840 frame and 1,142 state comparisons per level, and
74,676 arithmetic checks ([Linux](linux-acceptance/acceptance.json),
[macOS](macos-acceptance/acceptance.json)). Linux stage times are inflated by
other work on the host during the run.

The execution-spec-tests v5.4.0 Cancun state tests give the same result as
before on both hosts: 16,800 of 16,847 pass and the other 47 exceed the 256-entry
state tables ([Linux](linux-conformance-results.json),
[macOS](macos-conformance-results.json)). On Linux with eight parallel cases the
run takes 46 s instead of 149 s; the summed case time falls from 1,025 s to
363 s, and the slowest case from 69 s (`static_Call50000`) to 12 s
(`ContractCreationSpam`).

The first build of this change failed 603 cases in worlds without any code: a
zero-length `copy_code` still addressed an arena record, and the bulk copy's
range check trapped. `copy_code` now returns before touching the arena for empty
ranges, with a regression test. The acceptance corpora did not cover that case.
