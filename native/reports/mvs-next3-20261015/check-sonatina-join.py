import json
import os
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
TARGET = '/tmp/fevm-mvs-target-preserved-on-disk'
ENV = {**os.environ, 'TMPDIR': '/dev/shm/fevm-mvs-runs',
       'RAYON_NUM_THREADS': '1', 'CARGO_BUILD_JOBS': '2', 'CARGO_TARGET_DIR': TARGET}
COMMANDS = [
    ('format-write', ['cargo', '+nightly', 'fmt', '--all']),
    ('nextest', ['cargo', '+1.99.0', 'nextest', 'r', '--release', '--no-fail-fast', '--locked', '--workspace', '--all-features']),
    ('doctests', ['cargo', '+1.99.0', 'test', '--release', '--locked', '--workspace', '--all-features', '--doc']),
    ('docs', ['cargo', '+1.99.0', 'doc', '--release', '--locked', '--workspace', '--all-features', '--no-deps']),
    ('filecheck', ['cargo', '+1.99.0', 'run', '--release', '--locked', '-p', 'sonatina-filecheck']),
    ('clippy', ['cargo', '+1.99.0', 'clippy', '--release', '--locked', '--workspace', '--all-features', '--all-targets', '--', '-D', 'warnings']),
    ('format', ['cargo', '+nightly', 'fmt', '--all', '--', '--check']),
]
record = {'complete': False, 'checks': []}
for name, command in COMMANDS:
    started = time.perf_counter()
    with (BASE / f'sonatina-join-{name}.log').open('wb') as log:
        status = subprocess.run(command, cwd=BASE / 'sonatina', env=ENV,
                                stdout=log, stderr=subprocess.STDOUT).returncode
    record['checks'].append({'name': name, 'command': command, 'status': status,
                             'seconds': time.perf_counter() - started})
    (BASE / 'sonatina-join-checks.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'{name}: {status}', flush=True)
    if status:
        raise SystemExit(status)
record['complete'] = True
(BASE / 'sonatina-join-checks.json').write_text(json.dumps(record, indent=2) + '\n')
