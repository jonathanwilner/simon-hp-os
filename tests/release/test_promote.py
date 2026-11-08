import importlib.util, pathlib, unittest
spec = importlib.util.spec_from_file_location('promote', pathlib.Path(__file__).with_name('promote.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
SHA = 'a' * 40
class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.runs = [dict(id=1, head_sha=SHA, head_branch='main', event='push', conclusion='success')]
        self.statuses = [dict(id=i, context='fleet/canary/'+s, state='success', target_url='https://debug.example/evidence') for i,s in enumerate(('aarch64-linux','x86_64-linux'))]
    def test_accept(self): p.validate(SHA,self.runs,self.statuses)
    def test_wrong_revision(self):
        with self.assertRaises(ValueError): p.validate('b'*40,self.runs,self.statuses)
    def test_latest_failure(self):
        self.runs.append(dict(self.runs[0],id=2,conclusion='failure'))
        with self.assertRaises(ValueError): p.validate(SHA,self.runs,self.statuses)
    def test_missing_arch(self):
        with self.assertRaises(ValueError): p.validate(SHA,self.runs,self.statuses[:1])
    def test_latest_canary_failure(self):
        self.statuses.append(dict(self.statuses[0],id=10,state='failure'))
        with self.assertRaises(ValueError): p.validate(SHA,self.runs,self.statuses)
    def test_missing_evidence(self):
        self.statuses[0]['target_url']=''
        with self.assertRaises(ValueError): p.validate(SHA,self.runs,self.statuses)
    def test_pr_cannot_release(self):
        self.runs[0]['event']='pull_request'
        with self.assertRaises(ValueError): p.validate(SHA,self.runs,self.statuses)
if __name__=='__main__': unittest.main()
