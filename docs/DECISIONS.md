# Decisions Log

Format: ID | date | decision | rationale | status

## D-001 · 2026-08 · Trade data is the core flow signal
Apparent consumption (imports − exports) from HMRC OTS at CN8 level, 12-month
rolling. Rationale: GB has ~no domestic room-AC manufacture; commercial market
reports contradict each other; OTS is monthly, free, and unit-level.
**Status: adopted.**

## D-002 · 2026-08 · Type observed, use case modelled
Equipment type (T1–T7) is classified from CN codes + value/mass-per-unit
clustering. Use case (U1–U4) is a modelled allocation against anchors (EHS,
TM44, MCS, demand regression) with published priors and uncertainty bands.
Rationale: no feed observes end use; pretending otherwise would be false
precision. **Status: adopted (PRD §3.3).**

## D-003 · 2026-08 · Keepa API instead of retail scraping
Fixed ~30-SKU portable basket via Keepa (sales rank + review velocity), plus
pytrends as free redundancy. Rationale: direct Amazon/retailer scraping is
brittle and ToS-problematic; Keepa is cheap, stable, API-based.
**Status: adopted.**

## D-004 · 2026-08 · BSRIA purchase in year 1 only
Buy for the first validation gate (calibrates T3/T4 U1/U2 allocation priors at
initialisation, where a bad prior propagates); skip years 2–3 if VG1–VG4 run
clean. Check FERF / NESO-contact access before purchasing.
**Status: agreed, purchase pending.**

## D-005 · 2026-08 · Chillers excluded from unit counts
8418.69 tracked as a value-index satellite series only. Rationale: unit
economics incomparable with room/split AC; chiller-served buildings visible via
TM44 anyway; satellite guards against a structural shift to central plant.
**Status: adopted.**

## D-006 · 2026-08 · GB scaling of England-only EHS anchor
Scale by relative cooling degree days, not population (prevalence is
climate-driven; population scaling would overstate Scottish stock). Named
assumption with sensitivity range; revisit if Scottish House Condition Survey
adds a cooling question. **Status: adopted.**

## D-007 · 2026-08 · Publication via Hardflux
After two frozen vintages, methods-first (transparent methodology + published
residuals, not headline numbers). **Status: agreed, deferred.**

## D-008 · 2026-08 · Gate evidence never feeds the automated layer
BSRIA figures, installer/distributor/NESO calls validate only. Keeps the
automated layer reproducible from public data alone. **Status: adopted.**

## OPEN — Q1: supplementary-unit population rates
Go/no-go for the whole approach. Run `scripts/phase0_check.py`; go criterion is
≥90% value coverage of populated SuppUnit on the four core machine codes.
Fallback if fail: net-mass ÷ typical unit mass per type. **Status: OPEN.**
