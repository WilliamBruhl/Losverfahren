# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stratified sortition prototype.

This package implements a small fair-selection pipeline for citizen panels:

* :mod:`losverfahren.models` defines the plain :class:`~models.Candidate`
  data class shared across the package.
* :mod:`losverfahren.io_csv` reads/writes the primary CSV inputs.
* :mod:`losverfahren.io_excel` reads the legacy PBD workbook format and
  writes a result workbook.
* :mod:`losverfahren.quotas` derives per-attribute quota intervals from a
  population reference.
* :mod:`losverfahren.selection` solves a maximin LP to assign a marginal
  selection probability to every willing candidate, then samples a panel
  that respects every quota.
* :mod:`losverfahren.manifest` builds the canonical JSON + SHA-256
  ``run_hash`` used for audit.
* :mod:`losverfahren.cli` exposes the pipeline as a single command.
* :mod:`losverfahren.app` is the Streamlit UI on top.
"""

__all__ = ["models", "io_csv", "io_excel", "quotas", "selection", "manifest"]
