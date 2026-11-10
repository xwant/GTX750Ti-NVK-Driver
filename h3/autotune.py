#!/usr/bin/env python3
"""Offline, conservative H3 decision-table builder. No driver modification."""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

SCHEMA = 1
def key(record):
    # Caller must provide stable compiler/driver identity and canonical shader key.
    fields = ("gpu", "mesa_commit", "compiler_flags", "shader_sha256", "layout_sha256")
    values = [record.get(x) for x in fields]
    if any(not isinstance(x, str) or not x for x in values):
        raise ValueError("missing or invalid shader identity")
    if record["gpu"] != "GM107":
        raise ValueError("H3 v0 only supports GM107")
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()

def decide(record, min_gain=0.03):
    ident = key(record)
    pairs = record.get("pairs")
    if not isinstance(pairs, list) or len(pairs) < 8:
        return ident, "base", "insufficient_pairs"
    logratios = []
    for p in pairs:
        if not isinstance(p, dict):
            return ident, "base", "invalid_pair"
        a, b = p.get("base_ns"), p.get("h2_ns")
        if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or x <= 0 for x in (a, b)):
            return ident, "base", "invalid_pair"
        logratios.append(math.log(b / a))
    # Conservative one-sided t-style bound; deliberately no normality claim.
    mean = statistics.mean(logratios)
    sem = statistics.stdev(logratios) / math.sqrt(len(logratios))
    upper = mean + 2.5 * sem
    if upper < math.log(1 - min_gain):
        return ident, "h2", "measured_gain"
    return ident, "base", "no_confident_gain"

def build(records):
    result = {}
    for record in records:
        ident, mode, reason = decide(record)
        if ident in result:
            raise ValueError("duplicate identity")
        result[ident] = {"mode": mode, "reason": reason}
    return {"schema": SCHEMA, "policy": "default_base", "entries": result}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("measurements", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raw = json.loads(args.measurements.read_text())
    if not isinstance(raw, list):
        raise ValueError("expected JSON array")
    result = build(raw)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(result['entries'])} decisions; H2={sum(x['mode']=='h2' for x in result['entries'].values())}")

if __name__ == "__main__":
    main()
