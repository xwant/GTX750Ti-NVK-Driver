#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
work=${GM107_H2_WORKDIR:-"$root/work-h2"};work=$(cd "$work" && pwd)
id=$(date -u +%Y%m%dT%H%M%SZ)
bash "$root/bench/h2/run.sh" diag-on "$id-mechanism" "$work/bin/ubo-bench" --shaders "$work/shaders" --reads 8 --width 64 --height 32 --samples 2 --warmup 1
python3 - "$work/results/$id-mechanism/c0-summary.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
if r['malformed_records'] or r['selected_compile_events']<=0:raise SystemExit('No valid actual H2 promotion observed')
PY
for mode in base off on; do
 bash "$root/bench/h2/run.sh" "$mode" "$id-check-$mode" python3 "$root/bench/h2/check_micro.py" --exe "$work/bin/ubo-bench" --shaders "$work/shaders" --out "$work/results/$id-matrix-$mode" --validation
done
python3 - "$work/results" "$id" "$root/bench/h2" "$work" <<'PY'
from pathlib import Path
import sys
r=Path(sys.argv[1]);tag=sys.argv[2];sys.path.insert(0,sys.argv[3])
from evidence import library_paths,verify_paths
work=Path(sys.argv[4])
for mode in ('base','off','on'):
 variant='base' if mode=='base' else 'h2'
 checksum=(work/'logs'/f'library-{variant}.sha256').read_text().split()[0]
 expected=work/f'mesa-{variant}'/'build-h2/src/nouveau/vulkan/libvulkan_nouveau.so'
 directory=r/f'{tag}-matrix-{mode}'
 for index in range(31):
  verify_paths(library_paths((directory/f'{index:02}.stderr').read_text()),expected,checksum)
def uuid(mode):
 lines=(r/f'{tag}-matrix-{mode}'/'00.stderr').read_text().splitlines()
 values=[s.split()[1] for s in lines if s.startswith('PIPELINE_CACHE_UUID ')]
 if len(values)!=1:raise SystemExit('Missing/ambiguous UUID')
 return values[0]
if uuid('off')==uuid('on'):raise SystemExit('Cache UUID collision')
print('PASS distinct B0/B1 pipeline cache UUIDs; extended CTS/robustness still required')
PY
