import copy
import json
import unittest
from h3 import telemetry as t

class TelemetryTests(unittest.TestCase):
    def record(self):
        d={k:'a'*64 for k in t.HASHES}
        d.update({k:0 for k in t.COUNTS})
        d.update(schema=t.SCHEMA,identity_complete=True,hash_algorithm='blake3-256',
                 compiler_flags='0'*16,instructions=10,gprs=24,code_bytes=80,
                 address_ops=None,gpu_time_ns=None,chipset=279,stage=4,
                 ubo_loads=8,ubo_constant_offsets=8)
        return d
    def parse(self,d):return t.parse('NVK_H3 '+json.dumps(d),'b'*64)
    def test_valid_static_only(self):
        result=self.parse(self.record())
        self.assertEqual(result['scope'],'compiler_static')
        self.assertFalse(result['gpu_execution_verified'])
    def test_duplicate_and_order(self):
        a=self.record();b=copy.deepcopy(a);b['compile_key']='c'*64
        lines=['NVK_H3 '+json.dumps(x) for x in (a,b,a)]
        self.assertEqual(t.parse('\n'.join(lines),'b'*64),t.parse('\n'.join(reversed(lines)),'b'*64))
    def test_corrupt_records(self):
        for k,v in [('instructions',True),('code_bytes',0),('gprs',256),
                    ('ubo_loads',7),('gpu_time_ns',1),('shader_key','f'*63),
                    ('identity_complete',1),('stage',999),('schema','future')]:
            with self.subTest(k=k):
                d=self.record();d[k]=v
                with self.assertRaises(ValueError):self.parse(d)
    def test_duplicate_json_fields(self):
        line='NVK_H3 '+json.dumps(self.record())[:-1]+',"stage":4}'
        with self.assertRaises(ValueError):t.parse(line,'b'*64)
    def test_incomplete_and_truncated(self):
        d=self.record();d['identity_complete']=False
        with self.assertRaises(ValueError):self.parse(d)
        for line in ('noise only','NVK_H3 {','NVK_H3 '+json.dumps(self.record())+'!'):
            with self.assertRaises(ValueError):t.parse(line,'b'*64)
    def test_contradictory_same_compile(self):
        a=self.record();b=copy.deepcopy(a);b['gprs']+=1
        with self.assertRaises(ValueError):
            t.parse('\n'.join('NVK_H3 '+json.dumps(x) for x in (a,b)),'b'*64)
    def test_provenance(self):
        with self.assertRaises(ValueError):t.parse('NVK_H3 '+json.dumps(self.record()),'')
