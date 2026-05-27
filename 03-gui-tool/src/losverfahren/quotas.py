"""Quota intervals per feature value.

Given a panel size ``k`` and population shares ``π``, the default quota for a
feature value ``v`` is

    lo = floor(k · π_v)
    hi = ceil(k · π_v)

These intervals keep the underlying LP feasible even when individual cells
are empty in the candidate pool. The user can override them in the UI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Quota:
    feature: str
    value: str
    share: float
    lo: int
    hi: int


def default_quotas(
    population: dict[str, dict[str, float]], panel_size: int
) -> list[Quota]:
    out: list[Quota] = []
    for feature, shares in population.items():
        for value, share in shares.items():
            target = panel_size * share
            out.append(
                Quota(
                    feature=feature,
                    value=value,
                    share=share,
                    lo=int(math.floor(target)),
                    hi=int(math.ceil(target)),
                )
            )
    return out


def default_joint_quotas(
    joint_shares: list[tuple[dict[str, str], float]], panel_size: int
) -> list[Quota]:
    """Build joint quotas from ``[(criteria_dict, share), …]``.

    The resulting :class:`Quota` encodes the joint criterion via the
    convention ``feature = "F1×F2×…"`` and ``value = "v1|v2|…"``.
    """
    out: list[Quota] = []
    for criteria, share in joint_shares:
        feature = "×".join(criteria.keys())
        value = "|".join(criteria.values())
        target = panel_size * share
        out.append(
            Quota(
                feature=feature,
                value=value,
                share=share,
                lo=int(math.floor(target)),
                hi=int(math.ceil(target)),
            )
        )
    return out


def quotas_as_rows(quotas: list[Quota]) -> list[dict]:
    return [
        {
            "feature": q.feature,
            "value": q.value,
            "share": round(q.share, 4),
            "lo": q.lo,
            "hi": q.hi,
        }
        for q in quotas
    ]


def quotas_from_rows(rows: list[dict]) -> list[Quota]:
    return [
        Quota(
            feature=str(r["feature"]),
            value=str(r["value"]),
            share=float(r.get("share", 0.0) or 0.0),
            lo=int(r["lo"]),
            hi=int(r["hi"]),
        )
        for r in rows
    ]
