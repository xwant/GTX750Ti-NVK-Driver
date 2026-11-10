# Reproduced validation — 10 November 2026

These results concern the published two-patch series, not lost transient workspace artifacts.

- Source: Mesa 26.2.6 `8e87a503ebd91408c88596d1b9eeb5f4c0b2088d`.
- Patches replayed with `git am` on a clean independent worktree; resulting source tree matches the compiled H2 branch exactly (`patch-replay.txt`). H1 absent.
- Host build: Debian 13, GCC 14.2.0, Meson 1.12.1, Ninja 1.13.2, Rust 1.85.1, bindgen 0.71.1, cbindgen 0.27.0, LLVM/Clang 19.1.7, libdrm 2.4.124. Dependencies extracted into a private toolchain.
- `build-h2-cachyos.sh` completed with `GM107_HEADLESS=1 GM107_JOBS=6`: clean base shared library built, H2 shared library built, benchmark built, 13 SPIR-V modules compiled and passed spirv-val. It reused the H2 working tree; base was independently compiled. X11/Wayland configuration is prepared but **not tested on CachyOS here**.
- Original Nouveau CPU suite **4/4 PASS** (`base-tests.txt`); H2 suite **5/5 PASS** (`h2-tests.txt`). Assertions enabled, debugoptimized. Build options and library hashes are adjacent.
- H2 executable **24 checks PASS**, including real NIR transformations and full SM50 preprocessing/compiler execution (`nir-compiler.txt`). Negative cases compare serialized NIR and original cbuf maps. This is not universal binary equivalence against a separately compiled base.
- Synthetic FS: H2 off 100 instructions/24 GPR; on 10 instructions/24 GPR. No GPU execution or speedup follows from these static counts.
- C benchmark compiles with `-std=c11 -O2 -Wall -Wextra -Werror`.
- **31 software correctness cases PASS** with Khronos validation layer 1.4.309.0 on lavapipe Mesa 25.0.7, LLVM 19.1.7; exhaustive pixel readback, zero validation messages (`software-validation-*`). Includes changing UBO contents, descriptor offsets/rebinding, alternating pipelines, push descriptors, null-only, robust2 null/OOB, divergent offsets, 1/4/7/8/16/32 reads. Lavapipe does not run NVK/SM50 code.
- C0 parser **6 tests PASS**; existing frametime analyzer **12 tests PASS**. Shell syntax and Python compilation pass.

**Not performed:** actual GM107 execution/measurements, Dota shader capture/C0, GPU pipeline-cache UUID and cache persistence checks, Vulkan CTS, WSI/runtime checks on CachyOS, prolonged stability or FPS comparisons against NVIDIA. No performance improvement is claimed.

Run `check-gpu.sh` on the already configured Nouveau boot before timing, then collect Dota C0. Use `measure_micro.py` only after correctness checks and follow `docs/AB_PROTOCOL.md` for Dota.
