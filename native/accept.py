#!/usr/bin/env python3
"""Downstream acceptance for native FeVM, arithmetic, and SwissTable."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True, help='bootstrap build.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true', help='omit noisy timing measurements (recommended in shared CI)')
    args = parser.parse_args()
    build = json.loads(args.build.read_text())
    if not build.get('complete'):
        parser.error('compiler bootstrap is incomplete')
    compiler = Path(build['compiler'])
    if hashlib.sha256(compiler.read_bytes()).hexdigest() != build['compiler_sha256']:
        parser.error('compiler hash does not match the build record')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = out / 'acceptance.json'
    if report.exists():
        parser.error('acceptance.json already exists; choose a fresh --out directory')
    record = {'schema': 1, 'build': build, 'host': platform.platform(), 'complete': False,
              'scope': 'native workspace tests, CLI smoke, numeric kernels, and SwissTable; Cancun conformance remains pending',
              'checks': []}
    report.write_text(json.dumps(record, indent=2) + '\n')
    commands = [([compiler, 'test', '--backend', 'native', '-O', level, ROOT],
                 f'workspace-O{level}') for level in ['0', '1', '2']]
    commands.append(([sys.executable, HERE / 'cli.py', '--fe', compiler,
                      '--out', out / 'cli'], 'cli-smoke'))
    commands.append(([sys.executable, HERE / 'swisstable/run.py', '--fe', compiler,
                      '--out', out / 'swisstable', '--check-only'], 'swisstable-differential'))
    arithmetic = [sys.executable, HERE / 'arith/run.py', '--fe', compiler, '--out', out / 'arithmetic']
    if args.check_only:
        arithmetic.append('--check-only')
    commands.append((arithmetic, 'arithmetic'))
    for command, name in commands:
        started = time.perf_counter()
        with out.joinpath(f'{name}.log').open('wb') as log:
            try:
                status = subprocess.run([str(x) for x in command], stdout=log, stderr=subprocess.STDOUT,
                                        timeout=3600).returncode
            except subprocess.TimeoutExpired:
                log.write(b'\nAcceptance command exceeded the 3600-second timeout.\n')
                status = 124
        record['checks'].append({'name': name, 'status': status, 'seconds': time.perf_counter() - started})
        report.write_text(json.dumps(record, indent=2) + '\n')
        print(f'{name}: {"passed" if status == 0 else "FAILED"}', flush=True)
    record['complete'] = all(check['status'] == 0 for check in record['checks'])
    report.write_text(json.dumps(record, indent=2) + '\n')
    sys.exit(0 if record['complete'] else 1)


if __name__ == '__main__':
    main()
