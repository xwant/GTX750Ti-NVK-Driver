# H3 roadmap

## Completed in dataset-v1

- Strict versioned paired datasets, H2 raw import with explicit provenance, origin/scope boundaries and canonical exports.
- Baseline fallback/H2 heuristic/statistical/small-tree comparison with grouped splitting and independent evaluation pairs.
- CPU reference table ABI with compatibility, bounded parsing, content cache identity and fail-closed lookup.
- Separate H2 tooling audit and regression tests; neither main nor original experiment branches are rewritten.

## H3.3 implementation requirements (now implemented below)

The diagnostic work targets an **opt-in diagnostic-only Mesa patch**, applied independently or after H2: canonical late-NIR hash + full layout semantic digest + specialization/robustness/compiler-policy identity, plus actual static UBO loads, SM50 instructions/GPR/spills/fills/address-op metrics where supported. Explicitly emit unavailable fields as null. Add real NIR/compiler tests proving instrumentation does not alter output, deterministic hashes, and different layout/robustness keys. Do not enable runtime H3 table selection yet.

Then: physical GM107 correctness and CTS for H2, audited base/off/on captures with fixed clocks/quality, Dota shader execution/hotness correlation, artifact review. Four synthetic microbenchmark configurations only establish measurement plumbing; they cannot justify a game model. Need many independent shader/layout families and titles/scenes, retaining failing and negative results.

After sufficient real data: measure predictive errors on entirely unseen shader/game families, false-H2 cost, confidence and reproducibility. Separate baseline compiler changes from H2 policy. Only then design a small C policy reader and cache identity integration, prove fallback and bound memory/compile overhead. Keep all integration opt-in until hardware acceptance.

No cloud AI in rendering. No online tuning, power-control changes or firmware work in this roadmap. Frequency control is outside H3's current scope and cannot compensate for missing correctness evidence.

## Completed H3.3 diagnostic implementation

- Actual canonical module/entrypoint/specialization source identity, post-link input NIR and indexed descriptor-layout/context key.
- Late-NIR and compiled-artifact identities, actual NAK counters, no policy inference.
- Strict static capture importer; separate CPU, library evidence and hardware smoke statuses.
- GitHub Actions matrix for base/H2/H3/H2+H3; exact fixture code comparisons.
- Unified hardware checklist and safe handoff collector.

Next: execute the hardware checklist, broaden real compiler capture coverage, add a GPU-free SPIR-V replay corpus across pipeline-layout/specialization/robustness variants and correlate runtime shader hotness before creating performance-labelled per-shader datasets. Final machine address-op counting remains unavailable. No H3 driver policy reader is enabled.
