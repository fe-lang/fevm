#!/usr/bin/env python3
"""Run repeated transactions in one native process and check that memory stays flat."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
COUNTS = (1000, 10000, 40000)


def peak_rss(executable, count):
    process = subprocess.Popen([str(executable), str(count)])
    _, status, usage = os.wait4(process.pid, 0)
    if status != 0:
        raise RuntimeError(f'{count} transactions: wait status {status}')
    return usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--level', choices=['0', '1', '2'], default='2')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run([str(args.fe.resolve()), 'build', str(HERE), '--backend', 'native', '-O', args.level,
                    '--emit', 'executable', '--out-dir', str(out)], check=True)
    rows = [{'transactions': count, 'peak_rss_bytes': peak_rss(out / 'fevm_soak', count)}
            for count in COUNTS]
    (out / 'results.json').write_text(json.dumps({'level': args.level, 'runs': rows}, indent=2) + '\n')
    first, last = rows[0]['peak_rss_bytes'], rows[-1]['peak_rss_bytes']
    print(f'peak RSS after {COUNTS[0]} and {COUNTS[-1]} transactions: {first} and {last} bytes')
    # Leaking even 32 bytes per transaction would add more than a mebibyte.
    if last - first > 1 << 20:
        raise SystemExit(f'peak RSS grew by {last - first} bytes')


if __name__ == '__main__':
    main()
