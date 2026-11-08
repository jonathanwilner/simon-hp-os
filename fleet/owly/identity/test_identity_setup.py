import contextlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('setup', Path(__file__).with_name('identity_setup.py'))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home / '.config'),
                                           'XDG_STATE_HOME': str(self.home / '.local/state'),
                                           'XDG_RUNTIME_DIR': str(self.home / 'runtime')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = setup.Setup(self.home)
        self.source = self.home / 'input'
        self.source.mkdir()
        self.data = {name: ('test ' + name).encode() for name in setup.FILES}
        for name, data in self.data.items(): (self.source / name).write_bytes(data)
        self.valid = dict(certificate_expires='2030-01-01T00:00:00Z', record_expires='2029-01-01T00:00:00Z', expires_epoch=time.time()+86400*30)

    def test_missing_does_not_claim_identity(self):
        self.assertFalse(self.app.status()['valid'])
        self.assertEqual(self.app.status()['state'], 'missing')

    def test_bad_identity_leaves_existing_files_unchanged(self):
        setup.private_dir(self.app.keys)
        (self.app.keys / 'certificate.pem').write_bytes(b'old')
        with patch.object(setup, 'validate', side_effect=setup.SetupError('key does not match certificate')):
            with self.assertRaises(setup.SetupError): self.app.import_directory(self.source)
        self.assertEqual((self.app.keys / 'certificate.pem').read_bytes(), b'old')
        self.assertFalse(self.app.settings.exists())

    def test_active_receiver_refuses_import(self):
        with patch.object(setup, 'validate', return_value=self.valid), patch.object(self.app, 'upstream_status', return_value={'receiving': True}):
            with self.assertRaisesRegex(setup.SetupError, 'Stop receiving'): self.app.import_directory(self.source)
        self.assertFalse(self.app.settings.exists())

    def test_import_backup_and_selfsigned_preserve_trio(self):
        with patch.object(setup, 'validate', return_value=self.valid), patch.object(self.app, 'upstream_status', return_value={'receiving': False}):
            result = self.app.import_directory(self.source)
            self.assertTrue(result['ok'])
            for name in setup.FILES:
                self.assertEqual((self.app.keys / name).read_bytes(), self.data[name])
                self.assertEqual((self.app.keys / name).stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.app.source(), 'disk')
            self.app.switch('self-signed')
            self.assertEqual(self.app.source(), 'self-signed')
            self.assertTrue(all((self.app.keys / name).exists() for name in setup.FILES))
            self.assertEqual(len(list(self.app.state.glob('backup-*'))), 2)

    def test_failed_postwrite_validation_restores_old_identity(self):
        setup.private_dir(self.app.keys)
        setup.private_dir(self.app.config)
        old = {name: ('old ' + name).encode() for name in setup.FILES}
        for name, data in old.items(): (self.app.keys / name).write_bytes(data)
        self.app.settings.write_text('sound=false\nidentity_source=self-signed\n')
        with patch.object(setup, 'validate', side_effect=[self.valid, setup.SetupError('expired')]), patch.object(self.app, 'upstream_status', return_value={'receiving': False}):
            with self.assertRaisesRegex(setup.SetupError, 'restored'): self.app.import_directory(self.source)
        for name, data in old.items(): self.assertEqual((self.app.keys / name).read_bytes(), data)
        self.assertEqual(self.app.settings.read_text(), 'sound=false\nidentity_source=self-signed\n')

    def test_expired_cache_cannot_remain_valid(self):
        setup.private_dir(self.app.keys)
        for name, data in self.data.items(): (self.app.keys / name).write_bytes(data)
        expired = dict(self.valid, expires_epoch=time.time()-1)
        with patch.object(setup, 'validate', return_value=expired):
            self.assertFalse(self.app.status()['valid'])
            self.assertEqual(self.app.status()['state'], 'expired')

    def test_symlink_and_oversize_inputs_rejected(self):
        (self.source / 'key.pem').unlink()
        (self.source / 'key.pem').symlink_to(self.source / 'certificate.pem')
        with self.assertRaises(setup.SetupError): self.app.import_directory(self.source)
        (self.source / 'key.pem').unlink()
        (self.source / 'key.pem').write_bytes(b'x' * (setup.MAX_FILE+1))
        with self.assertRaises(setup.SetupError): self.app.import_directory(self.source)

    def test_selfsigned_recovers_without_reading_bad_apple_files(self):
        setup.private_dir(self.app.keys)
        (self.app.keys / 'key.pem').symlink_to(self.source / 'key.pem')
        with patch.object(self.app, 'upstream_status', return_value={'receiving': False}), patch.object(self.app, 'status', return_value={}):
            self.assertTrue(self.app.switch('self-signed')['ok'])
        self.assertEqual(self.app.source(), 'self-signed')
        self.assertTrue((self.app.keys / 'key.pem').is_symlink())

    def test_failed_recovery_reports_backup_and_does_not_claim_restored(self):
        setup.private_dir(self.app.keys)
        for name in setup.FILES: (self.app.keys / name).write_bytes(b'old')
        original_write = setup.write_private
        def failing_write(path, data):
            if path.parent == self.app.keys: raise OSError('disk unavailable')
            return original_write(path, data)
        with patch.object(setup, 'validate', return_value=self.valid), patch.object(self.app, 'upstream_status', return_value={'receiving': False}), patch.object(setup, 'write_private', side_effect=failing_write):
            with self.assertRaisesRegex(setup.SetupError, 'recovery failed.*private backup'):
                self.app.import_directory(self.source)
        self.assertTrue(list(self.app.state.glob('backup-*')))

    def test_basic_legacy_pair_does_not_need_apple_renewal(self):
        setup.private_dir(self.app.keys)
        for name in setup.FILES[:2]: (self.app.keys / name).write_bytes(b'basic')
        fake = types.SimpleNamespace(is_self_signed=lambda _: True, key_matches=lambda *_: True)
        with patch.dict(setup.sys.modules, {'identity': fake}):
            self.assertEqual(self.app.status()['state'], 'missing')
            self.assertFalse(self.app.status()['configured'])

    def test_corrupt_cache_is_revalidated(self):
        setup.private_dir(self.app.keys)
        setup.private_dir(self.app.state)
        for name, data in self.data.items(): (self.app.keys / name).write_bytes(data)
        (self.app.state / 'validation-cache.json').write_text('{"checked":"bad","details": []}')
        with patch.object(setup, 'validate', return_value=self.valid) as validator:
            self.assertTrue(self.app.status()['valid'])
            validator.assert_called_once()

    def test_unconfigured_scheduled_check_is_successful(self):
        with patch.object(setup, 'Setup', return_value=self.app), patch.object(setup.sys, 'argv', ['setup', 'check', '--notify', '--json']), contextlib.redirect_stdout(__import__('io').StringIO()):
            self.assertEqual(setup.main(), 0)

    def test_helper_refuses_overwrite(self):
        helper = self.home / 'template'
        helper.mkdir()
        (helper / 'README.md').write_text('instructions')
        with patch.object(setup, 'HELPER', str(helper)):
            self.assertTrue(self.app.export_helper(self.home)['ok'])
            with self.assertRaises(setup.SetupError): self.app.export_helper(self.home)

if __name__ == '__main__': unittest.main()
