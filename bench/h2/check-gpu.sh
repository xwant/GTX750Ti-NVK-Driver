#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
work=${GM107_H2_WORKDIR:-"$root/work-h2"};work=$(cd "$work" && pwd)
id=$(date -u +%Y%m%dT%H%M%SZ)
bash "$root/bench/h2/run.sh" diag-on "$id-mechanism" "$work/bin/ubo-bench" --shaders "$work/shaders" --reads 8 --width 64 --height 32 --samples 2 --warmup 1
python3 - "$work/results/$id-mechanism/c0-summary.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]));assert r['selected_compile_events']>0,'No actual H2 promotion observed; stop before performance testing'
PY
for mode in base off on; do
 bash "$root/bench/h2/run.sh" "$mode" "$id-check-$mode" python3 "$root/bench/h2/check_micro.py" --exe "$work/bin/ubo-bench" --shaders "$work/shaders" --out "$work/results/$id-matrix-$mode" --validation
done
python3 - "$work/results" "$id" <<'PY'
from pathlib import Path
import sys
r=Path(sys.argv[1]);tag=sys.argv[2]
def uuid(mode):
 lines=(r/f'{tag}-matrix-{mode}'/'00.stderr').read_text().splitlines()
 values=[s.split()[1] for s in lines if s.startswith('PIPELINE_CACHE_UUID ')]
 assert len(values)==1
 return values[0]
assert uuid('off')!=uuid('on'),'Cache UUID collision'
print('PASS distinct B0/B1 pipeline cache UUIDs; extended CTS/robustness still required')
PY
