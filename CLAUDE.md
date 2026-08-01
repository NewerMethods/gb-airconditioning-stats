# CLAUDE.md — GB AC Outlook Data Pipeline ("Coolstock")

## What this project is

An automated pipeline producing an annually versioned baseline of air conditioning
sales (flow) and installed stock in Great Britain, segmented by equipment type
(T1–T7) and use case (U1–U4), built from public/API data with a manual annual
validation gate. It feeds a separate GB AC outlook/forecasting model, rerun yearly.

Full spec: `docs/PRD.md` (authoritative). Decisions log: `docs/DECISIONS.md`.
Verified source findings: `docs/RESEARCH_NOTES.md`.

## Why it exists

No trustworthy public GB AC statistics exist; commercial market reports contradict
each other. GB manufactures essentially no room AC, so HMRC trade data (apparent
consumption = imports − exports) is the core measurable signal, triangulated
against EHS (domestic stock anchor), TM44 lodgements (commercial), MCS (A2A heat
pumps), demand-vs-CDD regression (operating stock), and a retail basket (portables).

## Current status (as of Aug 2026)

- [x] PRD v0.1 drafted (`docs/PRD.md`)
- [x] Phase 0 script written (`scripts/phase0_check.py`) — **NOT YET RUN**
- [ ] **NEXT ACTION: run Phase 0** — pulls 2019–2025 OTS data for six CN8 codes,
      checks supplementary-unit population rates. Go criterion: ≥90% value
      coverage on 84151010/84151090/84158100/84158200. This is the go/no-go
      for the whole trade-data approach.
- [ ] Phase 1: core trade pipeline (ingestion → classification → apparent consumption)
- [ ] Phase 2: anchors + use-case allocation engine + stock-flow model
- [ ] Phase 3: validation gate tooling + freeze first vintage (v2026, covering CY2025)
- [ ] Phase 4: scheduling, monitoring pack, optional dashboard

## Key facts verified so far (do not re-derive; see RESEARCH_NOTES.md for sources)

- HMRC uktradeinfo API: open access, NO auth/key, OData, JSON or CSV
  ($format=csv), 40,000-row pagination via @odata.nextLink, 60 requests/min
  rate limit. Base: https://api.uktradeinfo.com — endpoints /OTS, /RTS,
  /Commodity, /Country, /FlowType. Swagger: /swagger/ui/index
- FlowTypeId: 1=EU imports, 2=EU exports, 3=non-EU imports, 4=non-EU exports
- Quantity fields (NetMass kg + SuppUnit item counts) are published except under
  suppression (SuppressionIndex 1/3/5 hide quantity). Parts code 84159000 has no
  supplementary unit; machine codes carry item counts.
- The API rejects some sandboxed/bot fetchers — always send a browser-like
  User-Agent header from scripts.
- EHS 2023–24 (EDRC/Reading reanalysis, June 2026): 4.3% of English households
  use AC (~1.06m homes); conflates portable and fixed. NESO: ~3% UK homes,
  ~0.3 TWh/yr; FES pathways 10–40% adoption by 2050.
- HS 2027 WCO revision WILL change CN codes — concordance table required (FR1.4).

## CN codes in scope (config/cn_codes.yaml is the single source of truth)

| CN8 | Maps to |
|-----|---------|
| 84151010 | Self-contained fixed (T2, some T6) |
| 84151090 | Splits — single/multi/VRF (T3/T4/T5; classifier splits by unit value) |
| 84158100 | Other reversible — portables + packaged mix (T1/T6; classifier) |
| 84158200 | Other cooling-only — portables + packaged mix (T1/T6; classifier) |
| 84158300 | Other, no refrigeration unit (edge; monitor) |
| 84186100 | Heat pumps excl. 8415 — T7 boundary policing only |

Type is classified from CN code + value-per-unit + mass-per-unit clustering.
Use case (domestic/small commercial/large commercial/industrial) is NEVER
directly observed — it is a modelled allocation with published priors and
uncertainty (PRD §3.3, FR4). Do not present allocated cells as measured.

## Conventions & hard rules

- **Vintages are immutable.** Every raw API pull is stored keyed by
  (source, pull_date) under `data/raw/`. HMRC revises history; never overwrite.
  Frozen annual baselines live in `vintages/vYYYY/` and are read-only after gate
  sign-off.
- **Config over code.** CN codes, survival-curve parameters, allocation priors,
  and validation tolerances all live in `config/`, never hardcoded.
- **Publish the residual.** Stock-flow reconciliation gaps are findings, not
  errors to smooth away. Every output cell carries estimator + confidence tags.
- **APIs and bulk downloads only.** No ToS-violating scraping. Keepa API is the
  deliberate substitute for Amazon scraping.
- **Rate limits:** uktradeinfo 60/min (sleep ≥1.1s between paginated calls).
- Python + pandas + parquet; runnable end-to-end on a laptop in <30 min;
  scheduling via GitHub Actions/cron. No heavy infrastructure.
- Style: match the owner's existing pipeline conventions (NESO TEC Register
  project): iterative cleaning with logged corrections, optional React
  dashboard on top.

## Cadence (once operational)

- Monthly: OTS pull (D1), Comtrade mirror (D2), retail basket (D7)
- Quarterly: TM44 delta (D3), MCS (D4), demand/CDD regression refresh (D6)
- Annual: EHS anchor (D5), stock-flow reconciliation, validation gate, freeze vintage

## Validation gate (annual, manual, ≤1 day)

Checklist VG1–VG7 in PRD §FR6. Gate-only external evidence (BSRIA figures,
installer/distributor/NESO calls) must never be ingested into the automated
layer — it validates, it does not feed.

## Open items

- Q1 (unit population rates): OPEN until phase0_check.py is run. Verify field
  casing (SuppUnit/NetMass/SuppressionIndex) against Swagger on first call.
- BSRIA purchase: agreed for year 1 (calibration), skip years 2–3. Check FERF /
  NESO-contact access before buying.
- Chillers (84186900): value-index satellite series only; excluded from unit counts.
- Scotland/Wales: scale England EHS anchor to GB by relative cooling degree days
  (not population); named assumption with sensitivity range.
- Publication (Hardflux): after two frozen vintages, methods-first.
