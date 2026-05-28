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
    read_candidates_csv,
    read_joint_population_csv,
    read_population_csv,
)
from losverfahren.io_excel import (  # noqa: E402
    FEATURES,
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
        "**1 · `candidates.csv` (Pflicht)** — eine Zeile pro Person.\n\n"
        "```\n"
        "ID,Geschlecht,Alterskategorie,Kanton,Ausbildung,Profil\n"
        "K001,Mann,36-55,Nord,AbiturMeister,\n"
        "K002,Frau,16-35,Süd,DualBachelor,\n"
        "```\n"
        "Spalte `Profil` ist optional (Freitext).\n\n"
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
        return read_candidates_csv(path)
    return read_candidates(path)


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
        cand_path = SAMPLE_DIR / "candidates.csv"
        pop_path = SAMPLE_DIR / "population.csv"
        joint_candidate = SAMPLE_DIR / "population_joint.csv"
        joint_path = joint_candidate if joint_candidate.exists() else None
        if not cand_path.exists():
            st.error(f"Beispiel-Daten nicht gefunden unter {SAMPLE_DIR}")
            st.stop()
        st.success(f"Beispiel-Daten geladen aus {SAMPLE_DIR}")
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
    candidates = _load_candidates_any(cand_path)
except Exception as e:  # noqa: BLE001
    _fail(
        "Kandidatenliste konnte nicht gelesen werden. Erwartet wird eine "
        "CSV mit den Spalten `ID, Geschlecht, Alterskategorie, Kanton, "
        "Ausbildung` (optional `Profil`) oder das alte PBD-Excel-Template.",
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
        # Force `note` to string so the data_editor accepts a TextColumn even
        # when the column is entirely empty (pandas would otherwise infer
        # float / NaN and Streamlit rejects the text config).
        df = pd.read_csv(path, dtype={"note": str}, keep_default_na=False,
                         na_values=[""])
    else:
        # Legacy xlsx path: synthesise a DataFrame from the marginals.
        rows = []
        for feat, d in population_loaded.items():
            for v, s in d.items():
                rows.append({"feature": feat, "value": v, "share": s})
        df = pd.DataFrame(rows)
    if "count" not in df.columns:
        df["count"] = pd.NA
    if "share" not in df.columns:
        df["share"] = pd.NA
    if "note" not in df.columns:
        df["note"] = ""
    df["note"] = df["note"].fillna("").astype(str)
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
        raw_joint_df = (
            pd.read_csv(joint_path, keep_default_na=False, na_values=[""])
            if joint_path.suffix.lower() == ".csv" else None
        )
    except Exception as e:  # noqa: BLE001
        st.warning(
            "Joint-Bevölkerungs-CSV konnte nicht gelesen werden — die "
            f"Auslosung läuft nur mit den Marginalen weiter. Details: "
            f"`{type(e).__name__}: {e}`"
        )
        joint_path = None
        joint_loaded = []

st.subheader("Kandidaten")
df_c = pd.DataFrame([{"ID": c.ID, **c.attrs,
                      "Profil": c.Profil or ""} for c in candidates])
st.write(f"{len(candidates)} Kandidaten geladen.")
st.dataframe(df_c, width='stretch', height=240)


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
    disabled=["feature", "value", "share"],
    key="pop_editor",
    column_config={
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
            edited_joint_df = st.data_editor(
                raw_joint_df, width='stretch', num_rows="dynamic",
                key="joint_editor",
                column_config={
                    "count": st.column_config.NumberColumn(
                        "count (Anzahl Personen)", min_value=0, step=1, format="%d"),
                    "share": st.column_config.NumberColumn(
                        "share (abgeleitet)", format="%.4f"),
                },
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
