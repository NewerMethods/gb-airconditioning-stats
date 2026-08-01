"""Phase 2 orchestrator: use-case allocation (FR4) + stock-flow model (FR5)
+ EHS anchor reconciliation. Reads the Phase 1 monthly apparent-consumption
output; run scripts/run_phase1.py first.

Deliverable (PRD §8 Phase 2): draft baseline table, type x use case, with
bands. Every allocated cell is modelled — never present it as measured.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.allocate import allocate
from pipeline.config import DATA_DIR
from pipeline.stockflow import ehs_reconciliation, stock_series

AC_PATH = DATA_DIR / "outputs" / "apparent_consumption_monthly.parquet"


def main():
    if not AC_PATH.exists():
        sys.exit("Phase 1 output missing — run scripts/run_phase1.py first")
    ac = pd.read_parquet(AC_PATH)

    print("[1/3] Use-case allocation (FR4)")
    alloc = allocate(ac)

    print("[2/3] Stock-flow model (FR5)")
    stock = stock_series(alloc)

    latest = int(alloc["year"].max())
    print(f"\n=== DRAFT BASELINE {latest} — FLOW (units/yr, modelled allocation) ===")
    fp = alloc[alloc["year"] == latest].pivot_table(
        index="type", columns="use_case", values="flow_units", aggfunc="sum").fillna(0).round(0)
    fp["TOTAL"] = fp.sum(axis=1)
    print(fp.to_string())

    print(f"\n=== DRAFT BASELINE {latest} — STOCK (units, modelled) ===")
    sp = stock[stock["year"] == latest].pivot_table(
        index="type", columns="use_case", values="stock_units", aggfunc="sum").fillna(0).round(0)
    sp["TOTAL"] = sp.sum(axis=1)
    print(sp.to_string())
    print(f"\nStock by use case, {latest} (central / lo / hi):")
    uc = stock[stock["year"] == latest].groupby("use_case")[
        ["stock_units", "stock_lo", "stock_hi"]].sum().round(0)
    print(uc.to_string())

    print("\n[3/3] EHS anchor reconciliation (VG3 groundwork)")
    rec = ehs_reconciliation(stock)
    print(f"  modelled U1 stock {rec['anchor_year']} ({'+'.join(rec['types_included'])}): "
          f"{rec['model_u1_stock']['central']:,} [{rec['model_u1_stock']['lo']:,} – {rec['model_u1_stock']['hi']:,}]")
    print(f"  EHS anchor (GB units): {rec['ehs_anchor_units']['central']:,} "
          f"[{rec['ehs_anchor_units']['lo']:,} – {rec['ehs_anchor_units']['hi']:,}]")
    print(f"  RESIDUAL (published, not smoothed): {rec['residual_units']:+,} units "
          f"({rec['residual_pct_of_anchor']:+.1%} of anchor); bands overlap: {rec['bands_overlap']}")

    print("\nOutputs: data/outputs/allocation_annual.csv, stock_annual.csv, ehs_reconciliation.json")


if __name__ == "__main__":
    main()
