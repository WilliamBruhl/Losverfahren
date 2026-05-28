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
from losverfahren.i18n import LANGUAGES, DEFAULT_LANG, t, join_codes  # noqa: E402
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

# Language must be initialised *before* set_page_config so the page title is
# rendered in the right language on first paint. The selectbox below writes
# back into the same session_state key, triggering a normal Streamlit rerun.
if "lang" not in st.session_state:
    st.session_state["lang"] = DEFAULT_LANG

st.set_page_config(page_title=t("page.title"), layout="wide")
st.title(t("page.heading"))
st.caption(t("page.caption"))



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
    _lang_codes = list(LANGUAGES.keys())
    st.selectbox(
        t("sidebar.lang"),
        _lang_codes,
        index=_lang_codes.index(st.session_state.get("lang", DEFAULT_LANG)),
        format_func=lambda c: LANGUAGES[c],
        key="lang",
    )

    st.header(t("sidebar.h_inputs"))

    _source_examples = t("sidebar.source.examples")
    _source_upload = t("sidebar.source.upload")
    source = st.radio(
        t("sidebar.source"),
        [_source_examples, _source_upload],
        index=0,
        help=t("sidebar.source.help"),
    )

    cand_path: Path | None = None
    pop_path: Path | None = None
    joint_path: Path | None = None

    if source == _source_examples:
        examples = _discover_examples()
        if not examples:
            st.error(t("sidebar.example.none"))
            st.stop()
        labels = list(examples.keys())
        choice = st.selectbox(
            t("sidebar.example.label"),
            labels,
            index=0,
            help=t("sidebar.example.help"),
        )
        chosen_dir = examples[choice]
        cand_path = chosen_dir / "candidates.csv"
        pop_path = chosen_dir / "population.csv"
        joint_candidate = chosen_dir / "population_joint.csv"
        joint_path = joint_candidate if joint_candidate.exists() else None
        if not cand_path.exists():
            st.error(t("sidebar.example.missing").format(path=chosen_dir))
            st.stop()
        readme = chosen_dir / "README.md"
        if readme.exists():
            with st.expander(t("sidebar.example.readme"), expanded=False):
                st.markdown(readme.read_text(encoding="utf-8"))
        joint_note = "" if joint_path is None else t("sidebar.example.joint_note")
        st.success(t("sidebar.example.loaded").format(
            choice=choice, joint_note=joint_note))
    else:
        cand_up = st.file_uploader(
            t("sidebar.upload.cand"), type=["csv", "xlsx"], key="cand"
        )
        pop_up = st.file_uploader(
            t("sidebar.upload.pop"),
            type=["csv", "xlsx"], key="pop"
        )
        joint_up = st.file_uploader(
            t("sidebar.upload.joint"),
            type=["csv"], key="joint",
            help=t("sidebar.upload.joint.help"),
        )
        if cand_up is None or pop_up is None:
            st.info(t("sidebar.upload.need_more"))
            st.stop()
        cand_path = _save_upload(cand_up, cand_up.name)
        pop_path = _save_upload(pop_up, pop_up.name)
        joint_path = _save_upload(joint_up, joint_up.name) if joint_up else None

    use_joint = st.checkbox(
        t("sidebar.use_joint"),
        value=joint_path is not None,
        disabled=joint_path is None,
        help=t("sidebar.use_joint.help"),
    )

    st.header(t("sidebar.h_params"))
    panel_size = st.number_input(t("sidebar.panel_size"), 5, 200, 30, 1)
    n_subs = st.number_input(t("sidebar.n_subs"), 0, 200, 30, 1)
    seed = st.number_input(t("sidebar.seed"), 0, 2**31 - 1, 20260527, 1)
    run = st.button(t("sidebar.run"), type="primary")


# ---------------------------------------------------------------- data load
def _fail(msg: str, exc: Exception) -> None:
    st.error(f"**{msg}**\n\n`{type(exc).__name__}: {exc}`")
    st.stop()

try:
    candidates, cand_warnings = _load_candidates_any(cand_path)
except Exception as e:  # noqa: BLE001
    _fail(t("load.cand_fail"), e)

try:
    population_loaded, pop_warnings = _load_population_any(pop_path)
except Exception as e:  # noqa: BLE001
    _fail(t("load.pop_fail"), e)

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
    _fail(t("load.pop_table_fail"), e)

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
        st.warning(t("load.joint_fail").format(
            err=f"{type(e).__name__}: {e}"))
        joint_path = None
        joint_loaded = []

st.subheader(t("cand.h"))

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

with st.expander(t("cand.schema_expander"), expanded=False):
    st.markdown(t("cand.schema.active").format(
        features=join_codes(active_features) or t("cand.schema.none")))
    if metadata_only:
        st.markdown(t("cand.schema.descriptive").format(
            features=join_codes(metadata_only)))
    if missing_in_candidates:
        st.warning(t("cand.schema.missing").format(
            features=join_codes(missing_in_candidates)))
    if cand_warnings:
        for w in cand_warnings:
            st.info(w)

if not active_features:
    st.error(t("cand.no_overlap"))
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
    "ID", help=t("cand.col.id_help"), required=True)}
for feat in cand_attr_cols:
    if feat in feature_options:
        cand_col_config[feat] = st.column_config.SelectboxColumn(
            feat, options=feature_options[feat],
            help=t("cand.col.feat_help"),
        )
    else:
        cand_col_config[feat] = st.column_config.TextColumn(
            feat, help=t("cand.col.desc_help")
        )

st.write(t("cand.count").format(n=len(candidates)))
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
    from losverfahren.models import Candidate  # local import to avoid cycle confusion
    candidates.append(Candidate(ID=cid, attrs=attrs))


# ---------------------------------------------------------------- population editor
st.subheader(t("pop.h"))
st.markdown(t("pop.body"))
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
            t("pop.col.feature"),
            options=sorted(set(raw_pop_df["feature"].dropna().astype(str)) | set(active_features)),
            help=t("pop.col.feature_help"),
        ),
        "value": st.column_config.TextColumn(
            t("pop.col.value"), help=t("pop.col.value_help")),
        "count": st.column_config.NumberColumn(
            t("pop.col.count"), min_value=0, step=1, format="%d",
            help=t("pop.col.count_help")),
        "share": st.column_config.NumberColumn(
            t("pop.col.share"), format="%.4f",
            help=t("pop.col.share_help")),
        "note": st.column_config.TextColumn(t("pop.col.note")),
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
with st.expander(t("pop.derived_expander"), expanded=False):
    rows = []
    for feat, d in population.items():
        for v, s in d.items():
            rows.append({"feature": feat, "value": v,
                         t("pop.derived.col_share"): round(s, 4)})
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
for feat, t_ in raw_totals.items():
    dev_pct = ((t_ - _median_total) / _median_total * 100) if _median_total > 0 else 0.0
    if abs(dev_pct) <= 2:
        flag = "✓"
    elif abs(dev_pct) <= 10:
        flag = "⚠"; warn_features.append(feat)
    else:
        flag = "✗"; err_features.append(feat)
    consistency_rows.append({
        t("expert.col.feature"): feat,
        t("expert.col.sum_count"): int(round(t_)),
        t("expert.col.delta_median"): round(dev_pct, 2),
        t("expert.col.status"): flag,
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
            t("expert.col.joint_covers"): dim,
            t("expert.col.sum_joint"): int(round(_joint_total)),
            t("expert.col.sum_marg"): int(round(marg)),
            t("expert.col.delta_pct"): round(dev, 2),
            t("expert.col.status"): flag,
        })

# Surface the warning at the top level so it is visible without opening
# the expander.
if err_features:
    st.error(t("warn.consistency.err").format(
        features=join_codes(err_features),
        median=f"{int(round(_median_total)):,}",
    ))
elif warn_features:
    st.warning(t("warn.consistency.warn").format(
        features=join_codes(warn_features)))
if joint_err:
    st.error(t("warn.joint_mismatch").format(
        features=join_codes(joint_err)))

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
    _more = (t("warn.drift_strong.more").format(n=len(drift_err)-8)
             if len(drift_err) > 8 else "")
    st.error(t("warn.drift_strong").format(
        items=', '.join(drift_err[:8]), more=_more))
elif drift_warn:
    st.warning(t("warn.drift_mild").format(n=len(drift_warn)))

# ----------------------------------------------------------- expert statistics
with st.expander(t("expert.expander"), expanded=False):
    st.markdown(t("expert.intro"))

    n_cand = len(candidates)
    n_feat = len(active_features)
    n_desc = len(metadata_only)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("expert.kpi.cands"), n_cand)
    col2.metric(t("expert.kpi.active"), n_feat)
    col3.metric(t("expert.kpi.descriptive"), n_desc)
    col4.metric(t("expert.kpi.ratio"),
                f"{int(panel_size)/n_cand:.1%}" if n_cand else "—")

    # ---------- consistency check across feature totals ----------------
    st.markdown(t("expert.consistency.h"))
    st.caption(t("expert.consistency.caption"))
    if consistency_rows:
        st.dataframe(pd.DataFrame(consistency_rows),
                     width='stretch', hide_index=True)
        _median_str = f"{int(round(_median_total)):,}".replace(",", "'")
        st.caption(t("expert.consistency.median").format(median=_median_str))
    else:
        st.info(t("expert.consistency.empty"))

    if joint_consistency_rows:
        st.caption(t("expert.joint_marg.caption"))
        st.dataframe(pd.DataFrame(joint_consistency_rows),
                     width='stretch', hide_index=True)

    # Per-feature comparison: candidate distribution vs. population.
    st.markdown(t("expert.compare.h"))
    st.caption(t("expert.compare.caption"))

    _col_delta_pp = t("expert.compare.col.delta_pp")
    _col_share_cand = t("expert.compare.col.share_cand")
    _col_share_pop = t("expert.compare.col.share_pop")
    _col_expected = t("expert.compare.col.expected")

    def _style_drift(df: pd.DataFrame):
        def row_style(row):
            d = abs(float(row[_col_delta_pp]))
            if d > 15:
                return ["background-color: #f8d7da"] * len(row)  # red
            if d > 5:
                return ["background-color: #fff3cd"] * len(row)  # yellow
            return [""] * len(row)
        return df.style.apply(row_style, axis=1).format({
            _col_share_cand: "{:.4f}",
            _col_share_pop: "{:.4f}",
            _col_delta_pp: "{:+.1f}",
            _col_expected: "{:.2f}",
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
                t("expert.compare.col.value"): v,
                t("expert.compare.col.n_cand"): cn,
                _col_share_cand: round(cs, 4),
                _col_share_pop: round(ps, 4),
                _col_delta_pp: round(delta_pp, 1),
                t("expert.compare.col.drift"): drift_flag,
                _col_expected: round(expected, 2),
                t("expert.compare.col.pool_ok"): "✓" if cn >= min_needed else "⚠",
            })
        tvd = tvd / 2
        st.markdown(t("expert.compare.tvd").format(feat=feat, tvd=tvd))
        st.dataframe(_style_drift(pd.DataFrame(rows)), width='stretch',
                     hide_index=True)

    # Joint coverage: useful when a joint distribution is loaded.
    if joint_loaded:
        st.markdown(t("expert.joint.h"))
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
        c1.metric(t("expert.joint.cells_with"),
                  f"{joint_cells_with_cands} / {joint_cells_total}")
        c2.metric(t("expert.joint.coverage"),
                  f"{joint_cells_with_cands/joint_cells_total:.1%}"
                  if joint_cells_total else "—")
        if empty_cells:
            st.warning(t("expert.joint.empty_warn").format(n=len(empty_cells)))
            with st.expander(t("expert.joint.empty_expander").format(
                    n=len(empty_cells)), expanded=False):
                st.dataframe(
                    pd.DataFrame(empty_cells,
                                 columns=[t("expert.joint.col.cell"),
                                          t("expert.joint.col.expected")]),
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
                t("expert.col.feature"): q.feature,
                t("expert.compare.col.value"): q.value,
                t("expert.pool.col.quota_min"): q.lo,
                t("expert.pool.col.in_pool"): n_in_pool,
                t("expert.pool.col.deficit"): q.lo - n_in_pool,
            })
    if risky:
        st.markdown(t("expert.pool.h"))
        st.error(t("expert.pool.err").format(n=len(risky)))
        st.dataframe(pd.DataFrame(risky), width='stretch', hide_index=True)
    else:
        st.success(t("expert.pool.ok"))


# ---------------------------------------------------------------- quotas preview
st.subheader(t("quotas.h"))
st.markdown(t("quotas.body"))
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
        t("quotas.joint_expander").format(n=len(joint_loaded)),
        expanded=False,
    ):
        st.markdown(t("quotas.joint_body"))
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
                    help=t("quotas.joint.col_help"),
                )
            joint_col_config["count"] = st.column_config.NumberColumn(
                t("pop.col.count"), min_value=0, step=1, format="%d")
            joint_col_config["share"] = st.column_config.NumberColumn(
                t("pop.col.share"), format="%.4f")
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
    with st.spinner(t("solve.spinner_members")):
        quotas: list[Quota] = default_quotas(population, int(panel_size))
        if use_joint and joint_loaded:
            quotas = quotas + default_joint_quotas(joint_loaded, int(panel_size))
        members = select_panel(candidates, quotas, int(panel_size), seed=int(seed))
except RuntimeError as e:
    st.error(t("solve.unsolvable").format(err=e))
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(t("solve.unexpected").format(err=f"{type(e).__name__}: {e}"))
    st.stop()

substitutes = None
sub_quotas: list[Quota] = []
sub_joint_dropped = False
if n_subs > 0:
    with st.spinner(t("solve.spinner_subs")):
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
    substitute_quotas=sub_quotas if substitutes is not None else None,
    inputs={"candidates": str(cand_path), "population": str(pop_path)},
    population_notes=population_notes,
)


# ---------------------------------------------------------------- results
st.subheader(t("result.h"))
c1, c2, c3, c4 = st.columns(4)
c1.metric(t("result.kpi.members"), len(members.panel))
c2.metric(t("result.kpi.subs"), 0 if substitutes is None else len(substitutes.panel))
c3.metric(t("result.kpi.minp"), f"{members.minimum_probability:.4f}")
c4.metric(t("result.kpi.runhash"), manifest["run_hash"][:12] + "…")

# Prominent relaxation warnings
all_relax = list(members.relaxations) + (substitutes.relaxations if substitutes else [])
if all_relax:
    with st.expander(t("result.relax_expander").format(n=len(all_relax)),
                     expanded=True):
        if members.relaxations:
            st.markdown(t("result.relax.members"))
            for r in members.relaxations:
                st.write("• " + r)
        if substitutes and substitutes.relaxations:
            st.markdown(t("result.relax.subs"))
            for r in substitutes.relaxations:
                st.write("• " + r)
else:
    st.success(t("result.no_relax"))

if sub_joint_dropped:
    st.warning(t("solve.sub_joint_dropped"))


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
    [t("result.tab.members"), t("result.tab.subs"), t("result.tab.bounds"),
     t("result.tab.probs"), t("result.tab.audit")]
)

with t_m:
    st.dataframe(_panel_table(members), width='stretch', height=420)

with t_s:
    if substitutes is None:
        st.write(t("result.subs.none"))
    else:
        st.dataframe(_panel_table(substitutes),
                     width='stretch', height=420)

with t_b:
    st.markdown(t("result.bounds.members_h"))
    st.caption(t("result.bounds.caption"))

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
        st.markdown(t("result.bounds.subs_h"))
        st.dataframe(_style_bounds(_bounds_table(substitutes, sub_quotas)),
                     width='stretch')

with t_p:
    df_p = pd.DataFrame(sorted(members.probabilities.items()),
                        columns=[t("result.probs.col_id"), t("result.probs.col_p")])
    st.dataframe(df_p, width='stretch', height=420)

with t_a:
    st.markdown(t("result.audit.runhash_h"))
    st.code(manifest["run_hash"])
    st.markdown(t("result.audit.parts_h"))
    st.json(manifest["hashes"])
    st.markdown(t("result.audit.rows_h"))
    st.dataframe(pd.DataFrame(manifest_audit_rows(manifest),
                              columns=[t("result.audit.col_key"),
                                       t("result.audit.col_val")]),
                 width='stretch', height=420)


# ---------------------------------------------------------------- downloads
st.subheader(t("dl.h"))
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
        t("dl.xlsx"),
        data=xlsx_path.read_bytes(),
        file_name="Losung-Ergebnis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
with col_b:
    st.download_button(
        t("dl.manifest"),
        data=json_buf.getvalue(),
        file_name="Losung-Manifest.json",
        mime="application/json",
    )
