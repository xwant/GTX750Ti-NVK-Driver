#!/usr/bin/env python3
"""Future CachyOS handoff: audited H2 builds/checks/captures -> scoped H3 datasets."""
import argparse
import os
from pathlib import Path
import subprocess
from .dataset import build,canonical,import_h2,require

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--skip-build',action='store_true');a=p.parse_args()
    audit=a.audit.resolve();out=a.out.resolve();require(not out.exists(),'output exists')
    require((audit/'docs/H2_AUDIT.md').is_file(),'use audit/h2-hardware-readiness checkout')
    require(not subprocess.check_output(['git','-C',str(audit),'status','--porcelain','--untracked-files=no'],text=True).strip(),'audit source is dirty')
    work=Path(os.getenv('GM107_H2_WORKDIR',audit/'work-h2')).resolve()
    env=dict(os.environ,GM107_H2_WORKDIR=str(work))
    if not a.skip_build:subprocess.run(['bash',str(audit/'build-h2-cachyos.sh')],check=True,env=env)
    subprocess.run(['bash',str(audit/'bench/h2/check-gpu.sh')],check=True,env=env)
    out.mkdir(parents=True)
    datasets={'base-off':[],'off-on':[]}
    specs=[('base-off',8,1,False)]+[('off-on',reads,draws,draws>1) for reads in (8,32) for draws in (1,64)]
    def completed():
        return {f for f in (work/'results').glob('*.json') if not f.name.endswith(('.manifest.json','.partial.json'))}
    for control,reads,draws,rebind in specs:
        before=completed()
        cmd=['python3',str(audit/'bench/h2/measure_micro.py'),'--control',control,'--reads',str(reads),'--draws',str(draws),'--pairs','16']
        if rebind:cmd+=['--rebind']
        subprocess.run(cmd,check=True,env=env)
        new=completed()-before;require(len(new)==1,'ambiguous capture')
        summary=new.pop();manifest=summary.with_name(summary.stem+'.manifest.json')
        ds=import_h2(summary,work/'results',manifest);datasets[control].extend(ds['records'])
        # Checkpoint completed inputs; no previous capture is deleted.
        (out/f'{control}.json').write_text(canonical(build(datasets[control])))
    print('Completed scoped datasets:',out)
    print('Microbenchmarks do not establish per-shader/game acceleration; collect Dota C0 separately.')
if __name__=='__main__':main()
