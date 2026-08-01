"""
Phase 0 go/no-go check — GB AC pipeline (PRD §8, Open Question 1)

Pulls HMRC uktradeinfo OTS data for the six target CN8 codes, 2019-2025,
and reports per code:
  - supplementary-unit (item count) population rate
  - suppression incidence
  - unit-value and unit-mass distributions (classifier separability preview)

Go criteria: SuppUnit populated for >=90% of trade value on 84151010,
84151090, 84158100, 84158200. Net-mass fallback viability reported otherwise.

Requires: pip install requests pandas
Rate limit: 60 req/min (script stays well under).
"""

import time
from datetime import date
from pathlib import Path

import requests
import pandas as pd

BASE = "https://api.uktradeinfo.com/OTS"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ac-pipeline-phase0/0.1)"}

# Raw pulls are keyed by (source, pull_date) — CLAUDE.md hard rule.
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "uktradeinfo_ots" / date.today().isoformat()

# Open Question 1: field casing must match the live schema, else coverage
# silently reads as 0%. Checked against the first payload; fail loudly.
EXPECTED_FIELDS = {"MonthId", "FlowTypeId", "SuppressionIndex", "Value", "NetMass", "SuppUnit"}

CODES = {
    84151010: "Self-contained fixed (T2/T6 candidate)",
    84151090: "Split systems (T3/T4/T5)",
    84158100: "Other, reversible (T1/T6 mix)",
    84158200: "Other, cooling only (T1/T6 mix)",
    84158300: "Other, no refrigeration unit",
    84186100: "Heat pumps excl. 8415 (T7 boundary)",
}

MONTH_START, MONTH_END = 201901, 202512


def fetch_code(commodity_id: int) -> pd.DataFrame:
    """Pull all OTS rows for one CN8 code across the window, paginating."""
    url = (
        f"{BASE}?$filter=CommodityId eq {commodity_id} "
        f"and MonthId ge {MONTH_START} and MonthId le {MONTH_END}"
    )
    rows = []
    while url:
        # The API's WAF intermittently answers 403 "Ip Forbidden" mid-run;
        # blocks clear within seconds, so back off and retry.
        for attempt in range(5):
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code in (403, 429, 500, 502, 503) and attempt < 4:
                time.sleep(2 ** (attempt + 2))
                continue
            break
        r.raise_for_status()
        payload = r.json()
        batch = payload.get("value", [])
        if batch:
            missing = EXPECTED_FIELDS - set(batch[0])
            if missing:
                raise RuntimeError(
                    f"OTS schema mismatch for {commodity_id}: missing fields {sorted(missing)} "
                    f"(got {sorted(batch[0])}) — check casing against /swagger/ui/index"
                )
        rows.extend(batch)
        url = payload.get("@odata.nextLink")
        time.sleep(1.1)  # stay under 60/min with headroom
    df = pd.DataFrame(rows)
    df["CommodityId"] = commodity_id
    return df


def summarise(df: pd.DataFrame, label: str) -> dict:
    imports = df[df["FlowTypeId"].isin([1, 3])].copy()
    n = len(imports)
    if n == 0:
        return {"code": label, "rows": 0}

    # Field names per API schema: Value (GBP), NetMass (kg), SuppUnit (items)
    su = pd.to_numeric(imports.get("SuppUnit"), errors="coerce")
    nm = pd.to_numeric(imports.get("NetMass"), errors="coerce")
    val = pd.to_numeric(imports.get("Value"), errors="coerce")

    populated = su.notna() & (su > 0)
    value_covered = val[populated].sum() / val.sum() if val.sum() else float("nan")

    unit_value = (val[populated] / su[populated]).replace([float("inf")], pd.NA)
    unit_mass = (nm[populated] / su[populated]).replace([float("inf")], pd.NA)

    suppressed = (
        imports["SuppressionIndex"].isin([1, 3, 5]).mean()
        if "SuppressionIndex" in imports
        else float("nan")
    )

    # Net-mass fallback viability: if item counts are absent, units must be
    # derived as NetMass / assumed-unit-mass and the classifier must separate
    # on value-per-kg instead of value-per-unit.
    nm_populated = nm.notna() & (nm > 0)
    nm_value_covered = val[nm_populated].sum() / val.sum() if val.sum() else float("nan")
    value_per_kg = (val[nm_populated] / nm[nm_populated]).replace([float("inf")], pd.NA)

    return {
        "code": label,
        "rows": n,
        "supp_unit_row_rate": round(populated.mean(), 3),
        "supp_unit_value_coverage": round(value_covered, 3),
        "net_mass_value_coverage": round(nm_value_covered, 3),
        "suppression_rate": round(suppressed, 3),
        "median_unit_value_gbp": round(unit_value.median(), 0),
        "p10_p90_unit_value": (
            round(unit_value.quantile(0.1), 0),
            round(unit_value.quantile(0.9), 0),
        ),
        "median_unit_mass_kg": round(unit_mass.median(), 1),
        "median_value_per_kg": round(value_per_kg.median(), 1),
        "p10_p90_value_per_kg": (
            round(value_per_kg.quantile(0.1), 1),
            round(value_per_kg.quantile(0.9), 1),
        ),
        "annual_import_units_latest": int(
            su[populated][imports["MonthId"] >= 202501].sum()
        ),
    }


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for code, desc in CODES.items():
        pq = RAW_DIR / f"raw_ots_{code}.parquet"
        if pq.exists():  # today's pull already stored — vintages are immutable
            print(f"Loading {code} — {desc} (already pulled today) ...")
            df = pd.read_parquet(pq)
        else:
            print(f"Fetching {code} — {desc} ...")
            df = fetch_code(code)
            df.to_parquet(pq)  # first vintage, keep it
        results.append(summarise(df, f"{code}"))

    out = pd.DataFrame(results)
    print("\n=== PHASE 0 GO/NO-GO SUMMARY ===")
    print(out.to_string(index=False))

    core = out[out["code"].isin(["84151010", "84151090", "84158100", "84158200"])]
    go = (core["supp_unit_value_coverage"] >= 0.9).all()
    print(f"\nGO criterion (>=90% value coverage on core codes): {'PASS' if go else 'FAIL — assess net-mass fallback'}")


if __name__ == "__main__":
    main()
