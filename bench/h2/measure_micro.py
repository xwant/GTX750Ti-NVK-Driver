#!/usr/bin/env python3
"""Paired physical-GPU measurement collector with raw evidence and completion gate."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
from evidence import benchmark_rows,check,sha


def read_run(directory, mode):
    directory=Path(directory)
    check((directory/'exit-status.txt').read_text().strip()=='0','failed run')
    verification=json.loads((directory/'verification.json').read_text())
    check(verification.get('status')=='verified','unverified driver mapping')
    check(sha(verification['library'])==verification['sha256'],'library changed since run')
    launch=dict(line.split('=',1) for line in (directory/'launch.txt').read_text().splitlines() if '=' in line)
    check(launch.get('mode')==mode,'wrong launch mode')
    stderr=(directory/'stderr.txt').read_text()
    check('PASS all pixels' in stderr and 'software=0' in stderr and 'GTX 750 Ti' in stderr,'missing hardware/completion evidence')
    with (directory/'stdout.txt').open() as f: rows=list(csv.DictReader(f))
    return benchmark_rows(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--control',choices=['base-off','off-on'],required=True)
    p.add_argument('--reads',type=int,choices=[1,4,7,8,16,32],default=8)
    p.add_argument('--draws',type=int,default=1);p.add_argument('--rebind',action='store_true')
    p.add_argument('--pairs',type=int,default=16,help='even >=8; 16 supports H3 calibration/held-out evaluation')
    a=p.parse_args()
    if not 1<=a.draws<=1280 or not 8<=a.pairs<=1000 or a.pairs%2:p.error('draws 1..1280; even 8..1000 pairs')
    root=Path(__file__).resolve().parents[2];work=Path(os.getenv('GM107_H2_WORKDIR',root/'work-h2')).resolve()
    tag=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+a.control
    modes=a.control.split('-');result=dict(control=a.control,reads=a.reads,draws=a.draws,rebind=a.rebind,pairs=[])
    orders=[]
    partial=work/'results'/f'{tag}.partial.json'
    for pair in range(a.pairs):
        row={};order=modes if pair%2==0 else modes[::-1];orders.append(order)
        for mode in order:
            run=f'{tag}-{pair:02}-{mode}'
            cmd=['bash',str(root/'bench/h2/run.sh'),mode,run,str(work/'bin/ubo-bench'),'--shaders',str(work/'shaders'),'--reads',str(a.reads),'--draws',str(a.draws),'--width','1280','--height','720','--samples','30','--warmup','5']
            if a.rebind:cmd+=['--rebind']
            subprocess.run(cmd,check=True)
            times=read_run(work/'results'/run,mode)
            row[mode]=dict(run=run,mean_gpu_ms=statistics.mean(times))
        result['pairs'].append(row)
        partial.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    ratios=[math.log(r[modes[1]]['mean_gpu_ms'])-math.log(r[modes[0]]['mean_gpu_ms']) for r in result['pairs']]
    rng=random.Random(750);boot=sorted(math.exp(statistics.mean(rng.choices(ratios,k=a.pairs))) for _ in range(20000))
    result.update(geomean_gpu_time_ratio_B_over_A=math.exp(statistics.mean(ratios)),bootstrap95=[boot[500],boot[19499]],note='Paired GPU duration, not FPS. Verify clocks, image and memory placement separately.')
    final=work/'results'/f'{tag}.json';check(not final.exists(),'output exists');final.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    # Explicit collected ordering; no invented game shader or layout identity.
    identities=[sha(work/'bin/ubo-bench')]+[sha(f) for f in sorted((work/'shaders').glob('*.spv'))]
    manifest=dict(schema='gm107.h2-import.v1',origin='hardware',gpu='GM107',scenario_group=f'ubo-{a.reads}-draws-{a.draws}-rebind-{a.rebind}',benchmark_sha256=hashlib.sha256(''.join(identities).encode()).hexdigest(),mesa_commit='8e87a503ebd91408c88596d1b9eeb5f4c0b2088d',pair_orders=orders,artifacts_verified=True)
    (work/'results'/f'{tag}.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(result,indent=2));print('H3 input:',final)
if __name__=='__main__':main()
