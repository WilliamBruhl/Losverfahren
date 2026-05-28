# SPDX-License-Identifier: AGPL-3.0-or-later
"""Streamlit UI for the Losverfahren prototype.

Run with::

    streamlit run 03-gui-tool/src/losverfahren/app.py

The app is intentionally self-contained: it expects CSV inputs in the
``sample-data/`` shape (candidates.csv + population.csv) but also accepts a
legacy ``PBD_Losung-Template.xlsx`` workbook for backwards compatibility.
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

# Make the script runnable both via `streamlit run path/to/app.py` and via
# `python -m losverfahren.app` by ensuring the package is importable.
_PKG_PARENT = Path(__file__).resolve().parents[1]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from losverfahren.io_csv import (  # noqa: E402
    _read_csv_normalised,
    read_candidates_csv,
    read_joint_population_csv,
    read_population_csv,
)
from losverfahren.io_excel import (  # noqa: E402
    read_candidates,
    read_population_marginals,
    write_result_workbook,
)
from losverfahren.manifest import build_manifest, manifest_audit_rows  # noqa: E402
from losverfahren.quotas import Quota, default_joint_quotas, default_quotas  # noqa: E402
from losverfahren.selection import _candidate_in_quota, select_panel  # noqa: E402


# Look for sample-data next to the package (works whether the app is run from
# the repo root, from inside ``03-gui-tool/``, or from a deployment image).
_HERE = Path(__file__).resolve()
for _candidate in (
    _HERE.parents[2] / "sample-data",       # 03-gui-tool/sample-data
    _HERE.parents[3] / "03-gui-tool" / "sample-data",  # repo-root deployment
    _HERE.parents[3] / "sample-data",
):
    if _candidate.exists():
        SAMPLE_DIR = _candidate
        break
else:
    SAMPLE_DIR = _HERE.parents[2] / "sample-data"

# Same discovery for the curated test-data bundles (Wallonia, UK, town
# council). The folder lives next to ``sample-data``.
TESTDATA_DIR: Path | None = None
for _candidate in (
    SAMPLE_DIR.parent / "test-data",
    _HERE.parents[2] / "test-data",
    _HERE.parents[3] / "03-gui-tool" / "test-data",
):
    if _candidate.exists():
        TESTDATA_DIR = _candidate
        break


def _discover_examples() -> dict[str, Path]:
    """Map a human label to a directory containing candidates+population CSVs."""
    # Pretty German labels for the bundled folders; fall back to the
    # directory name for anything else dropped into ``test-data/``.
    pretty = {
        "wallonia-fr": "Wallonie — Assemblée citoyenne (FR)",
        "uk-climate-en": "UK — Climate Assembly (EN)",
        "town-council-de": "Kleiner Bürgerrat — Beispielgemeinde (DE)",
    }
    out: dict[str, Path] = {}
    if SAMPLE_DIR.exists() and (SAMPLE_DIR / "candidates.csv").exists():
        out["PBD-Vorlage (DE, eingebaut)"] = SAMPLE_DIR
    if TESTDATA_DIR is not None:
        for sub in sorted(TESTDATA_DIR.iterdir()):
            if sub.is_dir() and (sub / "candidates.csv").exists() \
                    and (sub / "population.csv").exists():
                out[pretty.get(sub.name, sub.name)] = sub
    return out

st.set_page_config(page_title="Losverfahren — Bürgerpanel", layout="wide")
st.title("Losverfahren — geschichtete Zufallsauswahl")
st.caption(
    "Prototyp: Maximin-LP + Quoten-konformes Sampling. "
    "Inputs sind editierbare CSVs; jede Anpassung der Bevölkerungs-Daten "
    "und jede Quoten-Relaxation wird im Audit dokumentiert."
)

with st.expander("Datenformat (Spalten und Beispiel-Zeilen)", expanded=False):
    st.markdown(
        "Drei CSV-Dateien werden unterstützt — alle UTF-8, Komma-getrennt, "
        "erste Zeile ist die Kopfzeile. Excel-Templates (`.xlsx`) im alten "
        "PBD-Format werden weiterhin akzeptiert.\n\n"
        "### Flexible Schemata\n"
        "Die Merkmale (Geschlecht, Alter, Kanton, Beruf, …) sind **nicht "
        "fest verdrahtet**: du kannst beliebige Spalten in `candidates.csv` "
        "verwenden, solange die gleichen Namen auch in `population.csv` als "
        "`feature`-Werte auftauchen. Sprache und Spaltenzahl sind frei.\n\n"
        "Auch die Spalten-Kopfzeile selbst toleriert Synonyme — z.B. "
        "`Anzahl` statt `count`, `Anteil` statt `share`, `Merkmal` statt "
        "`feature`, `Wert` statt `value`, `Bemerkung` statt `note`, "
        "`Nummer` statt `ID` (Liste nicht abschließend).\n\n"
        "**1 · `candidates.csv` (Pflicht)** — eine Zeile pro Person.\n\n"
        "```\n"
        "ID,Geschlecht,Alterskategorie,Kanton,Ausbildung\n"
        "K001,Mann,36-55,Nord,AbiturMeister\n"
        "K002,Frau,16-35,Süd,DualBachelor\n"
        "```\n"
        "Jede Spalte außer `ID` ist ein Stratifizierungs-Merkmal. Zusätzliche "
        "deskriptive Spalten (z.B. `Email`) werden mitgeführt, aber nur "
        "für Quoten verwendet, wenn sie auch in `population.csv` vorkommen.\n\n"
        "**2 · `population.csv` (Pflicht, Marginalen)** — eine Zeile pro "
        "Merkmals-Ausprägung. Bevorzugt mit Spalte `count` (Personenzahl); "
        "`share` (Anteil 0–1) wird ebenfalls akzeptiert. `note` ist frei.\n\n"
        "```\n"
        "feature,value,count,note\n"
        "Geschlecht,Mann,31982,\n"
        "Geschlecht,Frau,32640,\n"
        "Alterskategorie,16-35,18223,Stand 2024\n"
        "```\n\n"
        "**3 · `population_joint.csv` (optional, gemeinsame Verteilung)** — "
        "eine Zeile pro Kombination. Beliebig viele Dimensions-Spalten plus "
        "`count` (oder `share`).\n\n"
        "```\n"
        "Geschlecht,Alterskategorie,Kanton,count\n"
        "Mann,16-35,Nord,5612\n"
        "Frau,56+,Süd,4933\n"
        "```\n\n"
        "**Brauche ich Datei 3?** Nein — die Marginalen aus Datei 2 reichen "
        "für eine korrekte Auslosung. Die Joint-Datei sorgt dafür, dass auch "
        "die *Kombinationen* (z.B. „junge Männer im Norden“) im Panel "
        "realistisch vertreten sind. Bei kleinem Kandidatenpool kann sie "
        "die Auslosung verschärfen; das Tool fällt dann automatisch auf die "
        "Marginalen zurück und vermerkt das."
    )


# ---------------------------------------------------------------- helpers
def _save_upload(upload, suffix: str) -> Path:
    tmp = Path(tempfile.mkdtemp()) / f"{upload.name}"
    tmp.write_bytes(upload.getbuffer())
    return tmp


def _load_candidates_any(path: Path):
    if path.suffix.lower() == ".csv":
        cands, warnings = read_candidates_csv(path)
        return cands, warnings
    return read_candidates(path), []


def _load_population_any(path: Path):
    if path.suffix.lower() == ".csv":
        return read_population_csv(path)  # (dict, warnings)
    return read_population_marginals(path), []


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("1 · Eingaben")

    source = st.radio(
        "Quelle",
        ["Beispiel-Daten verwenden", "Eigene Dateien hochladen"],
        index=0,
        help=(
            "Beispiel-Daten: bündelte CSVs aus dem mitgelieferten "
            "PBD-Template. Eigene Dateien: zwei (oder drei) CSVs "
            "im selben Format hochladen."
        ),
    )

    cand_path: Path | None = None
    pop_path: Path | None = None
    joint_path: Path | None = None

    if source == "Beispiel-Daten verwenden":
        examples = _discover_examples()
        if not examples:
            st.error("Keine Beispiel-Datensätze gefunden.")
            st.stop()
        labels = list(examples.keys())
        choice = st.selectbox(
            "Beispiel-Datensatz",
            labels,
            index=0,
            help=(
                "Drei kuratierte Datensätze plus die PBD-Vorlage. Jeder "
                "demonstriert ein anderes Schema/eine andere Sprache — "
                "die Tool-Logik passt sich automatisch an."
            ),
        )
        chosen_dir = examples[choice]
        cand_path = chosen_dir / "candidates.csv"
        pop_path = chosen_dir / "population.csv"
        joint_candidate = chosen_dir / "population_joint.csv"
        joint_path = joint_candidate if joint_candidate.exists() else None
        if not cand_path.exists():
            st.error(f"Beispiel-Daten nicht gefunden unter {chosen_dir}")
            st.stop()
        readme = chosen_dir / "README.md"
        if readme.exists():
            with st.expander("Datensatz-Beschreibung", expanded=False):
                st.markdown(readme.read_text(encoding="utf-8"))
        joint_note = "" if joint_path is None else " + Joint-Verteilung"
        st.success(f"Geladen: **{choice}**{joint_note}")
    else:
        cand_up = st.file_uploader(
            "Kandidatenliste (.csv oder .xlsx)", type=["csv", "xlsx"], key="cand"
        )
        pop_up = st.file_uploader(
            "Bevölkerungsstruktur — Marginalen (.csv oder .xlsx)",
            type=["csv", "xlsx"], key="pop"
        )
        joint_up = st.file_uploader(
            "Bevölkerungsstruktur — Joint-Verteilung (optional, .csv)",
            type=["csv"], key="joint",
            help=(
                "Optional. Eine zusätzliche CSV mit der gemeinsamen Verteilung "
                "mehrerer Merkmale (z.B. Geschlecht × Alterskategorie × "
                "Kanton). Liefert reichere Information als die Marginalen "
                "alleine — wird automatisch zugeschaltet, sobald hochgeladen. "
                "Format siehe »Datenformat« im Hauptbereich."
            ),
        )
        if cand_up is None or pop_up is None:
            st.info("Mindestens Kandidaten und Marginalen hochladen, um fortzufahren.")
            st.stop()
        cand_path = _save_upload(cand_up, cand_up.name)
        pop_path = _save_upload(pop_up, pop_up.name)
        joint_path = _save_upload(joint_up, joint_up.name) if joint_up else None

    use_joint = st.checkbox(
        "Joint-Quoten zusätzlich erzwingen",
        value=joint_path is not None,
        disabled=joint_path is None,
        help=(
            "Wenn aktiviert, werden zusätzlich Quoten für jede Zelle der "
            "joint Verteilung an die LP übergeben. Sonst werden nur die "
            "Marginalen verwendet. Wird automatisch aktiviert, sobald eine "
            "Joint-CSV vorhanden ist."
        ),
    )

    st.header("2 · Parameter")
    panel_size = st.number_input("Panelgröße", 5, 200, 30, 1)
    n_subs = st.number_input("Ersatzpersonen", 0, 200, 30, 1)
    seed = st.number_input("Seed", 0, 2**31 - 1, 20260527, 1)
    run = st.button("Auslosung starten", type="primary")


# ---------------------------------------------------------------- data load
def _fail(msg: str, exc: Exception) -> None:
    st.error(f"**{msg}**\n\n`{type(exc).__name__}: {exc}`")
    st.stop()

try:
    candidates, cand_warnings = _load_candidates_any(cand_path)
except Exception as e:  # noqa: BLE001
    _fail(
        "Kandidatenliste konnte nicht gelesen werden. Mindestens eine Spalte "
        "`ID` (oder ein Synonym wie `Nummer`, `Code`) plus eine "
        "Stratifizierungs-Spalte sind erforderlich.",
        e,
    )

try:
    population_loaded, pop_warnings = _load_population_any(pop_path)
except Exception as e:  # noqa: BLE001
    _fail(
        "Bevölkerungs-Marginalen konnten nicht gelesen werden. Erwartet wird "
        "eine CSV mit Spalten `feature, value, count` (oder `share`); "
        "optional `note`.",
        e,
    )

# Read the same population file as a raw DataFrame for the editor — this
# preserves the admin-friendly count and note columns even though the solver
# only needs normalised shares.
def _read_pop_raw(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        # Use the same alias-aware reader as the solver so headers like
        # `Merkmal/Wert/Anzahl/Bemerkung` map to feature/value/count/note.
        rows, _fields, _warnings = _read_csv_normalised(path)
        df = pd.DataFrame(rows)
    else:
        # Legacy xlsx path: synthesise a DataFrame from the marginals.
        rows = []
        for feat, d in population_loaded.items():
            for v, s in d.items():
                rows.append({"feature": feat, "value": v, "share": s})
        df = pd.DataFrame(rows)
    for col in ("feature", "value", "note"):
        if col not in df.columns:
            df[col] = ""
        # Force string dtype — otherwise pandas may infer INTEGER for a
        # `value` column that happens to contain only digit strings, which
        # Streamlit's TextColumn / SelectboxColumn then refuse to render.
        df[col] = df[col].fillna("").astype(str)
    for col in ("count", "share"):
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["feature", "value", "count", "share", "note"]]

try:
    raw_pop_df = _read_pop_raw(pop_path)
except Exception as e:  # noqa: BLE001
    _fail("Bevölkerungs-CSV ließ sich nicht in eine Tabelle laden.", e)

joint_loaded: list[tuple[dict[str, str], float]] = []
joint_warnings: list[str] = []
raw_joint_df: pd.DataFrame | None = None
if joint_path is not None:
    try:
        joint_loaded, joint_warnings = read_joint_population_csv(joint_path)
        if joint_path.suffix.lower() == ".csv":
            _jrows, _jfields, _ = _read_csv_normalised(joint_path)
            raw_joint_df = pd.DataFrame(_jrows)
            # Force every non-numeric dimension column to string so dropdowns
            # render even when values look numeric (e.g. age band "18").
            for _col in raw_joint_df.columns:
                if _col in ("count", "share"):
                    raw_joint_df[_col] = pd.to_numeric(
                        raw_joint_df[_col], errors="coerce")
                else:
                    raw_joint_df[_col] = raw_joint_df[_col].fillna("").astype(str)
        else:
            raw_joint_df = None
    except Exception as e:  # noqa: BLE001
        st.warning(
            "Joint-Bevölkerungs-CSV konnte nicht gelesen werden — die "
            f"Auslosung läuft nur mit den Marginalen weiter. Details: "
            f"`{type(e).__name__}: {e}`"
        )
        joint_path = None
        joint_loaded = []

st.subheader("Kandidaten (editierbar)")

# Discover the active schema from the data on disk.
cand_attr_cols: list[str] = []
_seen: set[str] = set()
for _c in candidates:
    for _k in _c.attrs.keys():
        if _k not in _seen:
            cand_attr_cols.append(_k)
            _seen.add(_k)
pop_features = list(population_loaded.keys())
active_features = [f for f in cand_attr_cols if f in pop_features]
metadata_only = [f for f in cand_attr_cols if f not in pop_features]
missing_in_candidates = [f for f in pop_features if f not in cand_attr_cols]

with st.expander("Erkanntes Schema", expanded=False):
    st.markdown(
        f"- **Aktive Merkmale (Quoten)**: "
        + (", ".join(f"`{x}`" for x in active_features) or "_keine_")
    )
    if metadata_only:
        st.markdown(
            "- **Nur deskriptiv** (in Kandidaten, nicht in Bevölkerung): "
            + ", ".join(f"`{x}`" for x in metadata_only)
        )
    if missing_in_candidates:
        st.warning(
            "In `population.csv` definierte Merkmale, die in `candidates.csv` "
            "fehlen — sie können nicht als Quote benutzt werden: "
            + ", ".join(f"`{x}`" for x in missing_in_candidates)
        )
    if cand_warnings:
        for w in cand_warnings:
            st.info(w)

if not active_features:
    st.error(
        "Keine überlappenden Merkmale zwischen `candidates.csv` und "
        "`population.csv` gefunden. Bitte sicherstellen, dass beide Dateien "
        "die gleichen Spalten-/`feature`-Namen verwenden (groß-/kleinschrift- "
        "und akzentempfindlich)."
    )
    st.stop()

# Build the candidate DataFrame with per-feature dropdown options.
cand_rows = [{"ID": c.ID, **{k: c.attrs.get(k, "") for k in cand_attr_cols}}
             for c in candidates]
raw_cand_df = pd.DataFrame(cand_rows)
for col in raw_cand_df.columns:
    raw_cand_df[col] = raw_cand_df[col].fillna("").astype(str)

# Allowed values per active feature come from population.csv — those are the
# canonical, admin-defined values. A dropdown then proposes exactly the same
# values that the quotas know about. Values currently used in candidates but
# not yet in population are included so an existing entry stays editable.
feature_options: dict[str, list[str]] = {}
for feat in active_features:
    opts = set(population_loaded.get(feat, {}).keys())
    opts.update(
        str(v).strip() for v in raw_cand_df[feat].tolist() if str(v).strip()
    )
    feature_options[feat] = sorted(opts)

cand_col_config: dict = {"ID": st.column_config.TextColumn(
    "ID", help="Eindeutige Kandidaten-Kennung.", required=True)}
for feat in cand_attr_cols:
    if feat in feature_options:
        cand_col_config[feat] = st.column_config.SelectboxColumn(
            feat, options=feature_options[feat],
            help=(f"Werte stammen aus `population.csv` / bereits vorhandenen "
                  f"Einträgen. Neue Ausprägungen zuerst in der "
                  f"Bevölkerungs-Tabelle anlegen."),
        )
    else:
        cand_col_config[feat] = st.column_config.TextColumn(
            feat, help="Nur deskriptiv — wird für Quoten nicht verwendet."
        )

st.write(f"{len(candidates)} Kandidaten geladen.")
edited_cand_df = st.data_editor(
    raw_cand_df, width='stretch', height=320, num_rows="dynamic",
    key="cand_editor", column_config=cand_col_config,
)

# Rebuild the candidate list from the edited table.
candidates = []
for _, row in edited_cand_df.iterrows():
    cid = str(row.get("ID") or "").strip()
    if not cid:
        continue
    attrs = {
        col: str(row[col]).strip()
        for col in cand_attr_cols
        if str(row.get(col) or "").strip()
    }
    from losverfahren.io_excel import Candidate  # local import to avoid cycle confusion
    candidates.append(Candidate(ID=cid, attrs=attrs))


# ---------------------------------------------------------------- population editor
st.subheader("Bevölkerungsstruktur (editierbar)")
st.markdown(
    "**Eingabeformat:** Spalte `count` enthält die Anzahl Personen pro "
    "Merkmalsausprägung — genau so wie sie aus den offiziellen "
    "Bevölkerungs-Tabellen kommt. Sie können die Zahlen direkt in der "
    "Tabelle anpassen, z.B. um eine neue Statistik einzuspielen.\n\n"
    "Die Spalte `share` (Anteil) wird **automatisch** aus den `count`-Werten "
    "abgeleitet und pro Merkmal auf 1 normiert. `share` ist nur informativ — "
    "der Solver verwendet immer die abgeleiteten Anteile.\n\n"
    "Die Spalte `note` ist für interne Anmerkungen gedacht "
    "(z.B. *„Stand 2022, Update ausstehend“*). Sie wirkt sich nicht auf das "
    "Ergebnis aus, wird aber im Audit-Eintrag mitgeführt."
)
if pop_warnings:
    for w in pop_warnings:
        st.warning(w)

edited_pop_df = st.data_editor(
    raw_pop_df,
    width='stretch', num_rows="dynamic",
    disabled=["share"],
    key="pop_editor",
    column_config={
        "feature": st.column_config.SelectboxColumn(
            "feature (Merkmal)",
            options=sorted(set(raw_pop_df["feature"].dropna().astype(str)) | set(active_features)),
            help=("Dropdown mit bereits vorhandenen Merkmalen. Ein neues "
                  "Merkmal anlegen: neue Zeile, Feldname in der Spalte "
                  "`feature` direkt eintippen (das ist nur über den "
                  "Stiftknopf möglich, sobald die Zeile aktiv ist)."),
        ),
        "value": st.column_config.TextColumn(
            "value (Ausprägung)",
            help="Frei wählbar; muss innerhalb eines Merkmals eindeutig sein."),
        "count": st.column_config.NumberColumn(
            "count (Anzahl Personen)", min_value=0, step=1, format="%d",
            help="Rohzahl aus der Bevölkerungs-Statistik."),
        "share": st.column_config.NumberColumn(
            "share (abgeleitet)", format="%.4f",
            help="Wird automatisch berechnet — keine Eingabe nötig."),
        "note": st.column_config.TextColumn("note (frei)"),
    },
)

# Build the normalised dict the solver expects, preferring count over share.
population: dict[str, dict[str, float]] = {}
for _, row in edited_pop_df.iterrows():
    feat = str(row["feature"]).strip()
    val = str(row["value"]).strip()
    if not feat or not val:
        continue
    cnt = row.get("count")
    if pd.notna(cnt) and float(cnt) >= 0:
        weight = float(cnt)
    else:
        share = row.get("share")
        weight = float(share) if pd.notna(share) else 0.0
    population.setdefault(feat, {})[val] = weight
for feat, d in population.items():
    total = sum(d.values()) or 1
    if abs(total - 1.0) > 1e-9:
        for k in d:
            d[k] /= total

# Live preview of derived shares for transparency
with st.expander("Abgeleitete Anteile (Kontrolle)", expanded=False):
    rows = []
    for feat, d in population.items():
        for v, s in d.items():
            rows.append({"feature": feat, "value": v, "share (derived)": round(s, 4)})
    st.dataframe(pd.DataFrame(rows), width='stretch')

# ------------------------------------------------ consistency pre-computation
# Computed *before* the Expertenmodus-Expander so the top-level warning is
# always visible — even when the expander is collapsed.
raw_totals: dict[str, float] = {}
for _, row in edited_pop_df.iterrows():
    feat = str(row.get("feature") or "").strip()
    if not feat:
        continue
    cnt = row.get("count")
    if pd.notna(cnt):
        try:
            raw_totals[feat] = raw_totals.get(feat, 0.0) + float(cnt)
        except (TypeError, ValueError):
            pass

_totals_list = [v for v in raw_totals.values() if v > 0]
_median_total = (sorted(_totals_list)[len(_totals_list) // 2]
                 if _totals_list else 0.0)

consistency_rows: list[dict] = []
warn_features: list[str] = []
err_features: list[str] = []
for feat, t in raw_totals.items():
    dev_pct = ((t - _median_total) / _median_total * 100) if _median_total > 0 else 0.0
    if abs(dev_pct) <= 2:
        flag = "✓"
    elif abs(dev_pct) <= 10:
        flag = "⚠"; warn_features.append(feat)
    else:
        flag = "✗"; err_features.append(feat)
    consistency_rows.append({
        "feature": feat,
        "Σ count": int(round(t)),
        "Δ vs. Median (%)": round(dev_pct, 2),
        "Status": flag,
    })

joint_consistency_rows: list[dict] = []
joint_err: list[str] = []
if joint_loaded and raw_joint_df is not None and "count" in raw_joint_df.columns:
    _joint_total = float(pd.to_numeric(
        raw_joint_df["count"], errors="coerce").fillna(0).sum())
    _joint_dim_cols = [c for c in raw_joint_df.columns
                       if c not in ("count", "share", "note")]
    for dim in _joint_dim_cols:
        marg = raw_totals.get(dim)
        if not marg or _joint_total <= 0:
            continue
        dev = (_joint_total - marg) / marg * 100
        if abs(dev) <= 2:
            flag = "✓"
        elif abs(dev) <= 10:
            flag = "⚠"
        else:
            flag = "✗"; joint_err.append(dim)
        joint_consistency_rows.append({
            "Joint deckt": dim,
            "Σ Joint count": int(round(_joint_total)),
            "Σ Marginal count": int(round(marg)),
            "Δ (%)": round(dev, 2),
            "Status": flag,
        })

# Surface the warning at the top level so it is visible without opening
# the expander.
if err_features:
    st.error(
        "**Inkonsistente Bevölkerungs-Summen**: "
        + ", ".join(f"`{f}`" for f in err_features)
        + f" weichen > 10 % vom Median ({int(round(_median_total)):,} Personen) ab. "
          "Das deutet meist auf unterschiedliche Stichjahre, abweichende "
          "Altersuntergrenzen oder einen Tippfehler hin. Das Tool rechnet "
          "trotzdem weiter (jedes Merkmal wird separat auf Summe 1 normalisiert), "
          "aber das Resultat repräsentiert dann eine *Mischpopulation*. "
          "Details unter »Statistik / Expertenmodus« weiter unten."
    )
elif warn_features:
    st.warning(
        "**Bevölkerungs-Summen leicht inkonsistent**: "
        + ", ".join(f"`{f}`" for f in warn_features)
        + " weichen 2 – 10 % vom Median ab. Details unter »Statistik / "
          "Expertenmodus«."
    )
if joint_err:
    st.error(
        "**Joint-Verteilung passt nicht zu den Marginalen**: Summe der "
        f"Joint-Counts weicht > 10 % von den Marginal-Summen für "
        + ", ".join(f"`{d}`" for d in joint_err)
        + " ab. Wahrscheinlich stammen Joint- und Marginal-Daten aus "
          "unterschiedlichen Quellen. Bitte prüfen."
    )

# ----- candidate ↔ population drift (per-row, surfaced at top level) -----
_n_total = len(candidates) or 1
drift_err: list[str] = []
drift_warn: list[str] = []
for _feat in active_features:
    _pop_d = population.get(_feat, {})
    _cnt: dict[str, int] = {}
    for _c in candidates:
        _v = _c.attrs.get(_feat, "")
        if _v:
            _cnt[_v] = _cnt.get(_v, 0) + 1
    for _v in set(_pop_d) | set(_cnt):
        _delta_pp = abs(_cnt.get(_v, 0) / _n_total - _pop_d.get(_v, 0.0)) * 100
        if _delta_pp > 15:
            drift_err.append(f"`{_feat}`={_v} (Δ {_delta_pp:+.0f} pp)")
        elif _delta_pp > 5:
            drift_warn.append(f"`{_feat}`={_v}")
if drift_err:
    st.error(
        "**Starke Pool-Verzerrung gegenüber der Bevölkerung** "
        f"(> 15 Prozentpunkte) bei: {', '.join(drift_err[:8])}"
        + (f" … (+{len(drift_err)-8} weitere)" if len(drift_err) > 8 else "")
        + ". Der Solver kann das im Rahmen der Quoten ausgleichen, aber bei "
          "kleinem Pool wird er einige Quoten relaxieren müssen. Details und "
          "Farbkennzeichnung unter »Statistik / Expertenmodus« weiter unten."
    )
elif drift_warn:
    st.warning(
        f"**Pool weicht spürbar von der Bevölkerung ab** "
        f"(5 – 15 pp bei {len(drift_warn)} Ausprägung(en)). Details unter "
        "»Statistik / Expertenmodus«."
    )

# ----------------------------------------------------------- expert statistics
with st.expander("Statistik / Expertenmodus", expanded=False):
    st.markdown(
        "Diagnose-Informationen über Kandidatenpool und Bevölkerungs-Vergleich "
        "— hilfreich, um *vor* der Auslosung systematische Verzerrungen zu "
        "erkennen."
    )

    n_cand = len(candidates)
    n_feat = len(active_features)
    n_desc = len(metadata_only)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Kandidaten", n_cand)
    col2.metric("Aktive Merkmale", n_feat)
    col3.metric("Nur deskriptiv", n_desc)
    col4.metric("Panel-/Pool-Quote", f"{int(panel_size)/n_cand:.1%}" if n_cand else "—")

    # ---------- consistency check across feature totals ----------------
    st.markdown("**Konsistenz-Check**")
    st.caption(
        "Jedes Merkmal wird *intern unabhängig* auf Summe 1 normalisiert "
        "(`share = count / Σ count` pro Merkmal). Dadurch funktioniert das "
        "Tool auch, wenn die Marginalen aus unterschiedlichen Quellen / "
        "Stichjahren stammen — verbirgt aber Inkonsistenzen. Diese Tabelle "
        "zeigt die Roh-Summen *vor* der Normalisierung."
    )
    if consistency_rows:
        st.dataframe(pd.DataFrame(consistency_rows),
                     width='stretch', hide_index=True)
        st.caption(
            "Median-Gesamtbevölkerung über alle Merkmale: "
            f"**{int(round(_median_total)):,}**. ".replace(",", "'")
            + "Toleranz: ±2 % ✓, ±10 % ⚠, darüber ✗."
        )
    else:
        st.info(
            "Keine `count`-Werte vorhanden — Konsistenz-Check übersprungen "
            "(es werden direkt die `share`-Werte verwendet)."
        )

    if joint_consistency_rows:
        st.caption("**Joint ↔ Marginalen** (Summen sollten übereinstimmen)")
        st.dataframe(pd.DataFrame(joint_consistency_rows),
                     width='stretch', hide_index=True)

    # Per-feature comparison: candidate distribution vs. population.
    st.markdown("**Verteilungs-Vergleich pro Merkmal** "
                "(Kandidaten-Anteil vs. Bevölkerungs-Anteil)")
    st.caption(
        "Flagge: **✓** ≤ 5 pp Abweichung, **⚠** 5 – 15 pp (gelb hinterlegt), "
        "**✗** > 15 pp (rot hinterlegt) — gleiche Farb-Konvention wie bei "
        "der Quoten-Realisierung weiter unten."
    )

    def _style_drift(df: pd.DataFrame):
        def row_style(row):
            d = abs(float(row["Δ (pp)"]))
            if d > 15:
                return ["background-color: #f8d7da"] * len(row)  # red
            if d > 5:
                return ["background-color: #fff3cd"] * len(row)  # yellow
            return [""] * len(row)
        return df.style.apply(row_style, axis=1).format({
            "Anteil_Kand.": "{:.4f}",
            "Anteil_Bev.": "{:.4f}",
            "Δ (pp)": "{:+.1f}",
            "erwartet @ Panel": "{:.2f}",
        })

    for feat in active_features:
        pop_d = population.get(feat, {})
        cand_counts: dict[str, int] = {}
        for c in candidates:
            v = c.attrs.get(feat, "")
            if v:
                cand_counts[v] = cand_counts.get(v, 0) + 1
        all_values = sorted(set(pop_d.keys()) | set(cand_counts.keys()))
        rows = []
        tvd = 0.0  # total variation distance
        n_total = n_cand or 1
        for v in all_values:
            cn = cand_counts.get(v, 0)
            cs = cn / n_total
            ps = pop_d.get(v, 0.0)
            delta_pp = (cs - ps) * 100
            expected = ps * int(panel_size)
            min_needed = int(round(ps * int(panel_size) - 0.499)) if ps else 0
            min_needed = max(0, min_needed)
            tvd += abs(cs - ps)
            if abs(delta_pp) > 15:
                drift_flag = "✗"
            elif abs(delta_pp) > 5:
                drift_flag = "⚠"
            else:
                drift_flag = "✓"
            rows.append({
                "value": v,
                "n_Kand.": cn,
                "Anteil_Kand.": round(cs, 4),
                "Anteil_Bev.": round(ps, 4),
                "Δ (pp)": round(delta_pp, 1),
                "Drift": drift_flag,
                "erwartet @ Panel": round(expected, 2),
                "Pool-OK?": "✓" if cn >= min_needed else "⚠",
            })
        tvd = tvd / 2
        st.markdown(
            f"*`{feat}`* — Total Variation Distance "
            f"$d_{{TV}} = \\tfrac12 \\sum |p_{{cand}} - p_{{pop}}|$ = "
            f"**{tvd:.3f}**  "
            f"(0 = perfekt repräsentativ, 1 = vollständig disjunkt)"
        )
        st.dataframe(_style_drift(pd.DataFrame(rows)), width='stretch',
                     hide_index=True)

    # Joint coverage: useful when a joint distribution is loaded.
    if joint_loaded:
        st.markdown("**Joint-Zellen-Abdeckung**")
        joint_cells_total = len(joint_loaded)
        joint_cells_with_cands = 0
        empty_cells: list[tuple[str, int]] = []
        for cell_attrs, weight in joint_loaded:
            label = " × ".join(f"{k}={v}" for k, v in cell_attrs.items())
            n_match = sum(
                1 for c in candidates
                if all(c.attrs.get(k) == v for k, v in cell_attrs.items())
            )
            if n_match > 0:
                joint_cells_with_cands += 1
            else:
                empty_cells.append((label, int(round(weight * int(panel_size)))))
        c1, c2 = st.columns(2)
        c1.metric("Zellen mit ≥1 Kandidaten",
                  f"{joint_cells_with_cands} / {joint_cells_total}")
        c2.metric("Abdeckungsquote",
                  f"{joint_cells_with_cands/joint_cells_total:.1%}"
                  if joint_cells_total else "—")
        if empty_cells:
            st.warning(
                f"{len(empty_cells)} Joint-Zellen haben **keinen** "
                "passenden Kandidaten — diese können nur durch "
                "Quoten-Relaxation oder Pool-Aufstockung berücksichtigt "
                "werden."
            )
            with st.expander(f"Leere Zellen ({len(empty_cells)})", expanded=False):
                st.dataframe(
                    pd.DataFrame(empty_cells,
                                 columns=["Zelle", "erwartet @ Panel"]),
                    width='stretch', hide_index=True,
                )

    # Pool feasibility: any value whose pool count is < lower quota bound?
    risky = []
    for q in default_quotas(population, int(panel_size)):
        n_in_pool = sum(
            1 for c in candidates if c.attrs.get(q.feature) == q.value
        )
        if n_in_pool < q.lo:
            risky.append({
                "feature": q.feature, "value": q.value,
                "Quote (min)": q.lo, "im Pool": n_in_pool,
                "Defizit": q.lo - n_in_pool,
            })
    if risky:
        st.markdown("**Pool-Engpässe**")
        st.error(
            f"{len(risky)} Merkmals-Ausprägung(en) haben weniger Kandidaten "
            "als die strikte Mindest-Quote verlangt. Der Solver wird hier "
            "automatisch relaxieren (gelb markiert in der Ergebnis-Tabelle "
            "weiter unten)."
        )
        st.dataframe(pd.DataFrame(risky), width='stretch', hide_index=True)
    else:
        st.success(
            "Alle Marginal-Quoten sind aus dem Pool heraus theoretisch "
            "erfüllbar (keine sofortige Relaxation nötig)."
        )


# ---------------------------------------------------------------- quotas preview
st.subheader("Quoten (abgeleitet)")
st.markdown(
    "Für eine Panelgröße $k$ und einen Bevölkerungs-Anteil $\\pi$ wird das "
    "Quoten-Intervall als $[\\lfloor k\\cdot\\pi \\rfloor,\\, \\lceil k\\cdot\\pi \\rceil]$ "
    "gesetzt. Das ist immer ein Bereich der Länge 0 oder 1 — das hält den "
    "Solver auch dann lösbar, wenn die Bevölkerungs-Anteile keine ganzen "
    "Personen ergeben.\n\n"
    "Anpassungen an der Bevölkerungs-Tabelle oben werden hier sofort sichtbar."
)
preview_q = default_quotas(population, int(panel_size))
if use_joint and joint_loaded:
    preview_q = preview_q + default_joint_quotas(joint_loaded, int(panel_size))
df_q = pd.DataFrame(
    [{"feature": q.feature, "value": q.value,
      "share": round(q.share, 4), "lo": q.lo, "hi": q.hi}
     for q in preview_q]
)
st.dataframe(df_q, width='stretch')

if joint_loaded:
    with st.expander(
        f"Joint-Verteilung (Geschlecht×Alter×Kanton) — {len(joint_loaded)} Zellen",
        expanded=False,
    ):
        st.markdown(
            "Diese Tabelle bildet die **gemeinsame** Verteilung von "
            "Geschlecht × Alter × Kanton ab und kommt direkt aus dem "
            "amtlichen Bevölkerungs-Cross-Tab. Wenn aktiviert (Checkbox links), "
            "verlangt der Solver pro Zelle eine Mindest- und Höchstzahl im "
            "Panel — das Ergebnis spiegelt damit die Bevölkerungs-Struktur "
            "feiner wider als bei reiner Verwendung der Marginalen.\n\n"
            "**Bei knappem Kandidatenpool kann das die Auslosung der "
            "Ersatzpersonen unlösbar machen.** In dem Fall fällt das Tool "
            "automatisch auf die Marginalen zurück und vermerkt das oben "
            "in einer Warnbox."
        )
        if raw_joint_df is not None:
            # Suggest values per joint dimension from population/candidates.
            joint_dim_cols = [c for c in raw_joint_df.columns
                              if c not in ("count", "share", "note")]
            joint_col_config: dict = {}
            for dim in joint_dim_cols:
                opts = sorted(
                    set(population_loaded.get(dim, {}).keys())
                    | set(str(v) for v in raw_joint_df[dim].dropna().astype(str))
                )
                joint_col_config[dim] = st.column_config.SelectboxColumn(
                    dim, options=opts,
                    help=("Auswahl aus `population.csv` plus bereits vorhandene "
                          "Werte dieser Dimension."),
                )
            joint_col_config["count"] = st.column_config.NumberColumn(
                "count (Anzahl Personen)", min_value=0, step=1, format="%d")
            joint_col_config["share"] = st.column_config.NumberColumn(
                "share (abgeleitet)", format="%.4f")
            edited_joint_df = st.data_editor(
                raw_joint_df, width='stretch', num_rows="dynamic",
                key="joint_editor", column_config=joint_col_config,
            )
            # rebuild joint_loaded from edited data
            new_joint: list[tuple[dict[str, str], float]] = []
            dim_cols = [c for c in edited_joint_df.columns
                        if c not in ("count", "share", "note")]
            for _, row in edited_joint_df.iterrows():
                criteria = {c: str(row[c]).strip() for c in dim_cols
                            if str(row[c]).strip() and str(row[c]) != "nan"}
                if len(criteria) != len(dim_cols):
                    continue
                cnt = row.get("count")
                if pd.notna(cnt) and float(cnt) >= 0:
                    w = float(cnt)
                else:
                    w = float(row.get("share") or 0)
                new_joint.append((criteria, w))
            total = sum(s for _, s in new_joint) or 1
            joint_loaded = [(c, s / total) for c, s in new_joint]
        else:
            df_j = pd.DataFrame(
                [{**c, "share": round(s, 6)} for c, s in joint_loaded]
            )
            st.dataframe(df_j, width='stretch')
        if joint_warnings:
            for w in joint_warnings:
                st.warning(w)

if not run:
    st.stop()


# ---------------------------------------------------------------- solve
try:
    with st.spinner("Mitgliederpanel wird ausgelost …"):
        quotas: list[Quota] = default_quotas(population, int(panel_size))
        if use_joint and joint_loaded:
            quotas = quotas + default_joint_quotas(joint_loaded, int(panel_size))
        members = select_panel(candidates, quotas, int(panel_size), seed=int(seed))
except RuntimeError as e:
    st.error(
        "**Die Auslosung der Mitglieder ist nicht lösbar.** "
        "Häufige Ursachen: Panelgröße größer als der Kandidatenpool, "
        "Quoten verlangen mehr Personen einer Kategorie als verfügbar, "
        "oder Joint-Verteilung zu fein für den Pool. "
        f"\n\nDetails: `{e}`"
    )
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(f"**Unerwarteter Fehler bei der Auslosung.**\n\n`{type(e).__name__}: {e}`")
    st.stop()

substitutes = None
sub_quotas: list[Quota] = []
sub_joint_dropped = False
if n_subs > 0:
    with st.spinner("Ersatzpersonen werden ausgelost …"):
        sub_quotas = default_quotas(population, int(n_subs))
        if use_joint and joint_loaded:
            sub_quotas_with_joint = sub_quotas + default_joint_quotas(
                joint_loaded, int(n_subs))
        else:
            sub_quotas_with_joint = sub_quotas
        try:
            substitutes = select_panel(
                candidates, sub_quotas_with_joint, int(n_subs),
                seed=int(seed) + 1,
                excluded_ids={c.ID for c in members.panel},
            )
            sub_quotas = sub_quotas_with_joint
        except RuntimeError:
            if use_joint and joint_loaded:
                sub_joint_dropped = True
                substitutes = select_panel(
                    candidates, sub_quotas, int(n_subs),
                    seed=int(seed) + 1,
                    excluded_ids={c.ID for c in members.panel},
                )
            else:
                raise

# Population notes — live from the editor, so admin edits are persisted
# into the result workbook and the manifest.
population_notes: list[dict[str, str]] = []
if "note" in edited_pop_df.columns:
    for _, _row in edited_pop_df.iterrows():
        _note = str(_row.get("note") or "").strip()
        if not _note:
            continue
        population_notes.append({
            "feature": str(_row.get("feature") or "").strip(),
            "value": str(_row.get("value") or "").strip(),
            "note": _note,
        })

manifest = build_manifest(
    seed=int(seed),
    panel_size_members=int(panel_size),
    panel_size_substitutes=int(n_subs),
    candidates=candidates,
    population=population,
    quotas=quotas,
    members=members,
    substitutes=substitutes,
    inputs={"candidates": str(cand_path), "population": str(pop_path)},
    population_notes=population_notes,
)


# ---------------------------------------------------------------- results
st.subheader("3 · Ergebnis")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mitglieder", len(members.panel))
c2.metric("Ersatz", 0 if substitutes is None else len(substitutes.panel))
c3.metric("Min p_i (Mitglieder)", f"{members.minimum_probability:.4f}")
c4.metric("Run-Hash", manifest["run_hash"][:12] + "…")

# Prominent relaxation warnings
all_relax = list(members.relaxations) + (substitutes.relaxations if substitutes else [])
if all_relax:
    with st.expander(f"⚠ {len(all_relax)} Quoten-Anpassung(en) — bitte prüfen",
                     expanded=True):
        if members.relaxations:
            st.markdown("**Mitglieder:**")
            for r in members.relaxations:
                st.write("• " + r)
        if substitutes and substitutes.relaxations:
            st.markdown("**Ersatz:**")
            for r in substitutes.relaxations:
                st.write("• " + r)
else:
    st.success("Alle Quoten wurden ohne Anpassung erfüllt.")

if sub_joint_dropped:
    st.warning(
        "Für die Ersatzpersonen waren die Joint-Quoten nicht erfüllbar — "
        "die Auslosung der Ersatzpersonen erfolgte nur mit den Marginalen. "
        "Joint-Verteilung bleibt für die Mitglieder erzwungen."
    )


def _panel_table(r) -> pd.DataFrame:
    return pd.DataFrame([{"ID": c.ID, **c.attrs} for c in r.panel])


def _bounds_table(r, qs) -> pd.DataFrame:
    rows = []
    # Count realised members per quota, honouring joint quotas (whose feature
    # name contains × and value contains |) via the same matcher the solver
    # uses. The previous (f, v)-tuple lookup only worked for marginals and
    # left joint rows stuck at 0.
    counts = [sum(1 for c in r.panel if _candidate_in_quota(c, q)) for q in qs]
    for q, (lo, hi), ist in zip(qs, r.effective_bounds, counts):
        rows.append({
            "feature": q.feature, "value": q.value,
            "lo_default": q.lo, "lo_effective": lo,
            "ist": ist,
            "hi_effective": hi, "hi_default": q.hi,
            "in range": lo <= ist <= hi,
        })
    return pd.DataFrame(rows)


t_m, t_s, t_b, t_p, t_a = st.tabs(
    ["Mitglieder", "Ersatz", "Quoten vs. Ist", "Wahrscheinlichkeiten", "Audit / Hashes"]
)

with t_m:
    st.dataframe(_panel_table(members), width='stretch', height=420)

with t_s:
    if substitutes is None:
        st.write("Keine Ersatzpersonen angefordert.")
    else:
        st.dataframe(_panel_table(substitutes),
                     width='stretch', height=420)

with t_b:
    st.markdown("**Mitglieder — Quoten-Intervall vs. realisiert**")
    st.caption(
        "🟡 gelb hinterlegte Zeilen = die Standardgrenzen `lo_default` / "
        "`hi_default` mussten relaxiert werden, damit der Solver lösbar bleibt "
        "(z.B. weil der Kandidatenpool nicht genug Personen einer Kategorie "
        "enthält). 🔴 rot = realisierte Anzahl außerhalb des effektiven "
        "Intervalls (sollte praktisch nie vorkommen)."
    )

    def _style_bounds(df: pd.DataFrame):
        def row_style(row):
            relaxed = (row["lo_default"] != row["lo_effective"]
                       or row["hi_default"] != row["hi_effective"])
            out_of_range = not row["in range"]
            if out_of_range:
                return ["background-color: #f8d7da"] * len(row)  # light red
            if relaxed:
                return ["background-color: #fff3cd"] * len(row)  # light yellow
            return [""] * len(row)
        return df.style.apply(row_style, axis=1)

    st.dataframe(_style_bounds(_bounds_table(members, quotas)),
                 width='stretch')
    if substitutes is not None:
        st.markdown("**Ersatz — Quoten-Intervall vs. realisiert**")
        st.dataframe(_style_bounds(_bounds_table(substitutes, sub_quotas)),
                     width='stretch')

with t_p:
    df_p = pd.DataFrame(sorted(members.probabilities.items()),
                        columns=["ID", "p_member"])
    st.dataframe(df_p, width='stretch', height=420)

with t_a:
    st.markdown("**Run-Hash (SHA-256)**")
    st.code(manifest["run_hash"])
    st.markdown("**Einzel-Hashes**")
    st.json(manifest["hashes"])
    st.markdown("**Audit-Zeilen**")
    st.dataframe(pd.DataFrame(manifest_audit_rows(manifest),
                              columns=["Schlüssel", "Wert"]),
                 width='stretch', height=420)


# ---------------------------------------------------------------- downloads
st.subheader("4 · Download")
out_tmp = Path(tempfile.mkdtemp())
xlsx_path = out_tmp / "Losung-Ergebnis.xlsx"
write_result_workbook(
    src_path=cand_path if cand_path.suffix.lower() == ".xlsx" else None,
    out_path=xlsx_path,
    members=members.panel,
    substitutes=substitutes.panel if substitutes else [],
    probabilities=members.probabilities,
    audit_rows=manifest_audit_rows(manifest),
    population_notes=population_notes,
)
json_buf = io.BytesIO()
import json
json_buf.write(json.dumps(manifest, ensure_ascii=False, indent=2,
                          sort_keys=True).encode("utf-8"))

col_a, col_b = st.columns(2)
with col_a:
    st.download_button(
        "Excel-Workbook (.xlsx)",
        data=xlsx_path.read_bytes(),
        file_name="Losung-Ergebnis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with col_b:
    st.download_button(
        "Manifest (.json, inkl. Hashes)",
        data=json_buf.getvalue(),
        file_name="Losung-Manifest.json",
        mime="application/json",
    )
