import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'fleet/release'))
import controller
from test_controller import config, evidence, REV

class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state=Path(self.tmp.name)
        self.conf=config()
        for lane in controller.VALIDATIONS:
            (self.state/('validation-'+lane+'.json')).write_text(json.dumps(evidence(lane)))
        for system in controller.SYSTEMS:
            (self.state/(system+'.json')).write_text(json.dumps(dict(revision=REV,system=system,passed=True,fresh_launch=True)))

    def test_real_git_atomic_promotion_and_retry(self):
        remote=self.state/'remote.git'; checkout=self.state/'checkout'
        def git(*args):
            return subprocess.check_output(['git',*map(str,args)],text=True,stderr=subprocess.DEVNULL).strip()
        git('init','--bare',remote); git('init','-b','main',checkout)
        git('-C',checkout,'config','user.name','Fleet test'); git('-C',checkout,'config','user.email','fleet@example.test')
        git('-C',checkout,'commit','--allow-empty','-m','candidate')
        revision=git('-C',checkout,'rev-parse','HEAD')
        git('-C',checkout,'remote','add','origin',remote); git('-C',checkout,'push','origin','main')
        self.conf['checkout']=str(checkout)
        for path in self.state.glob('*.json'):
            record=json.loads(path.read_text()); record['revision']=revision; path.write_text(json.dumps(record))
        controller.promotion(self.conf,self.state,revision)
        controller.promotion(self.conf,self.state,revision)
        self.assertEqual(git('--git-dir',remote,'rev-parse','fleet-stable'),revision)
        self.assertEqual(git('--git-dir',remote,'rev-parse','fleet-'+revision),revision)

    def test_missing_gate_cannot_publish(self):
        (self.state/'validation-nvidia.json').unlink()
        with patch.object(controller,'run') as run:
            with self.assertRaises(FileNotFoundError): controller.promotion(self.conf,self.state,REV)
            run.assert_not_called()

    def test_wrong_sha_never_publishes(self):
        with patch.object(controller,'run') as run:
            with self.assertRaises(ValueError): controller.promotion(self.conf,self.state,'b'*40)
            run.assert_not_called()

    def test_moved_main_never_publishes(self):
        with patch.object(controller,'run',side_effect=['','b'*40]) as run:
            with self.assertRaisesRegex(ValueError,'current main'): controller.promotion(self.conf,self.state,REV)
            self.assertFalse(any('push' in c.args[0] for c in run.call_args_list))

    def test_atomic_publish_and_idempotent_retry(self):
        observed=f'{REV}\trefs/heads/fleet-stable\n{REV}\trefs/tags/fleet-{REV}'
        with patch.object(controller,'run',side_effect=['',REV,'','','',observed]) as run:
            self.assertEqual(controller.promotion(self.conf,self.state,REV)['state'],'promoted')
            self.assertIn('--atomic',run.call_args_list[-2].args[0])
        # Retry after an interrupted success sees identical refs and republishes safely.
        with patch.object(controller,'run',side_effect=['',REV,f'{REV}\trefs/heads/fleet-stable','','',f'{REV}\trefs/tags/fleet-{REV}','',observed]):
            self.assertEqual(controller.promotion(self.conf,self.state,REV)['state'],'promoted')

    def test_wrong_existing_tag_cannot_publish(self):
        with patch.object(controller,'run',side_effect=['',REV,'','b'*40+'\trefs/tags/fleet-'+REV]) as run:
            with self.assertRaisesRegex(ValueError,'Immutable'): controller.promotion(self.conf,self.state,REV)
            self.assertFalse(any('push' in c.args[0] for c in run.call_args_list))

    def test_unverified_remote_refs_fail(self):
        with patch.object(controller,'run',side_effect=['',REV,'','','','']):
            with self.assertRaisesRegex(ValueError,'verified'): controller.promotion(self.conf,self.state,REV)

if __name__=='__main__': unittest.main()
