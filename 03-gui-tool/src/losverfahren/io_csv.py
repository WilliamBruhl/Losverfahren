# SPDX-License-Identifier: AGPL-3.0-or-later
"""CSV-native I/O for the GUI tool.

This module is intentionally independent of the legacy Excel layout. It
reads two (or three) flat CSV files that any admin user can edit in a
spreadsheet:

* ``candidates.csv`` — one row per candidate. ``ID`` is the only required
  column; every other column becomes a stratification attribute (e.g.
  ``Geschlecht, Alter, Kanton, Beruf, …`` — names and language are free).
* ``population.csv`` — long format: ``feature, value, count`` (``share`` is
  also accepted). One row per feature value.
* ``population_joint.csv`` — optional cross-tab; one column per dimension
  plus ``count`` / ``share``.

Column names are matched case-insensitively against a small alias table so
admins can keep their preferred wording (``Anzahl`` instead of ``count``,
``Merkmal`` instead of ``feature``, …). The actual stratification features
are *not* aliased — they are whatever the admin writes, and they only need
to match between ``candidates.csv`` and ``population.csv``.

A sample dataset lives under ``03-gui-tool/sample-data/``.
"""

from __future__ import annotations

import csv
import json
import unicodedata
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .io_excel import Candidate


# Aliases for the structural metadata columns (everything that is NOT a
# user-defined stratification feature). Keys are lowercase, accent-folded.
_COLUMN_ALIASES: dict[str, str] = {
    # ID
    "id": "ID", "nummer": "ID", "code": "ID",
    "teilnehmer-id": "ID", "teilnehmerid": "ID", "identifier": "ID",
    # count
    "count": "count", "anzahl": "count", "n": "count",
    "population": "count", "cnt": "count", "number": "count",
    # share
    "share": "share", "anteil": "share", "quote": "share",
    "prozent": "share", "percent": "share", "%": "share",
    # note
    "note": "note", "bemerkung": "note", "notiz": "note",
    "kommentar": "note", "comment": "note", "remarks": "note",
    # feature
    "feature": "feature", "merkmal": "feature",
    "attribute": "feature", "kategorie": "feature",
    # value
    "value": "value", "wert": "value",
    "auspraegung": "value", "level": "value",
}


def _fold(name: str) -> str:
    """Lowercase + strip diacritics for alias lookup (``Ä`` → ``a``)."""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return n.strip().lower()


def canonical_column(name: str) -> str | None:
    """Return the canonical metadata-column name for ``name`` or ``None``.

    Used to recognise an admin-written ``Anzahl`` column as ``count`` etc.
    Returns ``None`` for any column that is not a known metadata column —
    those are treated as stratification feature columns.
    """
    return _COLUMN_ALIASES.get(_fold(name))


def _normalise_fieldnames(
    fieldnames: Iterable[str],
) -> tuple[dict[str, str], list[str]]:
    """Return ``(orig → canonical-or-orig, alias_warnings)``.

    Metadata columns are renamed to their canonical name; feature columns
    keep their original casing. Duplicate canonical mappings raise.
    """
    mapping: dict[str, str] = {}
    seen_canonical: dict[str, str] = {}
    warnings: list[str] = []
    for raw in fieldnames:
        canon = canonical_column(raw)
        if canon is None:
            mapping[raw] = raw
            continue
        if canon in seen_canonical and seen_canonical[canon] != raw:
            raise ValueError(
                f"column {raw!r} aliases to {canon!r} but "
                f"{seen_canonical[canon]!r} already does"
            )
        seen_canonical[canon] = raw
        mapping[raw] = canon
        if raw != canon:
            warnings.append(f"column {raw!r} interpreted as {canon!r}")
    return mapping, warnings


def _read_csv_normalised(path: str | Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    """Read ``path``, normalising metadata column names.

    Returns ``(rows, fieldnames_canonical, alias_warnings)``.
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_fields = list(reader.fieldnames or [])
        mapping, warnings = _normalise_fieldnames(raw_fields)
        fields_canon = [mapping[c] for c in raw_fields]
        rows = [
            {mapping[k]: (v or "") for k, v in row.items() if k is not None}
            for row in reader
        ]
    return rows, fields_canon, warnings


def read_candidates_csv(
    path: str | Path,
) -> tuple[list[Candidate], list[str]]:
    """Read a candidates CSV with arbitrary attribute columns.

    ``ID`` is required. Every other column becomes a stratification attribute
    on the resulting :class:`Candidate`. Column names other than ``ID`` are
    preserved verbatim; only the ``ID`` column itself accepts common aliases.
    """
    rows, fields, warnings = _read_csv_normalised(path)
    if "ID" not in fields:
        raise ValueError(
            "candidates.csv must contain an 'ID' column (aliases: "
            "id, Nummer, Code, Teilnehmer-ID, …)"
        )
    attr_cols = [c for c in fields if c != "ID"]
    if not attr_cols:
        raise ValueError(
            "candidates.csv has only an ID column — add at least one "
            "stratification attribute (e.g. Geschlecht, Alterskategorie)."
        )
    out: list[Candidate] = []
    for row in rows:
        cid = (row.get("ID") or "").strip()
        if not cid:
            continue
        attrs = {
            col: (row.get(col) or "").strip()
            for col in attr_cols
            if (row.get(col) or "").strip()
        }
        out.append(Candidate(ID=cid, attrs=attrs))
    return out, warnings


def read_population_csv(path: str | Path) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Return ``(marginals_per_feature, warnings)``.

    Accepts either a ``count`` column (raw number of people, recommended) or
    a ``share`` column. When both are present, ``count`` wins. Shares are
    derived per feature so that values sum to 1.

    Features are *whatever appears* in the ``feature`` column — the loader
    no longer requires any specific set of names.
    """
    rows, fields, alias_warnings = _read_csv_normalised(path)
    missing_base = {"feature", "value"} - set(fields)
    if missing_base:
        raise ValueError(
            "population.csv is missing required columns: "
            f"{sorted(missing_base)} "
            "(aliases: Merkmal/feature, Wert/value)"
        )
    has_count = "count" in fields
    has_share = "share" in fields
    if not (has_count or has_share):
        raise ValueError(
            "population.csv must contain either a 'count' (Anzahl) or a "
            "'share' (Anteil) column."
        )

    raw: dict[str, dict[str, float]] = defaultdict(dict)
    used_counts = False
    for row in rows:
        feat = (row.get("feature") or "").strip()
        val = (row.get("value") or "").strip()
        if not feat or not val:
            continue
        cnt = row.get("count") if has_count else None
        if cnt not in (None, ""):
            used_counts = True
            raw[feat][val] = float(cnt)
        else:
            raw[feat][val] = float(row["share"]) if (row.get("share") or "") else 0.0

    warnings: list[str] = list(alias_warnings)
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
    return normalised, warnings


def read_joint_population_csv(
    path: str | Path,
) -> tuple[list[tuple[dict[str, str], float]], list[str]]:
    """Read a joint population CSV.

    Columns: one column per dimension (whatever the admin chose) plus either
    a ``count`` column (raw number of people, recommended) or a ``share``
    column. Dimension column names are preserved verbatim and must match
    the corresponding features in ``population.csv`` / ``candidates.csv``.
    """
    rows, fields, alias_warnings = _read_csv_normalised(path)
    has_count = "count" in fields
    has_share = "share" in fields
    if not (has_count or has_share):
        raise ValueError(
            "joint population CSV must include either 'count' (Anzahl) or "
            "'share' (Anteil)"
        )
    feature_cols = [c for c in fields if c not in ("count", "share", "note")]
    if not feature_cols:
        raise ValueError(
            "joint population CSV needs at least one dimension column"
        )
    out: list[tuple[dict[str, str], float]] = []
    for row in rows:
        criteria = {c: (row.get(c) or "").strip() for c in feature_cols
                    if (row.get(c) or "").strip()}
        if len(criteria) != len(feature_cols):
            continue
        try:
            if has_count and (row.get("count") or "").strip():
                val = float(row["count"])
            elif has_share:
                val = float(row["share"])
            else:
                continue
        except (TypeError, ValueError):
            continue
        out.append((criteria, val))

    total = sum(s for _, s in out)
    if total <= 0:
        raise ValueError("joint population CSV: values sum to 0")
    warnings = list(alias_warnings)
    if has_share and not has_count and abs(total - 1.0) > 0.01:
        warnings.append(f"joint population shares sum to {total:.4f}, re-normalising")
    out = [(c, s / total) for c, s in out]
    return out, warnings


def write_candidates_csv(path: str | Path, candidates: Iterable[Candidate]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidates = list(candidates)
    # Discover columns dynamically.
    cols: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        for k in c.attrs.keys():
            if k not in seen:
                cols.append(k)
                seen.add(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ID", *cols])
        for c in candidates:
            w.writerow([c.ID, *(c.attrs.get(k, "") for k in cols)])


def candidate_to_dict(c: Candidate) -> dict:
    return {"ID": c.ID, **c.attrs}


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
