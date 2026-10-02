#!/usr/bin/env python3
"""Compare Cancun state gas, refunds and journal boundaries against pinned revm."""
import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from run import HERE, ROOT, build_reference, command, digest, source_files
from state_contract import assert_anchors, compare, validate
from state_corpus import cases, encode, payload


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
    report = {
        'schema': 1, 'fork': 'Cancun', 'complete': False,
        'scope': 'frame results, watched persistent/transient/original state, warmness, signed refunds, '
                 'nested checkpoints and transaction settlement; signed envelopes and CALL/CREATE are excluded',
        'host': platform.platform(), 'source_sha256': hashes, 'compiler_sha256': digest(compiler),
        'compiler_version': subprocess.check_output([compiler, '--version'], text=True).strip(),
        'revision': subprocess.check_output(['git', '-C', ROOT, 'rev-parse', 'HEAD'], text=True).strip(),
        'dirty': bool(subprocess.check_output(['git', '-C', ROOT, 'status', '--porcelain'])),
        'reference': {'specification_revision': 'c335bc4e9e99f7b91024d9033bdc89ce54394848'},
        'levels': [],
    }
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
        data = command([reference, '--state'], out / 'reference.jsonl',
                       input=''.join(json.dumps(payload(row)) + '\n' for row in corpus).encode(), timeout=60)
        expected = [json.loads(line) for line in data.splitlines()]
        if len(expected) != len(corpus):
            raise AssertionError('reference returned the wrong number of cases')
        for case, results in zip(corpus, expected, strict=True):
            validate(case, results)
            assert_anchors(case, results)
            case['expected'] = results
        corpus_path = out / 'cases.jsonl'
        corpus_path.write_text(''.join(json.dumps(case) + '\n' for case in corpus))
        report |= {'cases_per_level': len(corpus), 'categories': dict(Counter(row['category'] for row in corpus)),
                   'corpus_sha256': digest(corpus_path)}
        save()
        for level in args.levels:
            folder = out / f'O{level}'
            folder.mkdir()
            row = {'level': level, 'complete': False, 'passed': 0}
            report['levels'].append(row)
            save()
            started = time.perf_counter()
            command([compiler, 'build', ROOT, '--ingot', 'fevm_state', '--backend', 'native', '-O', level,
                     '--emit', 'ir,executable', '--out-dir', folder,
                     '--report', '--report-out', folder / 'build.tar.gz'], folder / 'build.log')
            executable = folder / 'fevm_state'
            row |= {'build_seconds': time.perf_counter() - started, 'executable_sha256': digest(executable)}
            for case in corpus:
                observed = subprocess.run([str(executable), encode(case)], capture_output=True, timeout=30)
                try:
                    results = json.loads(observed.stdout)
                except (ValueError, UnicodeDecodeError):
                    results = None
                with (folder / 'states.jsonl').open('a') as states:
                    states.write(json.dumps({'case': case['name'], 'results': results}) + '\n')
                try:
                    if observed.returncode or observed.stderr:
                        raise AssertionError('process failed')
                    compare(case, case['expected'], results)
                except AssertionError as error:
                    row['failure'] = {'error': str(error), 'case': case, 'exit_status': observed.returncode,
                                      'actual': results, 'stdout': observed.stdout.decode(errors='replace'),
                                      'stderr': observed.stderr.decode(errors='replace')}
                    raise AssertionError(f'O{level} mismatch: {case["name"]}; see {report_path}') from error
                row['passed'] += 1
            row['complete'] = True
            save()
            print(f'Cancun state O{level}: {row["passed"]} passed', flush=True)
        if hashes != {str(path.relative_to(ROOT)): digest(path) for path in sources}:
            raise RuntimeError('sources changed during the state differential run')
        report['complete'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
