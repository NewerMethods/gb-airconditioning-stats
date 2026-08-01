"""D3 runner: pull EPB register full loads (non-domestic EPC + DEC) and
reduce them to per-year commercial AC evidence (U3 anchor input).

Requires a GOV.UK One Login bearer token — see pipeline/tm44.py docstring or
README for the one-time human setup. Fails with instructions if absent.

Usage: python scripts/run_tm44.py [--dataset non-domestic|display|both] [--pull-date YYYY-MM-DD]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.tm44 import DATASETS, TokenMissing, ingest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=[*DATASETS, "both"], default="both")
    ap.add_argument("--pull-date", default=None)
    args = ap.parse_args()
    datasets = DATASETS if args.dataset == "both" else (args.dataset,)

    print("[D3] EPB register ingestion (non-domestic EPC / DEC AC fields)")
    try:
        out = ingest(args.pull_date, datasets)
    except TokenMissing as e:
        sys.exit(f"\n{e}")
    print("\n=== COMMERCIAL AC EVIDENCE BY LODGEMENT YEAR ===")
    print(out.to_string(index=False))
    print("\nOutput: data/outputs/tm44_ac_evidence.csv")


if __name__ == "__main__":
    main()
