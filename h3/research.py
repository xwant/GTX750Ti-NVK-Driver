#!/usr/bin/env python3
"""Offline, bounded CART experiment. Research artifacts are never driver policies."""
import argparse
import math
from pathlib import Path
import statistics
from .autotune import decide_pairs
from .dataset import FEATURES, canonical, digest, load, pairs_ns, record_id, require, validate

# Only numeric available measurements; categorical correctness gates are separate.
LEARN_FEATURES = ('static_ubo_loads','instructions','gprs','spills','fills',
                  'address_ops','cbuf_bytes','draws')

def grouped_split(records, seed=750):
    """Connected components prohibit shared shader OR scenario/config leakage."""
    parent = list(range(len(records)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    seen = {}
    for i,r in enumerate(records):
        ident = r['identity']
        keys = [('scenario',r['origin'],ident['scenario_group'])]
        if r['kind']=='per_shader': keys.append(('shader',ident['shader_sha256']))
        else: keys.append(('config',r['origin'],ident['benchmark_sha256'],digest(ident['config'])))
        for key in keys:
            if key in seen: parent[find(i)] = find(seen[key])
            seen[key] = i
    groups={}
    for i,r in enumerate(records): groups.setdefault(find(i),[]).append(r)
    components=sorted(groups.values(),key=lambda g:digest([seed,sorted(record_id(r) for r in g)]))
    require(len(components)>=4,'need >=4 independent groups for train/test')
    cut=max(1,min(len(components)-1,int(len(components)*.7)))
    train=[r for g in components[:cut] for r in g];test=[r for g in components[cut:] for r in g]
    return train,test

def eligible(f):
    return f['h2_eligible'] is True and f['stage']=='fragment' and f['descriptor_class']=='ordinary' and f['access']=='constant' and f['static_ubo_loads'] is not None and f['static_ubo_loads']>=8 and f['cbuf_bytes'] is not None and 0<f['cbuf_bytes']<=65536

def label(r):
    # Calibration half only. Evaluation uses independent later pairs.
    return decide_pairs(pairs_ns(r)[:8])[0]=='h2'

def fit(rows, depth=3):
    y=[label(r) for r in rows]
    # Harmful H2 selections carry 4x penalty; small leaves stay base.
    def loss(labels):
        pos=sum(labels); neg=4*(len(labels)-pos)
        return pos*neg/(pos+neg) if pos+neg else 0.0
    leaf=dict(mode='h2' if len(rows)>=3 and all(y) else 'base',count=len(rows))
    if depth==0 or len(rows)<6 or len(set(y))==1: return leaf
    best=None
    for name in LEARN_FEATURES:
        if any(r['features'][name] is None for r in rows): continue
        values=sorted({r['features'][name] for r in rows})
        for a,b in zip(values,values[1:]):
            threshold=(a+b)/2
            left=[r for r in rows if r['features'][name]<=threshold]
            right=[r for r in rows if r['features'][name]>threshold]
            if min(len(left),len(right))<3: continue
            score=loss([label(r) for r in left])+loss([label(r) for r in right])
            choice=(score,name,threshold)
            if score<loss(y) and (best is None or choice<best[0]):best=(choice,left,right)
    if best is None:return leaf
    (score,name,threshold),left,right=best
    return dict(feature=name,threshold=threshold,left=fit(left,depth-1),right=fit(right,depth-1))

def predict(tree, features):
    if not eligible(features): return 'base'
    for _ in range(4):
        if 'mode' in tree:return tree['mode']
        value=features.get(tree['feature'])
        if type(value) not in (int,float) or not math.isfinite(value):return 'base'
        tree=tree['left'] if value<=tree['threshold'] else tree['right']
    return 'base'

def experiment(dataset, seed=750):
    records=validate(dataset)['records']
    require(records and len({(r['kind'],r['origin'],r['identity']['policy_a'],r['identity']['policy_b']) for r in records})==1,'compare one origin, scope and policy pair at a time')
    require(all(r['identity']['policy_a']=='off' and r['identity']['policy_b']=='on' for r in records),'research requires off/on comparison')
    require(all(len(r['pairs'])>=16 for r in records),'need 16 pairs: 8 calibration + >=8 held-out')
    train,test=grouped_split(records,seed);tree=fit(train)
    metrics={name:dict(cases=0,choose_h2=0,harmful_h2=0,wrong_choice=0,regret_ratios=[]) for name in ('base_fallback','h2_fixed','h3_statistics','small_tree')}
    for r in test:
        ratios=[math.log(p['h2_ns'])-math.log(p['base_ns']) for p in pairs_ns(r)[8:]]
        ratio=math.exp(statistics.mean(ratios))
        choices=dict(base_fallback='base',h2_fixed='h2' if eligible(r['features']) else 'base',
                     h3_statistics=decide_pairs(pairs_ns(r)[:8])[0],small_tree=predict(tree,r['features']))
        for name,choice in choices.items():
            m=metrics[name];on=choice=='h2';m['cases']+=1;m['choose_h2']+=on
            m['harmful_h2']+=on and ratio>1.0
            m['wrong_choice']+=on != (ratio<1.0)
            m['regret_ratios'].append((ratio if on else 1.0)/min(1.0,ratio))
    for m in metrics.values():
        ratios=m.pop('regret_ratios');m['geomean_regret']=math.exp(statistics.mean(map(math.log,ratios)))
    return dict(schema='gm107.research.v1',seed=seed,dataset_sha256=digest(validate(dataset)),
                origin=records[0]['origin'],scope=records[0]['kind'],driver_ready=False,
                train_ids=sorted(record_id(r) for r in train),test_ids=sorted(record_id(r) for r in test),
                calibration_pairs=8,evaluation_pairs='8 onward',metrics=metrics,
                model=dict(schema='gm107.tree.research.v1',max_depth=3,default='base',tree=tree,
                           driver_ready=False,features=list(LEARN_FEATURES)),
                note='Synthetic results test plumbing and a planted rule, not GPU acceleration. Statistical baseline uses per-case calibration; tree predicts unseen groups.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:
        require(not a.out.exists(),'output exists');a.out.write_text(canonical(experiment(load(a.dataset))))
    except (ValueError,OSError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
