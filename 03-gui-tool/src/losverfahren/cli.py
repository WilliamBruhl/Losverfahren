"""Command-line entry point.

CSV (recommended)::

    losverfahren draw \\
        --candidates 03-gui-tool/sample-data/candidates.csv \\
        --population 03-gui-tool/sample-data/population.csv \\
        --panel-size 30 --substitutes 30 --seed 20260527 \\
        --output 03-gui-tool/result.xlsx

Legacy Excel inputs (``PBD_Losung-Template.xlsx``) are still accepted; the
format is detected by file extension.

In addition to the .xlsx result, a JSON file with the same stem is written
(``result.json``) containing the canonical panel, all hashes and a
``run_hash`` that two independent re-runs with the same inputs + seed must
agree on.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .io_csv import (
    read_candidates_csv,
    read_joint_population_csv,
    read_population_csv,
    write_result_json,
)
from .io_excel import read_candidates, read_population_marginals, write_result_workbook
from .manifest import build_manifest, manifest_audit_rows
from .quotas import default_joint_quotas, default_quotas
from .selection import select_panel


def _load_candidates(path: Path):
    if path.suffix.lower() == ".csv":
        return read_candidates_csv(path)
    return read_candidates(path)


def _load_population(path: Path):
    if path.suffix.lower() == ".csv":
        marginals, warnings = read_population_csv(path)
        for w in warnings:
            print(f"  warn: {w}")
        return marginals
    return read_population_marginals(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="losverfahren")
    sub = parser.add_subparsers(dest="cmd", required=True)

    draw = sub.add_parser("draw", help="Draw a panel from a candidate file.")
    draw.add_argument("--candidates", type=Path, required=True,
                      help="Path to candidates .csv or .xlsx")
    draw.add_argument("--population", type=Path, required=True,
                      help="Path to population .csv or .xlsx")
    draw.add_argument("--joint", type=Path, default=None,
                      help="Optional joint population CSV (e.g. Geschlecht×Alter×Kanton)")
    draw.add_argument("--panel-size", type=int, default=30)
    draw.add_argument("--substitutes", type=int, default=30)
    draw.add_argument("--seed", type=int, default=20260527)
    draw.add_argument("--output", type=Path, required=True,
                      help="Output .xlsx (a sibling .json manifest is also written)")

    args = parser.parse_args(argv)
    if args.cmd != "draw":
        parser.print_help()
        return 1

    print(f"Reading candidates from {args.candidates} …")
    candidates = _load_candidates(args.candidates)
    print(f"  {len(candidates)} candidates")

    print(f"Reading population from {args.population} …")
    population = _load_population(args.population)
    quotas = default_quotas(population, args.panel_size)

    joint_loaded: list = []
    if args.joint is not None:
        print(f"Reading joint population from {args.joint} …")
        joint_loaded, jw = read_joint_population_csv(args.joint)
        for w in jw:
            print(f"  warn: {w}")
        quotas = quotas + default_joint_quotas(joint_loaded, args.panel_size)
        print(f"  {len(joint_loaded)} joint cells")
    print(f"  {len(quotas)} quota intervals total")

    print("Solving members …")
    members = select_panel(candidates, quotas, args.panel_size, seed=args.seed)
    print(f"  status: {members.solver_status}, min p_i = {members.minimum_probability:.4f}")
    for r in members.relaxations:
        print(f"  relaxation: {r}")

    substitutes = None
    if args.substitutes > 0:
        print("Solving substitutes …")
        member_ids = {c.ID for c in members.panel}
        sub_quotas = default_quotas(population, args.substitutes)
        if joint_loaded:
            sub_quotas = sub_quotas + default_joint_quotas(joint_loaded, args.substitutes)
        try:
            substitutes = select_panel(
                candidates, sub_quotas, args.substitutes, seed=args.seed + 1,
                excluded_ids=member_ids,
            )
        except RuntimeError as e:
            if joint_loaded:
                print(f"  joint quotas infeasible for substitutes ({e}); "
                      "retrying with marginals only")
                sub_quotas = default_quotas(population, args.substitutes)
                substitutes = select_panel(
                    candidates, sub_quotas, args.substitutes, seed=args.seed + 1,
                    excluded_ids=member_ids,
                )
            else:
                raise
        print(f"  status: {substitutes.solver_status}, "
              f"min p_i = {substitutes.minimum_probability:.4f}")
        for r in substitutes.relaxations:
            print(f"  relaxation: {r}")

    manifest = build_manifest(
        seed=args.seed,
        panel_size_members=args.panel_size,
        panel_size_substitutes=args.substitutes,
        candidates=candidates,
        population=population,
        quotas=quotas,
        members=members,
        substitutes=substitutes,
        inputs={"candidates": str(args.candidates),
                "population": str(args.population)},
    )
    audit_rows = manifest_audit_rows(manifest)

    out_xlsx: Path = args.output
    src_for_writer = args.candidates if args.candidates.suffix.lower() == ".xlsx" else None
    write_result_workbook(
        src_path=src_for_writer,
        out_path=out_xlsx,
        members=members.panel,
        substitutes=substitutes.panel if substitutes else [],
        probabilities=members.probabilities,
        audit_rows=audit_rows,
    )
    print(f"Wrote {out_xlsx}")

    out_json = out_xlsx.with_suffix(".json")
    write_result_json(out_json, manifest)
    print(f"Wrote {out_json}")
    print(f"  run_hash: {manifest['run_hash']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
