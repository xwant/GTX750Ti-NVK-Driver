# H3 architecture and future NVK boundary

Status: offline infrastructure and a **reference contract**. No H3 code is called by NVK. No cloud API, online learning or benchmark runs during rendering. Current game CPU/RAM overhead from H3 is zero because it is not integrated.

## Offline path

Audited H2 collection -> raw immutable logs + explicit manifest -> strict dataset -> scope/origin-isolated research -> human-reviewed per-shader evidence -> future validated table. Current benchmark/synthetic research artifacts stop before the deployment boundary. The small tree is a research model, not executable driver input.

`research.py` fits at most depth 3 on available numeric features. Weighted impurity penalizes false H2 selections, small/non-pure leaves remain base. Deterministic grouped splitting joins the same scenario, exact benchmark configuration, or shader across layouts into a connected component. Input sorting and fixed seed prevent accidental run-order dependence. Calibration uses first 8 pairs; evaluation uses later >=8 pairs. Evaluation values never train the tree. The statistical baseline consumes per-scenario calibration, whereas a tree predicts unseen groups; this difference must be disclosed.

## Reference policy ABI

`h3/policy_contract.py` defines `gm107.policy.contract.v1`, read-only JSON, maximum **65536 bytes / 512 sorted entries**, enum mode `base|h2`. Reject duplicates, unknown schema/fields, unsorted keys, oversized data, arbitrary expressions and incompatible context. Parsing failure yields one deterministic base policy. No pickle, eval, imports or user-provided operators are executed.

Compatibility context: GM107, exact Mesa baseline, compiler SHA-256, transformation SHA-256 and policy ABI. Entries are exclusively per_shader/hardware scope. These labels are necessary but not sufficient proof of validation; future packaging must require reviewed evidence, CTS/correctness results and controlled GPU measurements. A hostile user could forge JSON labels; the contract is not an attestation mechanism. It can only choose an already safe compiler transformation.

Shader key includes actual canonical late NIR, full descriptor-layout semantic digest, specialization digest, stage, robustness and compile flags. The current H2 C0 hash excludes layout and is **insufficient**. Until those inputs exist, no deployed H3 selection is justified.

## Proposed NVK integration

1. Optional table path, parsed once at physical-device initialization with explicit file-size/entry caps. Use a bounded C structure, not Python. C layout target <=64 KiB, no background worker.
2. Capture canonical shader/context key at the compiler boundary before H2 selection. Check all existing H2 eligibility guards independently of table contents. Missing/stale/ineligible/unknown entry chooses original NVK policy.
3. Binary-search sorted 32-byte keys once during shader compilation, O(log N); no per-draw lookup, inference, allocation, network or GPU tuning.
4. Include policy ABI, compiler/transform compatibility and **full canonical policy content digest** in shader/pipeline/disk-cache identity. Include effective per-shader choice in compiler key. A table swap requires a new device/instance/cache namespace; no mutable in-process hot reload.
5. Table may select only original lowering or the separately validated H2 promotion. It cannot supply shaders, addresses, barriers, clocks or arbitrary transformations.
6. Tests must call real NIR lowering, assert original slots, compile SM50, verify output under robustness/layout/pipeline transitions, and run GPU correctness/CTS before enabling experimental table consumption. CPU contract tests alone are not a driver implementation.

Python reference lookup demonstrates semantics and failure cases; its object memory and timings are not measurements of future C overhead. No model/table generated here is production-ready. Exact-entry tables are preferred to running even a small tree in the driver until evidence supports generalization.
