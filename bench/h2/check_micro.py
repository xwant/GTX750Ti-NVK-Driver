#!/usr/bin/env python3
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description='Correctness only; not an FPS test')
p.add_argument('--exe',required=True);p.add_argument('--shaders',required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--software',action='store_true');p.add_argument('--validation',action='store_true');a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
results=[]
cases=[['--reads',str(n),*opt] for n in (1,4,7,8,16,32) for opt in ([],['--dynamic'],['--draws','8','--rebind','--switch'],['--draws','8','--rebind','--switch','--push'])]
cases += [['--reads','32',*opt] for opt in (['--robust2'],['--null'],['--oob'],['--null','--push'],['--null-only'],['--null-only','--push'],['--oob','--dynamic','--draws','8','--rebind'])]
for options in cases:
 i=len(results);cmd=[a.exe,'--shaders',a.shaders,'--width','64','--height','32','--samples','2','--warmup','1',*options]
 if a.software:cmd+=['--software']
 if a.validation:cmd+=['--validation']
 with (a.out/f'{i:02}.csv').open('w') as out,(a.out/f'{i:02}.stderr').open('w') as err:
  r=subprocess.run(cmd,stdout=out,stderr=err,timeout=180)
 results.append(dict(args=options,exit=r.returncode));(a.out/'results.json').write_text(json.dumps(results,indent=2))
 print(f'{i:02} exit={r.returncode} {options}',flush=True)
 if r.returncode:print((a.out/f'{i:02}.stderr').read_text());raise SystemExit(r.returncode)
print(f'PASS {len(results)} correctness cases; software={a.software}; validation={a.validation}')
