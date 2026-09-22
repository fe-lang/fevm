# FeVM native acceptance on x86_64 Linux

## Result

**Blocked before bootstrap.** The required private FeVM checkout could not be
accessed through the environment's existing GitHub authorization. Per the
acceptance instructions, no credential workaround was attempted and no build or
acceptance stage was run.

The access probe exited with status 128:

```text
$ git ls-remote https://github.com/fe-lang/fevm.git refs/heads/native-acceptance
fatal: unable to access 'https://github.com/fe-lang/fevm.git/': CONNECT tunnel failed, response 403
```

Required environment change: rerun this task in a Linux x86_64 environment whose
network proxy permits GitHub access and whose existing GitHub authorization can
read the private `fe-lang/fevm` repository and its `native-acceptance` branch.

## Host

- Kernel platform: `Linux` (`uname -s`, exit 0)
- Machine architecture: `x86_64` (`uname -m`, exit 0)
- Python: `3.12.13`
- Node.js: `v20.20.2`
- npm: `11.4.2`
- rustup: `1.29.0`
- Available default Rust compiler: `1.92.0` (not substituted for the required
  Rust `1.98.1`)
- CMake: `3.28.3`
- Host C compiler: Ubuntu GCC `13.3.0`
- Git, Cargo, linker, binutils, and gzip were present on `PATH`.

## Pinned inputs checked

- Original Fe checkout HEAD:
  `85e64e8404642eaddcdd1ec8d275d7c26ab7ac31`
- Fe `Cargo.lock` SHA-256:
  `bbb0e2a4e3a98c393c61658a98211c7d43aebd11b8de2a1f90e925809345b498`
- Required FeVM revision (not fetched):
  `cc5b1caffade446868fa1c24b15ef0596fce269a`
- Required Sonatina revision (not fetched):
  `61fa661c23bbeeeab024c4e9936656b7a73bd8f4`
- Required Rust toolchain (not installed or invoked): `1.98.1`
- Required Fe feature (not built): `cranelift`

## Stage status

| Stage | Status | Exit code / evidence |
| --- | --- | --- |
| Host and prerequisite discovery | Complete | Commands exited 0; npm emitted a non-fatal unknown `http-proxy` configuration warning |
| Verify original Fe HEAD | Complete | Exit 0; exact pinned commit matched |
| Verify Fe `Cargo.lock` | Complete | Exit 0; exact pinned digest matched |
| Probe private FeVM branch access | Failed | Exit 128; CONNECT tunnel returned HTTP 403 |
| Clone full FeVM history | Not run | Blocked by the required access probe |
| Inspect `native/README.md`, `native/toolchain.json`, `native/bootstrap.py`, and `native/accept.py` | Not run | Private checkout unavailable |
| Bootstrap | Not run | Private checkout unavailable |
| Acceptance (`--check-only`) | Not run | Bootstrap and private checkout unavailable |

## Intended commands (not run)

```sh
python3 native/bootstrap.py --out native/out/linux-bootstrap --toolchain 1.98.1 --fe-repository https://github.com/argotorg/fe.git --sonatina-repository https://github.com/sbillig/sonatina.git
python3 native/accept.py --build native/out/linux-bootstrap/build.json --out native/out/linux-acceptance --check-only
```

## Counts and artifacts

No workspace, CLI smoke, SwissTable differential, or arithmetic differential
cases ran, so all executed-case counts are zero. No `build.json`,
`acceptance.json`, result JSON, workspace log, compiler binary, raw assembly, or
private FeVM source was produced or copied into this repository.
