# Run snapshot — 2026-08-01

**Draft output. Modelled allocations throughout — nothing here is a frozen,
gate-signed vintage.**

## Provenance

| | |
|---|---|
| Code/config commit | `8be7cad` (branch `claude/phase0-check-go-criterion-goxtyn`) |
| Trade data (D1) | HMRC OTS pulled 2026-08-01, window 2019-01 → 2026-05 (2026 partial), raw vintage `data/raw/uktradeinfo_ots/2026-08-01/` |
| Mirror (D2) | Comtrade public preview, China→UK, year 2024 |
| Classifier thresholds | Fitted on 2024 (`config/classifier_fitted.yaml`): T1/T6 boundary £8.97/kg, VRF £16.80/kg |
| Commands | `python scripts/run_phase1.py && python scripts/run_phase2.py` |

## Headlines

- GB apparent consumption ~370–600k units/yr, 2019–2025 (2021 peak).
- Draft 2025 installed stock ~4.4m units: U1 2.64m, U2 1.22m, U3 0.41m, U4 0.17m.
- EHS reconciliation (2023): modelled domestic stock 2.12m vs anchor 1.39m —
  **residual +52% (bands overlap)**; candidate explanations in CLAUDE.md.
- S3 classifier metric 64.9% vs ≥90% target (T3/T4 prior split is
  low-confidence by design). Unallocated import mass 7.5%.
- Mirror divergence breaches ±15% on every code (consignment-vs-origin
  artefact, documented in RESEARCH_NOTES).

## Files

| File | Contents |
|------|----------|
| `apparent_consumption_monthly.csv` | Phase 1 deliverable: month × type flows (units central/P10/P90, £, kg, estimator, confidence) |
| `allocation_annual.csv` | Phase 2: annual type × use-case flow allocation with envelope bands and share priors |
| `stock_annual.csv` | Phase 2: modelled installed stock, year × type × use-case, central/lo/hi scenarios |
| `ehs_reconciliation.json` | Modelled U1 stock vs EHS anchor, residual (VG3 groundwork) |
| `mirror_check.csv` | HMRC vs Comtrade China mirror on net mass (VG2 groundwork) |
| `corrections_log.csv` | Every raw-data correction applied (47 mass/1000 fixes + 1 flag-only) |

Column semantics: see the repository README, "Understanding the outputs".
