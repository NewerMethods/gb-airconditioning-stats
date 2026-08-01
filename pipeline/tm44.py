"""D3 ingestion: commercial AC evidence from the EPB register
(get-energy-performance-data.communities.gov.uk, MHCLG).

IMPORTANT context (verified 1 Aug 2026, see RESEARCH_NOTES):
- The old epc.opendatacommunities.org email+API-key service is gone; the
  replacement uses a GOV.UK One Login bearer token, which must be created
  by a human (2FA). Token lives on the "My account" page once signed in.
- TM44 air-conditioning inspection reports themselves are NOT published in
  bulk. The usable evidence is richer anyway: every non-domestic EPC and
  DEC record carries AIRCON_PRESENT, AIRCON_KW_RATING,
  ESTIMATED_AIRCON_KW_RATING and AC_INSPECTION_COMMISSIONED.

Token discovery: EPB_BEARER_TOKEN env var, else an `EPB_BEARER_TOKEN=...`
line in a git-ignored .env at the repo root.

Full loads are ~0.3-3 GB zips regenerated monthly; stored as immutable
(source, pull_date) vintages and aggregated in streaming chunks.
"""

import io
import os
import zipfile
from datetime import date

import pandas as pd
import requests

from .config import DATA_DIR, ROOT

BASE = "https://api.get-energy-performance-data.communities.gov.uk"
DATASETS = ("non-domestic", "display")

AC_COLS = ["aircon_present", "aircon_kw_rating", "estimated_aircon_kw_rating",
           "ac_inspection_commissioned"]
KEEP_COLS = AC_COLS + ["lodgement_date", "property_type", "uprn",
                       "building_reference_number"]


class TokenMissing(RuntimeError):
    pass


def _token() -> str:
    tok = os.environ.get("EPB_BEARER_TOKEN")
    if not tok:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith("EPB_BEARER_TOKEN="):
                    tok = line.split("=", 1)[1].strip().strip('"')
    if not tok:
        raise TokenMissing(
            "No EPB bearer token found. To set one up:\n"
            "  1. Go to https://get-energy-performance-data.communities.gov.uk\n"
            "     and sign in / create an account with GOV.UK One Login\n"
            "     (human step - email verification + 2FA, cannot be automated).\n"
            "  2. Copy the bearer token from your 'My account' page.\n"
            "  3. Put EPB_BEARER_TOKEN=<token> in a .env file at the repo root\n"
            "     (git-ignored) or export it as an environment variable."
        )
    return tok


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}", "Accept": "application/json"}


def file_info(dataset: str) -> dict:
    r = requests.get(f"{BASE}/api/files/{dataset}/csv/info", headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.json()["data"]


def download_full_load(dataset: str, pull_date: str | None = None):
    """GET /api/files/<dataset>/csv -> 302 -> signed S3 URL; stream to a vintage."""
    vdir = DATA_DIR / "raw" / "epb" / (pull_date or date.today().isoformat())
    vdir.mkdir(parents=True, exist_ok=True)
    dest = vdir / f"{dataset}-csv.zip"
    if dest.exists():
        print(f"  {dataset}: vintage already stored ({dest})")
        return dest

    info = file_info(dataset)
    print(f"  {dataset}: downloading full load "
          f"({info['fileSize'] / 1e9:.2f} GB, generated {info['lastUpdated'][:10]})")
    # requests drops the Authorization header on the cross-host redirect to
    # S3, which is required — the signed URL carries its own auth.
    with requests.get(f"{BASE}/api/files/{dataset}/csv", headers=_headers(),
                      timeout=600, stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def _normalise(col: str) -> str:
    return col.strip().lower().replace("-", "_")


def aggregate_ac_evidence(zip_path, dataset: str) -> pd.DataFrame:
    """Stream certificate CSVs out of the full-load zip and reduce to
    per-lodgement-year AC statistics."""
    yearly = {}
    with zipfile.ZipFile(zip_path) as z:
        members = [m for m in z.namelist()
                   if m.endswith(".csv") and "recommendation" not in m.lower()]
        for m in members:
            with z.open(m) as fh:
                for chunk in pd.read_csv(io.TextIOWrapper(fh, "utf-8", errors="replace"),
                                         chunksize=200_000, dtype=str,
                                         usecols=lambda c: _normalise(c) in KEEP_COLS):
                    chunk.columns = [_normalise(c) for c in chunk.columns]
                    if "lodgement_date" not in chunk or "aircon_present" not in chunk:
                        continue
                    chunk["year"] = pd.to_datetime(
                        chunk["lodgement_date"], errors="coerce").dt.year
                    chunk["ac"] = chunk["aircon_present"].str.strip().str.lower() \
                        .isin(["y", "yes", "1", "true"])
                    kw = pd.to_numeric(chunk.get("aircon_kw_rating"), errors="coerce")
                    est = pd.to_numeric(chunk.get("estimated_aircon_kw_rating"), errors="coerce")
                    chunk["kw"] = kw.fillna(est)
                    insp = chunk.get("ac_inspection_commissioned", pd.Series(dtype=str))
                    chunk["inspected"] = insp.astype(str).str.strip().isin(["1", "2"])
                    for y, g in chunk.groupby("year", dropna=True):
                        acc = yearly.setdefault(int(y), {
                            "certs": 0, "ac_present": 0, "kw_total": 0.0,
                            "kw_known": 0, "inspection_done_or_commissioned": 0})
                        acc["certs"] += len(g)
                        acc["ac_present"] += int(g["ac"].sum())
                        acc["kw_total"] += float(g.loc[g["ac"], "kw"].sum(skipna=True) or 0)
                        acc["kw_known"] += int(g.loc[g["ac"], "kw"].notna().sum())
                        acc["inspection_done_or_commissioned"] += int((g["ac"] & g["inspected"]).sum())

    out = (pd.DataFrame.from_dict(yearly, orient="index").sort_index()
           .rename_axis("lodgement_year").reset_index())
    out["dataset"] = dataset
    out["ac_share"] = (out["ac_present"] / out["certs"]).round(3)
    return out


def ingest(pull_date: str | None = None, datasets=DATASETS) -> pd.DataFrame:
    frames = []
    for ds in datasets:
        zp = download_full_load(ds, pull_date)
        print(f"  {ds}: aggregating AC evidence")
        frames.append(aggregate_ac_evidence(zp, ds))
    out = pd.concat(frames, ignore_index=True)
    outdir = DATA_DIR / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(outdir / "tm44_ac_evidence.csv", index=False)
    return out
