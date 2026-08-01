# Research Notes — verified findings and sources (Aug 2026)

## Firm public anchors

### English Housing Survey / EDRC (domestic stock)
- EHS 2023–24 (n=15,846), reanalysed by University of Reading / Energy Demand
  Research Centre, published 25 June 2026: **4.3% of English households use AC
  (~1.06m homes)**. Segmentation: detached 6.2%, over-75 households 3.0%,
  skewed to London/East, higher incomes, newer builds, frequent home-workers.
- Caveat (explicit in survey): "uses an air conditioner" does NOT imply a fixed
  installation — portables included. Treat as combined-stock anchor.
- A related EHS overheating stat: of ~3m households reporting overheating, only
  7% used an air conditioner (90% opened windows, 59% fans).
- Sources: reading.ac.uk/news (25 Jun 2026); edrc.ac.uk/publications/
  socio-technical-drivers-of-air-conditioning-adoption-and-use-in-uk-homes

### NESO
- ~3% of UK homes use AC, ~0.3 TWh/yr electricity; FES pathways put 2050
  household adoption at 10–40%. (Cited in the EDRC publication above.)

### TM44 / non-domestic EPC register (commercial stock)
- Systems >12 kW output require 5-yearly air conditioning inspection reports
  (ACIRs), lodged on the EPB register. Compliance imperfect (~one-third by
  common estimates) — gross-up factor must be published.
- **CORRECTIONS (verified 1 Aug 2026).** Two earlier beliefs are stale:
  1. epc.opendatacommunities.org (email + API key) is GONE — replaced by
     get-energy-performance-data.communities.gov.uk (MHCLG, beta). Auth is
     now a bearer token from a **GOV.UK One Login** account ("My account"
     page) — creating it is a human step (email verification + 2FA), it
     cannot be scripted.
  2. ACIRs/TM44 reports are NOT in the published data (not in the API
     datasets, not in the EPB live tables, not in the quarterly statistical
     release). The usable commercial-AC evidence is instead IN the
     certificate records themselves: non-domestic EPC and DEC records both
     carry AIRCON_PRESENT, AIRCON_KW_RATING, ESTIMATED_AIRCON_KW_RATING and
     AC_INSPECTION_COMMISSIONED (1=inspection done, 2=commissioned, 3=none,
     4=n/a, 5=unknown) — presence + capacity + a compliance signal.
- New API (base https://api.get-energy-performance-data.communities.gov.uk,
  headers `Authorization: Bearer <token>` + `Accept: application/json`):
  - GET /api/files/{non-domestic|display|domestic}/csv → 302 to signed S3
    zip of full data (non-domestic ≈2.9 GB, regenerated 1st of month);
    /info sub-path gives size + lastUpdated. requests must follow the
    redirect WITHOUT the bearer header (signed URL carries its own auth).
  - GET /api/{non-domestic|display|domestic}/search — geographic/time
    filters, 5,000 rows/page; plus a certificates-changed delta endpoint
    (right tool for the quarterly D3 refresh).
  - Data dictionaries download without auth: /download/data-dictionary?
    property_type=non-domestic|display|domestic.
  - England & Wales only; Scotland has a separate register
    (scottishepcregister.org.uk) — GB coverage needs both.
- Pipeline: `pipeline/tm44.py` + `scripts/run_tm44.py` ingest full loads as
  immutable vintages under data/raw/epb/<pull_date>/ and reduce to per-year
  AC evidence (data/outputs/tm44_ac_evidence.csv). Blocked only on the
  human token step.

### Market reports (for context only — DO NOT use as data)
- 2025 UK AC market size estimates range $1.33bn (OMR, 1.0% CAGR) to $1.85bn
  (Report Cubes, 6.13% CAGR) — mutually inconsistent; the motivation for this
  pipeline.

## HMRC uktradeinfo API (verified from official docs, Aug 2026)

- Docs: https://www.uktradeinfo.com/api-documentation
- Base: https://api.uktradeinfo.com ; endpoints /OTS, /RTS, /Commodity,
  /Country, /FlowType, /Port, /SITC, /Trader, /Import, /Export, /Trade
- Open access, no auth header, OData ($filter/$select/$expand/$apply/$top/
  $count/$format), JSON default, CSV via $format=csv (complex queries may 500
  in CSV)
- Pagination: 40,000-row limit, @odata.nextLink for next page; $skip for manual
  paging. Rate limit 60 requests/minute.
- FlowTypeId (OTS): 1 EU imports, 2 EU exports, 3 non-EU imports, 4 non-EU
  exports. (RTS: 1 all imports, 2 all exports.)
- SuppressionIndex 1–5; levels 3 and 5 suppress quantity while publishing
  value → quantity fields exist and are populated outside suppression.
- **Phase 0 result (run 1 Aug 2026, 2019–2025 pull): SuppUnit is 0.0 on every
  OTS row for all six target codes (84151010/84151090/84158100/84158200/
  84158300/84186100) — 0% value coverage, GO criterion FAILED.** This is
  structural, not suppression or field-casing: the UK Integrated Tariff
  assigns no supplementary-unit measure to any 8415/841861 leaf code
  (verified via trade-tariff.service.gov.uk API; positive control 8703211000
  cars carries a "Supplementary unit" measure and shows real SuppUnit counts
  in OTS). Item counts are never declared at import for AC machines.
- Phase 0 fallback check: NetMass populated for 100% of import value on all
  six codes, suppression rate 0.0. Median value-per-kg (imports): 84151010
  £18.1, 84151090 £12.8, 84158100 £21.1, 84158200 £23.7, 84158300 £17.7,
  84186100 £18.2; wide p10–p90 spreads on 841581/82 (up to ~£930/kg — likely
  civil-aircraft units in the tail) support value-per-kg classifier
  separation but require outlier handling.
- Field casing confirmed against live API: MonthId, FlowTypeId,
  SuppressionIndex, CommodityId, Value, NetMass, SuppUnit.
- Unit-count recovery routes tested 1 Aug 2026 — see "Mirror unit-count
  check" section below. Summary: COMEXT cannot recover counts (EU CN has no
  supplementary unit for 8415 either — the earlier p/st assumption was
  wrong); Comtrade partially can, and is the source for kg/unit priors.

## Mirror unit-count check (verified 1 Aug 2026)

### Eurostat COMEXT — NO
- Dataset DS-045409 (API: ec.europa.eu/eurostat/api/comext/dissemination/
  statistics/1.0/data/DS-045409; dims freq/reporter/partner/product/flow/
  indicators/TIME_PERIOD; indicators VALUE_IN_EUROS, QUANTITY_IN_100KG,
  SUPPLEMENTARY_QUANTITY).
- SUPPLEMENTARY_QUANTITY is absent for every 8415 CN8 code and 84186100
  across 8 reporters (IT/CZ/NL/DE/ES/BE/SE/PL, exports to GB, 2024).
  Positive controls populated: cars 87032110 (18,501 u), 87032319 (50,715 u),
  fridges 84181020 (2,712 u) DE→GB 2024. The EU CN, like the UK tariff,
  assigns no supplementary unit to 8415/841861.

### UN Comtrade partner mirror — PARTIAL (calibration, not direct counts)
- Public preview endpoint works without a key for annual single-cell queries:
  comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=&period=&
  partnerCode=&cmdCode=&flowCode= (filter rows to motCode=0, customsCode=C00,
  partner2Code=0 to avoid double counting). Full API needs a free key. HS6
  only — coarser than CN8.
- Partners reporting GENUINE item counts on exports to UK (qtyUnitCode 5,
  isQtyEstimated=false): China, Malaysia, Japan, Türkiye, USA.
  NOT reporting quantity: Thailand, Korea, Vietnam, and all EU27.
- Share of UK-reported 2024 import value from unit-reporting partners:
  841510 28% (Thailand+Korea are 50%), 841581 33% (EU 61%), 841582 71%
  (USA-heavy), 841583 43%, 841861 23% (EU 71%). Too patchy to sum into
  apparent consumption directly.
- Consignment vs origin asymmetry is fatal for direct use: UK records
  $27.7m of Japanese-ORIGIN 841510 imports (2024) while Japan records ~$0
  dispatched to UK — Japanese goods arrive via EU hubs. Mirror measures
  direct dispatch, HMRC measures origin.
- UK's own Comtrade import rows carry UN-ESTIMATED quantities only (fixed
  netWgt conversion, 23.75 kg/unit for 841510) — modelled, not independent.
- PRIMARY VALUE — kg/unit calibration priors for the net-mass fallback
  (all isQtyEstimated=false, 2024):
  | HS6 | China→UK kg/u | China→World kg/u | China→World $/u |
  |-----|--------------|------------------|-----------------|
  | 841510 | 29.3 | 37.4 | 190 |
  | 841581 | 30.5 | 63.4 | 461 |
  | 841582 | 24.1 | 30.0 | 181 |
  | 841583 | 5.6 | 15.3 | 121 |
  | 841861 | 98.4 | 79.5 | 798 |
  UK-vs-World gaps show ratios are mix-dependent → prefer partner-route-
  specific ratios, blend with spec-sheet priors, and re-pull annually.
  Malaysia/Japan/Türkiye/USA ratios also available per code for
  route-specific priors (e.g. Malaysia 841510 27.1 kg/u; USA skews heavy:
  91.6 kg/u 841510, 86.3 kg/u 841582 — packaged/rooftop mix).
- Swagger (field names/schemas): https://api.uktradeinfo.com/swagger/ui/index
- OTS monthly, ~2-month lag, revisions restate history → store every pull.
- **Environment note:** the API bot-blocks some automated fetchers; send a
  browser-like User-Agent. Documented for curl/Postman; maintained R package
  exists (github.com/pvdmeulen/uktrade) with working query examples.

## CN codes (UK Integrated Tariff / uktradeinfo commodity pages)

- 841510: "designed to be fixed to a window, wall, ceiling or floor,
  self-contained or split-system" → 84151010 self-contained, 84151090 split
- 841581/82/83: other AC (reversible / cooling-only / no refrigeration unit) —
  contains portables AND packaged/rooftop units → classifier needed
- 84159000: parts (excluded). CORRECTION (Phase 0, Aug 2026): the earlier
  belief that machine codes retain item-count units is wrong for the UK
  tariff — no 8415 leaf code carries a supplementary-unit measure, and HMRC
  OTS SuppUnit is zero throughout 2019–2025 (see HMRC section above).
- 84186100: heat pumps excl. 8415 (T7 boundary); 84186900: chillers etc.
  (satellite series only)
- Advance tariff rulings (tax.service.gov.uk) confirm e.g. reversible
  self-contained commercial packaged units land in 84151010.
- HS 2027 WCO revision will restructure codes — build concordance before then.

## Other feeds

- UN Comtrade: free keyed REST API; China→UK mirror at HS6 (841510 etc.);
  divergence tolerance ±15% default (VG2).
- MCS: public installation data, quarterly; A2A heat pumps partially covered.
- Demand/CDD: Elexon Insights + NESO APIs for demand; Met Office HadUK/MIDAS
  via CEDA for temperature.
- Keepa API: Amazon sales-rank/review history for the portable SKU basket.
- OEM landscape: portables overwhelmingly Midea/Gree/Haier OEM regardless of
  brand; splits led by Daikin, Mitsubishi Electric, Toshiba, LG, Samsung,
  Panasonic, Fujitsu; UK distribution e.g. Hughes Group. BSRIA (Bracknell) and
  Eurovent Market Intelligence are the manufacturer-submission benchmarks
  (paid, gate-only).
