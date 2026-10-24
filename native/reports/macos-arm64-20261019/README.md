# AArch64 macOS acceptance and conformance

FeVM `25d506c` on AArch64 macOS 15.6.1 (mb16), with Fe master `f69b911ce` built by
`native/bootstrap.py` from fresh upstream checkouts with Rust 1.99.0 and
`--features cranelift` ([build record](build.json); compiler SHA-256
`51958f3f242d5d025fdf2b34ed946fd0a6794f738ab96673c98cccd27e883d2d`).

All seven native acceptance stages pass (`native/accept.py --check-only`):

| Stage | Result | Seconds |
| --- | --- | ---: |
| workspace O0 | 75 passed | 388 |
| workspace O1 | 75 passed | 415 |
| workspace O2 | 75 passed | 375 |
| CLI/allocator | 35 passed at each of O0/O1/O2 | 304 |
| Cancun frames | 1,840 passed at each of O0/O1/O2 | 193 |
| Cancun state | 1,142 passed at each of O0/O1/O2 | 376 |
| arithmetic | 74,676 checks across 48 builds | 37 |

The execution-spec-tests v5.4.0 Cancun state tests give the same result as on
x86_64 Linux: 16,800 of 16,847 pass and the other 47 exceed the 256-entry state
tables ([results](conformance-results.json), 336 s with six parallel cases).
An earlier run of `6526ce2`, before the remaining precompiles, also passed all
seven acceptance stages on this host.
