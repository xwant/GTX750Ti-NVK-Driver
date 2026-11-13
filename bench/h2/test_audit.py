import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from evidence import benchmark_rows,library_paths,relocate_icd,sha,verify_paths
from measure_micro import read_run
from summarize_c0 import summarize

class AuditTests(unittest.TestCase):
    def test_icd_relocation_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'build').mkdir();(root/'icd').mkdir();lib=root/'build/libvulkan_nouveau.so';lib.write_bytes(b'fixture')
            src=root/'build/source.json';dest=root/'icd/copy.json'
            for path in ('libvulkan_nouveau.so',str(lib)):
                src.write_text(json.dumps({'ICD':{'library_path':path}}));relocate_icd(src,dest,lib)
                self.assertEqual(json.loads(dest.read_text())['ICD']['library_path'],str(lib))
            with self.assertRaises(ValueError):relocate_icd(src,dest,root/'other.so')
    def test_mapping_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib=Path(tmp)/'libvulkan_nouveau.so';lib.write_bytes(b'fixture')
            self.assertEqual(verify_paths([str(lib)],lib,sha(lib))['status'],'verified')
            for paths in ([],[str(lib)+' (deleted)'],['/wrong/libvulkan_nouveau.so']):
                with self.assertRaises(ValueError):verify_paths(paths,lib,sha(lib))
            with self.assertRaises(ValueError):verify_paths([str(lib)],lib,'0'*64)
    def test_csv_rejections_survive_optimized_python(self):
        base=dict(sample='0',gpu_ms='1',cpu_record_ms='0',submit_wait_ms='1',readback_ok='1',software='0')
        self.assertEqual(benchmark_rows([base],1),[1])
        for key,val in (('sample','1'),('gpu_ms','nan'),('gpu_ms','0'),('software','1'),('readback_ok','0'),('cpu_record_ms','inf')):
            row=dict(base);row[key]=val
            with self.assertRaises(ValueError):benchmark_rows([row],1)
        with self.assertRaises(ValueError):benchmark_rows([],30)
        code='from evidence import benchmark_rows; benchmark_rows([],30)'
        r=subprocess.run([sys.executable,'-O','-c',code],cwd=Path(__file__).parent,capture_output=True)
        self.assertNotEqual(r.returncode,0)
    def test_c0_bad_types_negative_and_partial(self):
        for raw in ('[]','null','{"schema":1,"event":"compile","nir":"x","loads":-1}',
                    '{"schema":1,"event":"compile","nir":"x","loads":1,"unknown_loads":0,"dynamic_ubo_loads":0,"eligible":1,"selected":-1,"available":true,"candidates":[{"reject":1},null]}'):
            r=summarize(['NVK_GM107_UBO '+raw]);self.assertEqual(r['verdict'],'invalid_log');self.assertFalse(r['rejection_counts'])
    def test_child_mapping_collector_and_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'out';out.mkdir();lib=root/'libvulkan_nouveau.so';lib.write_bytes(b'x'*4096)
            child="import mmap,time; f=open(%r,'rb'); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ); time.sleep(.3)"%str(lib)
            launcher="import subprocess,sys; p=subprocess.Popen([sys.executable,'-c',%r]); p.wait(); sys.exit(17)"%child
            r=subprocess.run([sys.executable,str(Path(__file__).parent/'launch_verified.py'),'--out',str(out),'--expected',str(lib),'--checksum',sha(lib),'--',sys.executable,'-c',launcher],capture_output=True,timeout=10)
            self.assertEqual(r.returncode,17,r.stderr)
            self.assertEqual(json.loads((out/'verification.json').read_text())['status'],'verified')
            evidence=json.loads((out/'process-library-evidence.json').read_text());self.assertTrue(evidence)
    def test_short_no_mapping_is_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lib=root/'libvulkan_nouveau.so';lib.write_bytes(b'fixture')
            r=subprocess.run([sys.executable,str(Path(__file__).parent/'launch_verified.py'),'--out',str(root),'--expected',str(lib),'--checksum',sha(lib),'--',sys.executable,'-c','pass'],capture_output=True,timeout=10)
            self.assertEqual(r.returncode,0);self.assertEqual(json.loads((root/'verification.json').read_text())['status'],'unverified')

    def test_read_run_requires_complete_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);lib=r/'libvulkan_nouveau.so';lib.write_bytes(b'fixture')
            (r/'verification.json').write_text(json.dumps(dict(status='verified',library=str(lib),sha256=sha(lib))))
            (r/'exit-status.txt').write_text('0');(r/'launch.txt').write_text('mode=on\n')
            (r/'stderr.txt').write_text('DEVICE GTX 750 Ti software=0\nPASS all pixels\n')
            with (r/'stdout.txt').open('w') as f:
                w=csv.writer(f);w.writerow(['sample','gpu_ms','cpu_record_ms','submit_wait_ms','readback_ok','software'])
                for i in range(30):w.writerow([i,1,0,1,1,0])
            self.assertEqual(read_run(r,'on'),[1]*30)
            with self.assertRaises(ValueError):read_run(r,'off')
            (r/'verification.json').write_text('{"status":"unverified"}')
            with self.assertRaises(ValueError):read_run(r,'on')
    def test_wrong_library_launch_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);lib=r/'libvulkan_nouveau.so';lib.write_bytes(b'fixture')
            p=subprocess.run([sys.executable,str(Path(__file__).parent/'launch_verified.py'),'--out',str(r),'--expected',str(lib),'--checksum','0'*64,'--',sys.executable,'-c','raise SystemExit(0)'],capture_output=True)
            self.assertNotEqual(p.returncode,0);self.assertFalse((r/'stdout.txt').exists())
    def test_interrupted_measurement_keeps_only_partial_summary(self):
        import os
        from unittest.mock import patch
        import measure_micro
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'results').mkdir()
            with patch.dict(os.environ,{'GM107_H2_WORKDIR':tmp}),patch.object(sys,'argv',['measure_micro.py','--control','off-on','--pairs','8']),patch.object(measure_micro,'read_run',return_value=[1.0]*30),patch.object(measure_micro.subprocess,'run',side_effect=[None,None,subprocess.CalledProcessError(1,['fixture'])]):
                with self.assertRaises(subprocess.CalledProcessError):measure_micro.main()
            outputs=list((root/'results').glob('*.json'))
            self.assertEqual(len(outputs),1);self.assertTrue(outputs[0].name.endswith('.partial.json'))
            result=json.loads(outputs[0].read_text());self.assertEqual(len(result['pairs']),1)
            self.assertNotIn('bootstrap95',result)
