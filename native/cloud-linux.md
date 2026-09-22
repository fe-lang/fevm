# Cloud/Linux acceptance handoff

The accepted native stack is reachable through these branches. Always check out
the exact commits; subsequent branch changes must not change an acceptance run.

| Repository | Branch | Commit |
|---|---|---|
| [FeVM](https://github.com/fe-lang/fevm/tree/native-acceptance) | `native-acceptance` | `cc5b1caffade446868fa1c24b15ef0596fce269a` |
| [Fe](https://github.com/argotorg/fe/tree/fevm-native-integration) | `fevm-native-integration` | `85e64e8404642eaddcdd1ec8d275d7c26ab7ac31` |
| [Sonatina](https://github.com/sbillig/sonatina/tree/fix-native-aggregate-construction) | `fix-native-aggregate-construction` | `61fa661c23bbeeeab024c4e9936656b7a73bd8f4` |

Use an **x86_64 Linux** environment with access to public FeVM and its full Git
history. The first [Cloud task](https://chatgpt.com/codex/tasks/task_e_6ab1f64ec6b883289a119636c3641358)
confirmed Linux x86_64 and the exact Fe revision/lockfile, but its network proxy
rejected the FeVM fetch with HTTP 403. Bootstrap and every acceptance stage were
**not run**; the proxy failure does not establish whether repository authorization
would otherwise succeed. Its report is retained in
[the Cloud attempt record](reports/linux-cloud-attempt.md).

FeVM is now public; anonymous HTTPS fetching of `native-acceptance` succeeds.
A [retry in the existing Fe environment](https://chatgpt.com/codex/tasks/task_e_6ab1f89f5b588328b0df74f3bd1951fc)
is checking whether public access also works through its network proxy. A dedicated FeVM environment can alternatively
check out the repository directly.
Set its setup script to `bash native/cloud-setup.sh` on `native-acceptance` and
enable task network access for GitHub and the Rust/Cargo/npm dependency downloads.
The [setup script](cloud-setup.sh) checks the host/tools, installs pinned Rust and
fetches the history needed for the SwissTable baseline. It does not run acceptance.

The [native README](README.md) lists prerequisites. Install the exact Rust
version and run from the pinned FeVM checkout, using fresh output directories:

```sh
uname -s -m
git rev-parse HEAD
python3 native/bootstrap.py --out native/out/linux-bootstrap \
  --toolchain 1.98.1 \
  --fe-repository https://github.com/argotorg/fe.git \
  --sonatina-repository https://github.com/sbillig/sonatina.git
python3 native/accept.py --build native/out/linux-bootstrap/build.json \
  --out native/out/linux-acceptance --check-only
```

Retain `build.json`, `acceptance.json`, CLI/arithmetic/SwissTable result JSON, and
workspace and failure logs. Record host, revisions, commands, exit codes and
counts; report failed or unexecuted stages explicitly. The suite covers native
workspace execution, CLI smoke, arithmetic and SwissTable, not Cancun conformance.
Shared Cloud hardware is suitable for correctness acceptance, not timing claims.

## Retained local work

Active compiler worktrees now live at
`/Users/sean/code/fe/fevm-native-integration` and
`/Users/sean/code/sonatina/native-aggregate-construction`.
Ten historical compiler worktrees were also moved under their respective
`~/code/fe` and `~/code/sonatina` directories, preserving uncommitted changes.
`native/out/retained/worktree-relocations.json` records all moves and revisions.

The retained temporary artifacts were copied to `native/out/retained/tmp`, with
SHA-256 verification of 23,796 regular files and preservation of seven symlinks
(4,617,558,667 regular-file bytes). The inventory is
`native/out/retained/artifact-relocations.json`. Original reports retain original
paths; the current compiler path is in
`native/out/retained/tmp/fevm-native-construction-bootstrap/build-relocated.json`.
The provider-fix draft remains uncommitted in
`/Users/sean/code/fe/fevm-stable-provider-draft` and has an additional patch copy
under `native/out/retained`. Generated binaries and caches are not Git artifacts.
