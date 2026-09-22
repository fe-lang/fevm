# FeVM native Linux acceptance: blocked before checkout

## Result

**Incomplete — blocked during the required public-repository access preflight.**

The host can reach ordinary public GitHub web pages and the Rust distribution
server, but anonymous Git smart-HTTP reads through the environment proxy fail
with HTTP 403. In accordance with the acceptance instructions, no proxy bypass
was attempted. The FeVM checkout, bootstrap, and acceptance runner were not run.

## Host and prerequisites observed

- Date observed: 2026-09-22 UTC
- Host: `Linux`, `x86_64`
- Original Fe checkout HEAD: `85e64e8404642eaddcdd1ec8d275d7c26ab7ac31`
- Git: 2.43.0
- Python: 3.12.13
- Node: 20.20.2
- npm: 11.4.2
- rustup: 1.29.0
- Installed active Rust: 1.95.0
- Required Rust 1.98.1: not installed; its distribution manifest was reachable
- CMake: 3.28.3
- Host C compiler: GCC 13.3.0
- `ld` and `gzip`: available

The environment was not allowed to substitute the installed Rust 1.95.0 (or
the also-installed Rust 1.92.0) for the pinned Rust 1.98.1.

## Exact pinned inputs

- Fe: `https://github.com/argotorg/fe.git`, branch
  `fevm-native-integration`, commit
  `85e64e8404642eaddcdd1ec8d275d7c26ab7ac31`
- FeVM: `https://github.com/fe-lang/fevm.git`, branch `native-acceptance`,
  commit `cc5b1caffade446868fa1c24b15ef0596fce269a`
- Sonatina: `https://github.com/sbillig/sonatina.git`, branch
  `fix-native-aggregate-construction`, commit
  `61fa661c23bbeeeab024c4e9936656b7a73bd8f4`
- Expected Fe `Cargo.lock` SHA-256:
  `bbb0e2a4e3a98c393c61658a98211c7d43aebd11b8de2a1f90e925809345b498`
- Rust: 1.98.1
- Fe feature: `cranelift`

## Network probes

Ordinary HTTPS access worked:

```text
$ curl -I --max-time 20 https://github.com
HTTP/1.1 200 OK

$ curl -I --max-time 20 https://static.rust-lang.org/dist/channel-rust-1.98.1.toml
HTTP/1.1 200 OK
```

All three anonymous public Git probes failed identically:

```text
$ git ls-remote https://github.com/fe-lang/fevm.git refs/heads/native-acceptance
error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403
fatal: expected flush after ref listing
[exit 128]

$ git ls-remote https://github.com/argotorg/fe.git refs/heads/fevm-native-integration
error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403
fatal: expected flush after ref listing
[exit 128]

$ git ls-remote https://github.com/sbillig/sonatina.git refs/heads/fix-native-aggregate-construction
error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403
fatal: expected flush after ref listing
[exit 128]
```

## Stage status

| Stage | Status | Exit/result |
| --- | --- | --- |
| Linux x86_64 host verification | Complete | Linux / x86_64 |
| General GitHub HTTPS probe | Complete | HTTP 200 |
| Rust 1.98.1 distribution probe | Complete | HTTP 200 |
| FeVM branch access preflight | Failed | exit 128, HTTP 403 |
| Fe and Sonatina branch probes | Failed | exit 128, HTTP 403 |
| Full-history FeVM clone and detached checkout | Not run | blocked by preflight |
| Inspection of `native/README.md`, `native/toolchain.json`, `native/bootstrap.py`, and `native/accept.py` | Not run | no FeVM checkout |
| Rust 1.98.1 installation | Not run | acceptance already blocked |
| Bootstrap | Not run | no FeVM checkout |
| Acceptance (`--check-only`) | Not run | no build manifest |
| Result artifact collection | Not run | no generated artifacts |

No test counts or failures are available because the acceptance runner never
started. No generated `build.json`, `acceptance.json`, CLI/arithmetic JSON,
SwissTable JSON, workspace logs, binaries, assembly, or FeVM source were added.

## Required environment change

Permit anonymous Git smart-HTTP access to the three public GitHub repositories
through the existing proxy. Once `git ls-remote` succeeds, rerun the complete
pinned bootstrap and acceptance commands without changing revisions, manifests,
optimization levels, or the Rust toolchain.
