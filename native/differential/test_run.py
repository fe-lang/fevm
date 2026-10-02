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
import accept

RUST_VERSION = json.loads((run.ROOT / 'native/toolchain.json').read_text())['rust_version']
FRAME = {'status': 'success', 'stack': [], 'output': '0x'}


class ReferenceBuildTests(unittest.TestCase):
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

    def test_acceptance_passes_bootstrap_rust_version(self):
        root = Path(tempfile.mkdtemp(prefix='fevm-accept-test-'))
        compiler = root / 'fe'
        compiler.write_bytes(b'test compiler')
        build = root / 'build.json'
        build.write_text(json.dumps({'complete': True, 'compiler': str(compiler),
                                     'compiler_sha256': run.digest(compiler),
                                     'manifest': {'rust_version': 'bootstrap-selected-toolchain'}}))
        with patch.object(sys, 'argv', ['accept.py', '--build', str(build), '--out', str(root / 'results')]), \
                patch.object(accept.platform, 'platform', return_value='test host'), \
                patch.object(accept.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as invoke:
            with self.assertRaises(SystemExit) as result:
                accept.main()
        self.assertEqual(result.exception.code, 0)
        commands = [call.args[0] for call in invoke.call_args_list]
        for runner in ['run.py', 'state_run.py']:
            command = next(command for command in commands if str(accept.HERE / f'differential/{runner}') in command)
            self.assertEqual(command[command.index('--toolchain') + 1], 'bootstrap-selected-toolchain')


if __name__ == '__main__':
    unittest.main()
