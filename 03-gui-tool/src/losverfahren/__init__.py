"""Stratified sortition prototype.

This package implements a small fair-selection pipeline for citizen panels:

* :mod:`losverfahren.io_excel` reads the existing workbook format and writes
  a result workbook in the same shape.
* :mod:`losverfahren.quotas` derives per-attribute quota intervals from a
  population reference.
* :mod:`losverfahren.selection` solves a maximin LP to assign a marginal
  selection probability to every willing candidate, then samples a panel
  that respects every quota.
* :mod:`losverfahren.audit` produces a reproducibility record.
* :mod:`losverfahren.cli` exposes the pipeline as a single command.
* :mod:`losverfahren.app` is the Streamlit UI on top.
"""

__all__ = ["io_excel", "quotas", "selection", "audit"]
