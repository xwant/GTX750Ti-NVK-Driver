#!/usr/bin/env python3
"""Track only descendants of this command; unknown mapping coverage never passes."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from evidence import check,library_paths,sha,verify_paths

def process(pid, proc=Path('/proc')):
    # starttime guards PID reuse; comm can contain spaces/parentheses.
    tail=(proc/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return tail[19],tail[0]

def collect(pid, expected_start, proc=Path('/proc')):
    try:
        start,state=process(pid,proc)
        if start!=expected_start or state=='Z': return [],[]
        try: children=(proc/str(pid)/'task'/str(pid)/'children').read_text().split()
        except OSError:
            # Some procfs mounts omit task/children; use PPid without selecting
            # unrelated same-user processes by executable name.
            children=[]
            for entry in proc.iterdir():
                if not entry.name.isdigit(): continue
                try:
                    tail=(entry/'stat').read_text().rsplit(')',1)[1].split()
                    if int(tail[1])==pid: children.append(entry.name)
                except (OSError,ValueError,IndexError): pass
        paths=[]
        for line in (proc/str(pid)/'maps').read_text().splitlines():
            parts=line.split(None,5)
            if len(parts)==6 and any(x in parts[-1] for x in ('libvulkan_nouveau','libvulkan_lvp','libGLX_nvidia')): paths.append(parts[-1])
        return paths,children
    except (OSError,IndexError): return [],[]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--expected',type=Path,required=True);p.add_argument('--checksum',required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    command=a.command[1:] if a.command[:1]==['--'] else a.command
    check(command,'missing command');check(sha(a.expected)==a.checksum,'library changed before launch')
    paths=set();tracked={};observations=[]
    with (a.out/'stdout.txt').open('w') as stdout,(a.out/'stderr.txt').open('w') as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr)
        try: tracked[child.pid]=process(child.pid)[0]
        except OSError: pass
        while True:
            for pid,start in list(tracked.items()):
                seen,children=collect(pid,start)
                for path in seen:
                    if path not in paths: observations.append(dict(pid=pid,starttime=start,path=path));paths.add(path)
                for sub in children:
                    try: tracked[int(sub)]=process(int(sub))[0]
                    except OSError: pass
            # Retain observed descendants after launcher exits. Missed detached
            # children produce unknown coverage, never a claim of verification.
            status=child.poll()
            live=False
            for pid,start in tracked.items():
                try:
                    now,state=process(pid)
                    live |= now==start and state!='Z'
                except OSError: pass
            if status is not None and not live: break
            time.sleep(.05)
        status=child.wait()
    (a.out/'process-library-evidence.json').write_text(json.dumps(observations,sort_keys=True)+'\n')
    # The owned microbenchmark logs its own /proc/self/maps before rendering;
    # this covers short runs which finish between process-tree polls.
    if Path(command[0]).name=='ubo-bench': paths.update(library_paths((a.out/'stderr.txt').read_text()))
    try: report=verify_paths(paths,a.expected,a.checksum)
    except (ValueError,OSError) as e: report=dict(status='unverified',reason=str(e))
    (a.out/'verification.json').write_text(json.dumps(report,sort_keys=True)+'\n')
    (a.out/'exit-status.txt').write_text(str(status)+'\n')
    return status
if __name__=='__main__': raise SystemExit(main())
