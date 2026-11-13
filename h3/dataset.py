#!/usr/bin/env python3
"""Versioned offline measurement datasets. No implicit promotion of evidence."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

SCHEMA = 'gm107.dataset.v1'
MESA = '8e87a503ebd91408c88596d1b9eeb5f4c0b2088d'
FEATURES = ('requested_ubo_reads', 'static_ubo_loads', 'instructions', 'gprs', 'spills',
            'fills', 'address_ops', 'cbuf_bytes', 'draws')

class Invalid(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise Invalid(message)

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'

def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()

def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'duplicate JSON key: ' + key)
            obj[key] = value
        return obj
    try:
        require(Path(path).stat().st_size <= 32 * 1024 * 1024, 'input too large')
        return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                          parse_constant=lambda s: (_ for _ in ()).throw(Invalid('nonfinite JSON')))
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        raise Invalid(str(e)) from e

def fields(obj, names):
    require(type(obj) is dict and set(obj) == set(names.split()), 'unexpected or missing fields: ' + names)

def text(value):
    require(type(value) is str and 0 < len(value) <= 1024, 'invalid text')

def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'invalid sha256')

def positive(value):
    require(type(value) in (int, float) and 0 < value <= 1e15 and math.isfinite(value),
            'duration must be finite, positive and <= 1e15 ns')

def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'invalid integer')

def validate_record(r):
    fields(r, 'kind origin identity provenance features pairs')
    require(r['kind'] in ('microbenchmark', 'per_shader'), 'unknown record kind')
    require(r['origin'] in ('synthetic', 'lavapipe', 'hardware'), 'unknown origin')
    ident = r['identity']
    common = 'scenario_group gpu mesa_commit policy_a policy_b benchmark_sha256 config'
    if r['kind'] == 'per_shader':
        common += ' shader_sha256 layout_sha256 compiler_identity'
    fields(ident, common)
    for name in ('scenario_group', 'gpu', 'policy_a', 'policy_b'):
        text(ident[name])
    require(ident['policy_a'] in ('base', 'off') and ident['policy_b'] in ('off', 'on') and
            (ident['policy_a'], ident['policy_b']) in (('base', 'off'), ('off', 'on')), 'invalid comparison')
    require(ident['mesa_commit'] == MESA, 'incompatible Mesa baseline')
    sha(ident['benchmark_sha256'])
    require(type(ident['config']) is dict and len(canonical(ident['config'])) <= 4096, 'invalid test config')
    # No unknown feature values or guessed identities: unavailable is null.
    if r['kind'] == 'per_shader':
        for name in ('shader_sha256', 'layout_sha256', 'compiler_identity'):
            sha(ident[name])
    prov = r['provenance']
    fields(prov, 'collector artifacts gpu_verified correctness_passed order_source')
    text(prov['collector'])
    require(type(prov['gpu_verified']) is bool and prov['correctness_passed'] is True, 'unverified correctness')
    require(prov['order_source'] in ('explicit_manifest', 'collector_sequence', 'synthetic_generator'), 'unknown pair order')
    require(type(prov['artifacts']) is list and 1 <= len(prov['artifacts']) <= 1024, 'missing provenance')
    artifacts = set()
    for item in prov['artifacts']:
        fields(item, 'name sha256'); text(item['name']); sha(item['sha256'])
        require(item['name'] not in artifacts, 'duplicate artifact'); artifacts.add(item['name'])
    if r['origin'] == 'hardware':
        require(ident['gpu'] == 'GM107' and prov['gpu_verified'], 'hardware needs verified GM107 provenance')
    elif r['origin'] == 'lavapipe':
        require(ident['gpu'] == 'lavapipe', 'software GPU mismatch')
    f = r['features']
    fields(f, ' '.join(FEATURES) + ' stage descriptor_class access h2_eligible')
    for name in FEATURES:
        if f[name] is not None:
            integer(f[name], 0, 1000000000)
    require(f['stage'] in (None, 'fragment', 'vertex', 'compute'), 'stage')
    require(f['descriptor_class'] in (None, 'ordinary', 'dynamic', 'mutable', 'inline'), 'descriptor class')
    require(f['access'] in (None, 'constant', 'dynamic', 'mixed'), 'access')
    require(f['h2_eligible'] is None or type(f['h2_eligible']) is bool, 'eligibility')
    require(type(r['pairs']) is list and 8 <= len(r['pairs']) <= 1000, 'need 8..1000 complete pairs')
    modes = [ident['policy_a'], ident['policy_b']]
    runs, orders, counts = set(), set(), set()
    for i, pair in enumerate(r['pairs']):
        fields(pair, 'index order a b'); require(pair['index'] == i and type(pair['index']) is int, 'pair sequence')
        require(pair['order'] in (modes, modes[::-1]), 'pair order mismatch'); orders.add(tuple(pair['order']))
        require(pair['order'] == (r['pairs'][0]['order'] if i % 2 == 0 else r['pairs'][0]['order'][::-1]), 'AB/BA must alternate')
        for arm, mode in (('a', modes[0]), ('b', modes[1])):
            run = pair[arm]; fields(run, 'run_id mode samples_ns')
            text(run['run_id']); require(run['run_id'] not in runs, 'reused run'); runs.add(run['run_id'])
            require(run['mode'] == mode, 'arm mismatch')
            values = run['samples_ns']; require(type(values) is list and 2 <= len(values) <= 10000, 'need raw samples')
            counts.add(len(values))
            for x in values: positive(x)
    require(len(counts) == 1 and len(orders) == 2, 'unequal sample counts or missing AB/BA order')
    return r

def record_id(r):
    return digest({k: r[k] for k in ('kind', 'origin', 'identity')})

def build(records):
    require(type(records) is list and len(records) <= 10000, 'record list')
    seen, runs, result = set(), set(), []
    for r in records:
        validate_record(r); ident = record_id(r)
        require(ident not in seen, 'duplicate/incompatible repeated scenario identity'); seen.add(ident)
        for pair in r['pairs']:
            for arm in ('a', 'b'):
                # Origin namespaces permit explicitly marked synthetic fixtures.
                key = (r['origin'], pair[arm]['run_id'])
                require(key not in runs, 'run reused across records'); runs.add(key)
        result.append(r)
    return dict(schema=SCHEMA, records=sorted(result, key=record_id))

def validate(dataset):
    fields(dataset, 'schema records'); require(dataset['schema'] == SCHEMA, 'unsupported dataset schema')
    return build(dataset['records'])

def pairs_ns(r):
    return [dict(base_ns=statistics.mean(p['a']['samples_ns']),
                 h2_ns=statistics.mean(p['b']['samples_ns'])) for p in r['pairs']]

def decisions(dataset):
    from .autotune import decide_pairs
    result = []
    for r in validate(dataset)['records']:
        mode, reason = decide_pairs(pairs_ns(r))
        if r['identity']['policy_a'] != 'off': mode, reason = 'base', 'base_off_control_only'
        result.append(dict(record_id=record_id(r), scope=r['kind'], origin=r['origin'],
                           decision=mode, reason=reason, deployable=False))
    return dict(schema='gm107.decisions.v1', default='base', driver_ready=False, entries=result)

def safe_run(root, name):
    require(type(name) is str and re.fullmatch('[A-Za-z0-9_.-]+', name) is not None and name not in ('.', '..'), 'unsafe run name')
    root = Path(root).resolve(); path = (root / name).resolve()
    require(path.parent == root, 'escaped run path')
    return path

def import_h2(summary_path, runs_root, manifest_path):
    """Legacy summaries alone are insufficient; require raw runs + explicit metadata."""
    raw, meta = load(summary_path), load(manifest_path)
    fields(meta, 'schema origin gpu scenario_group benchmark_sha256 mesa_commit pair_orders artifacts_verified')
    require(meta['schema'] == 'gm107.h2-import.v1' and meta['artifacts_verified'] is True, 'unverified manifest')
    require(type(raw) is dict and all(k in raw for k in ('control','reads','draws','rebind','pairs','geomean_gpu_time_ratio_B_over_A','bootstrap95')), 'incomplete H2 summary')
    require(raw['control'] in ('base-off','off-on'), 'comparison'); modes = raw['control'].split('-')
    integer(raw['reads'],1,32); require(raw['reads'] in (1,4,7,8,16,32), 'reads')
    integer(raw['draws'],1,1280); require(type(raw['rebind']) is bool, 'rebind')
    require(type(raw['pairs']) is list and 8 <= len(raw['pairs']) <= 1000, 'incomplete pairs')
    require(type(meta['pair_orders']) is list and len(meta['pair_orders']) == len(raw['pairs']), 'missing explicit order')
    artifacts = [dict(name='summary',sha256=filehash(summary_path)),dict(name='manifest',sha256=filehash(manifest_path))]
    pairs = []
    for i, item in enumerate(raw['pairs']):
        fields(item, ' '.join(modes)); pair = dict(index=i, order=meta['pair_orders'][i])
        for arm, mode in zip(('a','b'), modes):
            fields(item[mode], 'run mean_gpu_ms'); name = item[mode]['run']; path = safe_run(runs_root,name)
            require((path/'exit-status.txt').read_text().strip() == '0', 'failed/incomplete run')
            launch = dict(line.split('=',1) for line in (path/'launch.txt').read_text().splitlines() if '=' in line)
            require(launch.get('mode') == mode, 'launch mode mismatch')
            with (path/'stdout.txt').open() as f: rows = list(csv.DictReader(f))
            require(len(rows) == 30, 'expected 30 raw H2 samples')
            values = []
            for j, row in enumerate(rows):
                require(set(row) == {'sample','gpu_ms','cpu_record_ms','submit_wait_ms','readback_ok','software'}, 'CSV fields')
                require(row['sample'] == str(j) and row['readback_ok'] == '1', 'sample sequence/readback')
                require(row['software'] == ('1' if meta['origin']=='lavapipe' else '0'), 'origin/software conflict')
                try: ns = float(row['gpu_ms'])*1e6
                except (ValueError, TypeError): raise Invalid('duration')
                positive(ns); values.append(ns)
                for metric in ('cpu_record_ms','submit_wait_ms'):
                    try: v=float(row[metric])
                    except (ValueError,TypeError): raise Invalid('host timing')
                    require(math.isfinite(v) and v>=0, 'host timing')
            stated=item[mode]['mean_gpu_ms'];positive(stated)
            require(math.isclose(statistics.mean(values)/1e6,stated,rel_tol=1e-10,abs_tol=1e-9), 'summary/raw mean mismatch')
            # Hardware classification is a manifest claim AND recorded device/readback evidence.
            stderr=(path/'stderr.txt').read_text()
            if meta['origin']=='hardware':
                require('software=0' in stderr and 'GTX 750 Ti' in stderr and 'MAPPING ' in stderr and 'libvulkan_nouveau' in stderr, 'missing device/library evidence')
            require('PASS all pixels' in stderr, 'missing completion marker')
            for filename in ('stdout.txt','stderr.txt','launch.txt','exit-status.txt'):
                artifacts.append(dict(name=name+'/'+filename,sha256=filehash(path/filename)))
            pair[arm]=dict(run_id=name,mode=mode,samples_ns=values)
        pairs.append(pair)
    calculated=math.exp(statistics.mean(math.log(statistics.mean(p['b']['samples_ns']))-math.log(statistics.mean(p['a']['samples_ns'])) for p in pairs))
    stated=raw['geomean_gpu_time_ratio_B_over_A'];positive(stated)
    require(math.isclose(stated,calculated,rel_tol=1e-9), 'summary ratio mismatch')
    ci=raw['bootstrap95'];require(type(ci) is list and len(ci)==2,'CI');[positive(x) for x in ci];require(ci[0]<=ci[1],'CI order')
    features={k:None for k in FEATURES};features.update(requested_ubo_reads=raw['reads'],draws=raw['draws'],stage='fragment',descriptor_class='ordinary',access='constant',h2_eligible=None)
    record=dict(kind='microbenchmark',origin=meta['origin'],identity=dict(scenario_group=meta['scenario_group'],gpu=meta['gpu'],mesa_commit=meta['mesa_commit'],policy_a=modes[0],policy_b=modes[1],benchmark_sha256=meta['benchmark_sha256'],config=dict(reads=raw['reads'],draws=raw['draws'],rebind=raw['rebind'],width=1280,height=720,unit_source='gpu_ms',samples_per_run=30)),
                provenance=dict(collector='H2 legacy + explicit manifest',artifacts=artifacts,gpu_verified=meta['origin']=='hardware',correctness_passed=True,order_source='explicit_manifest'),features=features,pairs=pairs)
    return build([record])

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    for name in ('validate','summary','decisions'):
        q=sub.add_parser(name);q.add_argument('dataset',type=Path);q.add_argument('--out',type=Path)
    q=sub.add_parser('build');q.add_argument('inputs',nargs='+',type=Path);q.add_argument('--out',required=True,type=Path)
    q=sub.add_parser('import-h2');q.add_argument('summary',type=Path);q.add_argument('--runs',required=True,type=Path);q.add_argument('--manifest',required=True,type=Path);q.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    try:
        if a.cmd=='import-h2': result=import_h2(a.summary,a.runs,a.manifest)
        elif a.cmd=='build': result=build([r for f in a.inputs for r in validate(load(f))['records']])
        else:
            d=validate(load(a.dataset))
            if a.cmd=='decisions': result=decisions(d)
            elif a.cmd=='summary': result=dict(records=len(d['records']),counts={f'{k}/{o}':sum(r['kind']==k and r['origin']==o for r in d['records']) for k in ('microbenchmark','per_shader') for o in ('synthetic','lavapipe','hardware')},driver_ready=False)
            else: result=d
        output=canonical(result)
        if a.out:
            require(not a.out.exists(), 'refuse to overwrite output'); a.out.write_text(output)
        else: print(output,end='')
    except (Invalid,OSError,TypeError,KeyError,OverflowError) as e:
        p.exit(2, f'rejected: {e}\n')
if __name__=='__main__': main()
