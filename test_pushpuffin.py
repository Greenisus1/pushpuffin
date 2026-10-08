import unittest,tempfile,json,os,hashlib,base64
from pathlib import Path
from types import SimpleNamespace
import pushpuffin as p
class Tests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.f=self.root/'a.txt';self.f.write_bytes(b'hello')
 def tearDown(self):self.t.cleanup()
 def test_repo(self):self.assertEqual(p.validate_repo('a/test'),'a/test')
 def test_repo_bad(self):self.assertRaises(ValueError,p.validate_repo,'https://github.com/a/b')
 def test_prefix(self):self.assertEqual(p.remote_prefix('dir/sub'),'dir/sub')
 def test_traversal(self):self.assertRaises(ValueError,p.remote_prefix,'../x')
 def test_absolute(self):self.assertRaises(ValueError,p.remote_prefix,'/x')
 def test_stage(self):self.assertEqual(p.stage_files([self.f]),(('a.txt',b'hello'),))
 def test_prefix_stage(self):self.assertEqual(p.stage_files([self.f],'dir')[0][0],'dir/a.txt')
 def test_folder(self):d=self.root/'folder';d.mkdir();(d/'x.txt').write_bytes(b'x');self.assertEqual(p.stage_files([d]),(('folder/x.txt',b'x'),))
 def test_git_skipped(self):d=self.root/'folder';d.mkdir();(d/'.git').mkdir();(d/'.git'/'secret').write_text('x');(d/'a').write_text('y');self.assertEqual(len(p.stage_files([d])),1)
 def test_env_blocked(self):q=self.root/'.env';q.write_text('secret');self.assertRaises(ValueError,p.stage_files,[q])
 def test_key_blocked(self):q=self.root/'a.pem';q.write_text('secret');self.assertRaises(ValueError,p.stage_files,[q])
 def test_symlink(self):q=self.root/'link';q.symlink_to(self.f);self.assertRaises(ValueError,p.stage_files,[q])
 def test_duplicate(self):self.assertRaises(ValueError,p.stage_files,[self.f,self.f])
 def test_cap(self):self.f.write_bytes(b'x'*(p.MAX_FILE+1));self.assertRaises(ValueError,p.stage_files,[self.f])
 def test_empty(self):d=self.root/'empty';d.mkdir();self.assertRaises(ValueError,p.stage_files,[d])
 def test_staged_immutable(self):entries=p.stage_files([self.f]);self.f.write_text('changed');self.assertEqual(entries[0][1],b'hello')
 def test_env_cleanup(self):os.environ['GH_TOKEN']='dummy';self.assertNotIn('GH_TOKEN',p.gh_environment());os.environ.pop('GH_TOKEN')
 def test_dependency_missing(self):self.assertFalse(p.store_installed(self.root))
 def test_dependency_valid(self):q=self.root/'.local/share/pi-app-store/program/appstore.py';q.parent.mkdir(parents=True);q.write_text('x');w=self.root/'.local/bin/AppStore';w.parent.mkdir(parents=True);w.write_text('exec python3 '+str(q));self.assertTrue(p.store_installed(self.root))
 def fake(self,existing=False,fail=False):
  calls=[]
  def run(args,**kw):
   calls.append(args);endpoint=args[-1]
   if 'PUT' in args:
    if fail:return SimpleNamespace(returncode=1,stdout='',stderr='secret')
    body=json.loads(kw['input']);data=base64.b64decode(body['content']);obj={'content':{'sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}}
   elif endpoint=='user':obj={'login':'test-user'}
   elif '/branches/' in endpoint:obj={'commit':{'sha':'abc'}}
   elif '/git/trees/' in endpoint:obj={'tree':[{'path':'a.txt','type':'blob'}] if existing else [],'truncated':False}
   else:obj={'full_name':'owner/repo','private':True,'permissions':{'push':True}}
   return SimpleNamespace(returncode=0,stdout=json.dumps(obj),stderr='')
  return p.GHClient(run),calls
 def test_prepare(self):c,calls=self.fake();r=c.prepare('owner/repo','main',p.stage_files([self.f]));self.assertEqual(r['identity'],'test-user')
 def test_existing_blocked(self):c,calls=self.fake(existing=True);self.assertRaises(ValueError,c.prepare,'owner/repo','main',p.stage_files([self.f]))
 def test_upload(self):c,calls=self.fake();e=p.stage_files([self.f]);r=c.prepare('owner/repo','main',e);self.assertEqual(c.upload(r,e),['a.txt']);self.assertEqual(sum('PUT' in x for x in calls),1)
 def test_failure_redacted(self):
  c,calls=self.fake(fail=True);e=p.stage_files([self.f]);r=c.prepare('owner/repo','main',e)
  with self.assertRaises(RuntimeError) as caught:c.upload(r,e)
  self.assertNotIn('secret',str(caught.exception))
 # exception includes no raw stderr
 # explicit no retry
 def test_no_retry(self):c,calls=self.fake(fail=True);e=p.stage_files([self.f]);r=c.prepare('owner/repo','main',e);self.assertRaises(RuntimeError,c.upload,r,e);self.assertEqual(sum('PUT' in x for x in calls),1)
if __name__=='__main__':unittest.main()

class MoreTests(unittest.TestCase):
 def test_total_limit(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for i in range(6):
    q=Path(d)/str(i);q.write_bytes(b'x'*p.MAX_FILE);paths.append(q)
   self.assertRaises(ValueError,p.stage_files,paths)
 def test_count_limit(self):
  with tempfile.TemporaryDirectory() as d:
   for i in range(201):(Path(d)/str(i)).write_bytes(b'')
   self.assertRaises(ValueError,p.stage_files,[Path(d)])
 def test_cancel_before_write(self):
  import threading
  c,calls=Tests().fake();e=(('a.txt',b'hello'),);r=c.prepare('owner/repo','main',e);cancel=threading.Event();cancel.set()
  self.assertEqual(c.upload(r,e,cancel=cancel),[]);self.assertFalse(any('PUT' in x for x in calls))
 def test_remote_change(self):
  c,calls=Tests().fake();e=(('a.txt',b'hello'),);r=c.prepare('owner/repo','main',e);r['commit']='changed'
  self.assertRaises(ValueError,c.upload,r,e);self.assertFalse(any('PUT' in x for x in calls))
 def test_symlink_directory(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)/'folder';folder.mkdir();(folder/'link').symlink_to(Path(d),target_is_directory=True)
   self.assertRaises(ValueError,p.stage_files,[folder])
 def test_parent_file(self):
  c,calls=Tests().fake(existing=True);self.assertRaises(ValueError,c.prepare,'owner/repo','main',(('a.txt/x',b'hi'),))
 def test_unexpected_json(self):
  c=p.GHClient(lambda *a,**kw:SimpleNamespace(returncode=0,stdout='not-json'))
  self.assertRaises(RuntimeError,c.identity)
