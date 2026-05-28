# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plain data classes shared across the package.

Kept in a dedicated module so the CSV-first I/O path does not have to
import from ``io_excel`` just to obtain the :class:`Candidate` type.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    """One candidate with an arbitrary set of stratification attributes.

    ``attrs`` is the source of truth (a flat ``feature → value`` dict). Any
    column name in ``candidates.csv`` other than ``ID`` is preserved here
    verbatim, so adding a new field such as ``Beruf`` requires no code
    change.
    """

    ID: str
    attrs: dict[str, str] = field(default_factory=dict)
