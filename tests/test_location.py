import unittest,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from audit import pin_coordinates,maps_url,choose_candidate,normalize_search_link
from runner import validate_rows
class LocationTests(unittest.TestCase):
 def test_store_pin_not_viewport(self):
  c=pin_coordinates('https://www.google.com/maps/place/A/@20,70,15z/data=!3d28.5288!4d77.219');self.assertEqual((c['latitude'],c['longitude']),(28.5288,77.219))
 def test_viewport_not_pin(self):self.assertIsNone(pin_coordinates('https://www.google.com/maps/place/A/@20,70,15z'))
 def test_center_not_pin(self):self.assertIsNone(pin_coordinates('https://www.google.com/maps?center=20,70'))
 def test_invalid_pin(self):self.assertIsNone(pin_coordinates('https://www.google.com/maps/data=!3d91!4d77'))
 def test_short_links(self):
  for u in ['https://maps.app.goo.gl/Example','https://goo.gl/maps/Example','https://g.page/r/Example','https://share.google/Example']:self.assertEqual(maps_url(u),u)
 def test_search_links(self):
  for u in ['https://www.google.com/maps/search/?api=1&query=Example','https://www.google.com/search?q=Example+store']:self.assertEqual(maps_url(u),u)
 def test_google_search_to_maps(self):self.assertIn('/maps/search/?api=1&query=Example%20store',normalize_search_link('https://www.google.com/search?q=Example+store'))
 def test_ludocid_to_profile(self):self.assertEqual(normalize_search_link('https://www.google.com/search?q=A&ludocid=123'),'https://www.google.com/maps?cid=123')
 def test_short_host_spoof(self):
  with self.assertRaises(ValueError):maps_url('https://maps.app.goo.gl.attacker.test/example')
 def test_ambiguous_search_not_selected(self):
  entries=[{'url':'https://www.google.com/maps?cid=1','name':'A'},{'url':'https://www.google.com/maps?cid=2','name':'A'}];self.assertIsNone(choose_candidate(entries,'A'))
 def test_unique_branch_match(self):
  entries=[{'url':'https://www.google.com/maps?cid=1','name':'A','card':'A Mall One'},{'url':'https://www.google.com/maps?cid=2','name':'A','card':'A Mall Two'}];self.assertEqual(choose_candidate(entries,'A','Mall Two')['url'],'https://www.google.com/maps?cid=2')
 def test_duplicate_same_entity(self):
  self.assertIsNotNone(choose_candidate([{'url':'https://www.google.com/maps?cid=1','name':'A'}]*2))
 def test_zero_coordinate_is_valid(self):
  self.assertEqual(len(validate_rows([{'store_code':'A','maps_url':'https://www.google.com/maps?cid=1','keyword':'shoe','search_latitude':0,'search_longitude':10}])),1)
if __name__=='__main__':unittest.main()

class CoordinateLookupTests(unittest.TestCase):
 def test_lookup_requires_exact_entity_match(self):
  from unittest.mock import MagicMock,patch
  from audit import lookup_coordinates
  context=MagicMock();page=context.new_page.return_value
  page.locator.return_value.evaluate_all.return_value=['https://www.google.com/maps/place/Wrong/data=!1s0x1:0x1!3d10!4d20','https://www.google.com/maps/place/Right/data=!1s0x1:0x2!3d28!4d77']
  target={'entity_id':'cid-2','address':'Address: Example Street, City','category':'Shoe store'}
  with patch('audit.settle'),patch('audit.blocked',return_value=None),patch('audit.capture',return_value={'screenshot':'evidence.png','observed_at':'test'}):
   pin=lookup_coordinates(context,target,pathlib.Path('unused'))
  self.assertEqual((pin['latitude'],pin['longitude']),(28,77));self.assertEqual(pin['entity_id'],'cid-2');page.close.assert_called_once()
 def test_unmatched_result_is_not_used(self):
  from unittest.mock import MagicMock,patch
  from audit import lookup_coordinates
  context=MagicMock();context.new_page.return_value.locator.return_value.evaluate_all.return_value=['https://www.google.com/maps/place/Wrong/data=!1s0x1:0x1!3d10!4d20']
  with patch('audit.settle'),patch('audit.blocked',return_value=None),patch('audit.capture',return_value={'screenshot':'evidence.png','observed_at':'test'}):
   self.assertIsNone(lookup_coordinates(context,{'entity_id':'cid-2','address':'Address: Example Street, City','category':'Shoe store'},pathlib.Path('unused')))
