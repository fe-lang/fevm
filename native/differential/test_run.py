"""Reference build regressions; temporary artifacts are retained for inspection."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import run

sys.path.insert(0, str(run.ROOT / 'native'))
from arith.run import command as captured_command

RUST_VERSION = json.loads((run.ROOT / 'native/toolchain.json').read_text())['rust_version']
FRAME = {'status': 'success', 'stack': [], 'output': '0x'}


class ReferenceBuildTests(unittest.TestCase):
    def test_cli_build_timeout_is_accepted_and_enforced(self):
        output = captured_command([sys.executable, '-c', 'print("ready")'], timeout=5)
        self.assertEqual(output, b'ready\n')
        with self.assertRaises(subprocess.TimeoutExpired):
            captured_command([sys.executable, '-c', 'import time; time.sleep(5)'], timeout=0.05)

    def test_fresh_reference_ignores_ambient_target_and_toolchain(self):
        for setting in ['environment', 'config']:
            with self.subTest(setting=setting):
                root = Path(tempfile.mkdtemp(prefix='fevm-reference-test-'))
                here = root / 'native/differential'
                reference = here / 'reference'
                (reference / 'src').mkdir(parents=True)
                (reference / 'Cargo.toml').write_text(
                    '[package]\nname = "fevm-reference"\nversion = "0.1.0"\nedition = "2024"\n')
                (reference / 'Cargo.lock').write_text(
                    'version = 4\n\n[[package]]\nname = "fevm-reference"\nversion = "0.1.0"\n')
                (reference / 'src/main.rs').write_text(
                    'use std::io::{self, BufRead};\nfn main() {\n'
                    '    for line in io::stdin().lock().lines() {\n'
                    '        line.unwrap();\n'
                    f'        println!("{{}}", r#"{json.dumps(FRAME)}"#);\n'
                    '    }\n}\n')
                stale = reference / 'target/release/fevm-reference'
                stale.parent.mkdir(parents=True)
                stale.write_text('stale oracle must never run\n')
                cargo_home = root / 'cargo-home'
                cargo_home.mkdir()
                redirected = root / 'redirected-target'
                environment = {'CARGO_HOME': str(cargo_home), 'RUSTUP_TOOLCHAIN': 'uninstalled-ambient-toolchain'}
                if setting == 'environment':
                    environment['CARGO_TARGET_DIR'] = str(redirected)
                else:
                    (cargo_home / 'config.toml').write_text(f'[build]\ntarget-dir = "{redirected}"\n')
                out = root / 'results'
                out.mkdir()
                with patch.dict(os.environ, environment), patch.object(run, 'HERE', here):
                    if setting == 'config':
                        os.environ.pop('CARGO_TARGET_DIR', None)
                    binary, report = run.build_reference(out, RUST_VERSION)
                self.assertEqual(subprocess.check_output([binary], input='\n', text=True).strip(), json.dumps(FRAME))
                self.assertEqual(report['toolchain'], RUST_VERSION)
                self.assertEqual(report['rustc'].split()[1], RUST_VERSION)
                self.assertEqual(report['cargo'].split()[1], RUST_VERSION)
                self.assertEqual(binary, out / 'reference-target/release/fevm-reference')
                metadata = json.loads((out / 'reference-metadata.json').read_text())
                self.assertEqual(metadata['target_directory'], report['target_directory'])
                self.assertEqual(report['executable_sha256'], run.digest(binary))
                self.assertEqual(stale.read_text(), 'stale oracle must never run\n')
                self.assertFalse(redirected.exists())


if __name__ == '__main__':
    unittest.main()
