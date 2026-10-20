#!/usr/bin/env python3
"""Build a reduced real FeVM workload at O1 and check its execution."""
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
sys.path.insert(0, str(ROOT / 'native'))
from arith.run import artifacts as collect_artifacts

MODULES = {
    'checkpoints': ('constants', 'gas', 'journal', 'logs', 'state', 'transaction'),
    'inputs': ('constants', 'hex', 'types'),
    'calls': ('address', 'calls_runtime', 'constants', 'gas', 'journal', 'logs',
              'memory', 'state', 'transaction', 'types', 'vm'),
    'vm_inputs': ('address', 'constants', 'gas', 'inputs_runtime', 'journal', 'logs',
                  'memory', 'state', 'transaction', 'types', 'vm'),
}


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
    parser.add_argument('--probe', choices=MODULES, required=True)
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
    entry = Path(__file__).with_name(f'{args.probe}.fe')
    modules = MODULES[args.probe]
    sources = [manifest, entry, *(ROOT / f'ingots/evm/src/{name}.fe' for name in modules)]
    if args.probe == 'inputs':
        sources.append(ROOT / 'native/fixtures/vm_allocator.c')
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    config = manifest.read_text()
    if config.count('name = "fevm"') != 1:
        raise ValueError('unexpected FeVM ingot manifest')
    ingot_name = f'{args.probe}_probe'
    # The probe sits outside the workspace, so the precompiles become a path dependency.
    config = config.replace('fevm_precompiles = true',
                            f'fevm_precompiles = {{ path = "{os.path.relpath(ROOT / "ingots/precompiles", ingot)}" }}')
    (ingot / 'fe.toml').write_text(config.replace('name = "fevm"', f'name = "{ingot_name}"'))
    shutil.copy2(entry, ingot / 'src/lib.fe')
    for name in modules:
        shutil.copy2(ROOT / f'ingots/evm/src/{name}.fe', ingot / f'src/{name}.fe')
    env = os.environ.copy()
    env['RAYON_NUM_THREADS'] = '1'
    record = {
        'schema': 2, 'complete': False, 'host': platform.platform(), 'opt_level': 1,
        'scope': f'reduced {args.probe} build and execution; not full EVM acceptance',
        'probe': args.probe, 'runner_sha256': digest(Path(__file__)),
        'generated_manifest_sha256': digest(ingot / 'fe.toml'),
        'compiler': str(compiler), 'compiler_sha256': digest(compiler),
        'source_sha256': hashes, 'rayon_threads': 1,
        'borrowck_profile': env.get('FE_BORROWCK_PROFILE') == '1',
        'borrowck_subgraphs': env.get('FE_BORROWCK_SUBGRAPHS') == '1',
        'build_timeout_seconds': args.build_timeout,
        'timing_scope': 'build includes dependency resolution, optimization and linking',
    }
    report = out / 'result.json'
    report.write_text(json.dumps(record, indent=2) + '\n')
    artifacts = out / 'build'
    command = [str(compiler), 'build', str(ingot), '--backend', 'native', '-O', '1',
               '--emit', 'ir,executable', '--out-dir', str(artifacts)]
    if args.probe == 'inputs':
        command.extend(['--report', '--report-out', str(out / 'build.tar.gz')])
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
        executable = artifacts / ingot_name
        expected = {'checkpoints': b'11111111', 'inputs': b'inputs passed\n',
                    'vm_inputs': b'VM inputs passed\n', 'calls': b'CALL cases passed\n'}[args.probe]
        cases = [('execution', executable, [])]
        if args.probe == 'inputs':
            cases.extend((f'{kind}-{name}', executable, [kind, encoded, status])
                         for kind in ['p', 'i']
                         for name, encoded, status in [
                             ('empty', '', '0'), ('prefix', '0X5b', '0'),
                             ('large', '5b' * 50000, '0'),
                             ('odd', '5', '4'), ('invalid', '0x5bgg', '3'),
                         ])
            record['artifacts'] = collect_artifacts(
                executable, out / 'build.tar.gz', artifacts, object_name=f'{ingot_name}.o')
            # Watch both code and jump-map allocations. Failing the second must
            # still release the first; the allocator destructor checks counts.
            for failure_at in [0, 1, 2]:
                name = f'allocator-{failure_at}'
                controlled = artifacts / name
                link = ['cc', '-O2', '-Wall', '-Wextra', '-Werror',
                        f'-DFAIL_AT={failure_at}', '-DWATCH_SIZE=65536', '-DWATCH_SIZE_EXTRA=8192',
                        str(ROOT / 'native/fixtures/vm_allocator.c'), str(artifacts / f'{ingot_name}.o'),
                        '-o', str(controlled)]
                if run(link, out / f'{name}-link.log', 30, env):
                    raise RuntimeError(f'failed to link {name}')
                cases.append((name, controlled, ['p', '5b' * 50000, 'a' if failure_at else '0']))
        record['executable_sha256'] = digest(executable)
        record['checks'] = []
        for name, executable, arguments in cases:
            log = out / f'{name}.log'
            status = run([str(executable), *arguments], log, 10, env)
            observed = log.read_bytes()
            record['checks'].append({'name': name, 'status': status,
                                     'executable_sha256': digest(executable),
                                     'stdout': observed.decode(errors='replace'),
                                     'passed': status == 0 and observed == expected})
            if not record['checks'][-1]['passed']:
                raise RuntimeError(f'{name} failed; see {log.name}')
        if hashes != {str(path.relative_to(ROOT)): digest(path) for path in sources}:
            raise RuntimeError('benchmark sources changed during the run')
        record['complete'] = True
    except Exception as error:
        record['error'] = str(error)
        raise
    finally:
        report.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record['build']))
    print(f'{args.probe}: {len(record["checks"])} execution checks passed.')


if __name__ == '__main__':
    main()
