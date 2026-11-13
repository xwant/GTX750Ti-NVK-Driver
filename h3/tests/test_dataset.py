import copy
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from h3 import dataset as d
from h3.synthetic import record

class DatasetTests(unittest.TestCase):
    def test_deterministic_sort(self):
        a,b=record(1),record(2)
        self.assertEqual(d.canonical(d.build([a,b])),d.canonical(d.build([b,a])))
    def test_bad_numbers(self):
        for x in (0,-1,True,float('nan'),float('inf'),10**500,'100'):
            with self.subTest(x=str(x)[:30]):
                r=record();r['pairs'][0]['a']['samples_ns'][0]=x
                with self.assertRaises(d.Invalid):d.build([r])
    def test_structural_failures(self):
        changes=[lambda r:r.update(kind='game'),lambda r:r['pairs'].pop(),
                 lambda r:r['pairs'][1].update(index=True),
                 lambda r:r['pairs'][1].update(order=['off','on']),
                 lambda r:r['pairs'][1]['a'].update(run_id=r['pairs'][0]['a']['run_id']),
                 lambda r:r['pairs'][0]['a']['samples_ns'].pop(),
                 lambda r:r['identity'].update(mesa_commit='other'),
                 lambda r:r['features'].update(spills=-1),
                 lambda r:r['provenance'].update(correctness_passed=False),
                 lambda r:r['identity'].update(shader_sha256='invented')]
        for change in changes:
            r=record(pairs=8);change(r)
            with self.assertRaises((d.Invalid,ValueError)):d.build([r])
    def test_duplicate_and_cross_record_run(self):
        a,b=record(1),record(2)
        with self.assertRaises(d.Invalid):d.build([a,a])
        b['pairs'][0]['a']['run_id']=a['pairs'][0]['a']['run_id']
        with self.assertRaises(d.Invalid):d.build([a,b])
    def test_origins_do_not_escalate(self):
        r=record();r['origin']='hardware'
        with self.assertRaises(d.Invalid):d.build([r])
        r=record();r['origin']='lavapipe'
        with self.assertRaises(d.Invalid):d.build([r])
    def test_per_shader_needs_full_identity(self):
        r=record();r['kind']='per_shader'
        with self.assertRaises(d.Invalid):d.build([r])
    def test_table_never_driver_ready(self):
        table=d.decisions(d.build([record()]))
        self.assertFalse(table['driver_ready']);self.assertFalse(table['entries'][0]['deployable'])
    def test_schema_and_duplicate_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json'
            for text in ('{"x":1,"x":2}', '{"x":NaN}'):
                p.write_text(text)
                with self.assertRaises(d.Invalid):d.load(p)
        with self.assertRaises(d.Invalid):d.validate(dict(schema='v2',records=[]))
    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.json';p.write_text(d.canonical(d.build([record()])))
            for cmd in ('validate','summary','decisions'):
                r=subprocess.run([sys.executable,'-m','h3.dataset',cmd,str(p)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr);json.loads(r.stdout)
            out=Path(tmp)/'copy.json'
            r=subprocess.run([sys.executable,'-m','h3.dataset','build',str(p),'--out',str(out)],capture_output=True)
            self.assertEqual(r.returncode,0);self.assertEqual(p.read_bytes(),out.read_bytes())
            r=subprocess.run([sys.executable,'-m','h3.dataset','build',str(p),'--out',str(out)],capture_output=True)
            self.assertNotEqual(r.returncode,0)

# A legacy-format aggregate plus explicit metadata and raw runs; all SYNTHETIC.
def h2_fixture(root):
    root=Path(root);raw=dict(control='off-on',reads=8,draws=1,rebind=False,pairs=[],geomean_gpu_time_ratio_B_over_A=.9,bootstrap95=[.9,.9])
    orders=[]
    for i in range(8):
        item={};order=['off','on'] if i%2==0 else ['on','off'];orders.append(order)
        for mode in order:
            name=f'case-{i}-{mode}';run=root/name;run.mkdir()
            (run/'exit-status.txt').write_text('0\n');(run/'launch.txt').write_text('mode='+mode+'\n')
            (run/'stderr.txt').write_text('CONFIG reads=8 draws=1 rebind=0 dynamic=0 width=1280 height=720 validation=0\nPASS all pixels, software=0; no FPS claim\n')
            val=1 if mode=='off' else .9
            with (run/'stdout.txt').open('w') as f:
                w=csv.writer(f);w.writerow(['sample','gpu_ms','cpu_record_ms','submit_wait_ms','readback_ok','software'])
                for j in range(30):w.writerow([j,val,.01,.1,1,0])
            item[mode]=dict(run=name,mean_gpu_ms=val)
        raw['pairs'].append(item)
    summary=root/'summary.json';summary.write_text(json.dumps(raw))
    manifest=root/'manifest.json';manifest.write_text(json.dumps(dict(schema='gm107.h2-import.v1',origin='synthetic',gpu='synthetic-GM107-model',scenario_group='legacy-format-fixture',benchmark_sha256=d.digest('fixture'),mesa_commit=d.MESA,pair_orders=orders,artifacts_verified=True)))
    return summary,manifest

class ImportTests(unittest.TestCase):
    def test_import_units_and_unknown_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            s,m=h2_fixture(tmp);r=d.import_h2(s,tmp,m)['records'][0]
            self.assertEqual(r['pairs'][0]['a']['samples_ns'][0],1e6)
            self.assertIsNone(r['features']['gprs']);self.assertIsNone(r['features']['static_ubo_loads'])
            self.assertEqual(r['kind'],'microbenchmark')
    def test_reject_incomplete_corrupt_and_origin(self):
        for case in ('missing','short','nan','mean','origin','order','path','unfinished','config'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                s,m=h2_fixture(tmp);raw=json.loads(s.read_text());meta=json.loads(m.read_text())
                if case=='missing':(Path(tmp)/'case-0-off/stdout.txt').unlink()
                if case=='short':raw['pairs'].pop()
                if case=='nan':raw['pairs'][0]['off']['mean_gpu_ms']=float('nan')
                if case=='mean':raw['pairs'][0]['off']['mean_gpu_ms']=2
                if case=='origin':meta.update(origin='hardware',gpu='GM107')
                if case=='order':meta['pair_orders'][1]=['off','on']
                if case=='path':raw['pairs'][0]['off']['run']='../escape'
                if case=='config':(Path(tmp)/'case-0-off/stderr.txt').write_text('CONFIG reads=32 draws=1 rebind=0 dynamic=0 width=1280 height=720 validation=0\nPASS all pixels\n')
                if case=='unfinished':(Path(tmp)/'case-0-off/exit-status.txt').write_text('1')
                s.write_text(json.dumps(raw));m.write_text(json.dumps(meta))
                with self.assertRaises((d.Invalid,OSError)):d.import_h2(s,tmp,m)
    def test_cli_import_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary,manifest=h2_fixture(tmp);out=Path(tmp)/'dataset.json'
            cmd=[sys.executable,'-m','h3.dataset','import-h2',str(summary),'--runs',tmp,'--manifest',str(manifest),'--out',str(out)]
            r=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([sys.executable,'-m','h3.dataset','decisions',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);table=json.loads(r.stdout)
            self.assertFalse(table['driver_ready']);self.assertEqual(table['entries'][0]['scope'],'microbenchmark')

class CompatibilityTests(unittest.TestCase):
    def test_hardware_requires_matching_off_on_binaries(self):
        r=record();r['origin']='hardware';r['identity']['gpu']='GM107';r['provenance']['gpu_verified']=True
        r['identity']['driver_identities']['on']=d.digest('different build')
        with self.assertRaises(d.Invalid):d.build([r])
        r['identity']['driver_identities']['on']=None
        with self.assertRaises(d.Invalid):d.build([r])
    def test_hardware_import_preserves_build_and_rejects_mid_capture_change(self):
        # Fake recorded-device/library evidence exercises parsing only; it is
        # never exported as a measured hardware dataset or GPU-test result.
        with tempfile.TemporaryDirectory() as tmp:
            summary,manifest=h2_fixture(tmp);meta=json.loads(manifest.read_text())
            meta.update(origin='hardware',gpu='GM107');manifest.write_text(json.dumps(meta))
            lib=d.digest('test library bytes')
            for run in Path(tmp).glob('case-*'):
                stderr=run/'stderr.txt';stderr.write_text(stderr.read_text()+'DEVICE GTX 750 Ti software=0\nMAPPING /recorded/libvulkan_nouveau.so\n')
                (run/'verification.json').write_text(json.dumps(dict(status='verified',library='/recorded/libvulkan_nouveau.so',sha256=lib)))
                (run/'library-h2.sha256').write_text(lib+'  /recorded/libvulkan_nouveau.so\n')
            record=d.import_h2(summary,tmp,manifest)['records'][0]
            self.assertEqual(record['identity']['driver_identities'],dict(off=lib,on=lib))
            run=Path(tmp)/'case-7-on';other=d.digest('different library bytes')
            (run/'verification.json').write_text(json.dumps(dict(status='verified',library='/recorded/libvulkan_nouveau.so',sha256=other)))
            (run/'library-h2.sha256').write_text(other+'  /recorded/libvulkan_nouveau.so\n')
            with self.assertRaises(d.Invalid):d.import_h2(summary,tmp,manifest)
