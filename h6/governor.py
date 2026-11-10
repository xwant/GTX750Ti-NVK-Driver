#!/usr/bin/env python3
"""H6 GM107 adaptive stock-pstate *policy simulator*. Does not access hardware."""
import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    low_state: str = "07"
    high_state: str = "0f"
    min_boost_temp_c: float = 65.0
    thermal_down_temp_c: float = 75.0
    busy_up_pct: float = 75.0
    busy_down_pct: float = 35.0
    up_dwell_s: float = 10.0
    down_dwell_s: float = 15.0
    switch_cooldown_s: float = 20.0


class Governor:
    """Pure decision state machine. Never writes clocks/pstates."""

    def __init__(self, config=None):
        self.cfg = config or Config()
        self.state = self.cfg.low_state
        self.last_t = None
        self.last_switch_t = float("-inf")
        self.intent = None
        self.intent_since = None

    def step(self, sample):
        t = sample["t_s"]
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("t_s must be a finite number")
        if self.last_t is not None and t <= self.last_t:
            raise ValueError("samples must have strictly increasing timestamps")
        self.last_t = t

        gpu = sample.get("gpu")
        driver = sample.get("driver")
        active = sample.get("game_active")
        trusted = sample.get("busy_trusted")
        temp = sample.get("temp_c")
        busy = sample.get("busy_pct")
        valid_temp = (type(temp) in (int, float) and
                      math.isfinite(temp) and -20 <= temp <= 125)
        valid_busy = (type(busy) in (int, float) and
                      math.isfinite(busy) and 0 <= busy <= 100)
        supported = gpu == "GM107" and driver == "nouveau"
        trusted_sensor = trusted is True and valid_busy
        healthy = supported and valid_temp and temp < self.cfg.thermal_down_temp_c

        # Fail-closed: unknown model/driver, temperature, or trusted load -> low.
        if not healthy or not trusted_sensor:
            self._switch(self.cfg.low_state, t)
            self._clear_intent()
            return self._report("safety_fallback", t)

        # Hardware thermal safeguard always takes precedence over cooldowns.
        if temp >= self.cfg.thermal_down_temp_c:
            self._switch(self.cfg.low_state, t)
            self._clear_intent()
            return self._report("thermal_down", t)

        if active is True and busy >= self.cfg.busy_up_pct and temp <= self.cfg.min_boost_temp_c:
            desired = self.cfg.high_state
            dwell = self.cfg.up_dwell_s
            reason = "sustained_demand"
        elif active is False or busy <= self.cfg.busy_down_pct:
            desired = self.cfg.low_state
            dwell = self.cfg.down_dwell_s
            reason = "sustained_idle"
        else:
            self._clear_intent()
            return self._report("hysteresis_hold", t)

        if desired == self.state:
            self._clear_intent()
            return self._report("already_at_target", t)
        if self.intent != desired:
            self.intent = desired
            self.intent_since = t
        if t - self.intent_since < dwell:
            return self._report("dwell_pending", t)
        if t - self.last_switch_t < self.cfg.switch_cooldown_s:
            return self._report("cooldown_pending", t)
        self._switch(desired, t)
        self._clear_intent()
        return self._report(reason, t)

    def _switch(self, state, t):
        if self.state != state:
            self.state = state
            self.last_switch_t = t

    def _clear_intent(self):
        self.intent = None
        self.intent_since = None

    def _report(self, reason, t):
        return {"t_s": t, "proposed_pstate": self.state,
                "reason": reason, "applied_to_hardware": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="JSONL samples, see README")
    args = parser.parse_args()
    gov = Governor()
    for lineno, line in enumerate(args.trace.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            sample = json.loads(line)
            if not isinstance(sample, dict):
                raise ValueError("sample must be an object")
            print(json.dumps(gov.step(sample), sort_keys=True))
        except (ValueError, KeyError, TypeError) as exc:
            parser.error(f"line {lineno}: {exc}")


if __name__ == "__main__":
    main()
