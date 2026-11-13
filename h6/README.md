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


## Future goal: percentage-based adaptive boost (NOT implemented)

User experience: display a **requested core-clock multiplier** and measured actual clocks, e.g. 100%, 103%, 106%. The multiplier is defined relative to a clearly recorded stock reference core clock for the same GPU/BIOS and temperature regime, not a multiplier on FPS or a percentage of GPU utilization. A percentage is only a **requested target**, never proof that the hardware attained it.

Two separate capabilities must not be conflated:
- **Stock adaptive mode:** dynamically choose among validated board-defined Nouveau P-states; this is the only potential near-term hardware control path. Available states are discrete, so a smooth percentage slider may not be achievable, and display should reflect actual states/clocks.
- **Beyond-stock overclocking:** frequencies above validated factory clocks. This requires independent GM107-specific kernel/firmware/clock-control capability research, hardware stability testing, voltage/power/current and thermal protections; do not imply such capability exists in NVK or current Nouveau. No overclock actuator is authorized by this plan.

### Desired control strategy

1. User explicitly opts in, selects a performance target (e.g. frame-time budget) and a **maximum verified, supported multiplier**. Startup remains monitoring-only.
2. Identify a **GPU-bound** shortfall using trustworthy GPU telemetry and consistent frame-time evidence; low FPS alone may be a CPU bottleneck. The previously observed KDE 0% GPU reading is not reliable.
3. When headroom and GPU-bound demand persist, request one *verified supported* higher state at a time, with ramp-rate limits, minimum dwell time and hysteresis. Never blindly interpolate or synthesize hardware clock frequencies.
4. Confirm actual clocks and telemetry after each attempted change; reject ineffective or unstable changes.
5. Decrease the target on temperature rise, power/current limits, unstable clocks, repeated errors, faults, missing fan/sensor data, or lack of GPU-bound benefit. Losing telemetry disables boosts; restoration is not an excuse to instantaneously jump back to a high state.
6. Recover to a validated conservative state on application exit or controller termination when technically possible; hard GPU hangs may require reboot.

### Safety contract

Temperature alone is **not** a safe overclock boundary. Board limits, VRM/memory temperatures (often unavailable), power delivery, voltage, cooling/fan behavior, silicon variability and driver support also matter. Software thresholds are policy safeguards, not a hardware safety guarantee. Until device-specific validation, there is no universal "safe temperature" or safe maximum percentage for this card; never manufacture these values.

Do not write kernel parameters, firmware, voltages, fan curves, power limits or arbitrary clocks as part of H6 Phase 0. Never combine frequency experiments with H2/H3 performance tests when trying to attribute FPS changes to compiler optimizations.

### Implementation milestones

- H6.1: Pure policy simulation (current) choosing conservative existing P-state IDs, with tests.
- H6.2: Add an **abstract percent-target planning mode** and CPU-only trace-based tests; output recommendations only.
- H6.3: Separate read-only GM107 telemetry collector and evidence-grade GPU-bottleneck detector, with explicit sensor-quality states.
- H6.4: Explicitly opted-in *stock P-state* actuator only after supervised hardware acceptance and recovery validation.
- H6.5: Research *possible* beyond-stock clock control as a separate proposal; do not implement an overclock actuator without proving hardware capability and validating board-specific safeguards.

## H6.2 implemented: abstract percent simulation

`percent.py` is independent of the old stock-state simulator. It never reads or writes devices and offers no apply switch. Default abstract levels 100/103/106% are **synthetic test parameters**, not supported or safe GM107 frequencies. A cap floors to an explicitly listed level; no interpolation or invented hardware state occurs. MHz remains null unless an explicit reference is supplied (the example reference in tests is synthetic).

It requires trusted busy **and** CPU/GPU/frame timing plus explicit healthy sensor/fan and no power/clock-fault signals. GPU-bound classification requires >=85% busy, GPU duration >=80% of frame time, CPU duration <=80% of GPU duration and a missed target. It ramps one abstract step after sustained demand, with separate down threshold/dwell and cooldown. CPU-bound demand, missing/untrusted/faulty telemetry, temperature rejection, malformed or nonmonotonic timestamps, or stale trace gaps return to 100%. Invalid samples preserve the recovery cooldown. Hysteresis prevents oscillating between steps.

Those thresholds are a conservative artificial policy for tests, not validated measurements or guarantees. Real timing must distinguish GPU work from presentation/CPU waits; supplying low FPS or KDE's 0% alone never qualifies. Thermal thresholds alone cannot establish safety. Requested percent is relative to a recorded stock core reference; it is not utilization or predicted FPS.

```sh
python3 -m unittest discover -s h6 -p 'test_*.py' -v
python3 h6/percent.py h6/percent-example.jsonl
```

Every output includes `applied_to_hardware=false` and `hardware_support_verified=false`. `percent-example.jsonl` is explicitly synthetic. Hardware collection/actuation and real speedups remain NOT RUN. H2/H3 compiler experiments must retain fixed, recorded clock policy; do not combine them with future H6 state changes.
