"""CachyOS collection orchestrator. No installation, pstate or clock writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from .dataset import canonical
from .telemetry import parse

AUDIT = '8c77906e43095d1cce790fd96cd97a6199d0fd36'

def preflight(pci_root=Path('/sys/bus/pci/devices')):
    devices=[]
    for p in sorted(pci_root.iterdir()):
        try:
            if (p/'vendor').read_text().strip() != '0x10de':continue
            if not (p/'class').read_text().strip().startswith('0x03'):continue
            devices.append({'bdf':p.name,'device':(p/'device').read_text().strip(),
                            'driver':(p/'driver').resolve(strict=True).name})
        except OSError:continue
    # Existing audited H2 wrapper targets this BDF. Do not silently test a
    # different adapter. Add configurable BDF support in a separate H2 audit.
    if len(devices)!=1 or devices[0]['bdf']!='0000:01:00.0' or devices[0]['driver']!='nouveau':
        raise ValueError('requires one NVIDIA display adapter at 0000:01:00.0 bound to nouveau; no system changes made')
    return devices

def checked_repo(path, expected=None):
    head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
    if expected and head!=expected:raise ValueError('unexpected audit revision')
    if subprocess.check_output(['git','-C',str(path),'status','--porcelain','--untracked-files=no'],text=True).strip():
        raise ValueError('tracked source changes; use a clean checkout')
    return head

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--skip-build',action='store_true',help='reuse existing H2 build only')
    a=p.parse_args();root=Path(__file__).resolve().parents[1];audit=a.audit.resolve();out=a.out.resolve()
    if out.exists():p.error('output exists; choose a fresh directory')
    # Fail before expensive builds and without creating a misleading report.
    try:
        devices=preflight(); h3head=checked_repo(root); checked_repo(audit,AUDIT)
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        p.exit(77,str(exc)+'\n')
    out.mkdir(parents=True)
    report={'schema':'gm107.hardware.collection.v1','h3_commit':h3head,'audit_commit':AUDIT,
            'devices':devices,'acceptance':'NOT_RUN','H2_micro':'NOT_RUN','H3_micro':'NOT_RUN',
            'H6_hardware':'NOT_RUN','extended_CTS':'NOT_RUN','Dota':'NOT_RUN'}
    partial=out/'summary.partial.json'
    def save():partial.write_text(canonical(report))
    def run(cmd,env=None):subprocess.run([str(x) for x in cmd],check=True,env=env)
    save()
    try:
        cmd=[sys.executable,'-m','h3.collect_real','--audit',audit,'--out',out/'h2-datasets']
        if a.skip_build:cmd+=['--skip-build']
        run(cmd);report['H2_micro']='PASS';save()
        build=out/'h3-build';env=dict(os.environ,GM107_H3_WORKDIR=str(build))
        run(['bash',root/'build-h3-cachyos.sh'],env)
        lib=build/'build/src/nouveau/vulkan/libvulkan_nouveau.so'
        checksum=hashlib.sha256(lib.read_bytes()).hexdigest()
        sys.path.insert(0,str(audit/'bench/h2'))
        from evidence import relocate_icd, library_paths, verify_paths
        icd_in=build/'build/src/nouveau/vulkan'/f'nouveau_devenv_icd.{os.uname().machine}.json'
        icd_out=build/'private-icd.json'
        relocate_icd(icd_in,icd_out,lib)
        env=dict(os.environ,VK_DRIVER_FILES=str(icd_out),VK_ICD_FILENAMES=str(icd_out),
                 NVK_DEBUG='',NVK_SHADER_TELEMETRY='false',MESA_SHADER_CACHE_DISABLE='true',
                 MESA_SHADER_CACHE_DIR=str(out/'h3-cache'))
        for key in ('NAK_DEBUG','VK_ADD_DRIVER_FILES','VK_LOADER_DRIVERS_SELECT','VK_LOADER_DRIVERS_DISABLE',
                    'NVK_GM107_CMD_CACHE_LIMIT_KIB'):
            env.pop(key,None)
        h2work=Path(os.getenv('GM107_H2_WORKDIR',audit/'work-h2')).resolve()
        matrix=out/'h3-matrix'
        run([sys.executable,audit/'bench/h2/check_micro.py','--exe',h2work/'bin/ubo-bench',
             '--shaders',h2work/'shaders','--out',matrix,'--validation'],env)
        for i in range(31):
            verify_paths(library_paths((matrix/f'{i:02}.stderr').read_text()),lib,checksum)
        diag=out/'h3-diagnostic';diag.mkdir();env['NVK_SHADER_TELEMETRY']='true'
        run([sys.executable,audit/'bench/h2/launch_verified.py','--out',diag,
             '--expected',lib,'--checksum',checksum,'--',h2work/'bin/ubo-bench',
             '--shaders',h2work/'shaders','--reads','8','--width','64','--height','32',
             '--samples','2','--warmup','1'],env)
        if json.loads((diag/'verification.json').read_text()).get('status')!='verified':
            raise ValueError('diagnostic library load unverified')
        capture=parse((diag/'stderr.txt').read_text(),checksum)
        if any(r['chipset']!=0x117 for r in capture['records']):raise ValueError('not GM107')
        (diag/'compiler-capture.json').write_text(canonical(capture))
        report['H3_micro']='PASS';report['library_sha256']=checksum
        report['acceptance']='SMOKE_ONLY_EXTENDED_VALIDATION_PENDING';save()
        partial.rename(out/'summary.json')
        print('Saved smoke checks. CTS, Dota, long stability and H6 hardware remain NOT_RUN:',out)
    except BaseException as exc:
        report['failure']=type(exc).__name__+': '+str(exc);save();raise
if __name__=='__main__':main()
