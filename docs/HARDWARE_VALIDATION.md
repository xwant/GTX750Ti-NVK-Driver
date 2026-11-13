# Unified H2 / H3 / H6 hardware validation

**No physical GM107 results were produced during H3.3 development.** CPU/compiler PASS and synthetic H6 traces are separate from GPU acceptance. Keep H1, H2, H3 and clock policies isolated when attributing a result.

| Area | Remaining check on the actual GTX 750 Ti | Automated now | What it does not prove |
|---|---|---|---|
| Identity/environment | GM107, Nouveau binding, exact Mesa/patch/library hashes, loaded private ICD in every tested process | Collector preflight and audited mapping/hash checks | Unsupported or missed descendant coverage never passes |
| H2 mechanism | Actual promotion, preserved existing cbuf slots, offsets/descriptor bounds | Existing C0 smoke + 31-case readback matrices | Exhaustive correctness, all descriptor layouts or GPU faults |
| H2 correctness | CTS coverage for UBO/dynamic indexing, robustBufferAccess/2, null descriptors, mutable/push descriptors, descriptor transitions, 64 KiB boundaries | Small synthetic matrix only | CTS acceptance or Dota correctness |
| H2 caches | Base/off/on namespaces, B0/B1 UUID separation; serialized pipeline/cache load across restarts and policy changes | UUID smoke | Persistent-cache correctness across all applications |
| H2 performance | Repeated AB/BA with identical scene, quality, library A/B identities, temperatures and actual clocks recorded | 16-pair microbenchmark collection with raw CSV | Game shader acceleration or causality if clocks/thermal state drift |
| H3 identity | Stable keys across process restarts; source specialization, layout gaps/flags, push ranges, embedded samplers, robustness and FS-key changes | CPU fixtures, strict static capture, one real diagnostic smoke | Full real-game coverage, pipeline libraries with unavailable source |
| H3 code | Same machine bytes with diagnostics disabled/enabled on real captured shader corpus | Six CPU compiler fixtures | Universal no-change guarantee or hardware execution correctness |
| H3 metrics | Compare compiler counters against NAK outputs for real game shaders; dynamic descriptor/offset cases | Static parser and NAK counters | Hotness, occupancy, bottlenecks, measured shader GPU time |
| H3 performance data | Shader execution/hotness correlation and isolated base/off/on timings; held-out game/shader families | Not implemented | Existing static captures are never performance labels |
| H3 driver integration | Policy ABI v2, bounded C reader, exact build/transform compatibility, cache isolation, fallback and CTS | No driver table consumer | Old SHA256 policy contract cannot consume new BLAKE3 telemetry directly |
| WSI/Steam | KDE Wayland/X11, Steam children, repeated scene and long sessions, screenshots/readback correctness | Launch tracker available | Steam/WSI was not tested on the development host |
| Stability | Long mixed workload, VRAM pressure, dmesg faults, resets, recovery and suspend/resume | Not automated | A short smoke test cannot certify stability |
| H6 telemetry | Independently trusted busy/timing, correct sensor/fan/power-limit signals, actual core/memory clock feedback | Abstract simulation only | KDE's unreliable 0% is never trusted load |
| H6 capability | Read-only inventory of actual board states, reference clocks and driver capability | No write-capable code | Requested percentages do not imply realizable clock states |
| H6 acceptance | Supervised separate stock-state transition/stability/recovery validation before proposing an actuator | **NOT RUN; no actuator** | Temperature alone cannot establish a safe multiplier |

## One collection sequence on CachyOS (fish)

Use your **existing Nouveau boot**. This sequence does not change drivers, bootloader, BIOS, firmware, frequencies, voltage, power or fan controls. Development tools and Vulkan Validation Layers must already be installed; missing dependencies stop the builds. Reserve disk space for three private Mesa trees. The audit revision is pinned deliberately.

```fish
set stamp (date +%Y%m%d-%H%M%S)
set run_root /mnt/data/GTX750Ti-validation-$stamp
mkdir -p "$run_root"
and git clone --single-branch --branch experiment/h3-shader-telemetry https://github.com/xwant/GTX750Ti-NVK-Driver.git "$run_root/h3"
and git clone --single-branch --branch audit/h2-hardware-readiness https://github.com/xwant/GTX750Ti-NVK-Driver.git "$run_root/audit"
and git -C "$run_root/audit" checkout --detach 8c77906e43095d1cce790fd96cd97a6199d0fd36
and cd "$run_root/h3"
and python3 -m unittest discover -s h3/tests -v
and python3 -m h3.hardware_validation --audit "$run_root/audit" --out "$run_root/results"
```

The collector requires the one NVIDIA display adapter at `0000:01:00.0` because the existing audited H2 wrapper pins that BDF. Other BDFs or multiple adapters stop explicitly; no device is guessed. A later H2 tooling change can make BDF configurable without changing compiler patches. An NVIDIA proprietary boot stops with exit 77 before builds.

Steps: audited private H2 base/patched builds and CPU tests -> actual H2 GPU smoke/readback/cache checks -> paired base/off and off/on micro datasets -> independent H3 private WSI build and CPU tests -> H3 31-case GPU readback matrix with every mapping checked -> diagnostic micro launch and strict static capture. H3's matrix uses no H2 optimization. H6 does not run on the hardware.

`results/summary.json` means only smoke collection finished; `acceptance=SMOKE_ONLY_EXTENDED_VALIDATION_PENDING`. `summary.partial.json` means failure or interruption and is never a PASS. Original raw files are retained. Report, datasets and compiler capture stay separate. Do not run diagnostic collection as an FPS benchmark; hashes/logging can change CPU timings. Do not alter clock policies during H2/H3 A/B work.

After this, send `summary.json` (or partial report), H2 dataset files, `h3-diagnostic/compiler-capture.json`, matrix logs and build/test logs. Check the unautomated rows above before promoting any optimization.

## Later Dota diagnostic launch

After the successful build, replace the three absolute paths below with those printed/created in the run above. From the H3 checkout, Steam launch option:

```text
env PYTHONPATH=/mnt/data/GTX750Ti-validation-STAMP/h3 python3 -m h3.launch_telemetry --audit /mnt/data/GTX750Ti-validation-STAMP/audit --work /mnt/data/GTX750Ti-validation-STAMP/results/h3-build --out /mnt/data/GTX750Ti-validation-STAMP/dota-static -- %command%
```

The explicit PYTHONPATH permits Steam to use a different working directory. Use a new output directory for every run. This captures static compiler events only; it does not measure FPS, per-shader GPU time or game performance. Application pipeline-cache hits can omit records even with Mesa's cache disabled.
