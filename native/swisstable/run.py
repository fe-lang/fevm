#!/usr/bin/env python3
"""Compare exact SwissTable revisions: native behavior, probes, and CPU time."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'arith'))
from run import artifacts, command, host_info

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TABLE = 'ingots/swisstable/src/lib.fe'
BASELINE = '1a41c9609c95c884425c0f7262f9d914c71fcda2'
MASK64 = (1 << 64) - 1
MASK256 = (1 << 256) - 1
PRIMES = (0x9E3779B185EBCA87, 0xC2B2AE3D27D4EB4F,
          0x165667B19E3779F9, 0x85EBCA77C2B2AE63)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hash_key(key, variant):
    if variant == 'baseline':
        x = key ^ 0x9E3779B97F4A7C15
        x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK256
        x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & MASK256
        return (x ^ (x >> 31)) & MASK64
    p1, p2, p3, p4 = PRIMES

    def rotate(x, n):
        return ((x << n) | (x >> (64 - n))) & MASK64

    def update(acc, lane):
        return (rotate((acc + lane * p2) & MASK64, 31) * p1) & MASK64

    lanes = [(key >> shift) & MASK64 for shift in (0, 64, 128, 192)]
    accumulators = [update(acc & MASK64, lane)
                    for acc, lane in zip((p1 + p2, p2, 0, -p1), lanes)]
    h = sum(rotate(acc, shift) for acc, shift in zip(accumulators, (1, 7, 12, 18))) & MASK64
    for acc in accumulators:
        h = ((h ^ update(0, acc)) * p1 + p4) & MASK64
    h = (h + 32) & MASK64
    h = ((h ^ (h >> 33)) * p2) & MASK64
    h = ((h ^ (h >> 29)) * p3) & MASK64
    return h ^ (h >> 32)


class Model:
    """Physical probe accounting, checked separately from a dictionary oracle."""
    def __init__(self, variant):
        self.variant = variant
        self.ctrl = [255] * 256
        self.keys = [None] * 256

    def search(self, key):
        h = hash_key(key, self.variant)
        group = h & 240
        fingerprint = (h >> 8) & 127
        deleted = None
        slots = comparisons = 0
        for groups in range(1, 17):
            for slot in range(group, group + 16):
                slots += 1
                ctrl = self.ctrl[slot]
                if ctrl == fingerprint:
                    comparisons += 1
                    if self.keys[slot] == key:
                        return True, slot, (groups, slots, comparisons)
                if ctrl == 128 and deleted is None:
                    deleted = slot
                elif ctrl == 255:
                    return False, deleted if deleted is not None else slot, (groups, slots, comparisons)
            group = (group + 16) % 256
        return False, deleted, (16, slots, comparisons)

    def apply(self, kind, key):
        found, slot, probes = self.search(key)
        if kind == 1 and slot is not None:
            self.ctrl[slot] = (hash_key(key, self.variant) >> 8) & 127
            self.keys[slot] = key
        elif kind == 2 and found:
            self.ctrl[slot] = 128
        return probes


def instrument(source):
    """Count the real search loop in a separate generated diagnostic executable."""
    substitutions = [
        ('struct TableSearch {', 'struct TableSearch { groups: u64, slots: u64, comparisons: u64,', 1),
        ('let mut first_deleted: usize = 0',
         'let mut groups: u64 = 0\nlet mut slots: u64 = 0\nlet mut comparisons: u64 = 0\n'
         'let mut first_deleted: usize = 0', 1),
        ('while probe < TABLE_GROUPS {', 'while probe < TABLE_GROUPS { groups += 1', 1),
        ('let ctrl = self.ctrl[slot]', 'let ctrl = self.ctrl[slot]\nslots += 1\n'
         'if ctrl == fingerprint { comparisons += 1 }', 1),
        ('return TableSearch {', 'return TableSearch { groups, slots, comparisons,', 2),
        ('TableSearch { found: false,', 'TableSearch { groups, slots, comparisons, found: false,', 1),
    ]
    for old, new, count in substitutions:
        if source.count(old) != count:
            raise ValueError(f'probe instrumentation no longer matches source: {old!r}')
        source = source.replace(old, new)
    return source


def source_text(table, profile):
    # The production ingot tests run separately; this root embeds its exact
    # implementation to access private probe details without a public debug API.
    table = table.split('#[test]', 1)[0]
    if 'WrappingAdd' not in table:
        table = table.replace('use core::ops::WrappingMul', 'use core::ops::{WrappingAdd, WrappingMul}')
    if profile:
        table = instrument(table)
    diagnostic = '''let hash = key.hash()
let search = table.search(key, hash, h2(hash))
write64(search.groups)
write64(search.slots)
write64(search.comparisons)''' if profile else ''
    driver = HERE.joinpath('driver.fe').read_text()
    return table + driver.replace('__PROFILE_OPERATION__', diagnostic).replace('__PROFILE_QUERY__', diagnostic)


def workloads():
    rng = random.Random(0xFE5A155)
    families = {f'limb{limb}': [i << (64 * limb) for i in range(4096)] for limb in range(4)}
    families['repeated_limbs'] = [i * sum(1 << b for b in (0, 64, 128, 192)) for i in range(4096)]
    families['random'] = [rng.getrandbits(256) for _ in range(4096)]
    cases = []
    for family, keys in families.items():
        for occupancy in (64, 128, 224, 256):
            for history in ('fresh', 'churn', 'drained'):
                initial = 256 if history == 'drained' else occupancy
                live = list(range(initial))
                operations = [(1, keys[i], 2 * (i + 1)) for i in live]
                if history == 'drained':
                    operations += [(2, keys[i], 0) for i in live[:256 - occupancy]]
                    live = live[256 - occupancy:]
                elif history == 'churn':
                    for generation in range(1, 4):
                        replacement = []
                        for i, old in enumerate(live):
                            new = generation * occupancy + i
                            operations.extend([(2, keys[old], 0), (1, keys[new], 2 * (new + 1))])
                            replacement.append(new)
                        live = replacement
                # Evenly sample the entire live range rather than just early inserts.
                hits = [keys[live[i * len(live) // 64]] for i in range(64)]
                for kind, queries in [('hit', hits), ('miss', keys[3072:3136])]:
                    cases.append({'name': f'{family}-{occupancy}-{history}-{kind}',
                                  'family': family, 'occupancy': occupancy,
                                  'history': history, 'kind': kind,
                                  'operations': operations, 'queries': queries})
    # A dictionary oracle exercises full-table failure, updates, removal misses,
    # high limbs, and long mixed traces independently of the physical model.
    keys = families['random'][:384]
    operations = [(1, key, 2 * (i + 1)) for i, key in enumerate(keys)]
    operations += [(rng.choice((1, 1, 2)), rng.choice(keys), rng.getrandbits(255) << 1)
                   for _ in range(2048)]
    for offset in (0, 128, 256):
        cases.append({'name': f'mixed-oracle-{offset}', 'kind': 'oracle',
                      'operations': operations, 'queries': keys[offset:offset + 128]})
    # Every single bit, adjacent-bit pair, and complemented single bit is hashed
    # at runtime, supplementing the independent xxhsum golden vectors in Fe.
    keys = [0, MASK256] + [1 << i for i in range(256)]
    keys += [MASK256 ^ (1 << i) for i in range(256)]
    keys += [3 << i for i in range(255)]
    keys += families['random']
    for offset in range(0, len(keys), 256):
        cases.append({'name': f'hash-bits-{offset}', 'kind': 'oracle',
                      'operations': [], 'queries': keys[offset:offset + 256]})
    return cases


def expected(case):
    values = {}
    replies = []
    for kind, key, value in case['operations']:
        if kind == 1:
            success = key in values or len(values) < 256
            if success:
                values[key] = value
        else:
            success = key in values
            values.pop(key, None)
        replies.append((int(success), len(values)))
    return values, replies


def payload(case, rounds):
    data = bytearray(b'@' + struct.pack('<Q', len(case['operations'])))
    for kind, key, value in case['operations']:
        data += struct.pack('<Q', kind) + key.to_bytes(32, 'little') + value.to_bytes(32, 'little')
    data += struct.pack('<Q', len(case['queries']))
    data += b''.join(key.to_bytes(32, 'little') for key in case['queries'])
    return data + struct.pack('<Q', rounds)


def execute(executable, case, rounds, variant, profile, samples=1):
    data = command([executable], input=payload(case, rounds) * samples)
    values, replies = expected(case)
    # Each workload has even values, hence every timed lookup advances one key.
    cycle = [values.get(key, 0) & MASK64 ^ int(key in values) for key in case['queries']]
    cycles, tail = divmod(rounds, len(cycle))
    checksum = (cycles * sum(cycle) + sum(cycle[:tail])) & MASK64
    model = Model(variant)
    operation_probes = [model.apply(kind, key) for kind, key, value in case['operations']]
    query_probes = [model.search(key)[2] for key in case['queries']]
    deleted = model.ctrl.count(128)
    offset = 0

    def take(width=8):
        nonlocal offset
        end = offset + width
        if end > len(data):
            raise AssertionError(f'truncated output: {executable}: {case["name"]}')
        value = int.from_bytes(data[offset:end], 'little')
        offset = end
        return value

    ticks = []
    for sample in range(samples):
        for reply, probes in zip(replies, operation_probes):
            if profile:
                observed = tuple(take() for _ in range(3))
                if observed != probes:
                    raise AssertionError(f'operation probes: {observed} != {probes}')
            observed = (take(), take())
            if observed != reply:
                raise AssertionError(f'{case["name"]}: map result {observed} != {reply}')
        if take() != deleted:
            raise AssertionError(f'{case["name"]}: tombstone count differs')
        for key, probes in zip(case['queries'], query_probes):
            if profile and tuple(take() for _ in range(3)) != probes:
                raise AssertionError(f'{case["name"]}: query probes differ')
            observed = (take(), take(32), take(), take(), take())
            h = hash_key(key, variant)
            wanted = (int(key in values), values.get(key, 0), h, h & 240, (h >> 8) & 127)
            if observed != wanted:
                raise AssertionError(f'{case["name"]}: key {key:#x}: {observed} != {wanted}')
        ticks.append(take())
        observed = take()
        if observed != checksum:
            raise AssertionError(f'{case["name"]}: batch checksum {observed} != {checksum}')
    if offset != len(data):
        raise AssertionError(f'unexpected trailing output: {len(data) - offset} bytes')
    return ticks, query_probes, operation_probes, deleted


def summarize(probes):
    result = {}
    for index, name in enumerate(('groups', 'slots', 'equality_checks')):
        values = sorted(row[index] for row in probes)
        result[name] = {'mean': statistics.mean(values), 'max': max(values),
                        'p95': values[(95 * len(values) - 1) // 100],
                        'histogram': dict(sorted(Counter(values).items()))}
    return result


def build(fe, out, table, variant, level, profile):
    folder = out / f'{variant}-O{level}-{"probes" if profile else "timing"}'
    folder.mkdir()
    src = folder / 'kernel.fe'
    src.write_text(source_text(table, profile))
    command([fe, 'fmt', src])
    report = folder / 'build.tar.gz'
    started = time.perf_counter()
    command([fe, 'build', '--standalone', '--backend', 'native', '-O', level,
             '--emit', 'ir,executable', '--out-dir', folder, '--report', '--report-out', report, src])
    seconds = time.perf_counter() - started
    executable = folder / 'kernel'
    sizes = artifacts(executable, report, folder)
    return executable, {'variant': variant, 'level': level, 'profile': profile,
                        'source_sha256': digest(src.read_bytes()), 'build_seconds': seconds,
                        **sizes, 'checks': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--baseline-revision', default=BASELINE)
    parser.add_argument('--levels', nargs='+', choices=['0', '1', '2'], default=['0', '1', '2'])
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--batch-ms', type=int, default=10)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if min(args.samples, args.trials, args.batch_ms) < 1:
        parser.error('counts and durations must be positive')
    args.fe = args.fe.resolve()
    args.out = args.out.resolve()
    # Refuse any stale artifacts, including an interrupted run without results.
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('output directory must be empty')
    args.out.mkdir(parents=True, exist_ok=True)
    baseline_revision = command(['git', '-C', ROOT, 'rev-parse', '--verify',
                                 f'{args.baseline_revision}^{{commit}}']).decode().strip()
    sources = {'baseline': command(['git', '-C', ROOT, 'show', f'{baseline_revision}:{TABLE}']).decode(),
               'candidate': ROOT.joinpath(TABLE).read_text()}
    cases = workloads()
    corpus = json.dumps(cases, separators=(',', ':')).encode()
    args.out.joinpath('corpus.json').write_bytes(corpus)
    record = {'schema': 1, 'complete': False, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'host': host_info(args.out), 'baseline_revision': baseline_revision,
              'candidate_revision': command(['git', '-C', ROOT, 'rev-parse', 'HEAD']).decode().strip(),
              'candidate_dirty': bool(command(['git', '-C', ROOT, 'status', '--porcelain'])),
              'runner_sha256': digest(Path(__file__).read_bytes()),
              'driver_sha256': digest(HERE.joinpath('driver.fe').read_bytes()),
              'corpus_sha256': digest(corpus),
              'compiler': {'path': str(args.fe), 'sha256': digest(args.fe.read_bytes()),
                           'version': command([args.fe, '--version']).decode().strip()},
              'table_sha256': {key: digest(value.encode()) for key, value in sources.items()},
              'timing': 'uninstrumented native lookup CPU time; runtime keys, dependent next index; '
                        'startup/setup/I/O excluded; separate instrumented executable counts actual probes',
              'builds': [], 'comparisons': []}
    report = args.out / 'results.json'
    report.write_text(json.dumps(record, indent=2) + '\n')
    executables = {}
    for level in args.levels:
        for variant, table in sources.items():
            for profile in (False, True):
                executable, row = build(args.fe, args.out, table, variant, level, profile)
                executables[level, variant, profile] = executable
                for case in cases:
                    ticks, probes, operations, deleted = execute(executable, case, 257, variant, profile)
                    check = {'case': case['name'], 'operations': len(case['operations']),
                             'queries': len(case['queries']), 'deleted': deleted}
                    if profile:
                        check['query_probes'] = summarize(probes)
                        if operations:
                            check['operation_probes'] = summarize(operations)
                    row['checks'].append(check)
                # Confirm the independently relinked object obeys the same protocol.
                execute(executable.parent / 'relinked', cases[0], 257, variant, profile)
                record['builds'].append(row)
                report.write_text(json.dumps(record, indent=2) + '\n')
                print(f'{executable.parent.name}: {len(cases)} scenarios passed; '
                      f'text={row["text_bytes"]}; build={row["build_seconds"]:.2f}s', flush=True)
        if args.check_only:
            continue
        frequency = record['host']['clock_ticks_per_second']
        for case in cases:
            if case['kind'] == 'oracle':
                continue
            rounds = {}
            for variant in sources:
                n = 1024
                while True:
                    ticks = execute(executables[level, variant, False], case, n, variant, False)[0][0]
                    if ticks >= frequency * args.batch_ms / 1000 or n >= 1 << 24:
                        break
                    n *= 4
                if ticks == 0:
                    raise RuntimeError('insufficient timer resolution')
                rounds[variant] = n
            comparison = {'case': case['name'], 'level': level, 'rounds': rounds,
                          'trials': [], 'median_cpu_ns': {}}
            for trial in range(args.trials):
                order = list(sources) if trial % 2 == 0 else list(reversed(sources))
                values = {}
                for variant in order:
                    ticks = execute(executables[level, variant, False], case, rounds[variant],
                                    variant, False, args.samples + 1)[0][1:]
                    values[variant] = [t * 1e9 / frequency / rounds[variant] for t in ticks]
                comparison['trials'].append({'order': order, 'cpu_ns_per_lookup': values})
            for variant in sources:
                comparison['median_cpu_ns'][variant] = statistics.median(
                    x for trial in comparison['trials'] for x in trial['cpu_ns_per_lookup'][variant])
            comparison['speedup'] = (comparison['median_cpu_ns']['baseline'] /
                                     comparison['median_cpu_ns']['candidate'])
            record['comparisons'].append(comparison)
            report.write_text(json.dumps(record, indent=2) + '\n')
            print(f'O{level} {case["name"]}: {comparison["speedup"]:.2f}x', flush=True)
    record['complete'] = True
    report.write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
