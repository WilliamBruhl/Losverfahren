# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a self-contained, hashable JSON result + manifest.

The manifest contains:

* SHA-256 of the canonical candidate list,
* SHA-256 of the canonical population marginals,
* SHA-256 of the panel (members + substitutes) and probabilities,
* run-level SHA-256 chaining all of the above with seed + parameters.

Two independent re-runs with the same inputs + seed must produce the same
``run_hash`` — that is the integrity guarantee for archival and audit.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

import pulp

from .models import Candidate
from .quotas import Quota
from .selection import SelectionResult


_GENERATOR = "losverfahren 0.1.0 (maximin LP + repair sampler)"


def _solver_fingerprint() -> str:
    """Identifier for the LP solver stack baked into ``run_hash``.

    Different ``pulp`` / CBC versions can pick different optima on
    degenerate LPs, which would change the sampled panel without any
    change in the inputs. Pinning the solver version into ``run_hash``
    makes that environmental drift detectable.
    """
    return f"pulp={getattr(pulp, '__version__', 'unknown')}"


_NO_HASH = "—"  # rendered identically in xlsx and JSON when no panel exists


def _sha256(payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _candidates_payload(candidates: list[Candidate]) -> list[dict]:
    return [
        {"ID": c.ID, **{k: c.attrs[k] for k in sorted(c.attrs.keys())}}
        for c in sorted(candidates, key=lambda x: x.ID)
    ]


def _panel_payload(panel: list[Candidate]) -> list[str]:
    return sorted(c.ID for c in panel)


def _quotas_payload(quotas: list[Quota]) -> list[dict]:
    return [
        {"feature": q.feature, "value": q.value,
         "share": round(q.share, 6), "lo": q.lo, "hi": q.hi}
        for q in quotas
    ]


def _result_payload(r: SelectionResult, quotas: list[Quota]) -> dict:
    bounds = [
        {"feature": q.feature, "value": q.value, "lo_effective": lo, "hi_effective": hi}
        for q, (lo, hi) in zip(quotas, r.effective_bounds)
    ]
    return {
        "panel": _panel_payload(r.panel),
        "minimum_probability": round(r.minimum_probability, 6),
        "solver_status": r.solver_status,
        "effective_bounds": bounds,
        "relaxations": r.relaxations,
        "realised_marginals": {
            f"{f}={v}": n for (f, v), n in sorted(r.realised_marginals.items())
        },
    }


def build_manifest(
    *,
    seed: int,
    panel_size_members: int,
    panel_size_substitutes: int,
    candidates: list[Candidate],
    population: dict[str, dict[str, float]],
    quotas: list[Quota],
    members: SelectionResult,
    substitutes: SelectionResult | None,
    substitute_quotas: list[Quota] | None = None,
    inputs: dict[str, str] | None = None,
    population_notes: list[dict[str, str]] | None = None,
) -> dict:
    """Build the canonical manifest.

    ``quotas`` is the quota list used for the *member* draw.
    ``substitute_quotas`` is the (possibly different) list used for the
    substitute draw — different because the substitute panel size may
    differ, and because the joint quotas can be dropped on the
    marginal-only fallback path. Defaults to ``quotas`` for backwards
    compatibility.
    """
    if substitute_quotas is None:
        substitute_quotas = quotas

    cand_payload = _candidates_payload(candidates)
    pop_payload = {
        f: {v: round(s, 6) for v, s in sorted(d.items())}
        for f, d in sorted(population.items())
    }
    quotas_payload = _quotas_payload(quotas)
    sub_quotas_payload = _quotas_payload(substitute_quotas)
    members_payload = _result_payload(members, quotas)
    subs_payload = _result_payload(substitutes, substitute_quotas) if substitutes else None

    parts = {
        "candidates_sha256": _sha256(cand_payload),
        "population_sha256": _sha256(pop_payload),
        "quotas_sha256": _sha256(quotas_payload),
        "substitute_quotas_sha256": (
            _sha256(sub_quotas_payload) if substitutes else None
        ),
        "members_sha256": _sha256(members_payload),
        "substitutes_sha256": _sha256(subs_payload) if subs_payload else None,
    }

    run_seed = {
        "seed": int(seed),
        "panel_size_members": int(panel_size_members),
        "panel_size_substitutes": int(panel_size_substitutes),
        "generator": _GENERATOR,
        "solver": _solver_fingerprint(),
        **parts,
    }
    run_hash = _sha256(run_seed)

    return {
        "generator": _GENERATOR,
        "solver": _solver_fingerprint(),
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "seed": int(seed),
        "panel_size_members": int(panel_size_members),
        "panel_size_substitutes": int(panel_size_substitutes),
        "inputs": inputs or {},
        "candidate_count": len(candidates),
        "hashes": parts,
        "run_hash": run_hash,
        "population": pop_payload,
        "quotas": quotas_payload,
        "substitute_quotas": sub_quotas_payload if substitutes else None,
        "members": members_payload,
        "substitutes": subs_payload,
        "candidates": cand_payload,
        "population_notes": list(population_notes or []),
    }


def manifest_audit_rows(manifest: dict) -> list[tuple[str, str]]:
    """Compact audit rows derived from the manifest (for the xlsx audit sheet)."""
    h = manifest["hashes"]
    rows: list[tuple[str, str]] = [
        ("Zeitpunkt", manifest["created_at"]),
        ("Generator", manifest["generator"]),
        ("Solver", manifest.get("solver", _NO_HASH)),
        ("Seed", str(manifest["seed"])),
        ("Mitglieder (Soll)", str(manifest["panel_size_members"])),
        ("Ersatz (Soll)", str(manifest["panel_size_substitutes"])),
        ("Kandidaten (Anzahl)", str(manifest["candidate_count"])),
        ("Run-Hash (SHA-256)", manifest["run_hash"]),
        ("Kandidaten-Hash (SHA-256)", h["candidates_sha256"]),
        ("Bevölkerung-Hash (SHA-256)", h["population_sha256"]),
        ("Quoten-Hash (SHA-256)", h["quotas_sha256"]),
        ("Ersatz-Quoten-Hash (SHA-256)",
         h.get("substitute_quotas_sha256") or _NO_HASH),
        ("Mitglieder-Hash (SHA-256)", h["members_sha256"]),
        ("Ersatz-Hash (SHA-256)", h["substitutes_sha256"] or _NO_HASH),
        ("LP-Status (Mitglieder)", manifest["members"]["solver_status"]),
        ("Min p_i (Mitglieder)",
         f"{manifest['members']['minimum_probability']:.4f}"),
    ]
    if manifest["substitutes"]:
        rows.append(("LP-Status (Ersatz)", manifest["substitutes"]["solver_status"]))
        rows.append(("Min p_i (Ersatz)",
                     f"{manifest['substitutes']['minimum_probability']:.4f}"))

    rows.append(("", ""))
    rows.append(("Quoten-Intervalle", "feature / value / [lo, hi] (Anteil)"))
    for q in manifest["quotas"]:
        rows.append((f"  {q['feature']} = {q['value']}",
                     f"[{q['lo']}, {q['hi']}]  ({q['share']:.4f})"))

    for label, key in (("Mitglieder", "members"), ("Ersatz", "substitutes")):
        section = manifest[key]
        if not section:
            continue
        rows.append(("", ""))
        rows.append((f"Effektive Schranken — {label}", "feature / value / [lo, hi]"))
        for b in section["effective_bounds"]:
            rows.append((f"  {b['feature']} = {b['value']}",
                         f"[{b['lo_effective']}, {b['hi_effective']}]"))
        if section["relaxations"]:
            rows.append(("", ""))
            rows.append((f"Quoten-Anpassungen — {label}", ""))
            for r in section["relaxations"]:
                rows.append(("  •", r))
        rows.append(("", ""))
        rows.append((f"Realisierte Marginalen — {label}", ""))
        for k, v in section["realised_marginals"].items():
            rows.append((f"  {k}", str(v)))
    return rows
