# FeVM native acceptance on x86_64 Linux (2026-09-22)

## Result

**Complete: PASS.** Anonymous Git smart-HTTP access worked after POST was enabled,
the exact pinned compiler bootstrapped, and every acceptance stage exited zero.
This verifies the pinned native baseline on this Linux host. It does not establish
Cancun conformance or production EVM performance.

## Host and prerequisites

- Host: `Linux-6.18.44-x86_64-with-glibc2.39` (`uname -s`: `Linux`; `uname -m`:
  `x86_64`). The suite executed natively; it was not a cross-compilation run.
- Git: `2.43.0`.
- Python: `3.12.13`.
- Node/npm: `v20.20.2` / `11.4.2`.
- Rustup: `1.29.0` at initial inspection; it installed the required toolchain
  successfully. The build used `rustc 1.98.1 (48a229cea 2026-09-01)` and
  `cargo 1.98.1 (797e8a9bc 2026-08-05)`. The pre-existing default Rust 1.95.0
  and installed Rust 1.92.0 were not substituted.
- CMake: `3.28.3`.
- C compiler: `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`.
- Binutils: GNU `ld`, `size`, and `objdump` 2.42.

## Connectivity and exact inputs

No proxy bypass, credentials, sandbox weakening, revision substitution, or
manifest change was used.

- `git ls-remote https://github.com/fe-lang/fevm.git refs/heads/native-acceptance`
  exited 0 and reported branch tip
  `5fc564e112c4d703f6b5971c0c0d3debd2c82d49`.
- A full anonymous clone from `https://github.com/fe-lang/fevm.git` exited 0.
  The clone was detached at the requested ancestor
  `cc5b1caffade446868fa1c24b15ef0596fce269a`, and `git rev-parse HEAD`
  matched it.
- Bootstrap fetched and detached Fe at
  `85e64e8404642eaddcdd1ec8d275d7c26ab7ac31` from
  `https://github.com/argotorg/fe.git`.
- Bootstrap fetched and detached Sonatina at
  `61fa661c23bbeeeab024c4e9936656b7a73bd8f4` from
  `https://github.com/sbillig/sonatina.git`.
- Fe `Cargo.lock` SHA-256 was
  `bbb0e2a4e3a98c393c61658a98211c7d43aebd11b8de2a1f90e925809345b498`.
- Feature: `cranelift`.

The short smart-HTTP records are preserved in `connectivity/`. The FeVM clone
and all generated artifacts remain in the persistent workspace at
`/workspace/fevm-native-acceptance/fevm`.

## Commands and exit codes

After inspecting `native/README.md`, `native/toolchain.json`,
`native/bootstrap.py`, and `native/accept.py`, these requested commands were run
from the exact detached FeVM checkout:

```console
python3 native/bootstrap.py --out native/out/linux-bootstrap --toolchain 1.98.1 --fe-repository https://github.com/argotorg/fe.git --sonatina-repository https://github.com/sbillig/sonatina.git
# exit 0

python3 native/accept.py --build native/out/linux-bootstrap/build.json --out native/out/linux-acceptance --check-only
# exit 0
```

The compiler build completed in 1457.848 seconds. Its immutable copied binary
identified itself as `fe 26.3.0 (85e64e840)` and had SHA-256
`66dc8e715be3f9ab13b498abb676c9fcbad7b872b0bf174ff78ca887e38ec7d9`.
No binary or assembly is included in this evidence directory.

The initial bootstrap log redirection was opened before its parent `native/out`
existed, so `tee` reported `No such file or directory`; bootstrap itself
continued and exited 0. The durable `bootstrap-excerpt.log` records that logging
condition and the observed fetch/build completion lines. `build.json` is the
authoritative complete bootstrap record. Acceptance stdout/stderr was captured
successfully in `acceptance-run.log`; individual stage output is preserved in
the copied logs and result JSON.

## Acceptance counts

| Stage | Exit | Observed coverage | Duration |
| --- | ---: | --- | ---: |
| Workspace O0 | 0 | 12 passed, 0 failed | 210.917 s |
| Workspace O1 | 0 | 12 passed, 0 failed | 675.117 s |
| Workspace O2 | 0 | 12 passed, 0 failed | 649.647 s |
| CLI smoke | 0 | 10 cases at each of O0/O1/O2 (30 total) | 987.600 s |
| SwissTable differential | 0 | 2,004 scenarios across 12 builds | 128.177 s |
| Arithmetic differential | 0 | 74,676 cases across 48 builds | 153.180 s |

`acceptance.json` has `complete: true`; the CLI, SwissTable, and arithmetic
records also each have `complete: true`. There were no failed or not-run stages.
SwissTable timing comparisons are intentionally absent because this shared-host
run used `--check-only`.

## Included evidence

- `build.json`: completed bootstrap record.
- `acceptance.json`: completed top-level acceptance record.
- `cli-results.json`: CLI build and per-case results.
- `arithmetic-results.json`: arithmetic build and correctness results.
- `swisstable-results.json.gz`: deterministic gzip-compressed SwissTable record.
- `workspace-O0.log`, `workspace-O1.log`, `workspace-O2.log`: complete workspace
  test logs.
- `cli-smoke.log`, `swisstable-differential.log`, `arithmetic.log`: complete
  stage logs.
- `acceptance-run.log`: acceptance driver stdout/stderr and exit status.
- `bootstrap-excerpt.log`: available bootstrap/fetch/build excerpts and logging
  note.
- `connectivity/ls-remote.log`, `connectivity/clone.log`: anonymous Git probe
  and clone records.

The JSON records are preserved verbatim. Absolute paths within them refer to the
persistent FeVM artifact workspace and are not credentials or secrets.
