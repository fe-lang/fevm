#!/usr/bin/env bash
# Run as the setup script in a Cloud environment connected to FeVM.
set -euo pipefail

test "$(uname -s)" = Linux
test "$(uname -m)" = x86_64
for tool in git python3 node npm rustup cmake cc size objdump; do
    command -v "$tool" >/dev/null
done

rust_version=$(python3 -c 'import json; print(json.load(open("native/toolchain.json"))["rust_version"])')
rustup toolchain install "$rust_version" --profile minimal

rustup run "$rust_version" rustc --version
printf '%s\n' 'Setup complete. The acceptance task still needs network access for pinned compiler sources, Fe git dependencies, and locked Cargo/npm dependencies.'
