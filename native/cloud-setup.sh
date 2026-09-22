#!/usr/bin/env bash
# Run as the setup script in a Cloud environment connected to private FeVM.
set -euo pipefail

test "$(uname -s)" = Linux
test "$(uname -m)" = x86_64
for tool in git python3 node npm rustup cmake cc size objdump; do
    command -v "$tool" >/dev/null
done

rust_version=$(python3 -c 'import json; print(json.load(open("native/toolchain.json"))["rust_version"])')
rustup toolchain install "$rust_version" --profile minimal

# SwissTable needs the baseline source from Git history, even in a shallow clone.
if test "$(git rev-parse --is-shallow-repository)" = true; then
    git fetch --unshallow origin native-acceptance
else
    git fetch origin native-acceptance
fi

git cat-file -e cc5b1caffade446868fa1c24b15ef0596fce269a^{commit}
rustup run "$rust_version" rustc --version
printf '%s\n' 'Setup complete. The acceptance task still needs network access for pinned compiler sources and locked Cargo/npm dependencies.'
