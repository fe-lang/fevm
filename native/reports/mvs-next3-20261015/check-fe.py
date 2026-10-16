import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
FE = BASE / 'fe'
ENV = {**os.environ, 'TMPDIR': '/dev/shm/fevm-mvs-runs',
       'RAYON_NUM_THREADS': '1', 'CARGO_BUILD_JOBS': '2',
       'CARGO_TARGET_DIR': '/tmp/fevm-mvs-target-preserved-on-disk',
       'CARGO_NET_GIT_FETCH_WITH_CLI': 'true'}
count = int(ENV.get('GIT_CONFIG_COUNT', '0'))
ENV[f'GIT_CONFIG_KEY_{count}'] = f'url.{(BASE / "sonatina").as_uri()}.insteadOf'
ENV[f'GIT_CONFIG_VALUE_{count}'] = 'https://github.com/fe-lang/sonatina'
ENV['GIT_CONFIG_COUNT'] = str(count + 1)
LOCK = json.loads((BASE / 'fe-pin-update.json').read_text())['cargo_lock_sha256']
COMMANDS = [
    ('format', ['cargo', '+nightly', 'fmt', '--all']),
    ('nextest', ['cargo', '+1.99.0', 'nextest', 'r', '--release', '--no-fail-fast', '--locked', '--workspace', '--all-features']),
    ('doctests', ['cargo', '+1.99.0', 'test', '--release', '--locked', '--workspace', '--all-features', '--doc']),
    ('clippy', ['cargo', '+1.99.0', 'clippy', '--release', '--locked', '--workspace', '--all-features', '--all-targets', '--', '-D', 'warnings']),
    ('notes', ['make', 'check-notes', 'EISENBOTE=/tmp/fevm-mvs-refresh-20261014-r1/eisenbote']),
    ('format-check', ['cargo', '+nightly', 'fmt', '--all', '--', '--check']),
]
record = {'complete': False, 'checks': []}
for name, command in COMMANDS:
    started = time.perf_counter()
    with (BASE / f'fe-{name}.log').open('wb') as log:
        status = subprocess.run(command, cwd=FE, env=ENV,
                                stdout=log, stderr=subprocess.STDOUT).returncode
    record['checks'].append({'name': name, 'command': command, 'status': status,
                             'seconds': time.perf_counter() - started})
    assert hashlib.sha256((FE / 'Cargo.lock').read_bytes()).hexdigest() == LOCK
    (BASE / 'fe-checks.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'{name}: {status}', flush=True)
    if status:
        raise SystemExit(status)
record['complete'] = True
(BASE / 'fe-checks.json').write_text(json.dumps(record, indent=2) + '\n')
