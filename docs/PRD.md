# PRD — GB Air Conditioning Market Data Pipeline ("Coolstock")

**Owner:** Insights Manager (Jono) · **Status:** Draft v0.1 · **Date:** August 2026
**Purpose:** An automated, repeatable pipeline producing an annually versioned baseline of AC sales and installed stock in Great Britain, segmented by equipment type and use case, from public/API-accessible data, with a structured manual validation gate before each vintage is frozen.

---

## 1. Background & problem statement

No trustworthy public statistics exist for GB air conditioning sales or installs. Commercial market reports disagree materially with each other (2025 market-size estimates range $1.33bn–$1.85bn with CAGRs from 1% to 6%+) and are opaque about method. The only firm public anchors are:

- **English Housing Survey (EHS) 2023–24** (reanalysed by EDRC/Reading, 2026): 4.3% of English households use AC (~1.06m homes), with segmentation by dwelling, income, region — but conflating portable and fixed systems.
- **NESO estimate**: ~3% of UK homes, ~0.3 TWh/yr, with FES pathway adoption of 10–40% by 2050.
- **TM44 air conditioning inspection reports** on the non-domestic EPC register (systems >12kW, 5-yearly inspection, bulk-downloadable) — a genuine registry of commercial fixed systems, with imperfect compliance.
- **HMRC Overseas Trade Statistics**: monthly unit-level import/export data at CN8 level. GB manufactures essentially no room AC, so apparent consumption ≈ imports − exports.

The forecasting exercise (feeding the GB AC outlook model) repeats annually and needs a defensible, reproducible baseline with explicit uncertainty, not a one-off number.

## 2. Objectives & success criteria

**Objectives**

1. Produce an annual **baseline vintage**: units sold (flow) and installed stock, GB, by type × use case, with uncertainty bands, for the most recent complete calendar year.
2. Fully automated data acquisition at monthly/quarterly cadence; zero manual data entry before the validation gate.
3. Every published number traceable to source records (provenance tags) and reproducible from stored raw vintages.
4. A bounded manual validation gate (≤1 day/year) that can incorporate non-public checks (BSRIA figures, installer/distributor/NESO conversations) without contaminating the automated layer.

**Success criteria**

- S1: Year-2 refresh runs end-to-end with <2 hours of intervention before the gate.
- S2: Stock-flow reconciliation closes within the EHS confidence interval (or the residual is explained and published).
- S3: Type segmentation assigns ≥90% of imported units to a type with high confidence (classifier confidence score).
- S4: Independent demand-side stock estimate (CDD regression) falls within the published stock uncertainty band.
- S5: All source revisions (HMRC restatements) are absorbed without breaking historical vintages.

## 3. Segmentation taxonomy

### 3.1 Equipment types (T1–T7)

| ID | Type | Definition | Primary signal |
|----|------|-----------|----------------|
| T1 | Portable monobloc | Single-unit plug-in, exhaust hose, movable | CN 841581/82 + value/mass classifier; retail basket |
| T2 | Window / wall self-contained | Fixed self-contained (rare in GB) | CN 84151010 |
| T3 | Single split | One outdoor + one indoor unit, typically ≤7 kW | CN 84151090 + capacity/value classifier |
| T4 | Multi-split | One outdoor + 2–5 indoor units | CN 84151090 (shared with T3; allocation via priors + installer evidence) |
| T5 | VRF/VRV | Modular commercial refrigerant-flow systems | CN 84151090 high-value tail + TM44 |
| T6 | Packaged / rooftop | Self-contained commercial units | CN 841581/82 high-value/mass cluster |
| T7 | Air-to-air heat pump (reversible, marketed as heating) | Overlaps T3/T4 hardware | CN 841861 + MCS data; tracked to police boundary |

Out of scope: vehicle AC (8415.20), chillers (8418.69), evaporative coolers and fans, portable "air coolers" without refrigeration circuits.

### 3.2 Use cases (U1–U4)

| ID | Use case | Anchor evidence |
|----|----------|-----------------|
| U1 | Domestic | EHS prevalence & growth; retail channel (portables) |
| U2 | Small commercial (<12 kW systems: retail units, hospitality, small offices) | Residual allocation; installer priors; validation-gate evidence |
| U3 | Large commercial (>12 kW: offices, retail chains, hotels, public estate) | TM44 lodgements (capacity, sector via property type) |
| U4 | Industrial / process & data-adjacent | TM44 + explicit exclusions; flagged low-confidence |

### 3.3 Segmentation matrix — who claims each cell

Each (type × use case) cell is assigned exactly one **primary estimator** and ≥1 **cross-check**:

- **T1×U1** (portable domestic): apparent consumption of classified portables; cross-check retail basket velocity + Google Trends. Assume ≥95% of portables are U1; publish the assumption.
- **T3/T4×U1** (domestic splits): EHS fixed-stock growth × replacement model; cross-check MCS A2A + demand regression.
- **T3/T4×U2** (small commercial splits): residual of split imports after U1 and U3 allocation — the highest-uncertainty cell, flagged as such.
- **T5/T6×U3** (VRF/packaged large commercial): TM44 new lodgements grossed up by a compliance factor (estimated, published, and revisited at each gate).
- **T7 boundary**: A2A heat pumps reported separately; a sensitivity toggle includes/excludes them from cooling capacity.

**Design principle:** observable signals segment *type*; *use case* is a modelled allocation with explicit priors, updated annually against anchors, always published with uncertainty. No cell is presented as directly measured when it is allocated.

## 4. Data sources register

| # | Source | Access | Cadence | Fields | Role |
|---|--------|--------|---------|--------|------|
| D1 | HMRC uktradeinfo OTS | OData API, free | Monthly (~2-mo lag) | CN8 code, units, net mass, value, direction, partner country | Core flow signal |
| D2 | UN Comtrade | REST API, free key | Monthly | Mirror China→UK exports, HS6 | Consistency check |
| D3 | Non-domestic EPC / TM44 ACIRs | opendatacommunities bulk + API | Quarterly delta | Lodgement date, kW, property type, postcode | U3 stock & flow |
| D4 | MCS installations dashboard | Public data | Quarterly | A2A heat pump certified installs | T7 boundary |
| D5 | EHS annual release | Bulk download | Annual (~July) | Household AC use, segmentation | U1 stock anchor |
| D6 | Elexon/NESO demand + Met Office HadUK/MIDAS (CEDA) | APIs | Quarterly refresh | Half-hourly demand; daily temperature → CDD | Independent operating-stock estimate |
| D7 | Retail basket (Keepa API on ~30 fixed portable SKUs; pytrends) | Paid API (low cost); free API | Monthly | Sales rank, review velocity, price; search index | Portable dynamics & calibration |
| D8 | *Gate-only (non-public):* BSRIA/Eurovent figures, REFCOM installer & distributor calls, NESO FES cooling assumption | Manual | Annual | Benchmark unit sales by product type | Validation only — never ingested into the automated layer |

## 5. Functional requirements

### FR1 — Ingestion
- FR1.1 Monthly jobs: D1, D2, D7. Quarterly: D3, D4, D6. Annual: D5.
- FR1.2 Every pull stored raw and immutable, keyed by (source, pull-date): trade data revises, so vintages are first-class.
- FR1.3 Failures alert but never block other feeds; each feed independently retryable.
- FR1.4 CN code list is configuration, not code — HS 2027 revision will require remapping with an overlap-year concordance table.

### FR2 — Harmonisation & storage
- FR2.1 Parquet lake: `raw/ → clean/ → harmonised/` with schema contracts per source.
- FR2.2 GB vs UK: OTS is UK-wide; apply NI adjustment from Regional Trade Statistics shares (documented, sensitivity-tested; NI is small for this commodity).
- FR2.3 All series carried monthly internally; published quarterly and annually.

### FR3 — Type classification engine
- FR3.1 Rule layer: CN8 → candidate types (per §3.1).
- FR3.2 Statistical layer: within ambiguous codes, cluster on value-per-unit and mass-per-unit; classify to T1/T6 (in 841581/82) and T3/T4/T5 (within 84151090). Fit thresholds once on a training year; monitor drift.
- FR3.3 Each classified unit-flow carries a confidence score; low-confidence volume reported as "unallocated" rather than forced.

### FR4 — Use-case allocation engine
- FR4.1 Deterministic claims first: TM44-evidenced capacity → U3; portables → U1 (published assumption).
- FR4.2 Remaining split volume allocated U1/U2 by priors, updated annually by minimising disagreement with anchors (EHS stock delta, demand-regression stock, MCS). Simple Bayesian update or constrained least squares — keep it inspectable, not clever.
- FR4.3 Allocation priors, posteriors, and their year-on-year movement are outputs, not internals.

### FR5 — Stock-flow model
- FR5.1 Stock(t) = Stock(t−1) + Sales(t) − Retirements(t), per type × use case.
- FR5.2 Survival curves: T1 ~8–10 yr, T3/T4 ~12–15 yr, T5/T6 ~15–20 yr (Weibull; parameters configurable, revisited at gate).
- FR5.3 Reconciliation residual vs EHS anchor computed and published — the residual is a finding (exports leakage, misclassification, dormant portables), not an error to hide.

### FR6 — Validation gate (manual, annual)
Checklist executed before a vintage is frozen; each item pass/fail/flag with notes stored alongside the vintage:
- VG1 Unit-value and unit-mass drift per CN code (misclassification detector).
- VG2 HMRC vs Comtrade mirror asymmetry within tolerance (default ±15%).
- VG3 Stock-flow closure vs EHS interval (S2).
- VG4 Demand-regression stock vs published band (S4).
- VG5 External benchmark: BSRIA/Eurovent published or purchased figures.
- VG6 Three structured calls (script provided): REFCOM installer, distributor (e.g. Hughes), NESO FES contact.
- VG7 Sign-off freezes vintage `vYYYY`; downstream outlook model reads only frozen vintages.

### FR7 — Outputs
- FR7.1 Annual baseline vintage: CSV/parquet tables (flow & stock, type × use case × year, central + P10/P90) + methodology note auto-generated from config.
- FR7.2 Quarterly monitoring pack: trade flows, retail index, TM44 lodgement rate, demand-sensitivity coefficient.
- FR7.3 Optional React dashboard (TEC Register pattern): flows, stock, allocation, residuals, validation status.

## 6. Non-functional requirements

- **N1 Reproducibility:** any published number regenerable from raw vintages + config at a git tag.
- **N2 Provenance:** every output cell tagged with estimator, sources, confidence.
- **N3 Runtime:** full refresh <30 min on a laptop; no infrastructure dependency beyond scheduled runners (GitHub Actions/cron).
- **N4 Cost:** target <£300/yr automated (Keepa is the only paid feed); BSRIA licence optional, gate-only.
- **N5 Compliance:** APIs and bulk downloads only; no ToS-violating scraping. Keepa replaces direct Amazon scraping deliberately.

## 7. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| HS 2027 code revision breaks continuity | Certain (2027) | High | Concordance table + overlap-year dual mapping (FR1.4) |
| Low-value consignment (de minimis) e-commerce imports under-captured in OTS | Medium | Medium (portables) | Retail basket cross-check; treat portable floor as lower bound |
| TM44 compliance rate unknown/unstable | High | Medium (U3) | Publish gross-up factor; test vs BSRIA at gate |
| T3/T4 vs U1/U2 allocation wrong | High | Medium | Flag as modelled; widest bands; installer evidence at gate |
| Keepa basket SKU churn | Medium | Low | Annual basket refresh procedure; index chained across baskets |
| HMRC revisions restate history | Certain | Low | Vintage storage (FR1.2); publish revision log |
| Reversible A2A units drift between 8415 and 8418 classification | Medium | Medium | T7 tracked explicitly; sensitivity toggle (§3.3) |

## 8. Outline delivery plan

**Phase 0 — Spike (1 week):** Register for uktradeinfo/Comtrade/opendatacommunities/CEDA access; pull 5 years of D1 for the six CN codes; confirm units fields are populated (they are patchy for some codes — this is the go/no-go check); eyeball value/mass clustering separability.

**Phase 1 — Core trade pipeline (2–3 weeks):** FR1–FR3 for D1/D2. Deliverable: monthly apparent-consumption series by type, 2019–present, with classifier confidence. This alone beats every public source.

**Phase 2 — Anchors & allocation (2–3 weeks):** D3–D6 ingestion; use-case allocation engine (FR4); stock-flow model (FR5). Deliverable: draft baseline table, type × use case, with bands.

**Phase 3 — Gate & first vintage (1–2 weeks):** Validation checklist tooling, call scripts, methodology note generator; run first full gate; freeze **v2026** covering calendar 2025. Deliverable: baseline vintage feeding the outlook model.

**Phase 4 — Operationalise (1 week + ongoing):** Scheduled runners, alerting, quarterly monitoring pack, optional dashboard; handover doc so a team member can run year 2.

Total: ~7–10 weeks part-time effort; annual rerun thereafter targeted at <1 day plus the gate.

## 9. Open questions

1. Are unit quantities (supplementary units) consistently populated for all six CN codes in OTS? (Phase 0 go/no-go; fallback is net-mass ÷ typical unit mass.)
2. Buy BSRIA for the gate in year 1, or rely on press-released figures until the pipeline proves itself?
3. Should chillers (8418.69) enter scope for U3/U4 completeness, or stay excluded to keep the boundary clean?
4. Publish internally only, or is a sanitised public version (e.g. via Hardflux) worthwhile once two vintages exist?
5. Scotland/Wales segmentation: EHS is England-only — accept England-scaled GB domestic figures, or add Scottish House Condition Survey as a second anchor?
