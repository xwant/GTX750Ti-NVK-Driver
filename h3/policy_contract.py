"""Bounded reference API for a future NVK patch. Not called by the driver."""
import bisect
import json
from .dataset import MESA, canonical, digest

MAX_BYTES=65536
MAX_ENTRIES=512
SCHEMA='gm107.policy.contract.v1'

class Policy:
    def __init__(self, keys=(), modes=(), fingerprint='base'):
        self.keys=tuple(keys);self.modes=tuple(modes);self.fingerprint=fingerprint
    def select(self, shader_key, eligible=False):
        if eligible is not True or type(shader_key) is not str:return 'base'
        i=bisect.bisect_left(self.keys,shader_key)
        return self.modes[i] if i<len(self.keys) and self.keys[i]==shader_key else 'base'

def load_bytes(raw, expected):
    """Fail closed on any incompatible, malformed or oversized file."""
    fallback=Policy()
    try:
        if type(raw) is not bytes or len(raw)>MAX_BYTES or type(expected) is not dict:return fallback
        def unique(pairs):
            obj={}
            for k,v in pairs:
                if k in obj:raise ValueError('duplicate JSON key')
                obj[k]=v
            return obj
        table=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
        if set(table)!={'schema','compatibility','scope','origin','entries'}:return fallback
        if table['schema']!=SCHEMA or table['compatibility']!=expected:return fallback
        if expected.get('gpu')!='GM107' or expected.get('mesa_commit')!=MESA:return fallback
        if set(expected)!={'gpu','mesa_commit','compiler_sha256','transform_sha256','policy_abi'} or type(expected['policy_abi']) is not int or expected['policy_abi']!=1:return fallback
        for field in ('compiler_sha256','transform_sha256'):
            value=expected[field]
            if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):return fallback
        if table['scope']!='per_shader' or table['origin']!='hardware':return fallback
        entries=table['entries']
        if type(entries) is not list or len(entries)>MAX_ENTRIES:return fallback
        keys=[];modes=[]
        for e in entries:
            if type(e) is not dict or set(e)!={'key','mode'}:return fallback
            key=e['key']
            if type(key) is not str or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):return fallback
            if e['mode'] not in ('base','h2') or (keys and key<=keys[-1]):return fallback
            keys.append(key);modes.append(e['mode'])
        # Policy content changes compiler/pipeline cache identity even when a
        # selected shader happens to fall back. Future code must hash this.
        return Policy(keys,modes,digest(table))
    except (ValueError,TypeError,KeyError,UnicodeError,RecursionError):return fallback

def shader_key(identity):
    """All inputs must be actual compiler/layout semantic identities."""
    required={'nir_sha256','layout_sha256','specialization_sha256','stage','robustness','compile_flags'}
    if type(identity) is not dict or set(identity)!=required:raise ValueError('incomplete identity')
    for key in ('nir_sha256','layout_sha256','specialization_sha256'):
        value=identity[key]
        if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError(key)
    if identity['stage'] not in ('fragment','vertex','compute'):raise ValueError('stage')
    if any(type(identity[k]) is not int or not 0<=identity[k]<2**64 for k in ('robustness','compile_flags')):raise ValueError('flags')
    return digest(identity)
