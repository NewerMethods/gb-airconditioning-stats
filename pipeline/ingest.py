"""D1 ingestion: HMRC uktradeinfo OTS pulls, stored as immutable vintages.

Raw pulls are keyed by (source, pull_date) under data/raw/ and never
overwritten. Phase 1 pulls the full window (month_start -> latest published)
for every code in config/cn_codes.yaml.
"""

import time
from datetime import date

import pandas as pd
import requests

from .config import DATA_DIR, load

BASE = "https://api.uktradeinfo.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ac-pipeline-phase1/0.1)"}

EXPECTED_FIELDS = {"MonthId", "FlowTypeId", "SuppressionIndex", "Value", "NetMass", "SuppUnit"}


def _get(url: str) -> requests.Response:
    # The API's WAF intermittently answers 403 "Ip Forbidden"; blocks clear
    # within seconds, so back off and retry.
    for attempt in range(5):
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code in (403, 429, 500, 502, 503) and attempt < 4:
            time.sleep(2 ** (attempt + 2))
            continue
        break
    r.raise_for_status()
    return r


def fetch_ots(commodity_id: int, month_start: int) -> pd.DataFrame:
    url = f"{BASE}/OTS?$filter=CommodityId eq {commodity_id} and MonthId ge {month_start}"
    rows = []
    while url:
        payload = _get(url).json()
        batch = payload.get("value", [])
        if batch:
            missing = EXPECTED_FIELDS - set(batch[0])
            if missing:
                raise RuntimeError(
                    f"OTS schema mismatch for {commodity_id}: missing {sorted(missing)}"
                )
        rows.extend(batch)
        url = payload.get("@odata.nextLink")
        time.sleep(1.1)  # 60 req/min limit
    return pd.DataFrame(rows)


def vintage_dir(pull_date: str | None = None):
    d = DATA_DIR / "raw" / "uktradeinfo_ots" / (pull_date or date.today().isoformat())
    d.mkdir(parents=True, exist_ok=True)
    return d


def pull_all(pull_date: str | None = None) -> dict[str, pd.DataFrame]:
    """Pull (or load, if already stored under this pull_date) every code."""
    codes_cfg = load("cn_codes")
    month_start = codes_cfg["window"]["month_start"]
    vdir = vintage_dir(pull_date)
    out = {}
    for code in codes_cfg["codes"]:
        pq = vdir / f"full_ots_{code}.parquet"
        if pq.exists():
            print(f"  {code}: loading stored vintage")
            out[code] = pd.read_parquet(pq)
        else:
            print(f"  {code}: fetching from OTS")
            df = fetch_ots(int(code), month_start)
            df.to_parquet(pq)
            out[code] = df
    return out


def fetch_countries(pull_date: str | None = None) -> pd.DataFrame:
    """Country dimension (needed to identify partner countries, e.g. China)."""
    vdir = vintage_dir(pull_date)
    pq = vdir / "country.parquet"
    if pq.exists():
        return pd.read_parquet(pq)
    payload = _get(f"{BASE}/Country").json()
    df = pd.DataFrame(payload["value"])
    df.to_parquet(pq)
    return df
