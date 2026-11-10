#!/usr/bin/env python3
import json,sys
from collections import Counter
from pathlib import Path

def summarize(lines):
 records=[];hits=malformed=0;rejections=Counter()
 for line in lines:
  if not line.startswith('NVK_GM107_UBO '):continue
  try:
   r=json.loads(line[len('NVK_GM107_UBO '):])
   if r.get('schema')!=1:raise ValueError('schema')
   if r['event']=='cache_hit':hits+=1;continue
   if r['event']!='compile' or not isinstance(r['nir'],str):raise ValueError('event')
   for k in ('loads','unknown_loads','dynamic_ubo_loads','eligible','selected'):
    if type(r[k]) is not int:raise ValueError(k)
   if type(r['available']) is not bool:raise ValueError('available')
   for c in r['candidates']:
    for mask,name in ((1,'type'),(2,'dynamic_offset'),(4,'range')):
     if c['reject']&mask:rejections[name]+=1
   records.append(r)
  except (ValueError,KeyError,TypeError):malformed+=1
 applicable=sum(r['available'] and r['eligible']>0 for r in records)
 return dict(compile_events=len(records),unique_input_nir_hashes=len({r['nir'] for r in records}),applicable_compile_events=applicable,
             selected_compile_events=sum(r['selected']>=0 for r in records),cache_hit_events=hits,malformed_records=malformed,
             rejection_counts=dict(rejections),complete_coverage=False,
             verdict='candidates_observed' if applicable else 'no_candidates_observed' if records else 'no_compile_coverage',
             note='Compilation is not execution or hotness. Hash omits layout identity. Empty/cache-hit-only logs do not prove inapplicability.')
if __name__=='__main__':
 r=summarize(Path(sys.argv[1]).read_text(errors='replace').splitlines());print(json.dumps(r,indent=2));sys.exit(bool(r['malformed_records']))
