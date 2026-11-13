"""Strict import of compiler diagnostics, never GPU timing or training evidence."""
import argparse
import json
import re
from pathlib import Path
from .dataset import canonical, digest

SCHEMA = 'nvk.shader.telemetry.v1'
HASHES = ('shader_key','compile_key','nir_blake3','layout_blake3',
          'source_blake3','late_nir_blake3','code_blake3','driver_build_id')
COUNTS = ('stage','chipset','ubo_loads','ubo_constant_offsets','ubo_nonconstant_offsets',
          'ubo_max_constant_end','instructions','gprs','spills_to_mem','fills_from_mem',
          'spills_to_reg','fills_from_reg','scratch_bytes','code_bytes')
FIELDS = set(HASHES + COUNTS + ('schema','identity_complete','hash_algorithm',
                              'compiler_flags','address_ops','gpu_time_ns'))

def unique(items):
    result = {}
    for k,v in items:
        if k in result: raise ValueError('duplicate JSON field: '+k)
        result[k] = v
    return result

def validate(record):
    if type(record) is not dict or set(record) != FIELDS:
        raise ValueError('telemetry fields do not match ABI')
    if record['schema'] != SCHEMA or record['hash_algorithm'] != 'blake3-256':
        raise ValueError('unsupported telemetry schema or hash')
    if type(record['identity_complete']) is not bool:
        raise ValueError('identity_complete must be boolean')
    for k in HASHES:
        if type(record[k]) is not str or not re.fullmatch('[0-9a-f]{64}',record[k]):
            raise ValueError('invalid '+k)
    if type(record['compiler_flags']) is not str or not re.fullmatch('[0-9a-f]{16}',record['compiler_flags']):
        raise ValueError('invalid compiler_flags')
    for k in COUNTS:
        if type(record[k]) is not int or not 0 <= record[k] < 2**32:
            raise ValueError('invalid '+k)
    if record['stage'] not in (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14):
        raise ValueError('unknown stage')
    if record['gprs'] > 255 or not record['instructions'] or not record['code_bytes']:
        raise ValueError('invalid NAK counters')
    if record['ubo_loads'] != record['ubo_constant_offsets']+record['ubo_nonconstant_offsets']:
        raise ValueError('inconsistent UBO counters')
    if record['address_ops'] is not None or record['gpu_time_ns'] is not None:
        raise ValueError('v1 does not measure address instructions or GPU timing')
    return record

def parse(text, library_sha256):
    if not re.fullmatch('[0-9a-f]{64}',library_sha256): raise ValueError('library SHA256 required')
    records = {}; incomplete = 0
    for number,line in enumerate(text.splitlines(),1):
        if not line.startswith('NVK_H3 '): continue
        if len(line) > 16384: raise ValueError(f'line {number}: oversized record')
        try:
            obj = json.loads(line[7:],object_pairs_hook=unique,
                             parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
            validate(obj)
        except (ValueError,TypeError,RecursionError) as exc:
            raise ValueError(f'line {number}: {exc}') from exc
        if not obj['identity_complete']:
            incomplete += 1
            continue
        key = obj['compile_key']
        if key in records and records[key] != obj:
            raise ValueError('contradictory record for same compilation')
        records[key] = obj
    if not records: raise ValueError('no complete compiler records')
    return {'schema':'gm107.compiler.capture.v1','scope':'compiler_static',
            'library_sha256':library_sha256,'gpu_execution_verified':False,
            'incomplete_records':incomplete,
            'records':[records[k] for k in sorted(records)]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('log',type=Path);p.add_argument('--library-sha256',required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=parse(a.log.read_text(),a.library_sha256)
    with a.out.open('x') as f: f.write(canonical(result))
    print(f"{len(result['records'])} static compiler records; no hardware PASS; digest {digest(result)}")
if __name__=='__main__': main()
