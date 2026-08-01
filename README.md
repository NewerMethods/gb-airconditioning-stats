# GB AC Outlook Data Pipeline

Automated annual baseline of GB air conditioning sales and installed stock,
segmented by equipment type and use case. See CLAUDE.md for working context,
docs/PRD.md for the full spec, docs/DECISIONS.md and docs/RESEARCH_NOTES.md
for background.

## Quick start
1. `pip install requests pandas pyarrow`
2. `python scripts/phase0_check.py`  ← current next action (go/no-go)
