# H3.3 shader identity and compiler telemetry

Opt-in diagnostic-only patch for Mesa **26.2.6 / 8e87a503ebd91408c88596d1b9eeb5f4c0b2088d**. No policy selection, driver installation, GPU timing, cloud access or autotuning during rendering. Apply to clean Mesa, or after the two unchanged H2 patches for compatibility testing. H1 is absent.

## Identity ABI v1

Enable `NVK_SHADER_TELEMETRY=true`. Default false performs no diagnostic NIR traversal, serialization or output. The generic Vulkan compile-info boundary carries diagnostic source information; pipeline cache semantics are unchanged.

All named digests except `driver_build_id` are **BLAKE3-256**, not the SHA256 fields of H3 Dataset v1's old future-policy contract. They must not be silently relabelled or fed into that contract. This is a separate versioned compiler-capture ABI, not a decision table.

`source_blake3` hashes the actual module content hash, length-delimited entrypoint, stage and stage flags, requested subgroup size, and specialization constants. Specialization map entries are sorted by constantID, hashing ID, size and the referenced value bytes. Offsets, map order, structure padding and unused value bytes are excluded. Duplicate IDs, invalid ranges, allocation failure, >4096 constants, identifier-only modules or unavailable original source yield incomplete identity. No fake shader/layout/specialization identifiers are supplied for missing source. Ray-tracing paths are outside this GM107 patch. Source identity propagates for fresh graphics/compute pipelines and shader objects; library imports without retained source are incomplete.

`nir_blake3` uses `nir_serialize(..., strip=true)` at the post-preprocess/link, pre-NVK-lowering boundary. Names/debug metadata are stripped, and actual resolved specialization effects and linked interfaces are retained. This native Mesa format is scoped to the exact pinned compiler/NIR ABI and architecture, not a promise of cross-version or cross-endian equivalence.

`layout_blake3` includes set count, each index and explicit null marker, set creation flags, dynamic descriptor count, the real NVK descriptor-layout semantic digest, push-constant ranges and pointer-free embedded sampler states. NVK's digest includes binding types/counts/flags/offsets/strides/dynamic indices and YCbCr conversion state that changes compiler lowering. Runtime descriptor contents and descriptor GPU addresses are not compiler identity. Layout ordering is retained; semantically equivalent API layouts can conservatively miss each other's keys.

`shader_key` combines source, specialized input NIR, layout, stage, chipset/SM, shader flags, RT flags, next-stage mask, all robustness and null-descriptor behaviors, non-H2 compiler flags and every NAK fragment-key field. Existing H2 policy/diagnostic bits (15/16) are excluded **only from this comparison key**. This permits off/on comparison of the same input.

`late_nir_blake3` identifies the actual input to NAK after NVK lowering. `compile_key` combines shader key, late NIR, full compiler flags and the driver's real zero-padded ELF build ID. `driver_build_id` is a hex build-ID container, **not a claimed BLAKE3 digest**. Actual library SHA256 is also required by the capture importer. CPU fixture tests deliberately use a zero build ID and explicitly synthetic source fixtures.

## Real static metrics

The NIR visitor counts UBO `load_deref`/`load_ubo` instructions, constant versus nonconstant/unsupported offsets, and maximum statically known access end. Deref offsets honor explicit array stride and structure offsets with overflow checks; the maximum is saturated at UINT32_MAX. It is neither total buffer size nor a bound on dynamic accesses. Counts are static IR occurrences, not runtime execution counts.

NAK provides actual final instruction count, allocated GPR count, spills/fills to memory/register files, scratch bytes and code bytes. `code_blake3` hashes emitted code. `address_ops` and `gpu_time_ns` remain **null**: this ABI does not yet count final address instructions or measure GPU execution. No GPR-pressure/occupancy estimates or shader hotness are invented.

## Capture

`NVK_H3 {json}` records go to stderr in one locked stdio operation. Cache hits do not recompile or emit records; diagnostic collection disables Mesa's disk cache, but application pipeline caches may still cause misses in coverage. Absence of a record is not evidence of absence of a shader. No NIR or code payloads are dumped, only hashes and counters.

```sh
python3 -m h3.telemetry diagnostic.stderr --library-sha256 ACTUAL_LIBRARY_SHA256 --out compiler-capture.json
```

The importer validates fields, types, ranges, version, hash syntax, consistent UBO counts, duplicates and conflicting repeated compilations; rejects truncated records; excludes incomplete identities. Output is explicitly `scope=compiler_static`, `gpu_execution_verified=false`. Hash provenance alone is not an attestation. This data cannot train or deploy performance decisions without independently verified paired GPU timing, correctness and execution/hotness correlation.

For a real launch, prefer `h3.launch_telemetry`: it uses the pinned H2 audit process tracker, verifies actual descendant library mappings and checksums, normalizes the private ICD, separates caches, records failures as partial files, and refuses ambiguous coverage. Reusing an already running Steam process can produce unverified coverage; close that launcher before collecting. No arbitrary existing Dota process is selected by name.

## Verification boundary

The patch contains real NIR/NAK tests and canonical source tests. Separate codegen probes compare raw machine code in six static/dynamic fragment/vertex/compute fixtures across clean Mesa, diagnostics off and diagnostics on. H2+H3 is tested only to establish compatibility, not as a merged optimization. Finite fixture coverage cannot prove invariance for all shaders; CTS and hardware validation remain required.
