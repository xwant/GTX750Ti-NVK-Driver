# H3 GM107 autotuner — phase 0 (offline prototype)

This is an **offline policy prototype**, not a modified NVK driver, and **does not claim any FPS improvement**. H3 is isolated from H1 and H2. The only output is a JSON decision table; it is **not loaded by NVK**.

## Goal

Select between existing safe compiler policies (base or H2) using measured paired GPU times. Never perform ML inference, benchmarking, or additional compilation in the render loop. A future driver integration must first prove that shader and pipeline identity, descriptor layouts, compiler options, cache UUID and invalidation remain correct.

## Input

JSON array of records, each with:
- `gpu` exactly `GM107`
- `mesa_commit`, `compiler_flags`, `shader_sha256`, `layout_sha256` as nonempty strings
- `pairs`: at least eight independent matched A/B GPU timing pairs with positive finite `base_ns` and `h2_ns`.

The names are a **provisional schema**: use canonical SHA-256 of actual serialized inputs/layouts and verified driver identity before any integration. Never treat the synthetic examples as real hardware results.

## Policy

Compute paired log(h2/base) ratios; choose H2 only if the conservative upper bound (mean + 2.5 standard errors) is below log(0.97). Otherwise default to base. This is a heuristic screening rule, **not a calibrated statistical confidence interval**; independent samples, repeatability, scene relevance, and proper hardware measurements are still required. Never optimize a shader based on unrelated benchmark results.

## Run

```sh
python3 -m unittest discover -s h3 -p 'test_*.py' -v
python3 h3/autotune.py h3/example.json --out /tmp/h3-decisions.json
```

## Next gates

1. Finish H2 hardware correctness and C0 coverage on GM107.
2. Capture reproducible per-shader identity and genuinely matched GPU measurements; microbenchmark timings must not be attributed to Dota shaders.
3. Evaluate decision policy against held-out paired runs; compare with always-base and always-H2.
4. Only then implement a versioned, integrity-checked, read-only driver policy with strict cache separation, deterministic fallback and no render-loop overhead. Never load untrusted decision tables as shader code.
