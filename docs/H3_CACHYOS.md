# One sequence after returning to CachyOS

Use the already configured Nouveau boot. Scripts refuse an incompatible kernel binding; they do not change boot/modules/clocks. Reuse the existing Mesa build development dependencies. No installation into system driver directories occurs.

Fish sequence (two independent checkouts; preserve existing results):

```fish
set stamp (date +%Y%m%d-%H%M%S)
set audit_dir /mnt/data/GTX750Ti-H2-audit-$stamp
set h3_dir /mnt/data/GTX750Ti-H3-$stamp
git clone --single-branch --branch audit/h2-hardware-readiness https://github.com/xwant/GTX750Ti-NVK-Driver.git "$audit_dir"
and git clone --single-branch --branch experiment/h3-dataset-v1 https://github.com/xwant/GTX750Ti-NVK-Driver.git "$h3_dir"
and cd "$h3_dir"
and python3 -m unittest discover -s h3/tests -v
and python3 -m h3.collect_real --audit "$audit_dir" --out "$h3_dir/h3/results/real-$stamp"
```

Collector builds private base/H2 userspace libraries, runs audited GPU correctness checks, then one base/off control plus four off/on configurations (8/32 requested reads, 1/64 draws, 16 AB/BA pairs each), and imports completed raw captures into separate datasets. This is prepared/CPU-checked orchestration, **not executed on hardware here**. Missing dependencies or any failed evidence/correctness step stop it. It can take appreciable time. Keep source checkouts and all raw work-h2/results files.

After success send the scoped dataset summaries, raw provenance/checksums and any failures. Do not send unrelated Steam logs without review. H3 outputs remain non-deployable research data. For Dota C0 use the launch option printed by the audited build, run the exact replay/quality/resolution, and wait for all child game processes to exit before final log analysis. Hardware benchmark success alone does not prove Dota applicability.
