#!/usr/bin/env python3
"""Build and smoke-test the native FeVM CLI; this is not Cancun conformance."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from arith.run import artifacts, command

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    ('usage', [], 2, 'usage: fevm <hex-bytecode> [hex-calldata]\n'),
    ('empty', [''], 0, 'empty\n'),
    ('stop', ['00'], 0, 'empty\n'),
    ('add', ['6002600301'], 0, f'0x{5:064x}\n'),
    ('calldata-return', ['6002600060003760026000f3', '1234'], 0, '0x1234\n'),
    ('bad-hex', ['zz'], 3, 'invalid hex bytecode\n'),
    ('odd-hex', ['0'], 4, 'hex bytecode has an odd number of digits\n'),
    ('stack-underflow', ['01'], 10, 'stack underflow\n'),
    ('invalid', ['fe'], 17, 'invalid opcode\n'),
    ('revert', ['60006000fd'], 19, 'revert 0x\n'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    compiler = args.fe.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = {'schema': 1, 'scope': 'native FeVM CLI smoke, not Cancun conformance',
              'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
              'host': platform.platform(), 'complete': False, 'builds': []}
    report = out / 'results.json'
    report.write_text(json.dumps(record, indent=2) + '\n')
    for level in ['0', '1', '2']:
        folder = out / f'O{level}'
        folder.mkdir()
        archive = folder / 'build.tar.gz'
        started = time.perf_counter()
        log = command([compiler, 'build', ROOT, '--ingot', 'fevm', '--backend', 'native',
                       '-O', level, '--emit', 'ir,executable', '--out-dir', folder,
                       '--report', '--report-out', archive])
        folder.joinpath('build.log').write_bytes(log)
        build_seconds = time.perf_counter() - started
        executable = folder / 'fevm'
        sizes = artifacts(executable, archive, folder, object_name='fevm.o')
        row = {'level': level, 'build_seconds': build_seconds, **sizes, 'checks': []}
        record['builds'].append(row)
        for name, argv, status, output in CASES:
            result = subprocess.run([str(executable), *argv], capture_output=True, timeout=60)
            passed = result.returncode == status and result.stdout == output.encode() and not result.stderr
            row['checks'].append({'name': name, 'passed': passed, 'status': result.returncode,
                                  'stdout': result.stdout.decode(errors='replace'),
                                  'stderr': result.stderr.decode(errors='replace')})
            report.write_text(json.dumps(record, indent=2) + '\n')
            if not passed:
                raise AssertionError(f'O{level} {name}: {result!r}')
        # Use the same compiled VM object with a controlled host allocator.
        # Returning 65,537 bytes requires separate 131,072-byte data buffers.
        # The allocator also poisons fresh storage and checks exact releases.
        for failure_at, name in [(0, 'owned-output'), (1, 'memory-allocation-failure'),
                                 (2, 'output-allocation-failure')]:
            controlled = folder / name
            command(['cc', '-O2', '-Wall', '-Wextra', '-Werror', f'-DFAIL_AT={failure_at}',
                     ROOT / 'native/fixtures/vm_allocator.c', folder / 'fevm.o',
                     '-o', controlled])
            result = subprocess.run([str(controlled), '620100015ff3'],
                                    capture_output=True, timeout=60)
            expected_status = 21 if failure_at else 0
            expected_output = b'host allocation failed\n' if failure_at else b'0x' + b'00' * 65537 + b'\n'
            passed = (result.returncode == expected_status and result.stdout == expected_output
                      and not result.stderr)
            row['checks'].append({'name': name, 'passed': passed, 'status': result.returncode,
                                  'stdout_bytes': len(result.stdout),
                                  'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                                  'stderr': result.stderr.decode(errors='replace')})
            report.write_text(json.dumps(record, indent=2) + '\n')
            if not passed:
                raise AssertionError(f'O{level} {name}: status={result.returncode}, '
                                     f'output_bytes={len(result.stdout)}, stderr={result.stderr!r}')
        print(f'CLI O{level}: {len(row["checks"])} passed', flush=True)
    record['complete'] = True
    report.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
