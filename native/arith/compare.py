#!/usr/bin/env python3
"""Remeasure matching native artifacts in alternating baseline/candidate order."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

from run import host_info, measure


def artifacts(report):
    data = json.loads(report.read_text())
    if not data.get('complete'):
        raise RuntimeError(f'incomplete arithmetic run: {report}')
    result = {}
    for row in data['results']:
        key = (row['operation'], row['representation'], row['level'])
        executable = report.parent / f'{key[0]}-{key[1]}-O{key[2]}' / 'kernel'
        if hashlib.sha256(executable.read_bytes()).hexdigest() != row['executable_sha256']:
            raise RuntimeError(f'artifact no longer matches {report}: {executable}')
        result[key] = (executable, row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True, help='arithmetic results.json with retained artifacts')
    parser.add_argument('--candidate', type=Path, required=True, help='arithmetic results.json with retained artifacts')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--samples', type=int, default=7)
    parser.add_argument('--batch-ms', type=int, default=20)
    args = parser.parse_args()
    if min(args.trials, args.samples, args.batch_ms) < 1:
        parser.error('counts and duration must be positive')
    baseline, candidate = artifacts(args.baseline), artifacts(args.candidate)
    keys = sorted(baseline.keys() & candidate.keys())
    if not keys:
        parser.error('no common operation/representation/optimization combinations')
    for key in keys:
        if baseline[key][1]['source_sha256'] != candidate[key][1]['source_sha256']:
            parser.error(f'sources differ for {key}')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = out / 'comparison.json'
    if report.exists():
        parser.error('comparison.json already exists; choose a fresh --out directory')
    result = {'schema': 1, 'complete': False, 'host': host_info(out),
              'baseline_report': str(args.baseline.resolve()), 'candidate_report': str(args.candidate.resolve()),
              'baseline_report_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              'candidate_report_sha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
              'method': 'alternating order per trial; process CPU time; dependent op/xor loops; all checksums verified',
              'results': []}
    report.write_text(json.dumps(result, indent=2) + '\n')
    for key in keys:
        row = {'operation': key[0], 'representation': key[1], 'level': key[2],
               'source_sha256': baseline[key][1]['source_sha256'], 'trials': []}
        for trial in range(args.trials):
            order = ['baseline', 'candidate'] if trial % 2 == 0 else ['candidate', 'baseline']
            measurements = {'order': order}
            for name in order:
                executable = (baseline if name == 'baseline' else candidate)[key][0]
                measurements[name] = measure(executable, key[0], result['host']['clock_ticks_per_second'],
                                             args.samples, args.batch_ms)
            row['trials'].append(measurements)
        row['summary'] = []
        for operand in row['trials'][0]['baseline']:
            name = operand['operands']
            medians = {}
            for version in ['baseline', 'candidate']:
                samples = [sample for trial in row['trials'] for measurement in trial[version]
                           if measurement['operands'] == name for sample in measurement['cpu_ns_per_iteration']]
                medians[version] = statistics.median(samples)
            row['summary'].append({'operands': name, 'baseline_cpu_ns': medians['baseline'],
                                   'candidate_cpu_ns': medians['candidate'],
                                   'speedup': medians['baseline'] / medians['candidate']})
        result['results'].append(row)
        report.write_text(json.dumps(result, indent=2) + '\n')
        print(f'{key}: ' + ', '.join(f'{m["operands"]}={m["speedup"]:.2f}x' for m in row['summary']), flush=True)
    result['complete'] = True
    report.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
