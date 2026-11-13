# H2 hardware-readiness audit — 2026-11-13

Base: `afbf24b6a72f7c66bd069a7f2004c9d3d136add0`, isolated branch `audit/h2-hardware-readiness`.
No shader-selection changes were justified by this audit. Both existing patches and their checksums remain unchanged. They replay successfully on clean Mesa `8e87a503ebd91408c88596d1b9eeb5f4c0b2088d`.

## Confirmed tooling problems and corrections

| Finding | Correction | Regression evidence |
|---|---|---|
| run.sh used `pgrep -u ... -x dota2`, including unrelated games; paths were collected but never checked against the expected library | Supervise command descendants, retain PID starttimes against reuse and observed reparented descendants, compare canonical mapped paths and SHA-256; explicitly report unknown coverage | Actual child process mmaps a fixture file; wrong path/hash/deleted/missing mappings rejected; command exit 17 preserved; short unobserved run remains unverified |
| Timing collector accepted results without verified library evidence | Require verification.json, unchanged library hash, command completion, device marker and readback success before accepting any pair | read_run accepts complete fixture, rejects wrong mode and missing verification |
| Critical CSV/count/cache-UUID/promotion checks used Python assert, disabled by `python -O` | Explicit failures; strict column sets, sample sequence/count, finite positive GPU durations, nonnegative finite host durations | Invalid CSV still fails under `-O`; negative/nonfinite/software/readback errors rejected |
| Partial summary could have the same extension/shape as completed inputs; no durable explicit order/provenance manifest | Preserve partial file under `.partial.json`; completed file contains final statistics; companion `.manifest.json` records actual AB/BA sequence and benchmark binary/SPIR-V identity | H3 importer integration rejects incomplete summaries, missing/short raw captures and order mismatch; final CSV/evidence reader tested |
| C0 parser could crash on JSON arrays/null and accept negative counts or mutate rejection totals before discovering a malformed record | Strict record/candidate types and ranges; stage rejection accumulation until entire record succeeds; invalid_log verdict | null/array/negative/truncated/corrupt candidate cases plus all six historical parser tests |

A procfs mount in this environment omits task/PID/children. The collector uses a PPid fallback on such mounts; it does not select processes by global executable name. Polling can miss children that detach before observation. Such coverage remains unverified. The microbenchmark's own `/proc/self/maps` output supplies evidence for very short owned runs. Steam container path aliases may fail canonical path verification; that is an explicit acceptance block, not permission to treat the host's expected ICD as proof.

## ICD paths

The actual Mesa generator passes **absolute** `meson.current_build_dir()` into the development ICD; copying its JSON therefore works in the published build. No actual absolute-path bug was found. Added a relocation validator which canonicalizes a relative path against the ORIGINAL manifest directory, then writes an absolute path and requires it to equal the built library. Tests cover correct absolute/relative paths and unexpected targets. This protects reuse without changing valid manifest semantics.

## Driver static review

| Area | Finding and limit |
|---|---|
| Candidate | Only chipset 0x117 + fragment stage; >=8 static loads; ordinary UBO type; constant descriptor index; whole constant-offset footprint within 65536 bytes. This is a provisional static cost model. |
| Existing slots | Complete original sorted map is populated first; extra candidate appended only with room. Root/shader-data/dynamic-descriptor slots are preserved. Out-of-window entries retained for diagnostics are skipped in original selection. |
| Dynamic indices | Invalid/unknown UBO key increments shader-wide unknown count, blocking promotion; dynamic byte offsets accumulate rejection on that key. |
| Boundaries | Checked 64-bit multiply/add in extra offset analysis; size>0 and offset<=65536-size. Existing lowering also refuses end>65536. Negative signed indices become large unsigned indices and are rejected. Aggregate/vector/struct shapes still need more compiler/CTS coverage. |
| Robustness | robustBufferAccess2 never promoted. Ordinary robust access and null-only still require actual GM107 readback/CTS; software execution cannot prove this. |
| Cache | Effective H2 flag bit15 is suppressed on other GPU/no_cbuf; diagnostic bit16. Existing physical-device code hashes compiler flags into shader/pipeline and disk-cache identities. Actual on-device UUID/persistence tests remain pending. |
| Binding | Pre-Turing descriptor fetch and push-buffer split are unchanged; no proof here of transition correctness or a positive cost balance. |

## Checks and unperformed work

Run `python3 -m unittest discover -s bench/h2 -p 'test_*.py' -v` and `bash -n build-h2-cachyos.sh bench/h2/*.sh`. See `logs/h2-audit/` for this run. Patch replay/checksum verification passed. Prior H2 compiler/software results remain archived unchanged; they were **not re-run in this audit**, whose private toolchain has no extracted compiler dependencies. No new driver C code was changed.

Physical GM107, cache persistence, WSI/Steam container behavior, CTS, sustained stability and performance are unverified. Current wrappers may return a successful application exit with verification.status=unverified; all timing consumers require verified status. A diagnostic C0 log alone is not library verification or shader hotness.

Use updated `build-h2-cachyos.sh`, then `check-gpu.sh`. The timing collector now defaults to 16 pairs so H3 can reserve 8 calibration and 8 independent evaluation pairs. This does not make four small microbenchmark scenarios sufficient for a production model.
