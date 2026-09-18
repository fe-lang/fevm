#!/usr/bin/env python3
"""Build the pinned native Fe compiler from a fresh, detached checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def output(args, **kwargs):
    return subprocess.check_output([str(x) for x in args], text=True, **kwargs).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkout(repository, revision, destination):
    if destination.exists():
        raise RuntimeError(f'refusing to overwrite {destination}; choose a fresh --out directory')
    # git -C changes relative fetch paths; resolve local inputs from the caller.
    if Path(repository).exists():
        repository = str(Path(repository).resolve())
    run(['git', 'init', destination])
    run(['git', '-C', destination, 'fetch', repository, revision])
    run(['git', '-C', destination, 'checkout', '--detach', 'FETCH_HEAD'])
    actual = output(['git', '-C', destination, 'rev-parse', 'HEAD'])
    if actual != revision:
        raise RuntimeError(f'revision mismatch: wanted {revision}, got {actual}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=HERE / 'toolchain.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fe-repository', help='Git URL, local repository or bundle containing the pinned Fe commit')
    parser.add_argument('--sonatina-repository', help='Git URL, local repository or bundle containing the pinned Sonatina commit')
    parser.add_argument('--toolchain', default='stable', help='installed rustup toolchain; its version must match the manifest')
    parser.add_argument('--target-dir', type=Path, help='optional reusable Cargo artifact cache (sources still start clean)')
    parser.add_argument('--prepare-only', action='store_true', help='verify and materialize sources without compiling')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest['schema'] != 1:
        parser.error('unsupported manifest schema')
    rustc = output(['rustup', 'run', args.toolchain, 'rustc', '--version'])
    if rustc.split()[1] != manifest['rust_version']:
        parser.error(f"requires Rust {manifest['rust_version']}; selected toolchain reports {rustc}")
    host = ('aarch64-apple-darwin' if (platform.system(), platform.machine()) == ('Darwin', 'arm64')
            else 'x86_64-unknown-linux-gnu' if (platform.system(), platform.machine()) == ('Linux', 'x86_64')
            else None)
    if host not in manifest['hosts']:
        parser.error('supported hosts are macOS AArch64 and Linux x86_64')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    fe = out / 'fe'
    sonatina = out / 'sonatina'
    checkout(args.fe_repository or manifest['fe_repository'], manifest['fe_revision'], fe)
    checkout(args.sonatina_repository or manifest['sonatina_repository'], manifest['sonatina_revision'], sonatina)
    if digest(fe / 'Cargo.lock') != manifest['cargo_lock_sha256']:
        raise RuntimeError('Cargo.lock does not match the manifest')
    lock = (fe / 'Cargo.lock').read_text()
    if f"#{manifest['sonatina_revision']}" not in lock:
        raise RuntimeError('Fe Cargo.lock does not pin the expected Sonatina revision')
    env = os.environ.copy()
    # Scope URL rewriting to this build; do not modify global Git/Cargo settings.
    count = int(env.get('GIT_CONFIG_COUNT', '0'))
    env[f'GIT_CONFIG_KEY_{count}'] = f'url.{sonatina.as_uri()}.insteadOf'
    env[f'GIT_CONFIG_VALUE_{count}'] = manifest['sonatina_repository']
    env['GIT_CONFIG_COUNT'] = str(count + 1)
    env['CARGO_NET_GIT_FETCH_WITH_CLI'] = 'true'
    target = args.target_dir.resolve() if args.target_dir else out / 'target'
    env['CARGO_TARGET_DIR'] = str(target)
    record = {'manifest': manifest, 'host': host, 'rustc': rustc,
              'source_directory': str(fe), 'sonatina_source_directory': str(sonatina),
              'cargo': output(['rustup', 'run', args.toolchain, 'cargo', '--version']),
              'node': output(['node', '--version']), 'npm': output(['npm', '--version']),
              'cc': output(['cc', '--version']).splitlines()[0], 'target_directory': str(target), 'complete': False}
    out.joinpath('build.json').write_text(json.dumps(record, indent=2) + '\n')
    if args.prepare_only:
        print(f'Pinned clean sources prepared in {out}; compiler build not performed.')
        return
    grammar = fe / 'crates/tree-sitter-fe'
    run(['npm', 'ci', '--ignore-scripts'], cwd=grammar, env=env)
    run(['npm', 'rebuild', 'tree-sitter-cli'], cwd=grammar, env=env)
    run(['npx', '--no-install', 'tree-sitter', 'generate', '--abi=14'], cwd=grammar, env=env)
    started = time.perf_counter()
    run(['rustup', 'run', args.toolchain, 'cargo', 'build', '--release', '--locked', '-p', 'fe',
         '--features', ','.join(manifest['features'])], cwd=fe, env=env)
    record['compiler_build_seconds'] = time.perf_counter() - started
    if digest(fe / 'Cargo.lock') != manifest['cargo_lock_sha256']:
        raise RuntimeError('Cargo.lock changed during the locked build')
    if output(['git', '-C', fe, 'status', '--porcelain', '--untracked-files=no']):
        raise RuntimeError('tracked compiler sources changed during bootstrap')
    # A later build may reuse the cache; keep this accepted compiler immutable.
    binary = out / 'bin/fe'
    binary.parent.mkdir()
    shutil.copy2(target / 'release/fe', binary)
    record |= {'compiler': str(binary), 'compiler_sha256': digest(binary),
               'compiler_version': output([binary, '--version']), 'complete': True}
    out.joinpath('build.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'Native compiler: {binary}')


if __name__ == '__main__':
    main()
