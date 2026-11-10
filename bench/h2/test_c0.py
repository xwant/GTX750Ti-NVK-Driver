import json,unittest
from summarize_c0 import summarize

def line(**kw):
 r=dict(schema=1,event='compile',nir='x',loads=8,unknown_loads=0,dynamic_ubo_loads=0,eligible=1,selected=-1,available=True,candidates=[]);r.update(kw)
 return 'NVK_GM107_UBO '+json.dumps(r)
class Tests(unittest.TestCase):
 def test_empty(self):self.assertEqual(summarize([])['verdict'],'no_compile_coverage')
 def test_cache(self):self.assertEqual(summarize(['NVK_GM107_UBO {"schema":1,"event":"cache_hit"}'])['cache_hit_events'],1)
 def test_selected(self):self.assertEqual(summarize([line(),line(selected=2)])['selected_compile_events'],1)
 def test_blocked(self):self.assertEqual(summarize([line(available=False)])['applicable_compile_events'],0)
 def test_malformed(self):self.assertEqual(summarize(['NVK_GM107_UBO {',line(schema=2),line(available=1)])['malformed_records'],3)
 def test_reasons(self):self.assertEqual(summarize([line(candidates=[dict(reject=7)])])['rejection_counts'],dict(type=1,dynamic_offset=1,range=1))
