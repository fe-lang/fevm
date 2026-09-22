# FeVM native acceptance on x86_64 Linux

## Result

**Incomplete: blocked before checkout and execution.** The Cloud network proxy rejected
anonymous HTTPS access to the now-public FeVM repository. The required Rust 1.98.1
toolchain was also unavailable locally, and the same network environment prevented
`rustup` from downloading it. No pins were changed, no substitute toolchain was used,
and no acceptance stage was run.

## Host and prerequisites

Recorded on 2026-09-22 UTC for the requested `2026-09-21` evidence directory.

| Item | Observed value | Status |
| --- | --- | --- |
| Kernel / architecture | `Linux` / `x86_64` | Satisfies target host |
| Git | `/usr/bin/git` | Available |
| Python | `3.12.13` | Available; satisfies Python >=3.10 |
| Node / npm | `v20.20.2` / `11.4.2` | Available |
| rustup | `1.29.0` | Available |
| Rust 1.98.1 | Not installed; download blocked | **Blocked** |
| CMake | `3.28.3` | Available |
| C compiler | GCC `13.3.0` via `/usr/bin/cc` | Available |
| Linker / binutils | `/usr/bin/ld` | Available |

The installed Rust toolchains range from 1.83.0 through 1.95.0 (with gaps only as
shown by `rustup toolchain list`); 1.98.1 is not installed. The active/default
toolchain is Rust 1.92.0, and it was not substituted for the required toolchain.

## Exact inputs verified or requested

| Input | Pin | Verification |
| --- | --- | --- |
| Fe | `85e64e8404642eaddcdd1ec8d275d7c26ab7ac31` | Original checkout `HEAD` matches |
| Fe branch | `fevm-native-integration` | Pin supplied by owner; checkout is on local branch `work` at the exact commit |
| Fe `Cargo.lock` SHA-256 | `bbb0e2a4e3a98c393c61658a98211c7d43aebd11b8de2a1f90e925809345b498` | Matches |
| FeVM | `cc5b1caffade446868fa1c24b15ef0596fce269a` on `native-acceptance` | Not fetched; proxy blocked public branch query |
| Sonatina | `61fa661c23bbeeeab024c4e9936656b7a73bd8f4` on `fix-native-aggregate-construction` | Not fetched because the required early FeVM access check failed |
| Rust | `1.98.1` | Not installed; proxy blocked download |
| Fe feature | `cranelift` | Not run |

## Commands, exit codes, and failure excerpts

### Host inspection (exit 0)

```console
$ uname -s
Linux
$ uname -m
x86_64
$ python3 --version
Python 3.12.13
$ node --version
v20.20.2
$ npm --version
11.4.2
$ cmake --version
cmake version 3.28.3
$ cc --version
cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
```

### Original Fe pin and lockfile (exit 0)

```console
$ git rev-parse HEAD
85e64e8404642eaddcdd1ec8d275d7c26ab7ac31
$ sha256sum Cargo.lock
bbb0e2a4e3a98c393c61658a98211c7d43aebd11b8de2a1f90e925809345b498  Cargo.lock
```

### Public FeVM branch access (exit 128)

```console
$ git ls-remote https://github.com/fe-lang/fevm.git refs/heads/native-acceptance
fatal: unable to access 'https://github.com/fe-lang/fevm.git/': CONNECT tunnel failed, response 403
```

No authentication or network-control bypass was attempted.

### Required Rust installation (exit 1)

```console
$ rustup toolchain install 1.98.1 --profile minimal
info: syncing channel updates for 1.98.1-x86_64-unknown-linux-gnu
error: could not download file from 'https://static.rust-lang.org/dist/channel-rust-1.98.1.toml.sha256' to '/root/.rustup/tmp/5d23d98wh8qhupx2_file': error downloading file: error sending request for url (https://static.rust-lang.org/dist/channel-rust-1.98.1.toml.sha256): client error (Connect): tunnel error: unsuccessful
```

The temporary rustup filename is included only as the exact observed error; it is
not a durable artifact or a required path.

## Stage accounting

| Stage | Status | Exit code / counts |
| --- | --- | --- |
| Public FeVM branch preflight | **Failed** | Exit 128; CONNECT tunnel HTTP 403 |
| Install/probe Rust 1.98.1 | **Failed** | Exit 1; proxy tunnel unsuccessful |
| Full-history FeVM clone and detached pin verification | **Not run** | Blocked by preflight |
| Inspect `native/README.md`, `native/toolchain.json`, `native/bootstrap.py`, `native/accept.py` | **Not run** | FeVM checkout unavailable |
| Bootstrap | **Not run** | No `build.json`; zero build counts |
| Acceptance `--check-only` | **Not run** | No `acceptance.json`; zero workspace, CLI, SwissTable, and arithmetic counts |

Because bootstrap never started, there are no compiler binaries, parser outputs,
workspace logs, CLI/arithmetic JSON, SwissTable JSON, `build.json`, or
`acceptance.json` to preserve or copy. No generated artifacts were fabricated.

## Required environment change

Permit ordinary anonymous HTTPS CONNECT access to at least
`github.com`/`githubusercontent.com` and `static.rust-lang.org`, or preinstall the
exact Rust 1.98.1 toolchain and provide a complete full-history clone of the exact
public FeVM repository. Then rerun the two pinned commands without modifying
manifests, revisions, optimization levels, or cases.
