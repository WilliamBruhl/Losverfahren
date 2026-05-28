# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fair stratified selection — prototype.

Implements a simplified version of Flanigan et al. (2021):

1. **Maximin LP** assigns every candidate ``i`` a marginal selection
   probability ``p_i`` such that ``Σ p_i = panel_size``, every quota
   interval ``[lo_q, hi_q]`` holds and the minimum ``p_i`` is maximised.
2. **Repair sampling** turns the probabilities into an actual panel that
   respects every quota interval.

The same effective bounds ``(lo, hi)`` are used by the LP and by the sampler.
Bounds are automatically:

* **capped** by the number of candidates actually available in each bucket,
* **relaxed per feature** so that ``Σ lo ≤ panel_size ≤ Σ hi`` always holds
  (typically needed for the substitute draw on a small remaining pool).

Both relaxations are reported in the audit record.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

import pulp

from .io_excel import Candidate
from .quotas import Quota


# A quota whose ``feature`` contains ``×`` is a *joint* quota: feature names
# and values are split on ``×`` and ``|`` respectively, and a candidate must
# match every component to count towards the quota.
JOINT_SEP = "×"
VALUE_SEP = "|"


@dataclass
class SelectionResult:
    panel: list[Candidate]
    probabilities: dict[str, float]
    minimum_probability: float
    realised_marginals: dict[tuple[str, str], int]
    solver_status: str
    effective_bounds: list[tuple[int, int]] = field(default_factory=list)
    relaxations: list[str] = field(default_factory=list)


def _candidate_in_quota(c: Candidate, q: Quota) -> bool:
    if JOINT_SEP in q.feature:
        feats = q.feature.split(JOINT_SEP)
        vals = q.value.split(VALUE_SEP)
        return all(c.attrs.get(f) == v for f, v in zip(feats, vals))
    return c.attrs.get(q.feature) == q.value


def _effective_bounds(
    active: list[Candidate], quotas: list[Quota], panel_size: int
) -> tuple[list[tuple[int, int]], list[str]]:
    """Return per-quota ``(lo, hi)`` after availability cap + per-feature relax."""
    log: list[str] = []
    bounds: list[list[int]] = []  # [lo, hi, available]
    by_feature: dict[str, list[int]] = defaultdict(list)
    for i, q in enumerate(quotas):
        avail = sum(1 for c in active if _candidate_in_quota(c, q))
        lo = min(q.lo, avail)
        hi = min(max(q.hi, lo), avail) if avail > 0 else 0
        if lo != q.lo:
            log.append(f"{q.feature}={q.value}: lo {q.lo}→{lo} (only {avail} available)")
        if hi != q.hi and avail > 0 and hi < q.hi:
            log.append(f"{q.feature}={q.value}: hi {q.hi}→{hi} (only {avail} available)")
        bounds.append([lo, hi, avail])
        by_feature[q.feature].append(i)

    for feature, idxs in by_feature.items():
        # raise hi if too tight to fit panel
        guard = 0
        while sum(bounds[i][1] for i in idxs) < panel_size and guard < 2000:
            progressed = False
            for i in sorted(idxs, key=lambda j: -bounds[j][2]):
                if bounds[i][1] < bounds[i][2]:
                    bounds[i][1] += 1
                    log.append(
                        f"{feature}={quotas[i].value}: hi +1 → {bounds[i][1]} "
                        f"(per-feature relaxation)"
                    )
                    progressed = True
                    if sum(bounds[j][1] for j in idxs) >= panel_size:
                        break
            if not progressed:
                log.append(
                    f"{feature}: cannot reach panel size {panel_size} — "
                    f"only {sum(bounds[i][2] for i in idxs)} candidates total"
                )
                break
            guard += 1

        # lower lo if sum exceeds panel size
        guard = 0
        while sum(bounds[i][0] for i in idxs) > panel_size and guard < 2000:
            progressed = False
            for i in sorted(idxs, key=lambda j: -bounds[j][0]):
                if bounds[i][0] > 0:
                    bounds[i][0] -= 1
                    log.append(
                        f"{feature}={quotas[i].value}: lo -1 → {bounds[i][0]} "
                        f"(per-feature relaxation)"
                    )
                    progressed = True
                    if sum(bounds[j][0] for j in idxs) <= panel_size:
                        break
            if not progressed:
                break
            guard += 1

    return [(b[0], b[1]) for b in bounds], log


def _quota_counts(panel: Iterable[Candidate], quotas: list[Quota]) -> dict[int, int]:
    out: dict[int, int] = {}
    for i, q in enumerate(quotas):
        out[i] = sum(1 for c in panel if _candidate_in_quota(c, q))
    return out


def _violations(
    counts: dict[int, int], bounds: list[tuple[int, int]]
) -> list[int]:
    return [
        i for i, (lo, hi) in enumerate(bounds)
        if not (lo <= counts.get(i, 0) <= hi)
    ]


def _solve_maximin(
    active: list[Candidate],
    quotas: list[Quota],
    bounds: list[tuple[int, int]],
    panel_size: int,
) -> tuple[dict[str, float], float, str]:
    prob = pulp.LpProblem("maximin_panel", pulp.LpMaximize)
    p = {c.ID: pulp.LpVariable(f"p_{c.ID}", lowBound=0, upBound=1) for c in active}
    z = pulp.LpVariable("z", lowBound=0, upBound=1)
    prob += z

    prob += pulp.lpSum(p.values()) == panel_size, "panel_size"
    for c in active:
        prob += p[c.ID] >= z, f"min_{c.ID}"

    for q, (lo, hi) in zip(quotas, bounds):
        in_q = [p[c.ID] for c in active if _candidate_in_quota(c, q)]
        if not in_q:
            continue
        prob += pulp.lpSum(in_q) >= lo, f"lo_{q.feature}_{q.value}"
        prob += pulp.lpSum(in_q) <= hi, f"hi_{q.feature}_{q.value}"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    status_name = pulp.LpStatus.get(status, str(status))
    if status_name != "Optimal":
        raise RuntimeError(f"LP did not solve to optimality: {status_name}")

    probs = {cid: float(pulp.value(var) or 0.0) for cid, var in p.items()}
    return probs, float(pulp.value(z) or 0.0), status_name


def _sample_with_repair(
    active: list[Candidate],
    probabilities: dict[str, float],
    quotas: list[Quota],
    bounds: list[tuple[int, int]],
    panel_size: int,
    rng: random.Random,
    max_attempts: int = 200,
) -> list[Candidate]:
    for _ in range(max_attempts):
        panel = [c for c in active if rng.random() < probabilities.get(c.ID, 0.0)]
        outside = [c for c in active if c not in panel]
        while len(panel) > panel_size:
            panel.sort(key=lambda c: probabilities.get(c.ID, 0.0))
            outside.append(panel.pop(0))
        while len(panel) < panel_size:
            outside.sort(key=lambda c: -probabilities.get(c.ID, 0.0))
            panel.append(outside.pop(0))

        counts = _quota_counts(panel, quotas)
        for _ in range(500):
            v = _violations(counts, bounds)
            if not v:
                return panel
            i = v[0]
            q = quotas[i]
            lo, hi = bounds[i]
            cnt = counts[i]
            if cnt < lo:
                cand_in = [c for c in panel if not _candidate_in_quota(c, q)]
                cand_out = [c for c in outside if _candidate_in_quota(c, q)]
            else:
                cand_in = [c for c in panel if _candidate_in_quota(c, q)]
                cand_out = [c for c in outside if not _candidate_in_quota(c, q)]
            if not cand_in or not cand_out:
                break
            best = None
            for ci in cand_in:
                for co in cand_out:
                    new_panel = [c for c in panel if c is not ci] + [co]
                    nv = len(_violations(_quota_counts(new_panel, quotas), bounds))
                    if best is None or nv < best[0]:
                        best = (nv, ci, co)
            if best is None:
                break
            _, ci, co = best
            panel = [c for c in panel if c is not ci] + [co]
            outside = [c for c in outside if c is not co] + [ci]
            counts = _quota_counts(panel, quotas)
        if not _violations(counts, bounds):
            return panel

    raise RuntimeError(
        "Could not produce a panel that respects all quotas after "
        f"{max_attempts} attempts. Loosen the quota intervals."
    )


def select_panel(
    candidates: list[Candidate],
    quotas: list[Quota],
    panel_size: int,
    seed: int,
    excluded_ids: set[str] | None = None,
) -> SelectionResult:
    excluded_ids = excluded_ids or set()
    active = [c for c in candidates if c.ID not in excluded_ids]
    if len(active) < panel_size:
        raise ValueError(
            f"only {len(active)} candidates available for a panel of {panel_size}"
        )

    bounds, log = _effective_bounds(active, quotas, panel_size)
    probs, z, status = _solve_maximin(active, quotas, bounds, panel_size)
    rng = random.Random(seed)
    panel = _sample_with_repair(active, probs, quotas, bounds, panel_size, rng)

    realised: dict[tuple[str, str], int] = defaultdict(int)
    for c in panel:
        for f, v in c.attrs.items():
            realised[(f, v)] += 1
    return SelectionResult(
        panel=panel,
        probabilities=probs,
        minimum_probability=z,
        realised_marginals=dict(realised),
        solver_status=status,
        effective_bounds=bounds,
        relaxations=log,
    )
