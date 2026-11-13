"""Read-only ICD, process-library and benchmark evidence validation."""
import hashlib
import json
import math
from pathlib import Path

def check(ok, message):
    if not ok: raise ValueError(message)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def relocate_icd(source, target, expected):
    source,target,expected=Path(source),Path(target),Path(expected).resolve()
    data=json.loads(source.read_text());library=Path(data['ICD']['library_path'])
    if not library.is_absolute(): library=source.parent/library
    check(library.resolve()==expected and expected.is_file(),'ICD points to an unexpected/missing library')
    data['ICD']['library_path']=str(expected)
    target.write_text(json.dumps(data,sort_keys=True)+'\n')

def library_paths(stderr):
    paths=[]
    for line in stderr.splitlines():
        if line.startswith('MAPPING '):
            parts=line[len('MAPPING '):].split(None,5)
            if len(parts)==6: paths.append(parts[-1])
    return paths

def verify_paths(paths, expected, expected_sha):
    expected=Path(expected).resolve()
    check(sha(expected)==expected_sha,'library changed since build/launch')
    relevant=[p for p in paths if 'libvulkan_nouveau' in p or 'libvulkan_lvp' in p or 'libGLX_nvidia' in p]
    check(relevant,'no observed driver mapping: coverage unknown')
    for p in relevant:
        check(not p.endswith(' (deleted)'), 'mapped library was deleted')
        check(Path(p).resolve()==expected,'wrong mapped driver: '+p)
        check(sha(p)==expected_sha,'mapped library checksum mismatch')
    return dict(status='verified',library=str(expected),sha256=expected_sha)

def benchmark_rows(rows, expected_count=30):
    check(len(rows)==expected_count,'incomplete sample count')
    times=[]
    for i,r in enumerate(rows):
        check(set(r)=={'sample','gpu_ms','cpu_record_ms','submit_wait_ms','readback_ok','software'},'CSV schema')
        check(r['sample']==str(i) and r['readback_ok']=='1' and r['software']=='0','sample order/readback/software')
        try: values=[float(r[k]) for k in ('gpu_ms','cpu_record_ms','submit_wait_ms')]
        except (ValueError,TypeError): raise ValueError('malformed duration')
        check(all(math.isfinite(x) and x>=0 for x in values) and values[0]>0,'nonfinite/nonpositive duration')
        times.append(values[0])
    return times

if __name__=='__main__':
    import sys
    if sys.argv[1]=='icd': relocate_icd(*sys.argv[2:])
