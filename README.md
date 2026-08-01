# GB AC Outlook Data Pipeline ("Coolstock")

An automated, reproducible pipeline producing an annually versioned baseline
of **air conditioning sales (flow) and installed stock in Great Britain**,
segmented by equipment type (T1–T7) and use case (U1–U4), built entirely
from public/API data with a manual annual validation gate. It feeds a
separate GB AC outlook/forecasting model, rerun yearly.

**Why:** no trustworthy public GB AC statistics exist and commercial market
reports contradict each other. GB manufactures essentially no room AC, so
HMRC trade data (apparent consumption = imports − exports) is the core
measurable signal, triangulated against the English Housing Survey, the EPB
certificate register, MCS, demand-vs-CDD regression and a retail basket.

**Want the numbers without running anything?** → [`results/`](results/) holds
committed snapshots of full runs, each with provenance notes.

---

## Contents

- [Status & key findings](#status--key-findings)
- [How the pipeline works](#how-the-pipeline-works)
- [Repository layout](#repository-layout)
- [Running it](#running-it)
- [Understanding the outputs](#understanding-the-outputs)
- [Segmentation taxonomy](#segmentation-taxonomy)
- [Hard rules & conventions](#hard-rules--conventions)
- [Known limitations](#known-limitations)
- [Roadmap & cadence](#roadmap--cadence)

---

## Status & key findings

| Phase | Status | Outcome |
|-------|--------|---------|
| 0 — go/no-go spike | ✅ Done (Aug 2026) | **GO criterion failed structurally**: HMRC collects no item counts (supplementary units) for any 8415/841861 code — the UK tariff assigns them no supplementary-unit measure, verified against the tariff API with positive controls. Same is true of the EU CN, ruling out COMEXT. **Net-mass fallback validated**: NetMass covers 100% of import value, zero suppression. |
| 1 — core trade pipeline | ✅ Done | Monthly GB apparent consumption by type, 2019–present, derived as net mass ÷ kg-per-unit priors (priors calibrated from Comtrade partner-mirror kg/unit ratios + spec sheets). **~370–600k units/yr.** 47 grams-as-kg errors in HMRC raw data found and corrected (logged). |
| 2 — anchors, allocation, stock-flow | 🔨 Core built | Use-case allocation engine (FR4) + Weibull stock-flow (FR5). Draft 2025 stock **~4.4m units** (domestic 2.6m). EHS reconciliation: modelled domestic stock is **+52% above the EHS anchor** (bands overlap) — published as a finding. D3 (EPB register) ingestion built, blocked on a one-time human token step; D4 (MCS), D6 (CDD regression) not yet ingested. |
| 3 — validation gate + first vintage (v2026) | Not started | Gate checklist tooling; freeze first baseline covering CY2025. |
| 4 — operationalise | Not started | Scheduling, monitoring pack, optional dashboard. |

Full spec: [`docs/PRD.md`](docs/PRD.md) ·
Decisions log: [`docs/DECISIONS.md`](docs/DECISIONS.md) ·
Verified source findings (APIs, corrections, dead ends):
[`docs/RESEARCH_NOTES.md`](docs/RESEARCH_NOTES.md) ·
Working context for AI-assisted sessions: [`CLAUDE.md`](CLAUDE.md)

## How the pipeline works

```
D1 HMRC OTS (monthly CN8 trade) ─┐
                                 ├─ ingest → harmonise (logged corrections)
D2 Comtrade mirror (China→UK) ───┘         │
                                           ▼
                              classify type T1–T7
                     (CN8 rule layer + £/kg thresholds fitted
                      on a training year; near-threshold volume
                      published as UNALLOCATED, never forced)
                                           │
                                           ▼
                        units = NetMass ÷ kg-per-unit prior
                        (P10/P90 band from prior uncertainty)
                                           │
                                           ▼
                 monthly GB apparent consumption by type  ←— Phase 1 output
                                           │
                                           ▼
                   use-case allocation U1–U4 (FR4: deterministic
                   claims, then explicit priors — modelled, tagged)
                                           │
                                           ▼
                   Weibull stock-flow (FR5) → installed stock
                                           │
                                           ▼
              reconciliation vs anchors (EHS…) → residual PUBLISHED
```

Anchors in play or planned: **EHS** (domestic stock, ingested as config),
**EPB register** non-domestic EPC + DEC AC fields (commercial capacity —
module built, needs token), **MCS** (A2A heat pumps, pending), **CDD demand
regression** (operating stock, pending), **retail basket** (portables,
pending).

Key method facts (each verified, see RESEARCH_NOTES):

- HMRC publishes **no unit counts** for AC codes; units are always derived
  from mass. The P10/P90 band is the honest range — quote it.
- Type is classified from CN code + value-per-kg. Use case is **never
  observed** — it is a modelled allocation with published priors.
- The China mirror can't be summed into consumption (consignment-vs-origin
  asymmetry); it serves as a kg-per-unit calibration source and a
  consistency check.

## Repository layout

```
config/                 All parameters — nothing tunable lives in code
  cn_codes.yaml           CN8 codes in scope, survival curves, validation tolerances
  classifier.yaml         Classification rules, cleaning rules, NI-share assumption
  classifier_fitted.yaml  Machine-written fitted thresholds (+ provenance)
  unit_mass_priors.yaml   kg-per-unit priors per type, with bands and source notes
  anchors.yaml            EHS anchor, use-case share priors, opening stock, TM44 gross-up
pipeline/               Importable modules
  ingest.py               D1 OTS pulls → immutable raw vintages
  harmonise.py            Cleaning with logged corrections → data/clean/
  classify.py             FR3 type classification + threshold fitting
  units.py                Net-mass → unit derivation with bands
  apparent.py             Apparent consumption assembly, S3 metric
  mirror.py               D2 Comtrade mirror check (net-mass basis)
  allocate.py             FR4 use-case allocation
  stockflow.py            FR5 Weibull stock-flow + EHS reconciliation
  tm44.py                 D3 EPB register ingestion (needs bearer token)
scripts/                Entry points (see "Running it")
docs/                   PRD, decisions log, research notes
results/                Committed snapshots of full runs (start here for numbers)
data/                   Git-ignored working data:
  raw/<source>/<pull_date>/   immutable raw vintages
  clean/                      harmonised parquet + corrections log
  outputs/                    latest run outputs
vintages/               Frozen, gate-signed annual baselines (none yet)
```

## Running it

```bash
pip install -r requirements.txt

python scripts/run_phase1.py                    # D1 ingest → classify → apparent consumption + D2 mirror
python scripts/run_phase1.py --fit-classifier   # …refitting £/kg thresholds on the training year first
python scripts/run_phase1.py --skip-mirror      # …without the Comtrade call
python scripts/run_phase2.py                    # allocation → stock-flow → EHS reconciliation
python scripts/run_tm44.py                      # D3 EPB register pull (token required, below)
python scripts/phase0_check.py                  # historical: the Phase 0 go/no-go check
```

Notes:

- First Phase 1 run pulls ~7 years of HMRC OTS (a few minutes; the API is
  rate-limited to 60 req/min and its WAF occasionally 403s — the pipeline
  retries with backoff). Same-day reruns reuse the stored vintage.
- Phase 2 reads Phase 1's output; run them in order.
- Everything runs on a laptop; no infrastructure. Full refresh well under
  30 minutes.

### One-time setup: EPB register token (for `run_tm44.py`)

The EPB data service uses GOV.UK One Login — there is no scriptable key
signup, and the old opendatacommunities key route no longer exists. Once,
by hand:

1. Go to <https://get-energy-performance-data.communities.gov.uk> and
   sign in / create an account with GOV.UK One Login.
2. Copy the bearer token from your **My account** page.
3. Put `EPB_BEARER_TOKEN=<token>` in a `.env` file at the repo root
   (git-ignored), or export it as an environment variable.

The first run downloads the non-domestic full load (~3 GB, regenerated
monthly) into `data/raw/epb/<date>/` and reduces it to per-year commercial
AC evidence.

## Understanding the outputs

### `apparent_consumption_monthly.csv` (Phase 1)

One row per month × type:

| Column | Meaning |
|--------|---------|
| `month`, `type` | Month; equipment type T1–T7, or a bookkeeping bucket (below) |
| `units_central` | **Apparent consumption in units** = (imports − exports) × GB share, derived as net mass ÷ kg-per-unit prior. NOT a count HMRC publishes — a derived estimate. |
| `units_p10`, `units_p90` | Unit band from the kg-per-unit prior band. Reflects unit-mass uncertainty only, not classification uncertainty. |
| `value_gbp`, `net_mass_kg` | Net trade value (£) and net mass (kg), imports minus exports, GB-adjusted. Straight from HMRC (after logged corrections) — the firmest numbers in the file. |
| `estimator` | How the type was assigned: `cn_rule` (CN code unambiguous), `vpk_threshold` (value-per-kg classifier), `prior_allocation` (T3/T4 split — **modelled, not measured**). |
| `confidence` | Mass-weighted classifier confidence, 0–1. `prior_allocation` rows are capped at 0.40 by design. |
| `import_units_central` | Import side only (no export netting), for flow-into-country views. |

**Bookkeeping buckets** (units always zero; they exist so no trade value
disappears silently): `UNALLOCATED` (too close to a classifier threshold to
call — published, not forced), `EDGE_AIRCRAFT` (>£250/kg civil-aircraft
units, out of scope), `EDGE_MONITOR` (84158300, monitored), `SATELLITE`
(84186900 chillers, value-index only).

### `allocation_annual.csv` (Phase 2)

Annual type × use-case **flow** allocation: `flow_units` with
`flow_units_lo/hi` envelope bands (unit-band × share-band, deliberately
conservative), the `share_prior` applied, and an `estimator` tag
(`deterministic_assumption` for shares ≥0.85, else `prior_allocation`).
Complete calendar years only.

### `stock_annual.csv` (Phase 2)

Modelled installed **stock**, year × type × use-case, with
`stock_units`/`stock_lo`/`stock_hi` scenario runs. Built from flows +
Weibull survival + opening-stock assumptions (all in `config/anchors.yaml`).

### `ehs_reconciliation.json` / `mirror_check.csv` / `corrections_log.csv`

The published residual vs the EHS domestic anchor; the HMRC-vs-Comtrade
mirror comparison (net-mass basis); and every correction applied to raw
data, with the rule that triggered it.

### Reading all of it honestly

- Negative values are real findings (exports exceeding imports — e.g. the
  2022–23 T7 heat-pump re-export wave to the EU), not errors.
- Monthly series are noisy; aggregate to quarters/years for anything
  load-bearing.
- T3/T4 is a fixed 72/28 prior split of non-VRF split-system mass — an
  assumption, not a measurement.
- The latest year in the monthly file is partial (HMRC ~2-month lag);
  Phase 2 uses complete years only.

## Segmentation taxonomy

| Type | Definition | Primary signal |
|------|-----------|----------------|
| T1 Portable monobloc | Plug-in, movable | 841581/82 low-£/kg cluster |
| T2 Window/wall self-contained | Fixed self-contained (rare in GB) | CN 84151010 |
| T3 Single split | 1 outdoor + 1 indoor | 84151090, prior split |
| T4 Multi-split | 1 outdoor + 2–5 indoor | 84151090, prior split |
| T5 VRF/VRV | Modular commercial systems | 84151090 high-£/kg tail |
| T6 Packaged/rooftop | Self-contained commercial | 841581/82 high-£/kg cluster |
| T7 A2A heat pump | Reversible, marketed as heating | CN 84186100 (boundary policing) |

| Use case | Anchor evidence |
|----------|-----------------|
| U1 Domestic | EHS prevalence; retail channel |
| U2 Small commercial (<12 kW) | Residual allocation — highest uncertainty, flagged |
| U3 Large commercial (>12 kW) | EPB register AC capacity fields (pending token) |
| U4 Industrial/process | Flagged low-confidence |

## Hard rules & conventions

- **Vintages are immutable.** Every raw pull stored keyed by (source,
  pull_date) under `data/raw/`; HMRC revises history, so never overwrite.
  Frozen baselines live in `vintages/vYYYY/`, read-only after gate sign-off.
- **Config over code.** CN codes, priors, thresholds, tolerances — all in
  `config/`, never hardcoded. Fitted values are written to their own file
  with provenance.
- **Publish the residual.** Reconciliation gaps are findings, not errors to
  smooth away. Every output cell carries estimator + confidence tags.
- **APIs and bulk downloads only.** No ToS-violating scraping.
- **Gate-only evidence stays out of the pipeline.** BSRIA figures and
  installer/distributor calls validate; they never feed.

## Known limitations

- **S3 classifier metric 64.9% vs ≥90% target** — dominated by the designed-in
  low confidence of the T3/T4 prior split; needs capacity-mix evidence
  (EPB register, MCS) to close.
- **Opening-stock assumptions are guesses with wide bands** — the +52% EHS
  residual most likely implicates them; sensitivity work pending.
- **NI share (GB = UK × 0.975) is a named assumption** pending an RTS-based
  estimate.
- **Mirror check breaches ±15% everywhere** — consignment-vs-origin
  asymmetry; VG2 needs an origin-aware tolerance or EU-hub adjustment.
- **EPB register covers England & Wales only**; Scotland's separate register
  is not yet ingested. EHS is England-only, scaled to GB by relative cooling
  degree days (named assumption).
- **HS 2027 revision will change CN codes** — a concordance table is required
  before the 2027 data year.

## Roadmap & cadence

Remaining build: D4 MCS + D6 CDD regression ingestion; FR4.2 prior-update
step (fit allocation priors against anchors); D7 retail basket; Phase 3 gate
tooling + freeze v2026; Phase 4 scheduling/monitoring.

Once operational: **monthly** OTS + mirror + retail basket; **quarterly**
EPB delta, MCS, CDD refresh; **annually** EHS anchor, reconciliation,
validation gate (VG1–VG7, ≤1 day, manual), freeze vintage.
