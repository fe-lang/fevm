#!/usr/bin/env python3
"""Compare bounded Cancun frames with a pinned revm interpreter at O0/O1/O2."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from corpus import cases

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--levels', nargs='+', choices=['0', '1', '2'], default=['0', '1', '2'])
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    compiler = args.fe.resolve()
    sources = sorted([*ROOT.glob('ingots/**/*.fe'), *ROOT.glob('ingots/**/fe.toml'), ROOT / 'fe.toml',
                      *HERE.glob('*.py'), *HERE.glob('driver/**/*.fe'), HERE / 'driver/fe.toml',
                      HERE / 'reference/Cargo.toml', HERE / 'reference/Cargo.lock',
                      HERE / 'reference/src/main.rs'])
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    reference = HERE / 'reference/target/release/fevm-reference'
    report = {'schema': 1, 'fork': 'Cancun', 'scope': 'halt status, successful/reverted final stack, output; '
              'gas, memory accounting and external state are not compared', 'complete': False,
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
        command(['cargo', 'build', '--release', '--locked', '--manifest-path', HERE / 'reference/Cargo.toml'],
                out / 'reference-build.log')
        metadata = json.loads(subprocess.check_output(
            ['cargo', 'metadata', '--locked', '--format-version', '1',
             '--manifest-path', HERE / 'reference/Cargo.toml'], text=True))
        (out / 'reference-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        report['reference']['packages'] = [
            {'name': package['name'], 'version': package['version'], 'source': package['source']}
            for package in metadata['packages'] if package['name'].startswith('revm-')]
        report['reference']['executable_sha256'] = digest(reference)
        corpus = cases()
        payload = ''.join(json.dumps({key: row[key] for key in ['code', 'calldata']}) + '\n' for row in corpus)
        data = command([reference], out / 'reference.jsonl', input=payload.encode(), timeout=60)
        expected = [json.loads(line) for line in data.splitlines()]
        if len(expected) != len(corpus):
            raise AssertionError('reference returned the wrong number of frames')
        for case, frame in zip(corpus, expected, strict=True):
            if 'expected' in case and case['expected'] != frame:
                raise AssertionError(f'reference disagrees with specification anchor {case["name"]}: {frame}')
            case['expected'] = frame
        corpus_path = out / 'cases.jsonl'
        corpus_path.write_text(''.join(json.dumps(case) + '\n' for case in corpus))
        report |= {'frames_per_level': len(corpus), 'categories': dict(Counter(row['category'] for row in corpus)),
                   'corpus_sha256': digest(corpus_path)}
        save()
        for level in args.levels:
            folder = out / f'O{level}'
            folder.mkdir()
            row = {'level': level, 'complete': False, 'passed': 0}
            report['levels'].append(row)
            save()
            started = time.perf_counter()
            command([compiler, 'build', ROOT, '--ingot', 'fevm_frame', '--backend', 'native', '-O', level,
                     '--emit', 'ir,executable', '--out-dir', folder,
                     '--report', '--report-out', folder / 'build.tar.gz'], folder / 'build.log')
            executable = folder / 'fevm_frame'
            row |= {'build_seconds': time.perf_counter() - started, 'executable_sha256': digest(executable)}
            for case in corpus:
                observed = subprocess.run([str(executable), case['code'], case['calldata']],
                                          capture_output=True, timeout=10)
                try:
                    frame = json.loads(observed.stdout)
                except (ValueError, UnicodeDecodeError):
                    frame = None
                if observed.returncode or observed.stderr or frame != case['expected']:
                    row['failure'] = {'case': case, 'exit_status': observed.returncode, 'actual': frame,
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
