# results/ — committed run snapshots

Each dated subfolder is a **draft snapshot** of a full pipeline run
(Phase 1 + Phase 2), committed so results are inspectable on GitHub without
running anything. These are working outputs, **not** frozen baselines —
gate-signed annual vintages live in `vintages/vYYYY/` (none frozen yet) and
only those feed the outlook model.

Each snapshot folder contains a `RUN.md` recording provenance: the raw-data
pull date, the git commit of the code/config that produced it, and headline
numbers. Regenerate any snapshot with:

```
python scripts/run_phase1.py && python scripts/run_phase2.py
```

(outputs land in `data/outputs/`, git-ignored; copy them here to snapshot).

See the repository README for the full column-by-column guide to each file.

| Snapshot | Trade-data pull | Notes |
|----------|-----------------|-------|
| `2026-08-01/` | 2026-08-01 (HMRC OTS 2019-01 → 2026-05) | First full run. Draft priors throughout; EHS residual +52%. |
