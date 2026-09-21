#!/usr/bin/env python3
"""Native Fe numeric differential checks and CPU-time microbenchmarks (stdlib only)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import struct
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MASK = (1 << 256) - 1
OPERATIONS = {
    'add': ('a + b', 'add(a, b)'),
    'mul': ('a * b', 'mul(a, b)'),
    'div': ('a / b', 'divide(numerator: a, denominator: b).quotient'),
    'rem': ('a % b', 'divide(numerator: a, denominator: b).remainder'),
    'shl': ('a << b', 'shift_left(value: a, shift: b)'),
    'shr': ('a >> b', 'shift_right(value: a, shift: b)'),
    'lt': ('(a < b) as u256', 'Word { a: less(a, b) as u64, b: 0, c: 0, d: 0 }'),
    'pow': ('a ** b', 'power(base: a, exponent: b)'),
}


def command(args, **kwargs):
    result = subprocess.run([str(x) for x in args], capture_output=True, timeout=600, **kwargs)
    if result.returncode:
        raise RuntimeError(f'command failed ({result.returncode}): {args}\n'
                           + result.stdout.decode(errors='replace')
                           + result.stderr.decode(errors='replace'))
    return result.stdout


def reference(op, a, b):
    if op == 'add': return (a + b) & MASK
    if op == 'mul': return (a * b) & MASK
    if op == 'div': return a // b
    if op == 'rem': return a % b
    if op == 'shl': return (a << b) & MASK if b < 256 else 0
    if op == 'shr': return a >> b if b < 256 else 0
    if op == 'lt': return int(a < b)
    if op == 'pow': return pow(a, b, 1 << 256)
    raise ValueError(op)


def repeated(op, a, b, rounds):
    seed = a
    for _ in range(rounds):
        result = reference(op, a, b)
        a = result ^ seed
    return result


def vectors(op, count):
    rng = random.Random(0xFE256)
    edges = [0, 1, 2, 7, MASK, MASK - 1]
    for bit in [63, 64, 65, 127, 128, 129, 191, 192, 193, 255]:
        edges.extend([(1 << bit) - 1, 1 << bit, (1 << bit) + 1])
    pairs = [(a, b) for a in edges for b in edges]
    pairs += [(rng.getrandbits(256), rng.getrandbits(256)) for _ in range(count)]
    if op in ('shl', 'shr'):
        pairs += [(a, b) for a in edges for b in [0, 1, 63, 64, 65, 127, 128, 191, 192, 255, 256, 257]]
    if op in ('div', 'rem'):
        pairs = [(a, b) for a, b in pairs if b]
    return pairs


def source(op, representation):
    body = OPERATIONS[op][representation == 'limbs']
    if representation == 'builtin':
        setup = 'let seed = pack(lhs)\n    let b = pack(rhs)'
        finish = 'unpack(result)'
        next_a = 'result ^ seed'
    else:
        setup = 'let seed = lhs\n    let b = rhs'
        finish = 'result'
        next_a = 'xor(result, seed)'
    kernel = f'''
#[inline(never)]
#[arithmetic(unchecked)]
fn kernel(lhs: Word, rhs: Word, rounds: u64) -> Word {{
    {setup}
    let mut a = seed
    let mut result = seed
    let mut i: u64 = 0
    while i < rounds {{
        result = {body}
        a = {next_a}
        i += 1
    }}
    {finish}
}}
'''
    return HERE.joinpath('words.fe').read_text() + kernel + HERE.joinpath('driver.fe').read_text()


def execute(executable, op, cases):
    payload = b''.join(b'@' + struct.pack('<Q', n) + a.to_bytes(32, 'little')
                       + b.to_bytes(32, 'little') for a, b, n in cases)
    output = command([executable], input=payload)
    if len(output) != 40 * len(cases):
        raise AssertionError(f'{executable}: expected {40 * len(cases)} output bytes, got {len(output)}')
    ticks = []
    expected_results = {}
    for i, (a, b, n) in enumerate(cases):
        row = output[i * 40:(i + 1) * 40]
        observed = int.from_bytes(row[8:], 'little')
        key = (a, b, n)
        if key not in expected_results:
            expected_results[key] = repeated(op, a, b, n)
        expected = expected_results[key]
        if observed != expected:
            raise AssertionError(f'{executable}: {op} a={a:#x} b={b:#x} rounds={n}: '
                                 f'expected {expected:#x}, got {observed:#x}')
        ticks.append(int.from_bytes(row[:8], 'little'))
    return ticks


def host_info(out):
    system = (platform.system(), platform.machine())
    if system not in [('Darwin', 'arm64'), ('Linux', 'x86_64')]:
        raise RuntimeError(f'unsupported native acceptance host: {system}')
    # Verify the scalar libc clock ABI and conversion rather than assuming its rate.
    probe = out / 'clock_probe.c'
    probe.write_text('#include <stdio.h>\n#include <time.h>\n'
                     'int main(void) { printf("%zu %lld\\n", sizeof(clock_t), '
                     '(long long)CLOCKS_PER_SEC); return 0; }\n')
    binary = out / 'clock_probe'
    command(['cc', '-O2', probe, '-o', binary])
    width, frequency = map(int, command([binary]).split())
    if width != 8 or frequency <= 0:
        raise RuntimeError(f'unsupported clock_t ABI: {width} bytes / {frequency} Hz')
    return {'system': system[0], 'machine': system[1], 'platform': platform.platform(),
            'cpu': command(['sysctl', '-n', 'machdep.cpu.brand_string']).decode().strip()
            if system[0] == 'Darwin' else Path('/proc/cpuinfo').read_text().splitlines()[:25],
            'clock_ticks_per_second': frequency,
            'cc': command(['cc', '--version']).decode().splitlines()[0]}


def artifacts(executable, report, output, *, object_name):
    # Extract only the compiler's object bytes; never unpack arbitrary archive paths.
    with tarfile.open(report) as archive:
        objects = [m for m in archive.getmembers() if m.isfile() and Path(m.name).name == object_name]
        if len(objects) != 1:
            raise RuntimeError(f'expected one native object in {report}, found {len(objects)}')
        object_path = output / object_name
        object_path.write_bytes(archive.extractfile(objects[0]).read())
    started = time.perf_counter()
    command(['cc', object_path, '-o', output / 'relinked'])
    link_seconds = time.perf_counter() - started
    size_args = ['size', '-m', object_path] if platform.system() == 'Darwin' else ['size', '-A', object_path]
    size_text = command(size_args).decode()
    output.joinpath('size.txt').write_text(size_text)
    if platform.system() == 'Darwin':
        text_bytes = sum(int(line.split()[-1]) for line in size_text.splitlines()
                         if line.strip().startswith('Section ') and '__text' in line)
        assembly = command(['otool', '-tvV', object_path])
    else:
        text_bytes = sum(int(line.split()[1]) for line in size_text.splitlines()
                         if line.strip().startswith('.text'))
        assembly = command(['objdump', '-dr', object_path])
    if text_bytes <= 0:
        raise RuntimeError(f'failed to find native text size in {size_text}')
    output.joinpath('assembly.txt').write_bytes(assembly)
    return {'object_bytes': object_path.stat().st_size, 'text_bytes': text_bytes,
            'executable_bytes': executable.stat().st_size, 'relink_seconds': link_seconds,
            'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest()}


def measure(executable, op, frequency, samples, milliseconds):
    # Named operand classes make small-divisor claims distinguishable from full-width ones.
    operands = {'wide': (MASK - 0x123456789ABC, (1 << 191) + 0xFEDCBA98765)}
    if op in ('div', 'rem'):
        operands |= {'small': (MASK - 31, 7), 'both_u64': ((1 << 63) + 17, 7), 'equal': (MASK - 31, MASK - 31),
                     'numerator_smaller': (17, MASK - 31)}
    if op in ('shl', 'shr'): operands = {'shift_13': (MASK - 31, 13), 'shift_128': (MASK - 31, 128)}
    if op == 'pow': operands = {'exponent_17': (MASK - 30, 17), 'exponent_wide': (MASK - 30, (1 << 255) + 1)}
    rows = []
    for name, (a, b) in operands.items():
        rounds = 32
        while True:
            ticks = execute(executable, op, [(a, b, rounds)])[0]
            if ticks >= frequency * milliseconds / 1000 or rounds >= 1 << 22:
                break
            rounds *= 4
        if ticks == 0:
            raise RuntimeError('timer resolution insufficient; increase batch size')
        # First request warms the same process; every returned checksum is verified.
        measured = execute(executable, op, [(a, b, rounds)] * (samples + 1))[1:]
        ns = [t * 1e9 / frequency / rounds for t in measured]
        rows.append({'operands': name, 'lhs': hex(a), 'rhs': hex(b), 'rounds': rounds,
                     'cpu_ns_per_iteration': ns, 'median_cpu_ns': statistics.median(ns),
                     'min_cpu_ns': min(ns), 'max_cpu_ns': max(ns)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--operations', nargs='+', choices=OPERATIONS, default=list(OPERATIONS))
    parser.add_argument('--representations', nargs='+', choices=['builtin', 'limbs'], default=['builtin', 'limbs'])
    parser.add_argument('--levels', nargs='+', choices=['0', '1', '2'], default=['0', '1', '2'])
    parser.add_argument('--random-cases', type=int, default=128)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--batch-ms', type=int, default=20)
    parser.add_argument('--build-samples', type=int, help='default: three builds, or one with --check-only')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.build_samples is None:
        args.build_samples = 1 if args.check_only else 3
    if min(args.random_cases, args.samples, args.batch_ms, args.build_samples) < 1:
        parser.error('counts and durations must be positive')
    args.fe = args.fe.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.out.joinpath('results.json').exists():
        parser.error('results.json already exists; choose a fresh --out directory')
    result = {'schema': 1, 'complete': False,
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'host': host_info(args.out),
              'compiler': {'path': str(args.fe), 'version': command([args.fe, '--version']).decode().strip(),
                           'sha256': hashlib.sha256(args.fe.read_bytes()).hexdigest()},
              'harness_revision': command(['git', '-C', ROOT, 'rev-parse', 'HEAD']).decode().strip(),
              'harness_dirty': bool(command(['git', '-C', ROOT, 'status', '--porcelain'])),
              'timing': 'process CPU clock, input/output and startup excluded; dependent op/xor loop; '
                        'build includes compiler startup, link and report; relink measured separately',
              'results': []}
    args.out.joinpath('results.json').write_text(json.dumps(result, indent=2) + '\n')
    for op in args.operations:
        pairs = vectors(op, args.random_cases)
        cases = [(a, b, 1) for a, b in pairs]
        cases += [(a, b, 7) for a, b in pairs[::max(1, len(pairs) // 32)]]
        for representation in args.representations:
            for level in args.levels:
                name = f'{op}-{representation}-O{level}'
                folder = args.out / name
                folder.mkdir(exist_ok=True)
                src = folder / 'kernel.fe'
                src.write_text(source(op, representation))
                command([args.fe, 'fmt', src])
                build_seconds = []
                for _ in range(args.build_samples):
                    report = folder / f'build-{time.time_ns()}.tar.gz'
                    started = time.perf_counter()
                    command([args.fe, 'build', '--standalone', '--backend', 'native', '-O', level,
                             '--emit', 'ir,executable', '--out-dir', folder, '--report', '--report-out', report, src])
                    build_seconds.append(time.perf_counter() - started)
                executable = folder / 'kernel'
                execute(executable, op, cases)
                sizes = artifacts(executable, report, folder, object_name='kernel.o')
                execute(folder / 'relinked', op, cases[:10])
                row = {'operation': op, 'representation': representation, 'level': level,
                       'checked_cases': len(cases), 'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                       'build_seconds': build_seconds, 'median_build_seconds': statistics.median(build_seconds),
                       **sizes, 'measurements': []}
                if not args.check_only:
                    row['measurements'] = measure(executable, op, result['host']['clock_ticks_per_second'],
                                                  args.samples, args.batch_ms)
                result['results'].append(row)
                args.out.joinpath('results.json').write_text(json.dumps(result, indent=2) + '\n')
                print(f'{name}: {len(cases)} cases passed; text={sizes["text_bytes"]} bytes; '
                      f'build={row["median_build_seconds"]:.3f}s; '
                      + ', '.join(f'{m["operands"]}={m["median_cpu_ns"]:.1f} ns' for m in row['measurements']), flush=True)
    result['complete'] = True
    args.out.joinpath('results.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
