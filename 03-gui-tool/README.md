# 03 — Stand‑alone GUI Tool (prototype)

A small Python package that implements the maximin stratified sortition idea
from Flanigan et al. (2021) end‑to‑end. It runs entirely on its own — there
is **no dependency on the legacy Excel workbook** in `01-existing-implementation/`.

The default workflow uses two flat CSVs that any admin user can edit in a
spreadsheet:

* `sample-data/candidates.csv` — one row per candidate, columns `ID,
  Geschlecht, Alterskategorie, Kanton, Ausbildung, Profil`.
* `sample-data/population.csv` — long format with **raw counts**:
  `feature, value, count, note`. One row per feature value. The tool
  derives shares per feature automatically, so admin staff can paste the
  Bevölkerungs-Tabelle as-is and don't have to calculate percentages.
  A `share` column is also accepted as a fallback if no count is given.
  The `note` column is free text (e.g. *"Stand 2022, Update ausstehend"*) and
  is carried through to the audit.
* `sample-data/population_joint.csv` *(optional but recommended)* — the full
  joint Bevölkerungsstruktur as `Geschlecht, Alterskategorie, Kanton, count`.
  When provided, the LP additionally constrains each of the 12 joint cells,
  so the panel reflects the cross-tab and not just the marginals.

The legacy `PBD_Losung-Template.xlsx` layout is still accepted by the
loader for backwards compatibility, but it is **no longer required**.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e 03-gui-tool
```

Brings in `openpyxl`, `pandas`, `pulp` (with bundled CBC) and `streamlit`.

## CLI

```bash
losverfahren draw \
  --candidates 03-gui-tool/sample-data/candidates.csv \
  --population 03-gui-tool/sample-data/population.csv \
  --joint      03-gui-tool/sample-data/population_joint.csv \
  --panel-size 30 --substitutes 30 \
  --seed 20260527 \
  --output 03-gui-tool/result.xlsx
```

`--joint` is optional. If the substitute draw becomes infeasible with the
joint cells enforced (typical after the member draw has thinned a small
pool), the CLI **falls back to marginal-only quotas** for the substitutes
and logs that fact in the run output.

Two files are written:

* `result.xlsx` — workbook with the drawn members + substitutes, per‑candidate
  selection probability, and a full audit sheet.
* `result.json` — canonical JSON manifest with a SHA‑256 `run_hash` that two
  independent re-runs on the same inputs + seed are guaranteed to agree on.

## Streamlit UI

Local development:

```bash
streamlit run 03-gui-tool/src/losverfahren/app.py
```

For deployment (Streamlit Community Cloud), use the entry point at the
repo root:

```bash
streamlit run streamlit_app.py
```

Both paths resolve `sample-data/` automatically, so the "Beispiel-Daten
verwenden" radio works in either layout.

## Deployment to Streamlit Community Cloud

1. Push the repo to GitHub.
2. On https://share.streamlit.io point a new app at this repo.
3. Set **Main file path** to `streamlit_app.py`.
4. Python dependencies are read from the root `requirements.txt`; the
   runtime is pinned via `runtime.txt`.

No editable install is required: `streamlit_app.py` puts the bundled
`losverfahren` package on `sys.path` and re-runs the actual app file.

The UI:

1. Loads the sample CSVs (or accepts uploaded ones).
2. Shows the candidate list.
3. Lets the admin user **edit the population shares directly** in a table —
   any change immediately re-derives the quota intervals.
4. Runs the draw and shows:
   * panel size, min p_i, run_hash badge,
   * a prominent panel listing every quota relaxation (or a green note when
     none was needed),
   * tabs for members, substitutes, quota vs. realised counts, marginal
     probabilities, and the full audit + hash table,
   * download buttons for the `.xlsx` workbook and the `.json` manifest.

A `.streamlit/config.toml` at the repo root disables usage telemetry so the
welcome email prompt does not appear.

## Output formats

| File | Purpose |
|---|---|
| `result.xlsx` | Human‑readable workbook, audit sheet included. Suitable for archiving alongside today's Excel artefacts. |
| `result.json` | Machine‑readable canonical record. Contains the candidate list, population shares, quotas, both panels, all SHA‑256 component hashes, and a single `run_hash`. |

The `run_hash` is the SHA‑256 of a canonical JSON containing the seed, the
parameters, and the SHA‑256 of every component (candidates, population,
quotas, members, substitutes). If anyone tampers with a value, the recomputed
`run_hash` will not match — that is the integrity guarantee for audit.

## How the algorithm works

Let $k$ be the panel size and $C$ the set of willing candidates. For each
feature value $v$ of feature $f$ let $\pi_{f,v}$ be the population share
and $S_{f,v} \subseteq C$ the candidates carrying that value.

1. **Decision variables:** $p_i \in [0,1]$ for every $i \in C$.
2. **Panel size:** $\sum_{i \in C} p_i = k$.
3. **Quota intervals:**
   $\lfloor k\pi_{f,v}\rfloor \le \sum_{i \in S_{f,v}} p_i \le \lceil k\pi_{f,v}\rceil$.
4. **Maximin objective:** maximise $\min_i p_i$ (linear via an auxiliary
   $z$ with $p_i \ge z$).

If a feature's intervals cannot be honoured because some buckets are short
of candidates (typical on the substitute pool after the member draw), the
bounds are **relaxed per feature**: hi is raised up to availability, then lo
is lowered, until `Σ lo ≤ k ≤ Σ hi` again. Every individual relaxation step
is recorded in `relaxations[]` and surfaced in the UI banner, the CLI output,
the audit sheet, and the JSON manifest.

The resulting $\{p_i\}$ are then sampled via Bernoulli draws, snapped back to
size $k$, and **repaired by swaps** until every quota interval holds.

## Editing the framing data

`sample-data/population.csv` is the single source of truth for population
shares. Admin staff can update it in any spreadsheet editor — feature by
feature, row by row — and re-run the draw. The UI editor mirrors the same
table and writes any in-session changes through to the solver.

Both the **default** and the **effective** quota intervals end up in the
manifest, so any later relaxation is fully traceable to (a) the population
file at the time of the run and (b) the candidate pool at the time of the
run.

## Folder layout

```
03-gui-tool/
├── README.md                      (this file)
├── pyproject.toml                 (package definition + dependencies)
├── result.xlsx                    (sample output)
├── result.json                    (sample manifest)
├── sample-data/
│   ├── candidates.csv             (71 example candidates)
│   └── population.csv             (population shares in long format)
└── src/losverfahren/
    ├── __init__.py
    ├── io_csv.py                  (CSV reader/writer — primary path)
    ├── io_excel.py                (legacy xlsx reader + xlsx result writer)
    ├── quotas.py                  (quota intervals from population shares)
    ├── selection.py               (maximin LP + quota‑aware sampler)
    ├── audit.py                   (legacy audit rows; superseded by manifest)
    ├── manifest.py                (canonical JSON + SHA‑256 run_hash)
    ├── cli.py                     (argparse entry point: `losverfahren draw`)
    └── app.py                     (Streamlit UI)
```

## Reuse instead of reinventing

The Sortition Foundation's
[stratification‑app](https://github.com/sortitionfoundation/stratification-app)
(MIT) ships a more mature LEXIMIN implementation with proper dependent
rounding; the same group runs [Panelot](https://panelot.org). For a
production deployment it would be worth swapping the LP + sampler in
`selection.py` for that library and keeping only the I/O + UI layer here.
The current prototype is small enough to read end‑to‑end and to validate
the workflow on the bundled sample data.

## What's intentionally not in here yet

- Dependent rounding (the current sampler may need a few swap attempts on
  tight pools — every iteration is logged).
- PDF audit export — the audit lives on a sheet of the result workbook and
  in the JSON manifest, which is enough for archival.
- Persistence of edited quotas across UI sessions.
- A test suite beyond the deterministic CLI smoke run.
