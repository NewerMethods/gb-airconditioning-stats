"""Apparent consumption = imports - exports, monthly by type (GB).

OTS is UK-wide; GB = UK * (1 - ni_import_share), a named assumption
(config/classifier.yaml harmonisation block) pending an RTS-based estimate.
Provenance: every output row carries estimator and a mass-weighted
confidence; unallocated and edge volume is published alongside (N2).
"""

import numpy as np
import pandas as pd

from .config import DATA_DIR, load_classifier

UNIT_TYPES = ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]


def _wavg(g: pd.DataFrame, col: str, w: str) -> float:
    tw = g[w].sum()
    return float((g[col] * g[w]).sum() / tw) if tw else float("nan")


def apparent_consumption(units_df: pd.DataFrame) -> pd.DataFrame:
    gb_factor = 1.0 - load_classifier()["harmonisation"]["ni_import_share"]

    d = units_df.copy()
    sign = np.where(d["direction"] == "import", 1.0, -1.0)
    for col in ("units_central", "units_p10", "units_p90", "value_gbp", "net_mass_kg"):
        d[f"net_{col}"] = d[col] * sign * gb_factor

    grouped = []
    for (month, type_), g in d.groupby(["month", "type"]):
        grouped.append({
            "month": month,
            "type": type_,
            "units_central": g["net_units_central"].sum(),
            "units_p10": g["net_units_p10"].sum(),
            "units_p90": g["net_units_p90"].sum(),
            "value_gbp": g["net_value_gbp"].sum(),
            "net_mass_kg": g["net_net_mass_kg"].sum(),
            "estimator": g.groupby("estimator")["net_mass_kg"].apply(lambda s: s.abs().sum()).idxmax(),
            "confidence": _wavg(g, "confidence", "net_mass_kg"),
            "import_units_central": g.loc[g["direction"] == "import", "net_units_central"].sum(),
        })
    out = pd.DataFrame(grouped).sort_values(["month", "type"]).reset_index(drop=True)

    outdir = DATA_DIR / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    out.to_parquet(outdir / "apparent_consumption_monthly.parquet")
    out.to_csv(outdir / "apparent_consumption_monthly.csv", index=False)
    return out


def s3_metric(units_df: pd.DataFrame) -> float:
    """S3: share of imported unit-mass classified to a type at high confidence.

    Mass-based because unit counts don't exist for UNALLOCATED volume; using
    the mass denominator avoids flattering the metric.
    """
    rules = load_classifier()["rules"]
    imp = units_df[units_df["direction"] == "import"]
    in_scope = imp[~imp["type"].isin(["SATELLITE", "EDGE_MONITOR", "EDGE_AIRCRAFT"])]
    hi = in_scope["type"].isin(UNIT_TYPES) & (in_scope["confidence"] >= rules["high_confidence_min"])
    return float(in_scope.loc[hi, "net_mass_kg"].sum() / in_scope["net_mass_kg"].sum())


def annual_summary(ac: pd.DataFrame) -> pd.DataFrame:
    d = ac[ac["type"].isin(UNIT_TYPES)].copy()
    d["year"] = d["month"].dt.year
    piv = d.pivot_table(index="year", columns="type", values="units_central", aggfunc="sum")
    piv["TOTAL"] = piv.sum(axis=1)
    return piv.round(0)
