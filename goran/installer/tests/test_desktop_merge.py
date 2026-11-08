#!/usr/bin/env python3
"""Small real-Git update and activation-guard regression suite."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MERGE = ROOT / 'merge-desktop-update.sh'
GUARDS = ROOT / 'desktop-update-guards.sh'

def run(*args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)

class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.up = self.base/'up'; self.local = self.base/'local'
        run('git','init','-b','main',str(self.up))
        self.git('config','user.name','Test'); self.git('config','user.email','test@localhost')
        (self.up/'settings').write_text('original\n'); (self.up/'flake.lock').write_text('reviewed lock\n')
        self.git('add','.'); self.git('commit','-m','Initial'); self.promote()
        run('git','clone',str(self.up),str(self.local))
        self.git('config','user.name','Test',local=True);self.git('config','user.email','test@localhost',local=True)
    def git(self,*args,local=False,check=True):
        return run('git',*args,cwd=self.local if local else self.up,check=check)
    def promote(self):
        self.git('branch','-f','fleet-stable','HEAD')
    def upstream(self):
        (self.up/'feature').write_text('published\n');self.git('add','.');self.git('commit','-m','Published feature'); self.promote()
    def merge(self):
        return run('bash',str(MERGE),str(self.local),str(self.base/'record'),check=False)
    def test_clean_fast_forward(self):
        self.upstream(); self.assertEqual(self.merge().returncode,0)
        self.assertEqual(self.git('rev-parse','HEAD',local=True).stdout,self.git('rev-parse','HEAD').stdout)
    def test_dirty_and_local_commits_survive_future_update(self):
        (self.local/'custom').write_text('local commit');self.git('add','.',local=True);self.git('commit','-m','Customization',local=True)
        (self.local/'settings').write_text('staged\n');self.git('add','settings',local=True)
        (self.local/'settings').write_text('unstaged\n');(self.local/'untracked').write_text('personal\n')
        self.upstream(); self.assertEqual(self.merge().returncode,0)
        self.assertEqual((self.local/'settings').read_text(),'unstaged\n')
        self.assertTrue((self.local/'custom').exists());self.assertTrue((self.local/'untracked').exists())
        self.assertEqual((self.local/'flake.lock').read_text(),'reviewed lock\n')
        self.assertEqual(self.git('status','--porcelain',local=True).stdout,'')
        stash=(self.base/'record/original-stash').read_text().strip()
        self.assertEqual(self.git('show',stash+':settings',local=True).stdout,'unstaged\n')
        self.assertEqual(self.git('show',stash+'^2:settings',local=True).stdout,'staged\n')
        (self.up/'feature2').write_text('next');self.git('add','.');self.git('commit','-m','Next'); self.promote()
        self.assertEqual(self.merge().returncode,0);self.assertTrue((self.local/'custom').exists())
        self.assertFalse((self.up/'custom').exists())
    def test_conflict_keeps_recovery_and_abort(self):
        (self.local/'settings').write_text('local\n');(self.up/'settings').write_text('remote\n')
        self.git('add','.');self.git('commit','-m','Conflicting upstream'); self.promote()
        self.assertNotEqual(self.merge().returncode,0)
        self.assertIn('<<<<<<<',(self.local/'settings').read_text())
        self.assertTrue((self.base/'record/original-stash').exists())
        self.git('merge','--abort',local=True)
        self.assertEqual((self.local/'settings').read_text(),'local\n')
    def test_main_does_not_bypass_release_gate(self):
        self.upstream()
        tested = self.git('rev-parse','HEAD').stdout.strip()
        (self.up/'untested').write_text('not released')
        self.git('add','.'); self.git('commit','-m','Unpromoted')
        self.assertEqual(self.merge().returncode,0)
        self.assertEqual(self.git('rev-parse','HEAD',local=True).stdout.strip(),tested)
        self.assertFalse((self.local/'untested').exists())
        self.assertEqual((self.base/'record/release-channel').read_text().strip(),'fleet-stable')
    def test_existing_unpromoted_main_cannot_be_reported_as_stable(self):
        (self.up/'untested').write_text('not released')
        self.git('add','.'); self.git('commit','-m','Unpromoted')
        self.git('pull','--ff-only',local=True)
        result=self.merge()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('outside the tested release',result.stderr)
        self.assertTrue((self.local/'untested').exists())
        self.assertFalse((self.base/'record/recovery-branch').exists())
    def test_missing_release_stops_before_mutation(self):
        self.git('branch','-D','fleet-stable')
        (self.local/'settings').write_text('local dirty')
        result=self.merge()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unavailable',result.stderr)
        self.assertEqual((self.local/'settings').read_text(),'local dirty')
        self.assertFalse((self.base/'record/recovery-branch').exists())
    def test_explicit_development_selects_main(self):
        (self.up/'development').write_text('main only')
        self.git('add','.'); self.git('commit','-m','Development')
        result=run('bash',str(MERGE),str(self.local),str(self.base/'record'),'main',check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.local/'development').exists())
    def test_source_changed_guard(self):
        revision=self.git('rev-parse','HEAD',local=True).stdout.strip()
        cmd='source "$1"; require_stable_checkout "$2"'
        self.assertEqual(run('bash','-c',cmd,'guard',str(GUARDS),revision,cwd=self.local).returncode,0)
        (self.local/'new').write_text('changed')
        self.assertNotEqual(run('bash','-c',cmd,'guard',str(GUARDS),revision,cwd=self.local,check=False).returncode,0)
    def test_failed_activation_rolls_back(self):
        candidate=self.base/'candidate';previous=self.base/'previous'
        candidate.mkdir();previous.mkdir()
        (candidate/'activate').write_text('#!/bin/sh\nexit 7\n')
        (previous/'activate').write_text('#!/bin/sh\ntouch "'+str(self.base/'rolled-back')+'"\n')
        for p in [candidate/'activate',previous/'activate']:p.chmod(0o755)
        result=run('bash','-c','source "$1"; activate_with_rollback "$2" "$3" "$4"','guard',str(GUARDS),str(candidate),str(self.base/'profile'),str(previous),check=False)
        self.assertEqual(result.returncode,7);self.assertTrue((self.base/'rolled-back').exists())

if __name__ == '__main__': unittest.main()
