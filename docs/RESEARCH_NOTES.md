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
- Systems >12 kW output require 5-yearly air conditioning inspection reports,
  lodged on the non-domestic EPC register; bulk-downloadable via
  opendatacommunities.org (API with free registration). Compliance imperfect
  (~one-third by common estimates) — gross-up factor must be published.

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
- 84159000: parts (excluded; supplementary-unit measure was ended for the
  parts code per trade-tariff.service.gov.uk stop-press notices — machines
  retain item-count units)
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
