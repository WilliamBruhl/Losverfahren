"""CSV‑native I/O for the GUI tool.

This module is intentionally independent of the legacy Excel layout — it
reads two flat CSV files that any admin user can edit in a spreadsheet:

* ``candidates.csv`` — columns ``ID, Geschlecht, Alterskategorie, Kanton,
  Ausbildung`` (and an optional ``Profil``).
* ``population.csv`` — long format: ``feature, value, share``. One row per
  feature value. Shares per feature should add up to ~1.0; the loader
  re‑normalises and warns on drift > 1%.

A sample dataset lives under ``03-gui-tool/sample-data/``.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .io_excel import FEATURES, Candidate


def read_candidates_csv(path: str | Path) -> list[Candidate]:
    out: list[Candidate] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = {"ID", *FEATURES} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"candidates.csv is missing columns: {sorted(missing)}")
        for row in reader:
            if not row.get("ID"):
                continue
            out.append(
                Candidate(
                    ID=str(row["ID"]).strip(),
                    Geschlecht=str(row["Geschlecht"]).strip(),
                    Alterskategorie=str(row["Alterskategorie"]).strip(),
                    Kanton=str(row["Kanton"]).strip(),
                    Ausbildung=str(row["Ausbildung"]).strip(),
                    Profil=(row.get("Profil") or "").strip() or None,
                )
            )
    return out


def read_population_csv(path: str | Path) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Return ``(marginals_per_feature, warnings)``.

    Accepts either a ``count`` column (raw number of people, recommended) or
    a ``share`` column. When both are present, ``count`` wins. Shares are
    derived per feature so that values sum to 1.
    """
    raw: dict[str, dict[str, float]] = defaultdict(dict)
    used_counts = False
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing_base = {"feature", "value"} - fieldnames
        if missing_base:
            raise ValueError(f"population.csv is missing columns: {sorted(missing_base)}")
        if "count" not in fieldnames and "share" not in fieldnames:
            raise ValueError(
                "population.csv must contain either a 'count' or a 'share' column"
            )
        for row in reader:
            feat = (row.get("feature") or "").strip()
            val = (row.get("value") or "").strip()
            if not feat or not val:
                continue
            count = row.get("count") if "count" in fieldnames else None
            if count not in (None, ""):
                used_counts = True
                raw[feat][val] = float(count)
            else:
                raw[feat][val] = float(row["share"])

    warnings: list[str] = []
    normalised: dict[str, dict[str, float]] = {}
    for feat, d in raw.items():
        total = sum(d.values())
        if total <= 0:
            raise ValueError(f"population.csv: values for feature {feat!r} sum to 0")
        if not used_counts and abs(total - 1.0) > 0.01:
            warnings.append(
                f"feature {feat!r}: shares sum to {total:.4f}, re-normalising"
            )
        normalised[feat] = {k: v / total for k, v in d.items()}

    for feat in FEATURES:
        if feat not in normalised:
            warnings.append(f"feature {feat!r} missing from population.csv")
    return normalised, warnings


def read_joint_population_csv(
    path: str | Path,
) -> tuple[list[tuple[dict[str, str], float]], list[str]]:
    """Read a joint population CSV.

    Columns: one column per dimension (e.g. ``Geschlecht, Alterskategorie,
    Kanton``) plus either a ``count`` column (raw number of people,
    recommended) or a ``share`` column. Shares are derived so the cells sum
    to 1.
    """
    out: list[tuple[dict[str, str], float]] = []
    warnings: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        has_count = "count" in fieldnames
        has_share = "share" in fieldnames
        if not (has_count or has_share):
            raise ValueError(
                "joint population CSV must include either 'count' or 'share'"
            )
        feature_cols = [c for c in fieldnames if c not in ("count", "share")]
        for row in reader:
            criteria = {c: str(row[c]).strip() for c in feature_cols
                        if (row.get(c) or "").strip()}
            if len(criteria) != len(feature_cols):
                continue
            try:
                if has_count and (row.get("count") or "").strip():
                    val = float(row["count"])
                else:
                    val = float(row["share"])
            except (TypeError, ValueError):
                continue
            out.append((criteria, val))

    total = sum(s for _, s in out)
    if total <= 0:
        raise ValueError("joint population CSV: values sum to 0")
    if has_share and not has_count and abs(total - 1.0) > 0.01:
        warnings.append(f"joint population shares sum to {total:.4f}, re-normalising")
    out = [(c, s / total) for c, s in out]
    return out, warnings


def write_candidates_csv(path: str | Path, candidates: Iterable[Candidate]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ID", "Geschlecht", "Alterskategorie", "Kanton",
                    "Ausbildung", "Profil"])
        for c in candidates:
            w.writerow([c.ID, c.Geschlecht, c.Alterskategorie, c.Kanton,
                        c.Ausbildung, c.Profil or ""])


def write_population_csv(
    path: str | Path, marginals: dict[str, dict[str, float]]
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["feature", "value", "share"])
        for feat, d in marginals.items():
            for v, s in d.items():
                w.writerow([feat, v, f"{s:.6f}"])


def write_result_json(path: str | Path, payload: dict) -> None:
    """Persist the full result as JSON for downstream tooling / archival."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)


def candidate_to_dict(c: Candidate) -> dict:
    d = asdict(c)
    return d
