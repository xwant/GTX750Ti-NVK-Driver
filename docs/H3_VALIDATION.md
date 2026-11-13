# H3 validation — 2026-11-13

Run from the H3 checkout:

```sh
python3 -m unittest discover -s h3/tests -v
python3 -m unittest discover -s h3 -p test_autotune.py -v
python3 -m compileall -q h3
```

Run from the independent audit checkout:

```sh
python3 -m unittest discover -s bench/h2 -p 'test_*.py' -v
bash -n build-h2-cachyos.sh bench/h2/run.sh bench/h2/check-gpu.sh
```

Actual output is in `logs/h3/` and the audit branch's `logs/h2-audit/`. Previous H2 compiler/software logs remain historical evidence and were not represented as newly run hardware tests.

| Test area | Proves | Does not prove |
|---|---|---|
| Native dataset numbers/structure/order/duplicates | Rejects tested nonfinite, boolean, negative, incomplete, reused and incompatible inputs | Authentic physical measurement, stable pstate or absence of all malformed inputs |
| H2 import + CLI roundtrip | Raw CSV means/ratios/configs agree, units normalized, origin boundary maintained, canonical export/no overwrite | Real GPU correctness, game shader identity or hotness |
| Research determinism/group tests | Repeated/permuted input gives same split/model; scenario/config/shader connected groups stay together; held-out values don't train tree | Generalization to Dota or unseen games |
| Synthetic comparison | Planted-rule software experiment runs and reports harmful H2 choices/regret | Any observed nanoseconds, FPS or GPU improvement |
| Policy contract | Bounds, schema/context/key checks, base fallback, changed policy -> changed cache fingerprint | C parser/runtime overhead or NVK cache implementation |
| Audit process/ICD/CSV/parser tests | Observes actual child mmap, distinguishes wrong/unknown driver paths, survives Python -O, rejects tested corrupt records | Steam container handling or Maxwell execution |
| Patch replay/checksums | Original H2 series still applies to pinned Mesa with unchanged patch files | Successful current driver rebuild, Vulkan CTS or hardware conformance |

Synthetic generator creates 48 records, 16 pairs/record, 30 samples/arm; fixed seed 750 yields 33 train and 15 test records. See `logs/h3/synthetic-research.json` for actual metrics, labelled synthetic. Unknown compiler features remain null. Features that are explicitly generated are fixture properties, not claimed observations. H2 fixed baseline is its correctness/threshold heuristic, not a learned cost model. Statistical baseline receives per-test-scenario calibration; tree does not train on test scenarios. This is not an apples-to-apples runtime performance test.

The t-style H3 bound (mean log ratio + 2.5 SEM) is retained for comparison, not claimed as calibrated statistical coverage. Synthetic traces are correlated toy data. A production decision needs real paired data, independent holdouts, multiple-comparison control and confidence calibration.

Hardware and dependency blocks: no physical GPU, CachyOS or server; extracted Mesa build toolchain is unavailable in this session. No new C driver changes were made during the tooling audit. Actual GM107 correctness, pipeline-cache persistence, CTS, WSI, actual game quality/hotness, latency/FPS, power/thermal stability and future C overhead remain untested.

Additional compatibility regressions reject mixed driver builds in one research experiment and changing libraries within a capture. A test using explicitly fake recorded hardware metadata exercises the import success path and its consistency checks; it is a parser fixture in a temporary directory and is never an observed GPU dataset.
