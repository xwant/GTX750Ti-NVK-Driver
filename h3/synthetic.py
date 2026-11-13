"""Deterministic software fixtures. Values are invented for testing, never timings."""
import argparse
from pathlib import Path
from .dataset import FEATURES, MESA, build, canonical, digest

def record(index=0, ratio=0.9, pairs=16):
    group=f'synthetic-scenario-{index:03}'
    reads=(4,8,16,32)[index%4]; draws=(1,64,256)[index%3]
    f={k:None for k in FEATURES}
    f.update(requested_ubo_reads=reads,static_ubo_loads=reads,draws=draws,stage='fragment',
             descriptor_class='ordinary',access='constant',cbuf_bytes=1024,h2_eligible=reads>=8)
    r=dict(kind='microbenchmark',origin='synthetic',
           identity=dict(scenario_group=group,gpu='synthetic-GM107-model',mesa_commit=MESA,policy_a='off',policy_b='on',benchmark_sha256=digest('synthetic generator v1'),driver_identities=dict(off=digest('synthetic driver'),on=digest('synthetic driver')),config=dict(reads=reads,draws=draws,synthetic_case=index)),
           provenance=dict(collector='synthetic generator v1',artifacts=[dict(name='generator',sha256=digest('synthetic generator v1'))],gpu_verified=False,correctness_passed=True,order_source='synthetic_generator'),features=f,pairs=[])
    for i in range(pairs):
        a=[1000+((index*7+i*3+j)%11) for j in range(30)]
        b=[v*ratio*(1+((i+j)%3-1)*0.001) for j,v in enumerate(a)]
        r['pairs'].append(dict(index=i,order=['off','on'] if i%2==0 else ['on','off'],
                              a=dict(run_id=f'{group}-{i}-off',mode='off',samples_ns=a),
                              b=dict(run_id=f'{group}-{i}-on',mode='on',samples_ns=b)))
    return r

def dataset(count=48):
    # Deliberately has cases where threshold-only H2 makes harmful selections.
    records=[]
    for i in range(count):
        r=record(i)
        ratio=0.85 if r['features']['static_ubo_loads']>=8 and r['features']['draws']<64 else 1.12
        records.append(record(i,ratio))
    return build(records)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():p.error('output exists')
    a.out.write_text(canonical(dataset()))
