from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


def load(name: str) -> dict:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save(name: str, cfg: dict) -> None:
    """Write a machine-owned config file (e.g. classifier_fitted).

    Hand-edited configs are never rewritten by code — fitted values live in
    their own file so comments and provenance survive.
    """
    with open(CONFIG_DIR / f"{name}.yaml", "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def load_classifier() -> dict:
    """classifier.yaml with any fitted thresholds merged over the defaults."""
    cfg = load("classifier")
    fitted = load("classifier_fitted").get("fitted", {})
    cfg["thresholds"] = {**cfg["defaults"], **fitted}
    return cfg
