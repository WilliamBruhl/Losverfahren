"""Audit record for one draw."""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Iterable

from .io_excel import Candidate
from .quotas import Quota
from .selection import SelectionResult


def candidate_hash(candidates: Iterable[Candidate]) -> str:
    h = hashlib.sha256()
    for c in sorted(candidates, key=lambda x: x.ID):
        h.update(
            "|".join(
                [c.ID, c.Geschlecht, c.Alterskategorie, c.Kanton, c.Ausbildung]
            ).encode("utf-8")
        )
        h.update(b"\n")
    return h.hexdigest()


def build_audit(
    *,
    seed: int,
    panel_size_members: int,
    panel_size_substitutes: int,
    candidates: list[Candidate],
    quotas: list[Quota],
    members: SelectionResult,
    substitutes: SelectionResult | None,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [
        ("Zeitpunkt", dt.datetime.now().isoformat(timespec="seconds")),
        ("Seed", str(seed)),
        ("Kandidaten (Anzahl)", str(len(candidates))),
        ("Kandidaten-Hash (SHA-256)", candidate_hash(candidates)),
        ("Generator", "losverfahren 0.1.0 (maximin LP + repair sampler)"),
        ("Mitglieder", str(panel_size_members)),
        ("Ersatz", str(panel_size_substitutes)),
        ("LP-Status (Mitglieder)", members.solver_status),
        ("Min p_i (Mitglieder)", f"{members.minimum_probability:.4f}"),
        ("LP-Status (Ersatz)",
         substitutes.solver_status if substitutes else "—"),
        ("Min p_i (Ersatz)",
         f"{substitutes.minimum_probability:.4f}" if substitutes else "—"),
        ("", ""),
        ("Quoten (feature / value / lo / hi)", ""),
    ]
    for q in quotas:
        rows.append((f"  {q.feature} = {q.value}", f"[{q.lo}, {q.hi}]  (Anteil {q.share:.4f})"))
    rows.append(("", ""))
    rows.append(("Realisierte Marginalen — Mitglieder", ""))
    for (f, v), n in sorted(members.realised_marginals.items()):
        rows.append((f"  {f} = {v}", str(n)))
    rows.append(("", ""))
    rows.append(("Realisierte Marginalen — Ersatz", ""))
    if substitutes:
        for (f, v), n in sorted(substitutes.realised_marginals.items()):
            rows.append((f"  {f} = {v}", str(n)))
    return rows
