#!/usr/bin/env python3
"""Paired, run-level comparison of MangoHud per-frame logs (standard library).

Positive effects mean B is better, including p99 (A/B for lower-is-better).
This tool cannot verify matched scenes, driver identity or image correctness.
"""
import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path

from analyze_mangohud import analyze


METRICS = {
    "average_fps": 1,
    "one_percent_low_fps": 1,
    "p99_frametime_ms": -1,
}


def percentile(sorted_values, fraction):
    position = (len(sorted_values) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return (sorted_values[low] * (high - position)
            + sorted_values[high] * (position - low)
            if high != low else sorted_values[low])


def paired_effect(log_ratios, samples, seed):
    """Resample independent pairs, not the correlated frames within a run."""
    if not log_ratios or not all(math.isfinite(x) for x in log_ratios):
        raise ValueError("Expected finite, nonempty log ratios")
    if samples < 1:
        raise ValueError("Bootstrap sample count must be positive")
    rng = random.Random(seed)
    n = len(log_ratios)
    boot = sorted(statistics.fmean(rng.choices(log_ratios, k=n))
                  for _ in range(samples))
    return {
        "effect_percent": math.expm1(statistics.fmean(log_ratios)) * 100,
        "ci95_percent": [math.expm1(percentile(boot, p)) * 100
                         for p in (0.025, 0.975)],
    }


def load_pairs(manifest, min_pairs=8, duration=120.0, tolerance=2.0):
    if min_pairs < 2 or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Require at least two pairs and a positive duration")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Duration tolerance must be finite and nonnegative")
    manifest = Path(manifest).resolve()
    pairs, seen_files = {}, set()
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["pair", "variant", "file"]:
            raise ValueError("Manifest header must be exactly pair,variant,file")
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed manifest record at line {reader.line_num}")
            pair, variant, filename = (row[k].strip() for k in reader.fieldnames)
            if not pair or variant not in ("A", "B") or not filename:
                raise ValueError(f"Invalid manifest record at line {reader.line_num}")
            entries = pairs.setdefault(pair, {})
            if variant in entries:
                raise ValueError(f"Duplicate {variant} in pair {pair}")
            path = (manifest.parent / filename).resolve()
            identity = (path.stat().st_dev, path.stat().st_ino)
            if identity in seen_files:
                raise ValueError(f"Input file reused: {filename}")
            seen_files.add(identity)
            result = analyze(path)
            if abs(result["duration_s"] - duration) > tolerance:
                raise ValueError(f"{filename}: duration {result['duration_s']:.3f}s "
                                 f"outside {duration} +/- {tolerance}s")
            result["file"] = filename
            entries[variant] = result
    if len(pairs) < min_pairs:
        raise ValueError(f"Need >= {min_pairs} pairs; got {len(pairs)}")
    for pair, entries in pairs.items():
        if set(entries) != {"A", "B"}:
            raise ValueError(f"Incomplete pair: {pair}")
    return pairs


def compare(pairs, samples=20000, seed=750):
    metrics = {}
    for metric, direction in METRICS.items():
        ratios = [direction * (math.log(p["B"][metric])
                               - math.log(p["A"][metric]))
                  for p in pairs.values()]
        metrics[metric] = paired_effect(ratios, samples, seed)
        metrics[metric]["A_median"] = statistics.median(
            p["A"][metric] for p in pairs.values())
        metrics[metric]["B_median"] = statistics.median(
            p["B"][metric] for p in pairs.values())
    return {
        "schema": 1,
        "independent_units": "matched run pairs, not frames",
        "pair_count": len(pairs),
        "primary_metric": "average_fps",
        "positive_effect_means": "B better (p99 ratio inverted)",
        "bootstrap_samples": samples,
        "seed": seed,
        "metrics": metrics,
        "runs": pairs,
        "caveat": "CI cannot establish matched workload, correctness or causality; "
                  "secondary CIs are descriptive, not multiplicity-adjusted.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--per-frame", action="store_true",
                        help="Confirm every log used log_interval=0")
    parser.add_argument("--min-pairs", type=int, default=8)
    parser.add_argument("--samples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=750)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--duration-tolerance", type=float, default=2.0)
    args = parser.parse_args()
    if not args.per_frame:
        parser.error("Require --per-frame; sampled logs cannot give true 1% lows")
    if not 1000 <= args.samples <= 100000:
        parser.error("--samples must be between 1000 and 100000")
    try:
        pairs = load_pairs(args.manifest, args.min_pairs, args.duration,
                           args.duration_tolerance)
        report = compare(pairs, args.samples, args.seed)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
