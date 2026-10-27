#!/usr/bin/env python3
"""Time FeVM, revm and evmone on state-test benchmarks such as ipsilon/evm-benchmarks."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
_spec = importlib.util.spec_from_file_location('conformance', HERE.parent / 'conformance' / 'run.py')
conformance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conformance)


def cases(benchmarks, fork, selection):
    for path in sorted(benchmarks.rglob('*.json')):
        for name, test in json.loads(path.read_text()).items():
            labels = test.get('_info', {}).get('labels', {})
            for post in test['post'].get(fork, []):
                index = post['indexes']['data']
                label = f'{name}/{labels.get(str(index), index)}'
                if not selection or any(part in label for part in selection):
                    yield label, conformance.encode(test, post['indexes']), post


def outcome(command, payload, statuses):
    """The outcome one run of `command` reports for `payload`, comparable across
    drivers; `statuses` maps FeVM's numeric statuses to revm's names."""
    process = subprocess.run(command, input=payload, capture_output=True)
    assert process.returncode == 0, (command, process.returncode, process.stderr.decode(errors='replace')[-2000:])
    result = json.loads(process.stdout)
    if result['invalid']:
        return {'invalid': True}
    status = result['status']
    if statuses:
        status = 'success' if status == 0 else 'revert' if status == 19 else 'halt'
    return {'invalid': False, 'status': status.split()[0], 'gas_used': result['gas_used'],
            'logs_hash': result['logs_hash']}


def seconds(command, payload, runs, execute, repeat):
    """The least CPU time of `repeat` runs of `command RUNS TRANSACT`."""
    best = None
    for _ in range(repeat):
        process = subprocess.Popen([*command, str(runs), str(int(execute))], stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        process.stdin.write(payload)
        process.stdin.close()
        _, status, usage = os.wait4(process.pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0, (command, process.stderr.read().decode(errors='replace'))
        process.stderr.close()
        elapsed = usage.ru_utime + usage.ru_stime
        best = elapsed if best is None else min(best, elapsed)
    return best


def transaction_seconds(command, payload, target, repeat):
    """CPU seconds per transaction: building the pre-state and applying the
    transaction RUNS times, minus only building it RUNS times."""
    runs = 8
    while True:
        cost = seconds(command, payload, runs, True, 1) - seconds(command, payload, runs, False, 1)
        if cost * 4 >= target or runs >= 1 << 24:
            break
        runs *= 4
    runs = max(runs, int(runs * target / max(cost, 1e-9)))
    return (seconds(command, payload, runs, True, repeat) - seconds(command, payload, runs, False, repeat)) / runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmarks', type=Path, required=True, help='directory of state-test JSON files')
    parser.add_argument('--fe', type=Path, help='compiler to build the conformance driver with')
    parser.add_argument('--executable', type=Path, help='reuse a built conformance driver')
    parser.add_argument('--revm', type=Path, help='reuse a built revm runner')
    parser.add_argument('--evmone', type=Path, help='also time this evmone runner (see evmone/build.sh)')
    parser.add_argument('--out', type=Path, default=ROOT / 'native' / 'out' / 'bench')
    parser.add_argument('--level', choices=['0', '1', '2'], default='2')
    parser.add_argument('--fork', default='London', help="the fixtures' post-state fork; execution uses Cancun")
    parser.add_argument('--target', type=float, default=0.3, help='CPU seconds of transactions per timed run')
    parser.add_argument('--repeat', type=int, default=3, help='timed runs per mode; the least time counts')
    parser.add_argument('--select', nargs='*', default=[], help='run cases whose label contains any of these')
    args = parser.parse_args()
    # Freed setup memory would otherwise return to the OS after every run, and
    # setup-only runs would pay to grow the heap again. Fixing the trim
    # threshold also fixes glibc's otherwise adaptive mmap threshold; at 32 MiB
    # it keeps large buffers on the heap, reused as in a long-running process.
    os.environ |= {'MALLOC_TRIM_THRESHOLD_': str(1 << 40), 'MALLOC_MMAP_THRESHOLD_': str(32 << 20)}
    if (args.fe is None) == (args.executable is None):
        parser.error('pass exactly one of --fe and --executable')
    fevm = args.executable
    if fevm is None:
        subprocess.run([args.fe, 'build', ROOT, '--ingot', 'fevm_conformance', '--backend', 'native',
                        '-O', args.level, '--out-dir', args.out / 'fevm'], check=True, stdout=subprocess.DEVNULL)
        fevm = args.out / 'fevm' / 'fevm_conformance'
    revm = args.revm
    if revm is None:
        manifest = HERE / 'revm' / 'Cargo.toml'
        subprocess.run(['cargo', 'build', '--release', '--quiet', '--manifest-path', manifest,
                        '--target-dir', args.out / 'revm'], check=True, cwd=HERE / 'revm')
        revm = args.out / 'revm' / 'release' / 'fevm-bench-revm'
    engines = {'fevm': fevm, 'revm': revm} | ({'evmone': args.evmone} if args.evmone else {})
    ratios = {name: [] for name in engines if name != 'fevm'}
    for label, payload, post in cases(args.benchmarks.resolve(), args.fork, args.select):
        outcomes = {name: outcome([path], payload, statuses=name == 'fevm') for name, path in engines.items()}
        row = {'case': label, 'gas_used': outcomes['fevm'].get('gas_used')}
        for name, path in engines.items():
            row[f'{name}_us'] = round(transaction_seconds([path], payload, args.target, args.repeat) * 1e6, 2)
        for name, values in ratios.items():
            values.append(row['fevm_us'] / row[f'{name}_us'])
            row[f'fevm/{name}'] = round(values[-1], 3)
        row['match'] = all(result == outcomes['fevm'] for result in outcomes.values()) \
            and outcomes['fevm'].get('logs_hash') == post['logs']
        if not row['match']:
            row |= {'outcomes': outcomes, 'expected_logs': post['logs']}
        print(json.dumps(row), flush=True)
    summary = {f'geomean fevm/{name}': round(math.exp(sum(map(math.log, values)) / len(values)), 3)
               for name, values in ratios.items() if values}
    print(json.dumps(summary))

if __name__ == '__main__':
    main()
