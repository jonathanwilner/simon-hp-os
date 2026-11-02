import json
import os
from pathlib import Path
import subprocess
import shutil
import shlex
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'update-hp-os.sh'

@unittest.skipIf(os.geteuid() == 0, 'bootstrap intentionally requires a normal login')
class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.checkout = self.home / 'public'
        self.checkout.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.checkout)], check=True)
        subprocess.run(['git', '-C', str(self.checkout), 'remote', 'add', 'origin', 'https://github.com/jonathanwilner/simon-hp-os.git'], check=True)
        installer = self.checkout / 'goran/installer'
        installer.mkdir(parents=True)
        (installer / 'update-desktop.sh').write_text('printf "%s\\n" "$@" > "$HOME/invoked"\n')
        (installer / 'migrate-local-config.py').write_text('import os,pathlib,sys,json\npathlib.Path(os.environ["HOME"],"migrated").write_text(json.dumps(sys.argv[1:]))\nsys.exit(int(os.environ.get("MIGRATE_EXIT",0)))\n')
        bindir = self.home / 'bin'
        bindir.mkdir()
        for name in ('nix', 'tmux'):
            p = bindir / name
            p.write_text('#!/bin/sh\nexit 0\n')
            p.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_STATE_HOME=str(self.home / "state"), PATH=str(bindir) + ':' + os.environ['PATH'])
        self.env.pop('SIMON_DESKTOP_CHECKOUT', None)
        self.real_git = shutil.which('git')
        self.git_wrapper = bindir / 'git'
        self.git_wrapper.write_text('#!/usr/bin/env bash\n'
            'if [[ "$3" == fetch ]]; then exit 0; fi\n'
            'if [[ "$3" == show && "$4" == FETCH_HEAD:goran/installer/merge-desktop-update.sh ]]; then printf "exit 0\\n"; exit 0; fi\n'
            'exec ' + shlex.quote(self.real_git) + ' "$@"\n')
        self.git_wrapper.chmod(0o755)


    def run_script(self, *args):
        return subprocess.run(['bash', str(SCRIPT), '--checkout', str(self.checkout), *args], env=self.env, text=True, capture_output=True)

    def legacy(self):
        p = self.home / 'src/nixos-amd'
        p.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(p)], check=True)
        profile = p / 'goran/installer/simon-home.nix'
        profile.parent.mkdir(parents=True)
        profile.write_text('{}')
        return p

    def test_missing_checkout_clones_public_source(self):
        subprocess.run(['git', '-C', str(self.checkout), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.checkout), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        git = shlex.quote(shutil.which('git'))
        seed = shlex.quote(str(self.checkout))
        wrapper = self.home / 'bin/git'
        wrapper.write_text('#!/usr/bin/env bash\nset -e\nif [[ "$1" == clone ]]; then\n'
                           '  [[ "$3" == https://github.com/jonathanwilner/simon-hp-os.git ]]\n'
                           f'  {git} clone -- {seed} "$4"\n'
                           f'  {git} -C "$4" remote set-url origin "$3"\n'
                           f'elif [[ "$3" == fetch ]]; then exit 0;\n'
                           'elif [[ "$3" == show ]]; then printf "exit 0\\n";\n'
                           f'else exec {git} "$@"; fi\n')
        wrapper.chmod(0o755)
        self.checkout = self.home / 'new-public'
        result = self.run_script('--build-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / 'invoked').exists())

    def test_old_checkout_updates_tools_and_preserves_dirty_config(self):
        installer = self.checkout / 'goran/installer'
        (installer / 'migrate-local-config.py').unlink()
        (self.checkout / 'local-config.nix').write_text('original\n')
        def git(*args):
            return subprocess.run([self.real_git, '-C', str(self.checkout), *args], check=True, capture_output=True)
        git('add', '.')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'old installation')
        seed = self.home / 'published'
        subprocess.run([self.real_git, 'clone', '-q', str(self.checkout), str(seed)], check=True)
        subprocess.run([self.real_git, '-C', str(seed), 'branch', '-M', 'main'], check=True)
        new_installer = seed / 'goran/installer'
        (new_installer / 'merge-desktop-update.sh').write_bytes((SCRIPT.parent / 'goran/installer/merge-desktop-update.sh').read_bytes())
        (new_installer / 'migrate-local-config.py').write_text('import pathlib,os\npathlib.Path(os.environ["HOME"],"migrated").write_text("new helper")\n')
        subprocess.run([self.real_git, '-C', str(seed), 'add', '.'], check=True)
        subprocess.run([self.real_git, '-C', str(seed), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'publish migration tools'], check=True)
        (self.checkout / 'local-config.nix').write_text('custom setting\n')
        (self.checkout / 'untracked.nix').write_text('custom module\n')
        self.legacy()
        self.git_wrapper.write_text('#!/usr/bin/env bash\n'
            f'if [[ "$3" == fetch ]]; then exec {shlex.quote(self.real_git)} -C "$2" fetch {shlex.quote(str(seed))} main; fi\n'
            f'if [[ "$1" == fetch ]]; then exec {shlex.quote(self.real_git)} fetch {shlex.quote(str(seed))} main; fi\n'
            f'exec {shlex.quote(self.real_git)} "$@"\n')
        result = self.run_script('--build-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / 'migrated').read_text(), 'new helper')
        self.assertEqual((self.checkout / 'local-config.nix').read_text(), 'custom setting\n')
        self.assertEqual((self.checkout / 'untracked.nix').read_text(), 'custom module\n')
        self.assertTrue(git('for-each-ref', 'refs/simon-update-recovery').stdout.strip())
        self.assertTrue((self.home / 'invoked').exists())

    def test_build_only_forwarded(self):
        result = self.run_script('--build-only', '--attach')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = (self.home / 'invoked').read_text()
        self.assertIn('--build-only', args)
        self.assertIn('--attach', args)
        self.assertFalse((self.home / 'migrated').exists())

    def test_wrong_origin_stops_before_updater(self):
        subprocess.run(['git', '-C', str(self.checkout), 'remote', 'set-url', 'origin', 'https://example.com/other.git'], check=True)
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertFalse((self.home / 'invoked').exists())

    def test_legacy_detected_and_baseline_forwarded(self):
        old = self.legacy()
        self.assertEqual(self.run_script('--legacy-base', 'abc123').returncode, 0)
        args = json.loads((self.home / 'migrated').read_text())
        self.assertEqual(args, ['--from', str(old), '--to', str(self.checkout), '--legacy-base', 'abc123'])
        self.assertEqual((old / 'goran/installer/simon-home.nix').read_text(), '{}')

    def test_migration_conflict_prevents_activation(self):
        self.legacy()
        self.env['MIGRATE_EXIT'] = '2'
        self.assertEqual(self.run_script().returncode, 2)
        self.assertFalse((self.home / 'invoked').exists())

    def test_same_source_and_target_refused(self):
        self.assertNotEqual(self.run_script('--from', str(self.checkout)).returncode, 0)
        self.assertFalse((self.home / 'invoked').exists())

if __name__ == '__main__': unittest.main()
