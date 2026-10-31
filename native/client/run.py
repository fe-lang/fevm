#!/usr/bin/env python3
"""Build fevm and run the session client's tests against it."""
import argparse
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fe', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--level', default='2', choices=['0', '1', '2'])
    parser.add_argument('--toolchain', default=json.loads((ROOT / 'native/toolchain.json').read_text())['rust_version'],
                        help='installed rustup toolchain for the client (default: pinned Rust version)')
    parser.add_argument('--build-timeout', type=int, default=600,
                        help='seconds allowed for the Fe build (default: 600)')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    subprocess.run([str(args.fe.resolve()), 'build', '--backend', 'native', '--ingot', 'fevm', '-O', args.level,
                    '--out-dir', str(out), str(ROOT)], check=True, timeout=args.build_timeout)
    subprocess.run(['rustup', 'run', args.toolchain, 'cargo', 'test', '--locked', '--target-dir', str(out / 'target')],
                   cwd=HERE, check=True, env=os.environ | {'FEVM_BIN': str(out / 'fevm')})


if __name__ == '__main__':
    main()
