# Suggested GitHub Issues

Эти задачи можно превратить в GitHub Issues после создания репозитория.

## 1. [GPU] Verify NVK physical-device enumeration on GM107

**Goal:** collect baseline and patched `vulkaninfo --summary` under Nouveau, headless/TTY where possible.

**Acceptance:** log command, exit code, deviceName, error output for both variants, plus kernel/Nouveau messages and system details. Do not infer compatibility from library compilation alone.

## 2. [DRM] Diagnose black flashing on KDE Wayland + Nouveau

**Observed:** two boot sessions on 2026-11-09; Nouveau detects 2048 MiB, but screen intermittently blacks out when moving mouse. KWin falls back to legacy modesetting and reports `EACCESS`; kernel `gr: DATA_ERROR` refers to Discord channel.

**Next steps:** isolate Discord/autostart, test graphical session without Discord, compare X11 if available, capture `journalctl -b` and DRM/KWin messages. Avoid attributing causality without A/B isolation.

## 3. [Benchmark] Compare NVK base, patch-off, patch-256 KiB

**Blocker:** first verify GM107 Vulkan device enumeration and rendering correctness.

**Metrics:** benchmark readback correctness, memory-budget estimates, frametime distributions, repeated alternated A/B runs. Record negative results too; do not claim FPS improvements without evidence.

## 4. [Docs] Record exact reproducible hardware-validation commands

Create script for collecting kernel, PCI, ICD, vulkaninfo and dmesg/journal with optional sanitization. Do not record unnecessary private information or firmware dumps.