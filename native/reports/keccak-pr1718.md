# Local #1718 compiler for the Keccak workstream

The local development compiler integrates Fe master
`04d34410582e4ddac3f516c6ded1a0fdb4a31b3c` with
[PR #1718](https://github.com/argotorg/fe/pull/1718) head
`cfe41afdffc88b6de748e69d9596dbcfd195b8fd`, including the dead-wrapper-result,
unread-cell and lossy-cast fixes. Its merge commit is
`0c100f1c8b1afd29f7b106eb9e40df0fc11aa01b` on local branch
`integrate/fevm-pr1718-cfe41-20261002`.

The immutable binary is
`native/out/keccak-pr1718-20261002/toolchain/bin/fe`, with SHA-256
`03b4eab8fc8d330f25fd963680a776e1ae05f09984d2f3685f69a632f8d14317`.
It uses Rust 1.98.1, the default Fe features plus `cranelift`, and the same
Sonatina revision and Cargo lock as the published-master checkpoint. Borrow
profiling is disabled in this binary. Compiler tracked sources are clean.

The merge is local. The public default in `native/toolchain.json` remains the
independently accepted published-master pin. To rebuild this local integration
from the repository containing its commit:

```sh
python3 native/bootstrap.py \
  --manifest native/reports/keccak-pr1718-toolchain.json \
  --fe-repository /home/sean/code/fe \
  --out native/out/pr1718-rebuild --toolchain 1.98.1
```

## Verification

All 4,485 release compiler tests pass with all features enabled (one configured
skip). Nightly formatting and strict all-target/all-feature Clippy pass. The
production binary checks `borrowck_unread_many_arm_results.fe` in 0.17 seconds,
and all three standalone Keccak library tests pass at O0/O1/O2.

All 35 FeVM workspace tests, 1,835 frame cases and 383 state sequences pass
at O2. Both differential executables are byte-for-byte identical to the accepted
master executables, with the same three declared frame simultaneous-fault
reason differences. All 16 CLI/allocator/journal checks pass at each of
O0/O1/O2, and arithmetic passes 74,676 checks across 48 generated builds.

The [verification record](linux-x86_64-keccak-pr1718.json) retains all stage
results, compiler and executable identities, source hashes, raw check timings,
and memory accounting. Every recorded runtime/harness source hash was rechecked
against the final tree. The run peaked at 8.26 GiB inside its 12-GiB scope,
with no memory-limit or OOM events. The workspace log and
[local compiler manifest](keccak-pr1718-toolchain.json) accompany the record;
full artifacts remain under `native/out/keccak-pr1718-20261002`.

This is the local compiler verification matrix described above. The separate
[published-master checkpoint](keccak-integration.md) retains the full seven-stage
acceptance at every optimization level. Both are Linux x86_64 checkpoints.

## Checking time

One identical-source `fe check . --ingot fevm` per compiler gave:

| Compiler | User CPU seconds | Wall seconds | Maximum RSS, KiB |
| --- | ---: | ---: | ---: |
| Published master 04d344105 | 137.68 | 158.06 | 856176 |
| Master plus #1718 cfe41afdf | 79.22 | 79.82 | 855240 |

That is about 42.5% less user CPU time for this check. This is a single
observation on a shared host; the master run overlapped another compiler build.
It is not a controlled benchmark or a claim about total native build time.
The raw timing records and compiler identities are retained under
`native/out/keccak-pr1718-20261002`.
