"""D2 consistency check: HMRC China-origin imports vs China's reported
exports to the UK (Comtrade mirror), per HS6, latest common complete year.

Compared on NET MASS, not value: both sides report kg, which sidesteps
FX conversion and the CIF/FOB wedge. Known caveat (RESEARCH_NOTES): HMRC
records origin, the mirror records direct dispatch, so hub-routed goods
depress the mirror side — divergence beyond tolerance is a flag to
investigate, not an automatic error.

Uses the keyless Comtrade public preview endpoint (annual, single cells).
"""

import time

import pandas as pd
import requests

from .config import DATA_DIR, load
from .ingest import fetch_countries

PREVIEW = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ac-pipeline-phase1/0.1)"}
CHINA_COMTRADE, UK_COMTRADE = 156, 826


def _mirror_netkg(hs6: str, year: int) -> float | None:
    for attempt in range(5):
        try:
            r = requests.get(PREVIEW, params={
                "reporterCode": CHINA_COMTRADE, "period": str(year),
                "partnerCode": UK_COMTRADE, "cmdCode": hs6, "flowCode": "X",
            }, headers=HEADERS, timeout=60)
        except requests.ConnectionError:  # throttling can reset the connection
            if attempt < 4:
                time.sleep(15 * (attempt + 1))
                continue
            raise
        if r.status_code == 429 and attempt < 4:  # keyless preview throttles hard
            time.sleep(15 * (attempt + 1))
            continue
        break
    r.raise_for_status()
    rows = [x for x in (r.json().get("data") or [])
            if x.get("motCode", 0) == 0 and x.get("customsCode") == "C00"
            and x.get("partner2Code", 0) == 0]
    return rows[0]["netWgt"] if rows else None


def mirror_check(clean: pd.DataFrame, pull_date: str | None = None) -> pd.DataFrame:
    tolerance = load("cn_codes")["validation"]["mirror_asymmetry_tolerance"]

    countries = fetch_countries(pull_date)
    china_ids = countries.loc[countries["CountryCodeAlpha"] == "CN", "CountryId"].tolist()

    imp = clean[(clean["direction"] == "import") & clean["CountryId"].isin(china_ids)].copy()
    imp["hs6"] = imp["cn8"].str[:6]
    latest_full_year = int(clean.loc[clean["MonthId"] % 100 == 12, "year"].max())

    results = []
    for hs6 in sorted(imp["hs6"].unique()):
        hmrc_kg = imp.loc[(imp["hs6"] == hs6) & (imp["year"] == latest_full_year),
                          "net_mass_kg"].sum()
        year = latest_full_year
        mirror_kg = _mirror_netkg(hs6, year)
        if mirror_kg is None and year > 2019:  # mirror side may lag a year
            year -= 1
            mirror_kg = _mirror_netkg(hs6, year)
            hmrc_kg = imp.loc[(imp["hs6"] == hs6) & (imp["year"] == year),
                              "net_mass_kg"].sum()
        div = (hmrc_kg - mirror_kg) / mirror_kg if mirror_kg else float("nan")
        results.append({
            "hs6": hs6, "year": year,
            "hmrc_china_origin_kg": round(hmrc_kg),
            "mirror_china_dispatch_kg": round(mirror_kg) if mirror_kg else None,
            "divergence": round(div, 3) if mirror_kg else None,
            "within_tolerance": bool(abs(div) <= tolerance) if mirror_kg else None,
        })
        time.sleep(1.2)

    out = pd.DataFrame(results)
    outdir = DATA_DIR / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(outdir / "mirror_check.csv", index=False)
    return out
