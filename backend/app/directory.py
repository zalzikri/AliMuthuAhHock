"""The product directory.

Public descriptions and links only. The hackathon rules allow dummy or public data
only, so nothing is mirrored out of the internal documentation site - docs are
linked, never copied.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build() -> list[dict]:
    return json.loads((ROOT / "data" / "products.json").read_text())


def for_project(key: str | None) -> dict | None:
    if not key:
        return None
    return next((p for p in build() if p["key"] == key), None)
