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

## H3.3 implementation verification (2026-11-13)

CPU-only local validation used the pinned Mesa tree, Rust 1.85.1 and LLVM/Clang 19. Development dependencies were extracted into a private toolchain; no system GPU driver was installed. The H2 patches were unchanged. Logs under `logs/h3-telemetry` replace no previous results.

| Check | Result | Proves / does not prove |
|---|---|---|
| `python3 -m unittest discover -s h3/tests -v` | 35 PASS | Dataset/research/contract + strict telemetry import and sysfs preflight fixtures; not GPU correctness |
| Same command with `python3 -O` | 35 PASS | Checks remain active without assertions; not device behavior |
| `python3 -m unittest discover -s h3 -p test_autotune.py -v` | 8 PASS | Phase 0 compatibility; no real training data |
| Audited H2 `python3 [-O] -m unittest discover -s bench/h2 -p 'test_*.py' -v` | 15 PASS in each mode | Existing capture/parser regressions remain covered |
| `meson test -C BUILD --suite nouveau --print-errorlogs -j 4` | base 5/5, H2 6/6, H3 6/6, H2+H3 7/7 | Includes external codegen probe; NAK software tests skip hardware/nvdisasm tests explicitly |
| `test_nvk_shader_telemetry` repeated in separate processes | PASS | Canonical source/spec and context identity; identical code/NAK info/cbuf map off/on in real SM50 compilation |
| `cmp` of six codegen probe outputs | PASS | Unpatched vs H3 off/on; H2 vs H2+H3 off/on; H2 promotion-on also retains exact code. Not exhaustive corpus coverage |
| `actionlint 1.7.12` on both new workflows | PASS | Workflow syntax/dependency expressions, not a GitHub-hosted run |
| `bash -n` new build scripts and H2 launch/build/check scripts | PASS | Shell syntax only |
| Hardware collector on host without PCI sysfs | exit 77, no output directory | Fail-closed preflight; no hardware checks claimed |

Reproducible portable CPU builds (use a new output per variant; `AUDIT` is a checkout of `8c77906e43095d1cce790fd96cd97a6199d0fd36`):

```sh
bash ci/build_mesa.sh base /tmp/gm107-base "$AUDIT"
bash ci/build_mesa.sh h2 /tmp/gm107-h2 "$AUDIT"
bash ci/build_mesa.sh h3 /tmp/gm107-h3 "$AUDIT"
bash ci/build_mesa.sh h2-h3 /tmp/gm107-h2-h3 "$AUDIT"
cmp /tmp/gm107-base/codegen-off.txt /tmp/gm107-h3/codegen-off.txt
cmp /tmp/gm107-h2/codegen-policy-on.txt /tmp/gm107-h2-h3/codegen-policy-on.txt
```

The development host rebuilt the four variants incrementally in disposable Mesa trees; GitHub Actions starts independent clean builds. `codegen-comparison.json` records the actual output checksums. No physical GM107, GPU timing, Dota, WSI, CTS, power control or overclock test was run. `address_ops` remains unavailable, and the new capture ABI cannot consume or deploy the old SHA256 policy contract.

During implementation, a generic NIR offset helper was found to count scalar size instead of the explicit 16-byte fixture array stride. The telemetry visitor now walks explicit array/struct offsets; the regression asserts a final byte end of 116 for eight scalar reads at stride 16. Specialization hashing also canonicalizes map order/padding and validates ranges instead of copying the existing native cache hash. These are fixes to the new diagnostic implementation; no new confirmed H2 compiler defect was found.

Hardware handoff: [HARDWARE_VALIDATION.md](HARDWARE_VALIDATION.md).
