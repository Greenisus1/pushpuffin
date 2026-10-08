import unittest,tempfile,os
from pathlib import Path
from unittest.mock import patch
import pushpuffin as p
class Tests(unittest.TestCase):
 def test_regular_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'a.txt';f.write_bytes(b'hello');self.assertEqual(p.stage_files([f]),(('a.txt',b'hello'),))
 def test_replaced_before_open(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'a.txt';f.write_bytes(b'one');other=Path(d)/'b.txt';other.write_bytes(b'two');original=os.open
   def swapped(path,flags,*args,**kw):
    other.replace(f);return original(path,flags,*args,**kw)
   with patch.object(p.os,'open',side_effect=swapped):self.assertRaises(ValueError,p.stage_files,[f])
 def test_symlink_no_follow(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'a.txt';f.write_bytes(b'one');other=Path(d)/'b.txt';other.write_bytes(b'two');original=os.open
   def swapped(path,flags,*args,**kw):
    f.unlink();f.symlink_to(other);return original(path,flags,*args,**kw)
   with patch.object(p.os,'open',side_effect=swapped):
    with self.assertRaises((OSError,ValueError)):p.stage_files([f])
if __name__=='__main__':unittest.main()
