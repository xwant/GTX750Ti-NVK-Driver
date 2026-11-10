# H6 — GM107 Adaptive Boost (Phase 0: simulation only)

**Status:** isolated prototype. The policy **never writes to GPU clocks, power limits, voltages, fans, debugfs or the system**. It has NOT been tested on a real GTX 750 Ti. There is no performance claim. It must not be treated as a safe, production-ready overclocking daemon.

## Goal

Develop an optional and auditable user-space GPU performance policy independent of NVK/H1/H2/H3. It should eventually choose between **verified, factory-present** Nouveau pstate IDs, initially \`07\` and \`0f\` as previously observed on the target GM107, without changing clocks outside board-defined states. This is *stock-state management*, **not** overclocking beyond factory settings.

Do not port Kepler BAR0/PMU offsets from third-party auto-reclocking code to GM107. A userspace daemon must not infer accurate GPU activity from KDE's reported 0% utilization; that sensor has already proved unreliable in this project's Nouveau tests. Without a separate verified utilization source, no automatic boost is permitted.

## Current behavior

\`governor.py\` reads an **offline JSONL trace** with fields:
- \`t_s\`: monotonic timestamp in seconds (strictly increasing);
- \`gpu\`: exact string \`GM107\`;
- \`driver\`: exact string \`nouveau\`;
- \`game_active\`: true/false, a hypothetical game-presence signal;
- \`busy_pct\`: verified GPU load in [0,100];
- \`busy_trusted\`: true **only if independently validated** (not based on KDE's unreliable display);
- \`temp_c\`: verified GPU temperature in Celsius.

The simulator recommends the high stock pstate \`0f\` after 10 s of uninterrupted game activity and at least 75% verified GPU busy while temperature is at most 65 °C. It recommends \`07\` after 15 s of low demand and observes a 20 s post-transition cooldown. Temperature >= 75 °C, missing temperature, untrusted busy, wrong driver/GPU immediately recommend \`07\`. These numbers are **initial experimental policy parameters, not validated thermal limits for this particular board**. The policy lacks actual clock feedback, hwmon validation, dmesg checks and crash recovery.

All output includes \`"applied_to_hardware": false\`. There is no \`--apply\` flag.

## Local software-only tests

\`\`\`sh
python3 -m unittest discover -s h6 -p 'test_*.py' -v
python3 h6/governor.py h6/example.jsonl
\`\`\`

## Hardware acceptance requirements before any write-capable implementation

1. Confirm the Nouveau binding and correct PCI BDF; inspect actual pstate file and hwmon readings on GM107 (do not assume debugfs index).
2. Independently validate available stock states and reproducibly stable transition \`07\` to \`0f\` in a supervised session with console/SSH recovery. Previous brief success is not proof of prolonged safety.
3. Obtain a trustworthy GPU activity or GPU-bound-work metric. Do not treat an unsupported or zero-reading KDE sensor as idle/healthy.
4. Identify correct temperature, fan-health, effective core/memory frequency and debugfs failure feedback. Handle missing or inconsistent telemetry as disabling boost. A pstate write can appear to succeed without an actual clock change.
5. Build a **separate, explicitly opt-in** actuator with validated allowlist and state readback. No kernel, BIOS, firmware, voltage, fan or power-limit writes. Prefer least privilege; no long-running unreviewed root daemon.
6. Add watchdog/rollback on abnormal temperature, faults, process termination and unsupported hardware; never assume rollback can recover a GPU hard hang.
7. Benchmark both **performance and thermal/stability** under matched GPU workloads and clock/temperature recording. Do not combine hardware clock changes with H2/H3 compiler A/B tests.

The existing NVIDIA boot is the recovery path; do not modify bootloader, kernel parameters, or installed drivers.

Reference: ArchWiki Nouveau power management documents experimental debugfs reclocking and warns about hangs/overheating. Other projects' Kepler-specific PMU access is not transferable directly to GM107.
