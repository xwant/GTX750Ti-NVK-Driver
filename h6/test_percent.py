import copy
import math
import unittest
from percent import Config,Planner

def sample(t,**kwargs):
    d=dict(t_s=t,gpu='GM107',driver='nouveau',game_active=True,busy_trusted=True,
           timing_trusted=True,sensor_ok=True,fan_ok=True,power_limited=False,
           clock_unstable=False,temp_c=55,busy_pct=95,frame_ms=24,gpu_ms=22,cpu_ms=6)
    d.update(kwargs);return d
class PercentTests(unittest.TestCase):
    def boosted(self):
        p=Planner()
        for t in range(11):r=p.step(sample(t))
        self.assertEqual(r['requested_pct'],103)
        return p
    def test_ramp_dwell_and_cooldown(self):
        p=Planner();rows=[p.step(sample(t)) for t in range(50)]
        self.assertTrue(all(r['requested_pct']==100 for r in rows[:10]))
        self.assertEqual(rows[10]['requested_pct'],103)
        self.assertEqual(rows[29]['requested_pct'],103)
        self.assertEqual(rows[30]['requested_pct'],106)
        self.assertTrue(all(not r['applied_to_hardware'] for r in rows))
    def test_cap_floor(self):
        for cap,want in ((100,100),(102,100),(103,103),(105,103)):
            p=Planner(Config(max_pct=cap))
            for t in range(60):r=p.step(sample(t))
            self.assertEqual(r['requested_pct'],want)
    def test_no_invented_reference(self):
        self.assertIsNone(Planner().step(sample(0))['requested_mhz'])
        p=Planner(Config(reference_mhz=1000))
        for t in range(11):r=p.step(sample(t))
        self.assertEqual(r['requested_mhz'],1030)
    def test_cpu_bound_is_baseline(self):
        p=self.boosted();r=p.step(sample(11,cpu_ms=23,gpu_ms=10,busy_pct=40))
        self.assertEqual(r['reason'],'cpu_bound');self.assertEqual(r['requested_pct'],100)
    def test_fallback_signals(self):
        for key,value in [('gpu','other'),('driver','nvidia'),('game_active',None),
                          ('game_active',False),('busy_trusted',False),('timing_trusted',False),
                          ('sensor_ok',False),('fan_ok',None),('power_limited',True),
                          ('clock_unstable',True),('temp_c',75),('temp_c',True),
                          ('busy_pct',math.nan),('gpu_ms',math.inf),('cpu_ms',0),('gpu_ms',30)]:
            with self.subTest(key=key,value=value):
                r=self.boosted().step(sample(11,**{key:value}))
                self.assertEqual(r['requested_pct'],100)
    def test_missing_fields_fall_back(self):
        for key in sample(0):
            p=self.boosted();s=sample(11);del s[key]
            r=p.step(s);self.assertEqual(r['requested_pct'],100,key)
    def test_stale_gap_breaks_dwell(self):
        p=Planner();p.step(sample(0));r=p.step(sample(10))
        self.assertEqual(r['reason'],'stale_trace')
        for t in range(11,21):r=p.step(sample(t))
        self.assertEqual(r['requested_pct'],100)
        self.assertEqual(p.step(sample(21))['requested_pct'],103)
    def test_invalid_timestamp_resets(self):
        for t in (-1,True,math.inf,10):
            r=self.boosted().step(sample(t));self.assertEqual(r['requested_pct'],100)
    def test_invalid_sample_preserves_recovery_cooldown(self):
        p=self.boosted();p.step(None)
        for t in range(11,30):r=p.step(sample(t))
        self.assertEqual(r['requested_pct'],100)
        self.assertEqual(p.step(sample(30))['requested_pct'],103)
    def test_hysteresis_hold(self):
        p=self.boosted()
        r=p.step(sample(11,busy_pct=75))
        self.assertEqual(r['requested_pct'],103);self.assertEqual(r['reason'],'hysteresis_hold')
    def test_down_dwell(self):
        p=self.boosted()
        for t in range(11,32):r=p.step(sample(t,busy_pct=50))
        self.assertEqual(r['requested_pct'],100)
    def test_temperature_blocks_up(self):
        p=Planner()
        for t in range(60):r=p.step(sample(t,temp_c=70))
        self.assertEqual(r['requested_pct'],100)
    def test_deterministic(self):
        trace=[sample(t,busy_pct=95 if t<40 else 50) for t in range(80)]
        a=Planner();b=Planner()
        self.assertEqual([a.step(s) for s in trace],[b.step(copy.deepcopy(s)) for s in trace])
    def test_bad_config(self):
        for kw in (dict(max_pct=math.nan),dict(levels=(100,100)),dict(levels=(103,106)),
                   dict(reference_mhz=0),dict(up_dwell_s=-1),dict(max_gap_s=0),
                   dict(up_temp_c=80),dict(down_busy_pct=90)):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):Config(**kw)
    def test_malformed(self):
        self.assertEqual(self.boosted().step(None)['requested_pct'],100)
