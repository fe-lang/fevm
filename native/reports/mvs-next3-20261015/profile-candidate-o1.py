import json
import os
import signal
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
COMPILER = str(BASE / 'candidate-bootstrap/bin/fe')
resources = BASE / 'resources.jsonl'
sample = None
while sample is None:
    try:
        with resources.open('rb') as file:
            file.seek(max(0, resources.stat().st_size - 65536))
            latest = json.loads(file.read().splitlines()[-1])
        for process in latest['compiler_processes']:
            args = process['arguments']
            if args[0] == COMPILER and 'test' in args and '-O' in args and args[args.index('-O') + 1] == '1':
                sample = process
                break
        if json.loads((BASE / 'acceptance/acceptance.json').read_text())['complete']:
            break
    except (OSError, ValueError, IndexError):
        pass
    if sample is None:
        time.sleep(2)
if sample is None:
    raise SystemExit('O1 compiler exited before attachment')
pid = sample['pid']
started = time.time()
with (BASE / 'candidate-O1.log').open('w') as log:
    perf = subprocess.Popen(
        ['perf', 'record', '-e', 'task-clock:u', '-F', '49', '--call-graph', 'dwarf,8192', '--timestamp', '-p', str(pid),
         '-o', str(BASE / 'candidate-O1.data')], stdout=log, stderr=subprocess.STDOUT,
        env={**os.environ, 'DEBUGINFOD_URLS': ''})
    while perf.poll() is None:
        try:
            running = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')[0].decode() == COMPILER
        except OSError:
            running = False
        if not running or time.time() - started > 2400:
            perf.send_signal(signal.SIGINT)
            break
        time.sleep(1)
    status = perf.wait(timeout=30)
record = {'compiler': COMPILER, 'pid': pid, 'started_unix': started,
          'finished_unix': time.time(), 'frequency_hz': 49, 'event': 'task-clock:u',
          'initial_sample_cpu_seconds': sample['cpu_seconds'], 'status': status,
          'scope': 'Fixed O1 acceptance compiler from first resource-sample detection until process exit; earlier startup excluded.'}
(BASE / 'candidate-O1-capture.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
