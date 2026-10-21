import sys,pathlib,tempfile,unittest,json
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from audit import maps_url,identity,load_rows,assess,public_url
class Tests(unittest.TestCase):
 def test_cid_exact(self):self.assertEqual(identity('https://www.google.com/maps?cid=3023275743767149335'),'cid-3023275743767149335')
 def test_hex_identity(self):self.assertEqual(identity('https://www.google.com/maps/data=!1s0x390ce1ce96b5f98f:0x29f4d5455d4bbb17'),'cid-3023275743767149335')
 def test_no_name_identity_guess(self):self.assertIsNone(identity('https://www.google.com/maps/place/Foot+Locker'))
 def test_maps_host_impersonation_rejected(self):
  with self.assertRaises(ValueError):maps_url('https://google.com.attacker.test/maps')
 def test_google_non_maps_rejected(self):
  with self.assertRaises(ValueError):maps_url('https://www.google.com/search?q=shoes')
 def test_credentials_rejected(self):
  with self.assertRaises(ValueError):maps_url('https://user:password@google.com/maps')
 def test_private_network_blocked(self):
  with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]):self.assertFalse(public_url('http://example.test'))
 def test_empty_capture_not_missing_website(self):
  c=next(x for x in assess({}) if x['id']=='B06');self.assertEqual(c['status'],'Unknown')
 def test_add_website_is_observed_missing(self):
  c=next(x for x in assess({'website_link_state':'missing'}) if x['id']=='B06');self.assertEqual(c['status'],'Fail')
 def test_gallery_capture_not_visual_pass(self):
  c=next(x for x in assess({'gallery':{'items':[{}]}}) if x['id']=='B11');self.assertEqual(c['status'],'Partial');self.assertIn('visual',c['finding'])
 def test_full_registry(self):self.assertEqual(len(assess({})),70)
 def test_bulk_invalid_missing_keyword(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'a.csv';p.write_text('store_code,maps_url\nDS4,https://www.google.com/maps?cid=123\n')
   with self.assertRaises(ValueError):load_rows(p)
 def test_bulk_path_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'a.csv';p.write_text('store_code,maps_url,keyword\n../../oops,https://www.google.com/maps?cid=123,shoe\n')
   with self.assertRaises(ValueError):load_rows(p)
 def test_bulk_order_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'a.csv';p.write_text('store_code,maps_url,keyword\nB,https://www.google.com/maps?cid=123,shoe\nA,https://www.google.com/maps?cid=456,sneaker\n');self.assertEqual([x['store_code'] for x in load_rows(p)],['B','A'])
if __name__=='__main__':unittest.main()
