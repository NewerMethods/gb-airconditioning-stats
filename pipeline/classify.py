"""FR3: type classification engine.

Rule layer: CN8 -> candidate types (config/cn_codes.yaml).
Statistical layer: within ambiguous codes, threshold on value-per-kg (GBP/kg)
— value-per-unit is unavailable (Phase 0: no supplementary units).

Every allocation row carries (type, estimator, confidence). Rows too close to
a threshold are reported as UNALLOCATED rather than forced (FR3.3). T3/T4
allocation of non-VRF split mass is a modelled prior, tagged as such — never
present it as measured (CLAUDE.md).
"""

from datetime import date

import numpy as np
import pandas as pd

from .config import load, load_classifier, save


def _confidence(vpk: pd.Series, threshold: float, rules: dict) -> pd.Series:
    dist = (np.log10(vpk) - np.log10(threshold)).abs()
    frac = (dist / rules["full_confidence_log10_distance"]).clip(upper=1.0)
    return rules["confidence_floor"] + frac * (rules["confidence_cap"] - rules["confidence_floor"])


def _near_threshold(vpk: pd.Series, threshold: float, rules: dict) -> pd.Series:
    return (np.log10(vpk) - np.log10(threshold)).abs() < rules["unallocated_log10_band"]


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """Return allocation rows: one input row may split into several (T3/T4)."""
    cfg = load_classifier()
    thr, rules = cfg["thresholds"], cfg["rules"]
    codes = load("cn_codes")["codes"]
    out = []

    def emit(rows: pd.DataFrame, type_: str, estimator: str, conf, mass_share: float = 1.0):
        if not len(rows):
            return
        r = rows.copy()
        r["type"] = type_
        r["estimator"] = estimator
        r["confidence"] = conf if not np.isscalar(conf) else float(conf)
        if mass_share != 1.0:
            r["net_mass_kg"] *= mass_share
            r["value_gbp"] *= mass_share
        out.append(r)

    for cn8, meta in codes.items():
        d = df[df["cn8"] == cn8]
        if not len(d):
            continue
        role = meta["role"]

        if role == "satellite_value_index":
            emit(d, "SATELLITE", "value_index_only", 1.0)
        elif role == "monitor":
            emit(d, "EDGE_MONITOR", "cn_rule", 1.0)
        elif cn8 == "84151010":
            emit(d, "T2", "cn_rule", 0.90)
        elif cn8 == "84186100":
            emit(d, "T7", "cn_rule", 0.90)
        elif cn8 == "84151090":
            vpk = d["value_per_kg"]
            no_signal = vpk.isna()
            is_vrf = ~no_signal & (vpk > thr["vrf_vpk_threshold"])
            near = ~no_signal & _near_threshold(vpk, thr["vrf_vpk_threshold"], rules)
            emit(d[near | no_signal], "UNALLOCATED", "vpk_threshold", 0.0)
            emit(d[is_vrf & ~near], "T5", "vpk_threshold",
                 _confidence(vpk[is_vrf & ~near], thr["vrf_vpk_threshold"], rules))
            rest = d[~is_vrf & ~near & ~no_signal]
            for t, share in rules["t3_t4_mass_shares"].items():
                emit(rest, t, "prior_allocation", rules["prior_allocation_confidence"], share)
        elif cn8 in ("84158100", "84158200"):
            vpk = d["value_per_kg"]
            no_signal = vpk.isna()
            edge = ~no_signal & (vpk > thr["edge_vpk_threshold"])
            emit(d[edge], "EDGE_AIRCRAFT", "vpk_threshold", 0.90)
            body = d[~edge & ~no_signal]
            bvpk = body["value_per_kg"]
            near = _near_threshold(bvpk, thr["t1_t6_log_vpk_threshold"], rules)
            emit(d[no_signal], "UNALLOCATED", "vpk_threshold", 0.0)
            emit(body[near], "UNALLOCATED", "vpk_threshold", 0.0)
            hi = ~near & (bvpk > thr["t1_t6_log_vpk_threshold"])
            lo = ~near & ~hi
            emit(body[hi], "T6", "vpk_threshold",
                 _confidence(bvpk[hi], thr["t1_t6_log_vpk_threshold"], rules))
            emit(body[lo], "T1", "vpk_threshold",
                 _confidence(bvpk[lo], thr["t1_t6_log_vpk_threshold"], rules))
        else:
            raise ValueError(f"no classification rule for {cn8} (role={role})")

    return pd.concat(out, ignore_index=True)


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return float(np.interp(q, cum, v))


def _weighted_2means_log10(values: np.ndarray, weights: np.ndarray) -> float:
    """Mass-weighted 2-means on log10(value_per_kg); returns the midpoint
    between cluster centres, back-transformed. Deliberately dependency-free
    and inspectable."""
    x = np.log10(values)
    c = np.array([_weighted_quantile(x, weights, 0.25), _weighted_quantile(x, weights, 0.75)])
    for _ in range(50):
        assign = np.abs(x[:, None] - c[None, :]).argmin(axis=1)
        new = np.array([
            np.average(x[assign == k], weights=weights[assign == k]) if (assign == k).any() else c[k]
            for k in (0, 1)
        ])
        if np.allclose(new, c, atol=1e-9):
            break
        c = new
    return float(10 ** c.mean())


def fit_classifier(clean: pd.DataFrame) -> dict:
    """Fit thresholds on the training year (imports only, mass-weighted) and
    write them to config/classifier_fitted.yaml with provenance."""
    cfg = load_classifier()
    year = cfg["training_year"]
    edge = cfg["thresholds"]["edge_vpk_threshold"]

    imp = clean[(clean["direction"] == "import") & (clean["year"] == year)
                & clean["value_per_kg"].notna() & (clean["value_per_kg"] > 0)]

    body = imp[imp["cn8"].isin(["84158100", "84158200"]) & (imp["value_per_kg"] < edge)]
    t1_t6 = _weighted_2means_log10(body["value_per_kg"].to_numpy(),
                                   body["net_mass_kg"].to_numpy())

    split = imp[imp["cn8"] == "84151090"]
    vrf = _weighted_quantile(split["value_per_kg"].to_numpy(),
                             split["net_mass_kg"].to_numpy(),
                             cfg["fit"]["vrf_mass_quantile"])

    fitted = {
        "fitted": {
            "t1_t6_log_vpk_threshold": round(t1_t6, 2),
            "vrf_vpk_threshold": round(vrf, 2),
        },
        "fit_meta": {
            "training_year": year,
            "fit_date": date.today().isoformat(),
            "method": "t1_t6: mass-weighted 2-means on log10(GBP/kg), 841581/82 imports; "
                      f"vrf: mass-weighted q{cfg['fit']['vrf_mass_quantile']} of GBP/kg, 84151090 imports",
            "n_rows": {"t1_t6": int(len(body)), "vrf": int(len(split))},
        },
    }
    save("classifier_fitted", fitted)
    print(f"  fitted thresholds (training year {year}): "
          f"t1_t6={fitted['fitted']['t1_t6_log_vpk_threshold']} GBP/kg, "
          f"vrf={fitted['fitted']['vrf_vpk_threshold']} GBP/kg")
    return fitted
