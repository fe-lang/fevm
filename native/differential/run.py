#!/usr/bin/env python3
"""Compare bounded Cancun frames with a pinned revm interpreter at O0/O1/O2."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from corpus import cases
from contract import assert_anchor, compare, validate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log, *, input=None, timeout=1800):
    with log.open('wb') as output:
        try:
            result = subprocess.run([str(arg) for arg in args], input=input, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            output.write(b'\nRunner timeout; this is not an EVM halt classification.\n')
            raise
    if result.returncode:
        raise RuntimeError(f'command exited {result.returncode}; see {log}')
    return log.read_bytes()


def build_reference(out, toolchain):
    target = out / 'reference-target'
    reference = target / 'release/fevm-reference'
    rustup = ['rustup', 'run', toolchain]
    cargo = [*rustup, 'cargo']
    record = {
        'toolchain': toolchain, 'target_directory': str(target),
        'rustc': subprocess.check_output([*rustup, 'rustc', '--version'], text=True).strip(),
        'cargo': subprocess.check_output([*cargo, '--version'], text=True).strip()}
    command([*cargo, 'build', '--release', '--locked', '--target-dir', target,
             '--manifest-path', HERE / 'reference/Cargo.toml'], out / 'reference-build.log')
    metadata = json.loads(subprocess.check_output(
        [*cargo, 'metadata', '--locked', '--format-version', '1',
         '--manifest-path', HERE / 'reference/Cargo.toml'], text=True,
        env=os.environ | {'CARGO_TARGET_DIR': str(target)}))
    (out / 'reference-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    record['packages'] = [
        {key: package[key] for key in ['name', 'version', 'source']}
        for package in metadata['packages'] if package['name'].startswith('revm-')]
    record['executable_sha256'] = digest(reference)
    return reference, record


def source_files():
    return sorted([*ROOT.glob('ingots/**/*.fe'), *ROOT.glob('ingots/**/fe.toml'), ROOT / 'fe.toml',
                   ROOT / 'native/toolchain.json', *HERE.glob('*.py'),
                   *HERE.glob('*driver/**/*.fe'), *HERE.glob('*driver/fe.toml'),
                   HERE / 'reference/Cargo.toml', HERE / 'reference/Cargo.lock',
                   *HERE.glob('reference/src/**/*.rs')])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--toolchain', default=json.loads((ROOT / 'native/toolchain.json').read_text())['rust_version'],
                        help='installed rustup toolchain for the reference (default: pinned Rust version)')
    parser.add_argument('--levels', nargs='+', choices=['0', '1', '2'], default=['0', '1', '2'])
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    compiler = args.fe.resolve()
    sources = source_files()
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    report = {'schema': 2, 'fork': 'Cancun', 'scope': 'outcome, remaining gas, output, completed stack/active memory; '
              'simultaneous-fault reasons retained separately; external state is not compared', 'complete': False,
              'host': platform.platform(), 'source_sha256': hashes, 'compiler_sha256': digest(compiler),
              'compiler_version': subprocess.check_output([compiler, '--version'], text=True).strip(),
              'revision': subprocess.check_output(['git', '-C', ROOT, 'rev-parse', 'HEAD'], text=True).strip(),
              'dirty': bool(subprocess.check_output(['git', '-C', ROOT, 'status', '--porcelain'])),
              'reference': {'specification_revision': 'c335bc4e9e99f7b91024d9033bdc89ce54394848'},
              'levels': []}
    report_path = out / 'results.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    save()
    try:
        command([sys.executable, '-m', 'unittest', 'discover', '-s', HERE, '-p', 'test_*.py'],
                out / 'contract-tests.log')
        reference, reference_record = build_reference(out, args.toolchain)
        report['reference'] |= reference_record
        corpus = cases()
        payload = ''.join(json.dumps({key: row[key] for key in ['code', 'calldata', 'gas_limit']}) + '\n' for row in corpus)
        data = command([reference], out / 'reference.jsonl', input=payload.encode(), timeout=60)
        expected = [json.loads(line) for line in data.splitlines()]
        if len(expected) != len(corpus):
            raise AssertionError('reference returned the wrong number of frames')
        for case, frame in zip(corpus, expected, strict=True):
            validate(frame, case['gas_limit'])
            if 'expected' in case:
                assert_anchor(frame, case['expected'])
            case['expected'] = frame
        corpus_path = out / 'cases.jsonl'
        corpus_path.write_text(''.join(json.dumps(case) + '\n' for case in corpus))
        report |= {'frames_per_level': len(corpus), 'categories': dict(Counter(row['category'] for row in corpus)),
                   'corpus_sha256': digest(corpus_path)}
        save()
        for level in args.levels:
            folder = out / f'O{level}'
            folder.mkdir()
            row = {'level': level, 'complete': False, 'passed': 0, 'reason_differences': []}
            report['levels'].append(row)
            save()
            started = time.perf_counter()
            command([compiler, 'build', ROOT, '--ingot', 'fevm_frame', '--backend', 'native', '-O', level,
                     '--emit', 'ir,executable', '--out-dir', folder,
                     '--report', '--report-out', folder / 'build.tar.gz'], folder / 'build.log')
            executable = folder / 'fevm_frame'
            row |= {'build_seconds': time.perf_counter() - started, 'executable_sha256': digest(executable)}
            for case in corpus:
                observed = subprocess.run([str(executable), case['code'], case['calldata'], str(case['gas_limit'])],
                                          capture_output=True, timeout=10)
                try:
                    frame = json.loads(observed.stdout)
                except (ValueError, UnicodeDecodeError):
                    frame = None
                error = None
                try:
                    if observed.returncode or observed.stderr:
                        raise AssertionError('process failed')
                    difference = compare(case, case['expected'], frame)
                    if difference:
                        row['reason_differences'].append(difference)
                except AssertionError as failure:
                    error = str(failure)
                with (folder / 'frames.jsonl').open('a') as frames:
                    frames.write(json.dumps({'case': case['name'], 'frame': frame}) + '\n')
                if error:
                    row['failure'] = {'error': error, 'case': case, 'exit_status': observed.returncode, 'actual': frame,
                                      'stdout': observed.stdout.decode(errors='replace'),
                                      'stderr': observed.stderr.decode(errors='replace')}
                    raise AssertionError(f'O{level} mismatch: {case["name"]}; see {report_path}')
                row['passed'] += 1
            row['complete'] = True
            save()
            print(f'Cancun frames O{level}: {row["passed"]} passed', flush=True)
        if hashes != {str(path.relative_to(ROOT)): digest(path) for path in sources}:
            raise RuntimeError('sources changed during the differential run')
        report['complete'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
