"""Phase 1 orchestrator: D1 ingestion -> harmonise -> classify -> net-mass
unit derivation -> monthly apparent consumption by type, plus the D2 mirror
check. PRD §8 Phase 1 deliverable.

Usage:
  python scripts/run_phase1.py [--fit-classifier] [--skip-mirror] [--pull-date YYYY-MM-DD]

--fit-classifier refits value-per-kg thresholds on the training year and
writes config/classifier_fitted.yaml before classifying.
--pull-date reuses an existing raw vintage instead of pulling today's.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.apparent import annual_summary, apparent_consumption, s3_metric
from pipeline.classify import classify, fit_classifier
from pipeline.harmonise import harmonise
from pipeline.ingest import pull_all
from pipeline.mirror import mirror_check
from pipeline.units import derive_units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-classifier", action="store_true")
    ap.add_argument("--skip-mirror", action="store_true")
    ap.add_argument("--pull-date", default=None)
    args = ap.parse_args()

    print("[1/5] Ingest (D1: HMRC OTS)")
    raw = pull_all(args.pull_date)

    print("[2/5] Harmonise")
    clean = harmonise(raw)

    if args.fit_classifier:
        print("[2b] Fit classifier thresholds")
        fit_classifier(clean)

    print("[3/5] Classify types")
    alloc = classify(clean)

    print("[4/5] Derive units (net-mass / prior) and apparent consumption")
    units_df = derive_units(alloc)
    ac = apparent_consumption(units_df)

    print("\n=== ANNUAL APPARENT CONSUMPTION, GB, UNITS (central) ===")
    print(annual_summary(ac).to_string())
    print(f"\nS3 — high-confidence classified share of import mass: {s3_metric(units_df):.1%} (target >=90%)")

    unalloc = units_df[(units_df['type'] == 'UNALLOCATED') & (units_df['direction'] == 'import')]
    in_scope = units_df[~units_df["type"].isin(["SATELLITE", "EDGE_MONITOR", "EDGE_AIRCRAFT"])
                        & (units_df["direction"] == "import")]
    print(f"Unallocated import mass (published, not forced): "
          f"{unalloc['net_mass_kg'].sum() / in_scope['net_mass_kg'].sum():.1%}")

    if not args.skip_mirror:
        print("\n[5/5] D2 mirror check (HMRC vs Comtrade, China, net mass)")
        try:
            print(mirror_check(clean, args.pull_date).to_string(index=False))
        except Exception as e:  # FR1.3: a feed failure alerts, never blocks
            print(f"  MIRROR CHECK FAILED (non-blocking): {e}")
    else:
        print("\n[5/5] mirror check skipped")

    print("\nOutputs: data/outputs/apparent_consumption_monthly.{parquet,csv}, data/outputs/mirror_check.csv")


if __name__ == "__main__":
    main()
