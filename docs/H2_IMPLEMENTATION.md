# H2 — implementation and hardware handoff

10 November 2026. **Implemented; GPU acceptance pending.** No Dota FPS improvement or advantage over NVIDIA is claimed. C0 applicability to actual Dota fragment shaders is unknown until the diagnostic replay on GM107.

## Source and isolation

Project base: `c6efe1e7a59575433138b0c190b205d131f30499`.
Mesa base: clean 26.2.6, `8e87a503ebd91408c88596d1b9eeb5f4c0b2088d`.
Apply `patches/h2/0001-*.patch`, then `0002-*.patch`; verify the adjacent SHA256SUMS.
Experimental Mesa branch: `experiment/gm107-ubo-cbuf`. **H1 is not applied.**
Use `build-h2-cachyos.sh`; the old `build-cachyos.sh` still builds H1.

## Changes and mechanism

- **C0:** `NVK_DEBUG=gm107_ubo_diag` logs JSON prefixed `NVK_GM107_UBO`. It records stripped input-NIR BLAKE3, static UBO load count, candidates and rejection masks, unknown/dynamic-descriptor loads, available slot and selected index. Masks: 1 descriptor type, 2 dynamic byte offset, 4 invalid range. Buffer contents are never dumped. Shader deserialization logs a cache-hit event without inventing compiler coverage.
- **H2:** `NVK_DEBUG=gm107_ubo_cbuf` appends at most one ordinary UBO after the entire upstream cbuf map. It requires GM107 (`0x117`), fragment stage, at least eight static loads, constant descriptor index and all byte offsets constant, and every byte accessed within the 64 KiB window. Checked 64-bit offset arithmetic rejects overflow. The existing deterministic sort chooses the candidate; original slots/order are preserved.
- Unknown descriptor indexing rejects promotion for the whole shader. `robustBufferAccess2`, indirect shader binding and `no_cbuf` disable promotion. Dynamic, inline and mutable UBO types keep upstream policy. Push descriptors use the existing graphics binding implementation. The unknown-index/robust2 exclusions deliberately narrow the original plan.
- Effective H2 compiler-flags bit 15 is zero on other GPUs and under `no_cbuf`; C0 uses bit 16. Existing physical-device code hashes compiler flags into shader/pipeline cache identity and disk-cache configuration. No cache-key machinery was bypassed. Wrappers also separate cache directories per mode.
- No edits to descriptor binding commands, barriers, allocator, instruction latencies, clock/power control, firmware, kernel or boot configuration. Pre-Turing indirect cbuf binding still carries its upstream command-buffer split/descriptor-fetch cost. Fewer shader instructions can lose against that overhead on draw-heavy scenes.

## Verified artifacts

The authoritative logs are in `logs/h2/VALIDATION.md` and adjacent files. Earlier transient workspace files were lost before publication; only re-created and re-run checks are claimed for this patch series.

NIR tests call **real NVK lowering**, compare original map prefixes, check promoted `load_ubo` count, and byte-compare serialized NIR for off/negative cases. They cover 7/8 loads, FS/VS/CS, constant/dynamic/out-of-layout descriptor index, dynamic/mixed byte offsets, mutable and push layouts, constant-window boundaries, slot exhaustion, preserving dynamic slots, indirect bind, robust2 and effective compiler flags. The same fixture traverses preprocessing and the full SM50 compiler with no GPU device. These checks do not establish universal base/off binary equivalence or Vulkan conformance.

The synthetic eight-load FS compiles to 100 instructions/24 GPR with H2 off and 10 instructions/24 GPR with H2 on. **This is compiler output, not a measured speedup.** No actual Dota shader was supplied.

## Private CachyOS build

Required tools: git, C/C++ compiler, Meson, Ninja, Rust, bindgen, cbindgen, pkg-config, Python/Mako/PyYAML, glslangValidator and spirv-val; development headers/libraries include Vulkan, libdrm, libelf, X11/XCB, Wayland/protocols and Mesa's LLVM/SPIR-V build dependencies. Reuse the working H1 build dependencies. For the new benchmark, packages commonly needed are `glslang spirv-tools vulkan-headers vulkan-validation-layers`. Meson's dependency errors are authoritative for current CachyOS packages. The script names missing tools and **never installs packages or drivers**.

```fish
bash build-h2-cachyos.sh
and bash bench/h2/check-gpu.sh
```

Default private directory `work-h2`; exported `GM107_H2_WORKDIR` overrides it. `GM107_JOBS` defaults to four. A=base, B0=H2/off, B1=**the same H2 library/on**. Separate compilation for B0/B1 is unnecessary and risks mismatched options. Build logs include source heads, dirty diffs, build options, dependency versions and library/SPIR-V checksums. `GM107_HEADLESS=1` is only for CPU development, not Dota.

`check-gpu.sh` refuses an NVIDIA kernel binding without changing it. Use the existing tested Nouveau boot manually. It first requires actual promotion in the eight-read benchmark's C0+H2 log, then runs 31 correctness cases with validation for A/B0/B1, then verifies B0/B1 advertise different pipeline cache UUIDs. Errors and missing requested capabilities stop testing; no pass is fabricated. Unsupported instance/GPU/layer returns 77; other requested-feature failures are errors.

**Rollback:** remove the application launch wrapper and restart it; no system driver was installed. If necessary use the existing NVIDIA boot. Do not change Limine/initramfs for this userspace experiment. User Steam caches are not deleted. A failed/changed source tree is not reset; choose a fresh work directory.

## C0 in Dota

Build script prints this Steam launch option with the actual absolute checkout path:

```text
bash "/absolute/checkout/bench/h2/run.sh" diag dota-c0 %command%
```

Use it for the same 120-second replay segment, three-bar preset and resolution in AB_PROTOCOL.md. This diagnostic run disables the Mesa disk shader cache only for that process. **Do not use its timing as FPS evidence.** Use a new run name for each launch; existing result directories are never overwritten.

Send `work-h2/results/dota-c0/c0-summary.json`, `launch.txt`, `loaded-libraries.txt`, `exit-status.txt`, and lines starting `NVK_GM107_UBO` in `stderr.txt`. Review unrelated game stderr before sharing. If Steam detaches a child process, wait for Dota to exit and rerun `python3 bench/h2/summarize_c0.py work-h2/results/dota-c0/stderr.txt` so all late compiler records are included.

Counts represent compilation events, **not executed/hot shaders or unique pipelines**. The NIR hash omits pipeline-layout identity. Empty logs/cache hits mean missing coverage, not proof H2 is inapplicable. Even zero candidates in one replay are not proof for all Dota scenes. `diag-on` additionally records selected cbuf slots. Timing modes `base`, `off`, `on` have no diagnostics/NAK dumps. Confirm actual private-driver mappings, especially inside Steam containers; absent/mismatched mappings invalidate driver identification.

## GPU microbenchmark

`ubo_bench.c` uses Vulkan graphics, ordinary UBOs, a full-screen triangle and R32_UINT offscreen rendering. Runtime UBO values change each iteration. Each read feeds an integer recurrence; every output pixel is checked. Reads 1/4/7/8/16/32 and divergent byte-offset controls are available. Rebinding uses distinct aligned descriptor offsets. `--switch` alternates the selected-read pipeline with a one-read pipeline, exercising different cbuf-map decisions. `--push` exercises push descriptors. `--null`/`--oob` exercise robust2 fallback; `--null-only` tests a null descriptor with robust2 off. OOB range is 256 bytes. No WSI/display changes occur.

The 31-case correctness matrix includes these controls and requires a GTX 750 Ti by default. Explicit `--software` selects a CPU Vulkan device and marks results as software-only. Lavapipe does **not** run NVK or Maxwell machine code.

GPU timestamps cover clear, draws and binding work before readback. Availability and valid-bit wrap are checked. CPU record and submit-to-fence durations are separate; submit-to-fence includes readback. Default UBO storage is host-visible; actual memory-type flags are logged. This does not establish results for device-local UBOs or Dota allocation patterns. GPU duration is not input-to-photon latency.

## A/B protocol

After correctness and C0, use the paired runner:

```fish
python3 bench/h2/measure_micro.py --control base-off --reads 8
and python3 bench/h2/measure_micro.py --control off-on --reads 8
and python3 bench/h2/measure_micro.py --control off-on --reads 32
and python3 bench/h2/measure_micro.py --control off-on --reads 8 --draws 64 --rebind
```

Each invocation uses eight AB/BA pairs, 5 warmup + 30 measured samples, and separate warmed caches. It reports geometric paired GPU-time ratio B/A with bootstrap CI across pairs. B/A below 1 means less GPU time, **not Dota FPS**. 1280x720 total pixel coverage stays constant as draws partition it into stripes. Validate fixed pstate, temperatures, loaded library, image and memory placement separately; no tool writes clocks. KDE's previously observed 0% utilization is not a valid GPU-load measurement.

Then follow [AB_PROTOCOL.md](AB_PROTOCOL.md): A vs B0 sanity, B0 vs B1, eight paired Dota runs at identical quality/scene with raw frametimes, then NVIDIA under identical conditions. Use the existing `bench/compare_ab.py` for Dota frames, not microbenchmark GPU-duration CSV.

## Pending acceptance and next hypothesis

Real GM107 correctness, relevant Vulkan CTS UBO/robustness/descriptor cases, cache persistence, CachyOS X11/Wayland runtime, Dota C0/hotness, sustained stability and performance remain unverified. Passing the synthetic test or software validation alone is insufficient.

If adequate C0 coverage finds no applicable *executed* Dota FS, record H2 as inapplicable to that workload; do not weaken safety guards to manufacture candidates. Dynamic UBO descriptors already use cbufs upstream. Next investigate NAK SM50 instruction count/register pressure/spills and address arithmetic on captured hot Dota shaders, then propose a compiler transformation with correctness tests. No such next optimization is claimed yet.

If candidates exist but many-draw performance regresses, measure the existing indirect-bind overhead before considering a cost model. Static eight-load count alone is provisional. Do not remove synchronization or enable all UBOs indiscriminately.
