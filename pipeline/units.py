"""Net-mass unit derivation: units = NetMass / kg-per-unit prior.

The prior band (p10/p90 kg per unit) becomes the unit-count band, inverted:
heavy prior -> few units. Types without a prior (UNALLOCATED, EDGE_*,
SATELLITE) keep mass and value but carry no unit estimate — unallocated
volume is published, not forced (FR3.3).
"""

import numpy as np
import pandas as pd

from .config import load


def derive_units(alloc: pd.DataFrame) -> pd.DataFrame:
    priors = load("unit_mass_priors")["priors"]
    d = alloc.copy()
    for col in ("units_central", "units_p10", "units_p90"):
        d[col] = np.nan
    for t, p in priors.items():
        m = d["type"] == t
        mass = d.loc[m, "net_mass_kg"]
        d.loc[m, "units_central"] = mass / p["central"]
        d.loc[m, "units_p10"] = mass / p["p90"]
        d.loc[m, "units_p90"] = mass / p["p10"]
    return d
