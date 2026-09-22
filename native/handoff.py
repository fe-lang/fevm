#!/usr/bin/env python3
"""Package committed FeVM/Fe/Sonatina sources for Linux without publishing them."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def git(repository, *args):
    return subprocess.check_output(['git', '-C', str(repository), *map(str, args)], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True, help='verified bootstrap build.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build = json.loads(args.build.read_text())
    if not build.get('complete'):
        parser.error('bootstrap is incomplete')
    if git(ROOT, 'status', '--porcelain'):
        parser.error('commit the FeVM tooling before creating the handoff')
    manifest = build['manifest']
    if json.loads(HERE.joinpath('toolchain.json').read_text()) != manifest:
        parser.error('build manifest differs from the committed toolchain manifest')
    repositories = {
        'fevm': (ROOT, git(ROOT, 'rev-parse', 'HEAD')),
        'fe': (Path(build['source_directory']), manifest['fe_revision']),
        'sonatina': (Path(build['sonatina_source_directory']), manifest['sonatina_revision']),
    }
    for name, (repository, revision) in repositories.items():
        if git(repository, 'rev-parse', 'HEAD') != revision:
            parser.error(f'{name} checkout no longer matches the build record')
        if git(repository, 'status', '--porcelain', '--untracked-files=no'):
            parser.error(f'{name} has tracked source changes')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bundles = {}
    for name, (repository, revision) in repositories.items():
        bundle = out / f'{name}.bundle'
        if bundle.exists():
            parser.error(f'refusing to overwrite {bundle}; choose a fresh --out directory')
        git(repository, 'bundle', 'create', bundle, 'HEAD')
        git(repository, 'bundle', 'verify', bundle)
        bundles[name] = {'revision': revision, 'file': bundle.name,
                         'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest()}
    out.joinpath('handoff.json').write_text(json.dumps({
        'schema': 1, 'linux_execution': 'not run',
        'toolchain': manifest, 'bundles': bundles,
    }, indent=2) + '\n')
    out.joinpath('README.md').write_text(f'''# Native Linux acceptance handoff

Prepared from committed sources. The bundles contain the source histories.
Linux execution is **not yet verified**. This handoff targets x86_64 Linux.
Install Git, Python 3.10+, Node/npm, Rust {manifest['rust_version']} via rustup, CMake, a C compiler
and binutils. Verify the bundle SHA-256 values in `handoff.json` before use.

From this directory:

```sh
git init fevm
git -C fevm fetch ../fevm.bundle {repositories['fevm'][1]}
git -C fevm checkout --detach FETCH_HEAD
cd fevm
python3 native/bootstrap.py --out native/out/linux-toolchain \\
  --toolchain {manifest['rust_version']} \\
  --fe-repository ../fe.bundle --sonatina-repository ../sonatina.bundle
python3 native/accept.py --build native/out/linux-toolchain/build.json \\
  --out native/out/linux-acceptance --check-only
```

Return `build.json`, `acceptance.json`, `arithmetic/results.json`, `cli/results.json`,
`swisstable/results.json`, `cancun-frames/results.json`, and the acceptance logs. For performance measurements, use an idle host and omit
`--check-only`; retain all samples, emitted IR, objects and disassembly.
A failing command must remain a failure in the report. This validates the native
workspace tests, CLI smoke, Cancun frame results, numeric kernels, and SwissTable;
full Cancun conformance remains pending.
''')
    print(out / 'README.md')


if __name__ == '__main__':
    main()
