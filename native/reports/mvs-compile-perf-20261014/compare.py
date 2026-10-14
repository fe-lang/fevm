import hashlib
import argparse
import json
import os
import statistics
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--pattern', default='*.sntn')
parser.add_argument('--out', default='comparison')
args = parser.parse_args()
OUT = BASE / args.out
OUT.mkdir(exist_ok=True)
ENV = {**os.environ, 'RAYON_NUM_THREADS': '1', 'TMPDIR': '/dev/shm/fevm-mvs-runs'}
ROWS = []
SAMPLES = []
for source in sorted((BASE / 'fixtures').glob(args.pattern)):
    case = source.stem
    measured = {'baseline': [], 'candidate': []}
    for repeat in range(6):
        order = ['baseline', 'candidate'] if repeat % 2 == 0 else ['candidate', 'baseline']
        for variant in order:
            timing = OUT / f'{case}-{repeat}-{variant}.time.json'
            started = time.perf_counter()
            child = subprocess.run(
                ['/usr/bin/time', '-f', '{"user":%U,"system":%S,"rss_kib":%M}',
                 '-o', str(timing), str(BASE / f'sonatina-{variant}'), 'verify', str(source)],
                env=ENV, capture_output=True, timeout=180)
            elapsed = time.perf_counter() - started
            (OUT / f'{case}-{repeat}-{variant}.log').write_bytes(child.stdout + child.stderr)
            sample = {'case': case, 'variant': variant, 'repeat': repeat,
                      'warmup': repeat == 0, 'seconds': elapsed, 'status': child.returncode,
                      **json.loads(timing.read_text().splitlines()[-1])}
            SAMPLES.append(sample)
            (OUT / 'samples.json').write_text(json.dumps(SAMPLES, indent=2) + '\n')
            assert child.returncode == 0 and child.stdout == b'ok\n', (case, variant, child.stdout, child.stderr)
            if repeat:
                measured[variant].append(sample)
    medians = {variant: statistics.median(row['seconds'] for row in samples)
               for variant, samples in measured.items()}
    row = {'case': case, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
           'median_wall_seconds': medians,
           'speedup': medians['baseline'] / medians['candidate'],
           'median_peak_rss_kib': {variant: statistics.median(row['rss_kib'] for row in samples)
                                   for variant, samples in measured.items()}}
    ROWS.append(row)
    record = {'complete': False,
              'scope': 'Full IR verification including parsing/startup; one warmup pair and five alternating measured pairs, one Rayon worker, no concurrent task builds/tests.',
              'binaries': {variant: hashlib.sha256((BASE / f'sonatina-{variant}').read_bytes()).hexdigest()
                           for variant in measured}, 'results': ROWS}
    (OUT / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'{case}: {medians["baseline"]:.6f}s -> {medians["candidate"]:.6f}s ({row["speedup"]:.2f}x)', flush=True)
record['complete'] = True
(OUT / 'results.json').write_text(json.dumps(record, indent=2) + '\n')
