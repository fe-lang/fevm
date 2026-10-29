#!/usr/bin/env python3
"""Build and smoke-test the native FeVM CLI; this is not conformance."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from arith.run import artifacts, command

ROOT = Path(__file__).resolve().parent.parent
# The bytes of a boxed child `Frame` (packed, with the stack on the heap).
FRAME_BOX_SIZE = 477
CASES = [
    ('usage', [], 2, 'usage: fevm <hex-bytecode> [hex-calldata]\n'),
    ('empty', [''], 0, 'empty\n'),
    ('stop', ['00'], 0, 'empty\n'),
    ('keccak-empty', ['5f5f20'], 0, '0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470\n'),
    ('keccak-abc', ['626162635f526003601d20'], 0, '0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45\n'),
    ('extcode-absent-size', ['602c3b'], 0, f'0x{0:064x}\n'),
    ('extcode-absent-hash', ['602c3f'], 0, f'0x{0:064x}\n'),
    ('extcode-absent-copy', ['60015f5f602c3c60015ff3'], 0, '0x00\n'),
    ('log-empty', ['5f5fa0'], 0, 'empty\n'),
    ('blobhash-empty', ['5f49'], 0, f'0x{0:064x}\n'),
    ('add', ['6002600301'], 0, f'0x{5:064x}\n'),
    ('calldata-return', ['6002600060003760026000f3', '1234'], 0, '0x1234\n'),
    ('large-code-size', ['3800' + '00' * 8191], 0, f'0x{8193:064x}\n'),
    ('large-calldata-size', ['36', 'ab' * 9001], 0, f'0x{9001:064x}\n'),
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
    parser.add_argument('--build-timeout', type=int, default=600,
                        help='seconds allowed per Fe build (default: 600)')
    args = parser.parse_args()
    if args.build_timeout < 1:
        parser.error('--build-timeout must be positive')
    compiler = args.fe.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = {'schema': 1, 'scope': 'native FeVM CLI smoke, not conformance',
              'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
              'host': platform.platform(), 'build_timeout_seconds': args.build_timeout,
              'complete': False, 'builds': []}
    report = out / 'results.json'
    report.write_text(json.dumps(record, indent=2) + '\n')
    for level in ['0', '1', '2']:
        folder = out / f'O{level}'
        folder.mkdir()
        archive = folder / 'build.tar.gz'
        started = time.perf_counter()
        log = command([compiler, 'build', ROOT, '--ingot', 'fevm', '--backend', 'native',
                       '-O', level, '--emit', 'ir,executable', '--out-dir', folder,
                       '--report', '--report-out', archive], timeout=args.build_timeout)
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
        journal = folder / 'journal'
        journal.mkdir()
        journal_archive = journal / 'build.tar.gz'
        log = command([compiler, 'build', ROOT, '--ingot', 'fevm_journal', '--backend', 'native',
                       '-O', level, '--emit', 'ir,executable', '--out-dir', journal,
                       '--report', '--report-out', journal_archive], timeout=args.build_timeout)
        journal.joinpath('build.log').write_bytes(log)
        artifacts(journal / 'fevm_journal', journal_archive, journal, object_name='fevm_journal.o')
        controlled = journal / 'allocation-failure'
        command(['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-DFAIL_AT=1', '-DWATCH_SIZE=100352',
                 ROOT / 'native/fixtures/vm_allocator.c', journal / 'fevm_journal.o',
                 '-o', controlled])
        result = subprocess.run([str(controlled)], capture_output=True, timeout=60)
        passed = result.returncode == 0 and not result.stdout and not result.stderr
        row['checks'].append({'name': 'journal-allocation-failure', 'passed': passed,
                              'status': result.returncode,
                              'stdout': result.stdout.decode(errors='replace'),
                              'stderr': result.stderr.decode(errors='replace')})
        report.write_text(json.dumps(record, indent=2) + '\n')
        if not passed:
            raise AssertionError(f'O{level} journal allocation failure: {result!r}')
        accounts = folder / 'accounts'
        accounts.mkdir()
        account_archive = accounts / 'build.tar.gz'
        log = command([compiler, 'build', ROOT, '--ingot', 'fevm_accounts', '--backend', 'native',
                       '-O', level, '--emit', 'ir,executable', '--out-dir', accounts,
                       '--report', '--report-out', account_archive], timeout=args.build_timeout)
        accounts.joinpath('build.log').write_bytes(log)
        artifacts(accounts / 'fevm_accounts', account_archive, accounts, object_name='fevm_accounts.o')
        for failure_at in [0, 1, 2]:
            controlled = accounts / f'allocator-{failure_at}'
            command(['cc', '-O2', '-Wall', '-Wextra', '-Werror', f'-DFAIL_AT={failure_at}',
                     ROOT / 'native/fixtures/vm_allocator.c', accounts / 'fevm_accounts.o',
                     '-o', controlled])
            result = subprocess.run([str(controlled)], capture_output=True, timeout=60)
            passed = result.returncode == 0 and not result.stdout and not result.stderr
            row['checks'].append({'name': f'account-code-allocator-{failure_at}', 'passed': passed,
                                  'status': result.returncode,
                                  'stdout': result.stdout.decode(errors='replace'),
                                  'stderr': result.stderr.decode(errors='replace')})
            report.write_text(json.dumps(record, indent=2) + '\n')
            if not passed:
                raise AssertionError(f'O{level} account code allocation {failure_at}: {result!r}')
        calls = folder / 'calls'
        calls.mkdir()
        calls_archive = calls / 'build.tar.gz'
        log = command([compiler, 'build', ROOT, '--ingot', 'fevm_calls', '--backend', 'native',
                       '-O', level, '--emit', 'ir,executable', '--out-dir', calls,
                       '--report', '--report-out', calls_archive], timeout=args.build_timeout)
        calls.joinpath('build.log').write_bytes(log)
        artifacts(calls / 'fevm_calls', calls_archive, calls, object_name='fevm_calls.o')
        # A depth-two CALL chain allocates one box per child, of the frame's
        # packed size. Fail each in turn; every success must be released.
        for failure_at in [0, 1, 2]:
            controlled = calls / f'allocator-{failure_at}'
            command(['cc', '-O2', '-Wall', '-Wextra', '-Werror', f'-DFAIL_AT={failure_at}',
                     f'-DWATCH_SIZE={FRAME_BOX_SIZE}', '-DSUCCESS_ALLOCS=2',
                     ROOT / 'native/fixtures/vm_allocator.c', calls / 'fevm_calls.o', '-o', controlled])
            result = subprocess.run([str(controlled)], capture_output=True, timeout=60)
            passed = result.returncode == 0 and not result.stdout and not result.stderr
            row['checks'].append({'name': f'call-frame-allocator-{failure_at}', 'passed': passed,
                                  'status': result.returncode,
                                  'stdout': result.stdout.decode(errors='replace'),
                                  'stderr': result.stderr.decode(errors='replace')})
            report.write_text(json.dumps(record, indent=2) + '\n')
            if not passed:
                raise AssertionError(f'O{level} call frame allocation {failure_at}: {result!r}')
        # LOG0 owns a separate copy of its frame memory. Check both allocation
        # failures using the already compiled interpreter object.
        for failure_at in [0, 1, 2]:
            controlled = folder / f'log-data-allocator-{failure_at}'
            command(['cc', '-O2', '-Wall', '-Wextra', '-Werror', f'-DFAIL_AT={failure_at}',
                     ROOT / 'native/fixtures/vm_allocator.c', folder / 'fevm.o', '-o', controlled])
            result = subprocess.run([str(controlled), '620100015fa0'], capture_output=True, timeout=60)
            expected = b'host allocation failed\n' if failure_at else b'empty\n'
            passed = result.returncode == (21 if failure_at else 0) and result.stdout == expected and not result.stderr
            row['checks'].append({'name': f'log-data-allocator-{failure_at}', 'passed': passed,
                                  'status': result.returncode, 'stdout': result.stdout.decode(errors='replace'),
                                  'stderr': result.stderr.decode(errors='replace')})
            report.write_text(json.dumps(record, indent=2) + '\n')
            if not passed:
                raise AssertionError(f'O{level} log data allocation {failure_at}: {result!r}')
        logs = folder / 'logs'
        logs.mkdir()
        log_archive = logs / 'build.tar.gz'
        log = command([compiler, 'build', ROOT, '--ingot', 'fevm_logs', '--backend', 'native',
                       '-O', level, '--emit', 'ir,executable', '--out-dir', logs,
                       '--report', '--report-out', log_archive], timeout=args.build_timeout)
        logs.joinpath('build.log').write_bytes(log)
        artifacts(logs / 'fevm_logs', log_archive, logs, object_name='fevm_logs.o')
        for mode, size in [('h', 94208), ('b', 128), ('b', 256)]:
            for failure_at in [0, 1]:
                name = f'log-headers-{failure_at}' if mode == 'h' else f'blob-hashes-{size}-{failure_at}'
                controlled = logs / name
                command(['cc', '-O2', '-Wall', '-Wextra', '-Werror', f'-DFAIL_AT={failure_at}',
                         f'-DWATCH_SIZE={size}', '-DSUCCESS_ALLOCS=1',
                         ROOT / 'native/fixtures/vm_allocator.c', logs / 'fevm_logs.o', '-o', controlled])
                result = subprocess.run([str(controlled), mode], capture_output=True, timeout=60)
                passed = result.returncode == 0 and not result.stdout and not result.stderr
                row['checks'].append({'name': name, 'passed': passed, 'status': result.returncode,
                                      'stdout': result.stdout.decode(errors='replace'),
                                      'stderr': result.stderr.decode(errors='replace')})
                report.write_text(json.dumps(record, indent=2) + '\n')
                if not passed:
                    raise AssertionError(f'O{level} {name}: {result!r}')
        print(f'CLI O{level}: {len(row["checks"])} passed', flush=True)
    record['complete'] = True
    report.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
