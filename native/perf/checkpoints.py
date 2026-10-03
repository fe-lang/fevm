#!/usr/bin/env python3
"""Build a reduced real FeVM transaction workload at O1 and check its execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
MODULES = ('buffer', 'constants', 'gas', 'journal', 'logs', 'state', 'transaction')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log, timeout, env):
    with log.open('wb') as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            output.write(f'\nCommand exceeded the {timeout}-second timeout.\n'.encode())
            return 124


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--build-timeout', type=int, default=180)
    args = parser.parse_args()
    if args.build_timeout < 1:
        parser.error('--build-timeout must be positive')
    compiler = args.fe.resolve(strict=True)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    ingot = out / 'ingot'
    (ingot / 'src').mkdir(parents=True)
    manifest = ROOT / 'ingots/evm/fe.toml'
    entry = Path(__file__).with_suffix('.fe')
    sources = [manifest, entry, *(ROOT / f'ingots/evm/src/{name}.fe' for name in MODULES)]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    config = manifest.read_text()
    if config.count('name = "fevm"') != 1:
        raise ValueError('unexpected FeVM ingot manifest')
    (ingot / 'fe.toml').write_text(config.replace('name = "fevm"', 'name = "checkpoint_bench"'))
    shutil.copy2(entry, ingot / 'src/lib.fe')
    for name in MODULES:
        shutil.copy2(ROOT / f'ingots/evm/src/{name}.fe', ingot / f'src/{name}.fe')
    env = os.environ.copy()
    env['RAYON_NUM_THREADS'] = '1'
    record = {
        'schema': 1, 'complete': False, 'host': platform.platform(), 'opt_level': 1,
        'scope': 'reduced transaction/checkpoint/log build and execution; not full EVM acceptance',
        'compiler': str(compiler), 'compiler_sha256': digest(compiler),
        'source_sha256': hashes, 'rayon_threads': 1,
        'build_timeout_seconds': args.build_timeout,
        'timing_scope': 'build includes dependency resolution, optimization and linking',
    }
    report = out / 'result.json'
    report.write_text(json.dumps(record, indent=2) + '\n')
    artifacts = out / 'build'
    command = [str(compiler), 'build', str(ingot), '--backend', 'native', '-O', '1',
               '--emit', 'ir,executable', '--out-dir', str(artifacts)]
    started = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        status = run(command, out / 'build.log', args.build_timeout, env)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record['build'] = {
            'command': command, 'status': status, 'wall_seconds': time.perf_counter() - started,
            'user_seconds': after.ru_utime - before.ru_utime,
            'system_seconds': after.ru_stime - before.ru_stime,
            # This is the script's first child; its peak is the build's peak.
            'max_rss_bytes': after.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
        }
        if status:
            raise RuntimeError(f'build failed with status {status}; see build.log')
        executable = artifacts / 'checkpoint_bench'
        status = run([str(executable)], out / 'execution.log', 10, env)
        observed = (out / 'execution.log').read_bytes()
        record['execution'] = {'status': status, 'stdout': observed.decode(errors='replace'),
                               'executable_sha256': digest(executable)}
        if status or observed != b'11111111':
            raise RuntimeError('checkpoint/log execution failed; see execution.log')
        if hashes != {str(path.relative_to(ROOT)): digest(path) for path in sources}:
            raise RuntimeError('benchmark sources changed during the run')
        record['complete'] = True
    except Exception as error:
        record['error'] = str(error)
        raise
    finally:
        report.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record['build']))
    print('Nested log commit/rollback execution passed.')


if __name__ == '__main__':
    main()
