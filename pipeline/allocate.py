"""FR4: use-case allocation engine.

Deterministic claims first (T1 -> U1 at the published >=95% assumption,
T5/T6 -> predominantly U3), then prior shares for the genuinely unobserved
splits (T3/T4 across U1/U2). Use case is NEVER observed in trade data —
every output row is a modelled allocation and is tagged as such. Priors,
and later their year-on-year movement, are outputs (FR4.3).

Flow bands combine the unit-count band (kg-per-unit priors) with the
allocation share band multiplicatively — a deliberate worst-case envelope,
not a probabilistic interval.
"""

import pandas as pd

from .config import DATA_DIR, load

UNIT_TYPES = ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]


def annual_flows(ac_monthly: pd.DataFrame) -> pd.DataFrame:
    """Complete calendar years only, unit types only."""
    d = ac_monthly[ac_monthly["type"].isin(UNIT_TYPES)].copy()
    d["year"] = d["month"].dt.year
    complete = d.groupby("year")["month"].transform(lambda s: s.dt.month.nunique() == 12)
    d = d[complete]
    return (d.groupby(["year", "type"])[["units_central", "units_p10", "units_p90"]]
            .sum().reset_index())


def allocate(ac_monthly: pd.DataFrame) -> pd.DataFrame:
    shares = load("anchors")["use_case_shares"]
    flows = annual_flows(ac_monthly)
    rows = []
    for _, r in flows.iterrows():
        for uc, s in shares[r["type"]].items():
            rows.append({
                "year": int(r["year"]),
                "type": r["type"],
                "use_case": uc,
                "flow_units": r["units_central"] * s["central"],
                "flow_units_lo": min(r["units_p10"] * s["lo"], r["units_p10"] * s["hi"]),
                "flow_units_hi": max(r["units_p90"] * s["hi"], r["units_p90"] * s["lo"]),
                "share_prior": s["central"],
                "estimator": "deterministic_assumption" if s["central"] >= 0.85
                             else "prior_allocation",
            })
    out = pd.DataFrame(rows)

    outdir = DATA_DIR / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(outdir / "allocation_annual.csv", index=False)
    return out
