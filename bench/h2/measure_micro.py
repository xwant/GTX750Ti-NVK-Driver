#!/usr/bin/env python3
"""Eight paired AB/BA runs; GPU-time ratios, not Dota FPS."""
import argparse,csv,json,math,os,random,statistics,subprocess
from datetime import datetime,timezone
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--control',choices=['base-off','off-on'],required=True)
p.add_argument('--reads',type=int,choices=[1,4,7,8,16,32],default=8)
p.add_argument('--draws',type=int,default=1);p.add_argument('--rebind',action='store_true');a=p.parse_args()
if not 1<=a.draws<=1280:p.error('draws must be 1..1280')
root=Path(__file__).resolve().parents[2];work=Path(os.getenv('GM107_H2_WORKDIR',root/'work-h2')).resolve()
tag=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+a.control
modes=a.control.split('-');result=dict(control=a.control,reads=a.reads,draws=a.draws,rebind=a.rebind,pairs=[])
for pair in range(8):
 row={}
 for mode in modes if pair%2==0 else modes[::-1]:
  run=f'{tag}-{pair:02}-{mode}'
  cmd=['bash',str(root/'bench/h2/run.sh'),mode,run,str(work/'bin/ubo-bench'),'--shaders',str(work/'shaders'),'--reads',str(a.reads),'--draws',str(a.draws),'--width','1280','--height','720','--samples','30','--warmup','5']
  if a.rebind:cmd+=['--rebind']
  subprocess.run(cmd,check=True)
  with (work/'results'/run/'stdout.txt').open() as f:samples=list(csv.DictReader(f))
  assert len(samples)==30 and all(s['readback_ok']=='1' and s['software']=='0' for s in samples)
  times=[float(s['gpu_ms']) for s in samples];assert all(math.isfinite(t) and t>0 for t in times)
  row[mode]=dict(run=run,mean_gpu_ms=statistics.mean(times))
 result['pairs'].append(row)
 (work/'results'/f'{tag}.json').write_text(json.dumps(result,indent=2))
ratios=[math.log(r[modes[1]]['mean_gpu_ms']/r[modes[0]]['mean_gpu_ms']) for r in result['pairs']]
rng=random.Random(750);boot=sorted(math.exp(statistics.mean(rng.choices(ratios,k=8))) for _ in range(20000))
result.update(geomean_gpu_time_ratio_B_over_A=math.exp(statistics.mean(ratios)),bootstrap95=[boot[500],boot[19499]],note='B/A < 1: less GPU time. Not FPS or input latency. Verify clocks, loaded library, image and memory placement separately.')
(work/'results'/f'{tag}.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
