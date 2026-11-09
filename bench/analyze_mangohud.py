#!/usr/bin/env python3
"""Per-run statistics for MangoHud per-frame CSV. No sampled FPS substitution."""
import argparse
import csv
import math
import statistics
from pathlib import Path


def analyze(path):
    rows = list(csv.reader(Path(path).read_text(encoding="utf-8-sig").splitlines()))
    start = next((i for i, row in enumerate(rows)
                  if "frametime" in [v.strip().lower() for v in row]
                  and "fps" in [v.strip().lower() for v in row]), None)
    if start is None:
        raise ValueError(f"{path}: per-frame header not found")
    header = [v.strip().lower() for v in rows[start]]
    index = header.index("frametime")
    values = []
    for line, row in enumerate(rows[start + 1:], start + 2):
        if not row or not any(row):
            continue
        try:
            value = float(row[index])
        except (ValueError, IndexError) as exc:
            raise ValueError(f"{path}:{line}: malformed frame record") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{path}:{line}: invalid frametime")
        values.append(value)
    if len(values) < 100:
        raise ValueError(f"{path}: fewer than 100 frames")
    ordered = sorted(values)
    worst = ordered[-max(1, math.ceil(len(values) * .01)):]
    return {
        "file": str(path), "frames": len(values),
        "duration_s": sum(values) / 1000,
        "average_fps": 1000 / statistics.mean(values),
        "one_percent_low_fps": 1000 / statistics.mean(worst),
        "p99_frametime_ms": ordered[math.ceil(len(values) * .99) - 1],
        "max_frametime_ms": max(values),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-frame", action="store_true",
                        help="Confirm capture used log_interval=0")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    if not args.per_frame:
        parser.error("Confirm log_interval=0 with --per-frame; sampled logs cannot yield true 1% lows")
    results = [analyze(p) for p in args.files]
    writer = csv.DictWriter(__import__("sys").stdout, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)
