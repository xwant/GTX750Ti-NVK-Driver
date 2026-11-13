#!/usr/bin/env python3
"""Abstract percent-target simulator. No hardware access and no --apply mode."""
import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path


def number(value, low, high):
    return type(value) in (int,float) and math.isfinite(value) and low <= value <= high

@dataclass(frozen=True)
class Config:
    levels: tuple = (100,103,106)
    max_pct: float = 106
    reference_mhz: float | None = None
    target_ms: float = 16.667
    up_busy_pct: float = 85
    down_busy_pct: float = 60
    up_temp_c: float = 65
    down_temp_c: float = 75
    up_dwell_s: float = 10
    down_dwell_s: float = 15
    cooldown_s: float = 20
    max_gap_s: float = 2

    def __post_init__(self):
        if type(self.levels) is not tuple or not self.levels or self.levels[0]!=100:
            raise ValueError('abstract levels must start at 100 percent')
        if any(not number(x,100,200) for x in self.levels) or any(a>=b for a,b in zip(self.levels,self.levels[1:])):
            raise ValueError('levels must be finite and strictly increasing')
        if not number(self.max_pct,100,self.levels[-1]):raise ValueError('invalid cap')
        if self.reference_mhz is not None and not number(self.reference_mhz,1,10000):raise ValueError('invalid reference')
        if not number(self.target_ms,.1,1000):raise ValueError('invalid target')
        if not (number(self.down_busy_pct,0,100) and number(self.up_busy_pct,0,100) and self.down_busy_pct<self.up_busy_pct):
            raise ValueError('invalid busy hysteresis')
        if not (number(self.up_temp_c,-20,100) and number(self.down_temp_c,-20,100) and self.up_temp_c<self.down_temp_c):
            raise ValueError('invalid temperature hysteresis')
        for field in ('up_dwell_s','down_dwell_s','cooldown_s','max_gap_s'):
            if not number(getattr(self,field),.001,3600):raise ValueError('invalid '+field)

class Planner:
    def __init__(self, config=None):
        self.cfg=config or Config()
        self.levels=tuple(v for v in self.cfg.levels if v<=self.cfg.max_pct)
        self.index=0;self.last_t=None;self.last_switch=None
        self.intent=None;self.intent_since=None

    def _clear(self):self.intent=None;self.intent_since=None
    def _fallback(self,t,reason):
        if self.index:self.last_switch=t if t is not None else self.last_t
        self.index=0;self._clear()
        return self._report(t,reason,False)
    def _report(self,t,reason,bound):
        pct=self.levels[self.index]
        return dict(schema='gm107.h6.percent.simulation.v1',t_s=t,requested_pct=pct,
                    requested_mhz=None if self.cfg.reference_mhz is None else self.cfg.reference_mhz*pct/100,
                    gpu_bound=bound,reason=reason,applied_to_hardware=False,
                    hardware_support_verified=False)

    def step(self,s):
        if type(s) is not dict:return self._fallback(None,'malformed_sample')
        t=s.get('t_s')
        if not number(t,0,1e15) or (self.last_t is not None and t<=self.last_t):
            return self._fallback(None,'invalid_timestamp')
        gap=self.last_t is not None and t-self.last_t>self.cfg.max_gap_s
        self.last_t=t
        if gap:return self._fallback(t,'stale_trace')
        if s.get('gpu')!='GM107' or s.get('driver')!='nouveau':return self._fallback(t,'unsupported_device')
        if type(s.get('game_active')) is not bool:return self._fallback(t,'unknown_game_state')
        if not s['game_active']:return self._fallback(t,'game_exit')
        if any(s.get(k) is not True for k in ('busy_trusted','timing_trusted','sensor_ok','fan_ok')):
            return self._fallback(t,'untrusted_telemetry')
        if s.get('power_limited') is not False or s.get('clock_unstable') is not False:
            return self._fallback(t,'fault_or_unknown_limits')
        if not number(s.get('temp_c'),-20,125) or not number(s.get('busy_pct'),0,100):
            return self._fallback(t,'invalid_sensor')
        frame,gpu,cpu=(s.get(k) for k in ('frame_ms','gpu_ms','cpu_ms'))
        if not number(frame,.001,60000) or not number(gpu,.001,60000) or not number(cpu,.001,60000):
            return self._fallback(t,'invalid_timing')
        if gpu>frame*1.05 or cpu>frame*1.05:return self._fallback(t,'inconsistent_timing')
        if s['temp_c']>=self.cfg.down_temp_c:return self._fallback(t,'thermal_down')
        # This is a conservative synthetic classifier, not hardware evidence.
        bound=s['busy_pct']>=self.cfg.up_busy_pct and gpu>=.8*frame and cpu<=.8*gpu
        shortfall=frame>1.05*self.cfg.target_ms
        cpu_bound=cpu>=.9*frame and gpu<.7*frame
        if cpu_bound:return self._fallback(t,'cpu_bound')
        if bound and shortfall and s['temp_c']<=self.cfg.up_temp_c:
            desired=min(self.index+1,len(self.levels)-1);dwell=self.cfg.up_dwell_s;reason='gpu_bound_ramp'
        elif s['busy_pct']<=self.cfg.down_busy_pct or frame<.9*self.cfg.target_ms:
            desired=max(0,self.index-1);dwell=self.cfg.down_dwell_s;reason='demand_down'
        else:
            self._clear();return self._report(t,'hysteresis_hold',bound)
        if desired==self.index:self._clear();return self._report(t,'at_cap_or_baseline',bound)
        if self.intent!=desired:self.intent=desired;self.intent_since=t
        if t-self.intent_since<dwell:return self._report(t,'dwell_pending',bound)
        if self.last_switch is not None and t-self.last_switch<self.cfg.cooldown_s:
            return self._report(t,'cooldown_pending',bound)
        self.index=desired;self.last_switch=t;self._clear()
        return self._report(t,reason,bound)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path)
    p.add_argument('--max-pct',type=float,default=106);p.add_argument('--reference-mhz',type=float)
    a=p.parse_args();planner=Planner(Config(max_pct=a.max_pct,reference_mhz=a.reference_mhz))
    try:
        for line in a.trace.read_text().splitlines():
            if line.strip():print(json.dumps(planner.step(json.loads(line)),sort_keys=True,allow_nan=False))
    except (ValueError,TypeError) as exc:p.error(str(exc))
if __name__=='__main__':main()
