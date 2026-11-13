"""Launch a diagnostic command under the audited process/library tracker."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from .hardware_validation import preflight,checked_repo,AUDIT
from .dataset import canonical
from .telemetry import parse

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();cmd=a.command[1:] if a.command[:1]==['--'] else a.command
    if not cmd:p.error('command required')
    preflight();audit=a.audit.resolve();checked_repo(audit,AUDIT)
    work=a.work.resolve();out=a.out.resolve()
    if out.exists():p.error('output exists')
    lib=work/'build/src/nouveau/vulkan/libvulkan_nouveau.so'
    checksum=hashlib.sha256(lib.read_bytes()).hexdigest()
    if (work/'library.sha256').read_text().split()[0]!=checksum:raise ValueError('library changed since build')
    sys.path.insert(0,str(audit/'bench/h2'))
    from evidence import relocate_icd
    out.mkdir(parents=True)
    icd=out/'private-icd.json'
    relocate_icd(work/'build/src/nouveau/vulkan'/f'nouveau_devenv_icd.{os.uname().machine}.json',icd,lib)
    env=dict(os.environ,VK_DRIVER_FILES=str(icd),VK_ICD_FILENAMES=str(icd),
             NVK_SHADER_TELEMETRY='true',NVK_DEBUG='',MESA_SHADER_CACHE_DISABLE='true',
             MESA_SHADER_CACHE_DIR=str(out/'cache'))
    for k in ('NAK_DEBUG','VK_ADD_DRIVER_FILES','VK_LOADER_DRIVERS_SELECT','VK_LOADER_DRIVERS_DISABLE',
              'NVK_GM107_CMD_CACHE_LIMIT_KIB'):env.pop(k,None)
    partial=out/'capture.partial.json'
    partial.write_text(canonical({'status':'RUNNING','library_sha256':checksum}))
    try:
        subprocess.run([sys.executable,str(audit/'bench/h2/launch_verified.py'),
                        '--out',str(out),'--expected',str(lib),'--checksum',checksum,'--',*cmd],
                       env=env,check=True)
        if json.loads((out/'verification.json').read_text()).get('status')!='verified':
            raise ValueError('process/library coverage unknown; close existing game launchers and retry')
        capture=parse((out/'stderr.txt').read_text(),checksum)
        partial.write_text(canonical(capture));partial.rename(out/'compiler-capture.json')
        print('Static compiler capture:',out/'compiler-capture.json')
    except BaseException as exc:
        partial.write_text(canonical({'status':'FAILED','reason':str(exc),'library_sha256':checksum}));raise
if __name__=='__main__':main()
