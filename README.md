# GB AC Outlook Data Pipeline ("Coolstock")

Automated annual baseline of GB air conditioning sales (flow) and installed
stock, segmented by equipment type (T1–T7) and use case (U1–U4), built from
public/API data. See `docs/PRD.md` for the full spec, `CLAUDE.md` for working
context, `docs/RESEARCH_NOTES.md` for verified source findings.

## Progress to date (Aug 2026)

| Phase | Status | Outcome |
|-------|--------|---------|
| 0 — go/no-go spike | ✅ Done | GO criterion **failed structurally**: HMRC collects no item counts for AC codes (no supplementary unit in the UK tariff). Net-mass fallback validated: 100% value coverage, zero suppression. COMEXT ruled out (EU CN same); Comtrade mirrors give kg/unit calibration ratios, not usable counts. |
| 1 — core trade pipeline | ✅ Done | Monthly GB apparent consumption by type, 2019–present, from net mass ÷ unit-mass priors. ~370–600k units/yr. |
| 2 — anchors + allocation + stock-flow | 🔨 In progress | Use-case allocation engine and draft stock-flow model. |
| 3 — validation gate + first vintage (v2026) | Not started | |
| 4 — operationalise | Not started | |

## Quick start

```
pip install -r requirements.txt
python scripts/run_phase1.py              # ingest → classify → apparent consumption
python scripts/run_phase1.py --fit-classifier   # also refit value/kg thresholds on the training year
python scripts/run_phase2.py              # use-case allocation → stock-flow → EHS reconciliation
```

First run pulls ~7 years of HMRC OTS data (a few minutes; rate-limited).
Pulls are stored under `data/raw/uktradeinfo_ots/<date>/` and reused on
reruns the same day. Everything configurable lives in `config/` — CN codes,
unit-mass priors, classifier thresholds, cleaning rules.

## Understanding the Phase 1 output

`data/outputs/apparent_consumption_monthly.csv` (and `.parquet`) — one row
per month × type:

| Column | Meaning |
|--------|---------|
| `month`, `type` | Month; equipment type T1–T7, or a bookkeeping bucket (below) |
| `units_central` | **Apparent consumption in units** = (imports − exports) × GB share, derived as net mass ÷ kg-per-unit prior. NOT a count HMRC publishes — a derived estimate. |
| `units_p10`, `units_p90` | Unit band from the kg-per-unit prior band (`config/unit_mass_priors.yaml`). The band reflects unit-mass uncertainty only, not classification uncertainty. |
| `value_gbp`, `net_mass_kg` | Net trade value (£) and net mass (kg), imports minus exports, GB-adjusted. These come straight from HMRC (after logged corrections) and are the firmest numbers in the file. |
| `estimator` | How the type was assigned: `cn_rule` (CN code is unambiguous), `vpk_threshold` (value-per-kg classifier), `prior_allocation` (T3/T4 split — **modelled, not measured**). |
| `confidence` | Mass-weighted classifier confidence, 0–1. `prior_allocation` rows are capped at 0.40 by design. |

**Bookkeeping buckets** (units are always zero; they exist so no trade value
disappears silently):

- `UNALLOCATED` — volume too close to a classifier threshold to call (~7% of
  import mass). Published, not forced (PRD FR3.3).
- `EDGE_AIRCRAFT` — 841581/82 rows above £250/kg: civil-aircraft units, out
  of scope.
- `EDGE_MONITOR` — 84158300 (no refrigeration unit), monitored only.
- `SATELLITE` — 84186900 chillers, value-index series only.

**Reading it honestly:**

- Negative values happen (e.g. T7 in 2023) when exports exceed imports —
  that's a real finding (re-export waves), not an error.
- Monthly noise is high; aggregate to quarters or years for anything
  load-bearing.
- T3/T4 are a fixed prior split (72/28) of non-VRF split-system mass — treat
  their ratio as an assumption, not a measurement.
- 2026 is a partial year (HMRC publishes with ~2-month lag).
- `data/clean/corrections_log.csv` lists every raw-data correction applied
  (47 grams-as-kg mass fixes to date).
- `data/outputs/mirror_check.csv` compares HMRC China-origin imports against
  China's reported exports to the UK. Divergence exceeds the ±15% tolerance
  on every code — a documented consignment-vs-origin artefact, kept as a
  standing check, not a defect in the series.

## Known limitations (tracked in CLAUDE.md)

- S3 (≥90% of units classified high-confidence) is at ~65% — the T3/T4 prior
  split is low-confidence by design until Phase 2 capacity-mix evidence lands.
- The NI share (GB = UK × 0.975) is a named assumption pending an RTS-based
  estimate.
- Unit counts inherit the kg-per-unit priors' uncertainty — the P10/P90 band
  is the honest range; quote it.
