"""FR5: stock-flow model with Weibull survival, plus the EHS anchor
reconciliation. Stock(t) = surviving initial stock + surviving flow cohorts.

Opening stock (end-2018) is a named assumption (config/anchors.yaml) treated
as a single mid-life cohort (effective age = median_life / 2) — crude, but
transparent, and its error washes out as real cohorts accumulate. The
reconciliation residual vs EHS is a published finding (CLAUDE.md: publish
the residual), not something to calibrate away silently.

Scenario bands run the whole model at lo / central / hi inputs — an
envelope, not a probabilistic interval.
"""

import math

import numpy as np
import pandas as pd

from .config import DATA_DIR, load

SCENARIOS = {"lo": ("flow_units_lo", "lo"), "central": ("flow_units", "central"),
             "hi": ("flow_units_hi", "hi")}


def _weibull_survival(age: float, median: float, shape: float) -> float:
    lam = median / (math.log(2) ** (1 / shape))
    return math.exp(-((max(age, 0.0) / lam) ** shape))


def stock_series(alloc: pd.DataFrame) -> pd.DataFrame:
    anchors = load("anchors")
    curves = load("cn_codes")["survival_curves"]
    init = anchors["initial_stock_2018"]
    shares = anchors["use_case_shares"]
    years = sorted(alloc["year"].unique())

    rows = []
    for type_, uc_shares in shares.items():
        med, shp = curves[type_]["median"], curves[type_]["shape"]
        eff_age0 = med / 2  # initial cohort treated as mid-life
        s0 = _weibull_survival(eff_age0, med, shp)
        for uc, s in uc_shares.items():
            for scen, (flow_col, band) in SCENARIOS.items():
                init_units = init[type_][band] * s[band if scen != "central" else "central"]
                f = alloc[(alloc["type"] == type_) & (alloc["use_case"] == uc)] \
                    .set_index("year")[flow_col]
                for y in years:
                    dt = y - 2018
                    stock = init_units * _weibull_survival(eff_age0 + dt, med, shp) / s0
                    for c in years:
                        if c <= y:
                            stock += f.get(c, 0.0) * _weibull_survival(y - c, med, shp)
                    rows.append({"year": y, "type": type_, "use_case": uc,
                                 "scenario": scen, "stock_units": stock})

    long = pd.DataFrame(rows)
    out = long.pivot_table(index=["year", "type", "use_case"], columns="scenario",
                           values="stock_units").reset_index()
    out = out.rename(columns={"lo": "stock_lo", "central": "stock_units", "hi": "stock_hi"})
    out = out[["year", "type", "use_case", "stock_units", "stock_lo", "stock_hi"]]

    outdir = DATA_DIR / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(outdir / "stock_annual.csv", index=False)
    return out


def ehs_reconciliation(stock: pd.DataFrame) -> dict:
    """VG3 groundwork: modelled U1 stock vs the EHS-derived anchor band."""
    a = load("anchors")
    ehs = a["ehs_anchor"]
    year = ehs["anchor_year"]
    types = ["T1", "T2", "T3", "T4"] + (["T7"] if a["include_t7_in_domestic_stock"] else [])

    dom = stock[(stock["year"] == year) & (stock["use_case"] == "U1")
                & stock["type"].isin(types)]
    model = {k: float(dom[c].sum()) for k, c in
             [("central", "stock_units"), ("lo", "stock_lo"), ("hi", "stock_hi")]}

    anchor = {
        k: ehs["england_ac_homes"] * ehs["england_to_gb_cdd_factor"][k] * ehs["units_per_ac_home"][k]
        for k in ("central", "lo", "hi")
    }
    residual = model["central"] - anchor["central"]
    overlap = (model["lo"] <= anchor["hi"]) and (anchor["lo"] <= model["hi"])

    result = {
        "anchor_year": year,
        "types_included": types,
        "model_u1_stock": {k: round(v) for k, v in model.items()},
        "ehs_anchor_units": {k: round(v) for k, v in anchor.items()},
        "residual_units": round(residual),
        "residual_pct_of_anchor": round(residual / anchor["central"], 3),
        "bands_overlap": bool(overlap),
    }
    pd.DataFrame([result]).to_json(DATA_DIR / "outputs" / "ehs_reconciliation.json",
                                   orient="records", indent=2)
    return result
