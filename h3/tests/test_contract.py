import copy
import unittest
from h3.dataset import MESA,canonical,digest
from h3.policy_contract import MAX_BYTES,SCHEMA,load_bytes,shader_key

class ContractTests(unittest.TestCase):
    def fixture(self):
        context=dict(gpu='GM107',mesa_commit=MESA,compiler_sha256=digest('test compiler'),transform_sha256=digest('test transform'),policy_abi=1)
        identity=dict(nir_sha256=digest('test nir'),layout_sha256=digest('test layout'),specialization_sha256=digest('test specialization'),stage='fragment',robustness=0,compile_flags=0)
        key=shader_key(identity)
        table=dict(schema=SCHEMA,compatibility=context,scope='per_shader',origin='hardware',entries=[dict(key=key,mode='h2')])
        return context,identity,key,table
    def test_eligibility_and_absence_fallback(self):
        ctx,identity,key,table=self.fixture();p=load_bytes(canonical(table).encode(),ctx)
        self.assertEqual(p.select(key,True),'h2');self.assertEqual(p.select(key,False),'base');self.assertEqual(p.select('0'*64,True),'base')
    def test_invalid_tables(self):
        ctx,identity,key,table=self.fixture()
        for field,value in (('origin','synthetic'),('scope','microbenchmark'),('schema','future'),('entries',[dict(key=key,mode='exec')])):
            t=copy.deepcopy(table);t[field]=value;self.assertEqual(load_bytes(canonical(t).encode(),ctx).select(key,True),'base')
        for raw in (b'{',b'x'*(MAX_BYTES+1),b'{"schema":1,"schema":2}',b'__import__("os").system("false")'):
            self.assertEqual(load_bytes(raw,ctx).fingerprint,'base')
        t=copy.deepcopy(table);t['entries']*=2;self.assertEqual(load_bytes(canonical(t).encode(),ctx).fingerprint,'base')
    def test_cache_identity_and_compatibility(self):
        ctx,identity,key,t=self.fixture();a=load_bytes(canonical(t).encode(),ctx)
        t['entries'][0]['mode']='base';b=load_bytes(canonical(t).encode(),ctx);self.assertNotEqual(a.fingerprint,b.fingerprint)
        wrong=dict(ctx);wrong['compiler_sha256']=digest('other');self.assertEqual(load_bytes(canonical(t).encode(),wrong).fingerprint,'base')
        for field,value in (('robustness',2),('layout_sha256',digest('other layout')),('compile_flags',16)):
            modified=dict(identity);modified[field]=value;self.assertNotEqual(shader_key(modified),key)
    def test_missing_identity(self):
        with self.assertRaises(ValueError):shader_key(dict(nir_sha256=digest('only nir')))
