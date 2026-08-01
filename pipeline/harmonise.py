"""FR2: raw -> clean. One tidy row-level frame across all codes.

Cleaning rules are minimal and logged: this layer never drops trade value
silently. Suppression has been observed at zero for these codes (Phase 0),
but the flag is carried through in case that changes.
"""

import numpy as np
import pandas as pd

from .config import DATA_DIR, load_classifier

FLOW_DIRECTION = {1: "import", 2: "export", 3: "import", 4: "export"}


def _apply_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """Rule-based corrections for implausible declarations, every one logged.

    Currently one rule: a large-mass row priced below the plausibility floor
    is a suspected mass mis-declaration (grams entered as kg). The /1000 fix
    is applied only when it lands the row inside the plausible GBP/kg band;
    otherwise the row is flagged but left untouched.
    """
    cfg = load_classifier()["cleaning"]
    vpk = np.where(df["NetMass"] > 0, df["Value"] / df["NetMass"], np.nan)
    suspect = (
        (df["NetMass"] >= cfg["mass_scale_fix_min_kg"])
        & (vpk < cfg["vpk_implausible_floor"])
    )
    lo, hi = cfg["vpk_plausible_band"]
    fixable = suspect & (vpk * 1000 >= lo) & (vpk * 1000 <= hi)

    log = df.loc[suspect, ["MonthId", "FlowTypeId", "CommodityId", "CountryId",
                           "Value", "NetMass"]].copy()
    log["rule"] = np.where(fixable[suspect], "mass_div_1000", "flag_only")
    log["vpk_before"] = vpk[suspect].round(3)

    df = df.copy()
    df.loc[fixable, "NetMass"] = df.loc[fixable, "NetMass"] / 1000.0
    df["corrected"] = fixable

    clean_dir = DATA_DIR / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    log.to_csv(clean_dir / "corrections_log.csv", index=False)
    print(f"  corrections: {int(fixable.sum())} mass/1000 fixes, "
          f"{int(suspect.sum() - fixable.sum())} flagged-only (data/clean/corrections_log.csv)")
    return df


def harmonise(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for code, df in raw.items():
        d = df.copy()
        d["cn8"] = code
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)

    df["direction"] = df["FlowTypeId"].map(FLOW_DIRECTION)
    df["month"] = pd.to_datetime(df["MonthId"].astype(str), format="%Y%m")
    df["year"] = df["MonthId"] // 100
    for col in ("Value", "NetMass"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["suppressed_qty"] = df["SuppressionIndex"].isin([1, 3, 5])

    df = _apply_corrections(df)

    n0 = len(df)
    empty = (df["Value"] <= 0) & (df["NetMass"] <= 0)
    df = df[~empty].copy()
    print(f"  harmonise: {n0} rows in, dropped {int(empty.sum())} empty (no value, no mass)")

    # Classifier signal. Rows with mass suppressed or zero get NaN and are
    # classified by rule layer only.
    df["value_per_kg"] = np.where(df["NetMass"] > 0, df["Value"] / df["NetMass"], np.nan)

    keep = ["month", "year", "MonthId", "cn8", "direction", "FlowTypeId",
            "CountryId", "Value", "NetMass", "value_per_kg", "suppressed_qty",
            "corrected"]
    out = df[keep].rename(columns={"Value": "value_gbp", "NetMass": "net_mass_kg"})

    clean_dir = DATA_DIR / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    out.to_parquet(clean_dir / "ots_harmonised.parquet")
    return out
