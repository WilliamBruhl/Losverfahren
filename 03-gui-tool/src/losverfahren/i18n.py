# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lightweight UI translations for the Streamlit app.

Two languages are supported: German (default) and English. Translations are
stored as a flat ``{language: {key: text}}`` dict. Use :func:`t` to look up
the current language from ``streamlit.session_state['lang']``.

Strings that contain runtime values use :py:meth:`str.format` placeholders;
callers do the interpolation, e.g. ``t("warn.drift_strong").format(pp=15.2)``.

This module intentionally avoids any heavyweight i18n framework — keys are
short dotted identifiers grouped by area (``sidebar.*``, ``expert.*``,
``warn.*`` …).
"""

from __future__ import annotations

from typing import Iterable

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit always available at runtime
    st = None  # type: ignore[assignment]


LANGUAGES: dict[str, str] = {"de": "Deutsch", "en": "English"}
DEFAULT_LANG = "de"


TRANSLATIONS: dict[str, dict[str, str]] = {
    "de": {
        # --- page / chrome ---
        "page.title": "Losverfahren — Bürgerpanel",
        "page.heading": "Losverfahren — geschichtete Zufallsauswahl",
        "page.caption": (
            "Prototyp: Maximin-LP + Quoten-konformes Sampling. "
            "Inputs sind editierbare CSVs; jede Anpassung der Bevölkerungs-Daten "
            "und jede Quoten-Relaxation wird im Audit dokumentiert."
        ),
        # --- sidebar: language ---
        "sidebar.lang": "Sprache / Language",
        # --- data format expander ---
        "fmt.title": "Datenformat (Spalten und Beispiel-Zeilen)",
        "fmt.body": (
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
        ),
        # --- sidebar: inputs ---
        "sidebar.h_inputs": "1 · Eingaben",
        "sidebar.source": "Quelle",
        "sidebar.source.examples": "Beispiel-Daten verwenden",
        "sidebar.source.upload": "Eigene Dateien hochladen",
        "sidebar.source.help": (
            "Beispiel-Daten: bündelte CSVs aus dem mitgelieferten "
            "PBD-Template. Eigene Dateien: zwei (oder drei) CSVs "
            "im selben Format hochladen."
        ),
        "sidebar.example.none": "Keine Beispiel-Datensätze gefunden.",
        "sidebar.example.label": "Beispiel-Datensatz",
        "sidebar.example.help": (
            "Drei kuratierte Datensätze plus die PBD-Vorlage. Jeder "
            "demonstriert ein anderes Schema/eine andere Sprache — "
            "die Tool-Logik passt sich automatisch an."
        ),
        "sidebar.example.missing": "Beispiel-Daten nicht gefunden unter {path}",
        "sidebar.example.readme": "Datensatz-Beschreibung",
        "sidebar.example.joint_note": " + Joint-Verteilung",
        "sidebar.example.loaded": "Geladen: **{choice}**{joint_note}",
        "sidebar.upload.cand": "Kandidatenliste (.csv oder .xlsx)",
        "sidebar.upload.pop": "Bevölkerungsstruktur — Marginalen (.csv oder .xlsx)",
        "sidebar.upload.joint": "Bevölkerungsstruktur — Joint-Verteilung (optional, .csv)",
        "sidebar.upload.joint.help": (
            "Optional. Eine zusätzliche CSV mit der gemeinsamen Verteilung "
            "mehrerer Merkmale (z.B. Geschlecht × Alterskategorie × "
            "Kanton). Liefert reichere Information als die Marginalen "
            "alleine — wird automatisch zugeschaltet, sobald hochgeladen. "
            "Format siehe »Datenformat« im Hauptbereich."
        ),
        "sidebar.upload.need_more": "Mindestens Kandidaten und Marginalen hochladen, um fortzufahren.",
        "sidebar.use_joint": "Joint-Quoten zusätzlich erzwingen",
        "sidebar.use_joint.help": (
            "Wenn aktiviert, werden zusätzlich Quoten für jede Zelle der "
            "joint Verteilung an die LP übergeben. Sonst werden nur die "
            "Marginalen verwendet. Wird automatisch aktiviert, sobald eine "
            "Joint-CSV vorhanden ist."
        ),
        "sidebar.h_params": "2 · Parameter",
        "sidebar.panel_size": "Panelgröße",
        "sidebar.n_subs": "Ersatzpersonen",
        "sidebar.seed": "Seed",
        "sidebar.run": "Auslosung starten",
        # --- data load errors ---
        "load.cand_fail": (
            "Kandidatenliste konnte nicht gelesen werden. Mindestens eine Spalte "
            "`ID` (oder ein Synonym wie `Nummer`, `Code`) plus eine "
            "Stratifizierungs-Spalte sind erforderlich."
        ),
        "load.pop_fail": (
            "Bevölkerungs-Marginalen konnten nicht gelesen werden. Erwartet wird "
            "eine CSV mit Spalten `feature, value, count` (oder `share`); "
            "optional `note`."
        ),
        "load.pop_table_fail": "Bevölkerungs-CSV ließ sich nicht in eine Tabelle laden.",
        "load.joint_fail": (
            "Joint-Bevölkerungs-CSV konnte nicht gelesen werden — die "
            "Auslosung läuft nur mit den Marginalen weiter. Details: "
            "`{err}`"
        ),
        # --- candidates editor ---
        "cand.h": "Kandidaten (editierbar)",
        "cand.schema_expander": "Erkanntes Schema",
        "cand.schema.active": "- **Aktive Merkmale (Quoten)**: {features}",
        "cand.schema.none": "_keine_",
        "cand.schema.descriptive": (
            "- **Nur deskriptiv** (in Kandidaten, nicht in Bevölkerung): {features}"
        ),
        "cand.schema.missing": (
            "In `population.csv` definierte Merkmale, die in `candidates.csv` "
            "fehlen — sie können nicht als Quote benutzt werden: {features}"
        ),
        "cand.no_overlap": (
            "Keine überlappenden Merkmale zwischen `candidates.csv` und "
            "`population.csv` gefunden. Bitte sicherstellen, dass beide Dateien "
            "die gleichen Spalten-/`feature`-Namen verwenden (groß-/kleinschrift- "
            "und akzentempfindlich)."
        ),
        "cand.col.id_help": "Eindeutige Kandidaten-Kennung.",
        "cand.col.feat_help": (
            "Werte stammen aus `population.csv` / bereits vorhandenen "
            "Einträgen. Neue Ausprägungen zuerst in der "
            "Bevölkerungs-Tabelle anlegen."
        ),
        "cand.col.desc_help": "Nur deskriptiv — wird für Quoten nicht verwendet.",
        "cand.count": "{n} Kandidaten geladen.",
        # --- population editor ---
        "pop.h": "Bevölkerungsstruktur (editierbar)",
        "pop.body": (
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
        ),
        "pop.col.feature": "feature (Merkmal)",
        "pop.col.feature_help": (
            "Dropdown mit bereits vorhandenen Merkmalen. Ein neues "
            "Merkmal anlegen: neue Zeile, Feldname in der Spalte "
            "`feature` direkt eintippen (das ist nur über den "
            "Stiftknopf möglich, sobald die Zeile aktiv ist)."
        ),
        "pop.col.value": "value (Ausprägung)",
        "pop.col.value_help": "Frei wählbar; muss innerhalb eines Merkmals eindeutig sein.",
        "pop.col.count": "count (Anzahl Personen)",
        "pop.col.count_help": "Rohzahl aus der Bevölkerungs-Statistik.",
        "pop.col.share": "share (abgeleitet)",
        "pop.col.share_help": "Wird automatisch berechnet — keine Eingabe nötig.",
        "pop.col.note": "note (frei)",
        "pop.derived_expander": "Abgeleitete Anteile (Kontrolle)",
        "pop.derived.col_share": "share (derived)",
        # --- top-level consistency warnings ---
        "warn.consistency.err": (
            "**Inkonsistente Bevölkerungs-Summen**: {features} weichen > 10 % "
            "vom Median ({median} Personen) ab. Das deutet meist auf "
            "unterschiedliche Stichjahre, abweichende Altersuntergrenzen oder "
            "einen Tippfehler hin. Das Tool rechnet trotzdem weiter (jedes "
            "Merkmal wird separat auf Summe 1 normalisiert), aber das Resultat "
            "repräsentiert dann eine *Mischpopulation*. Details unter "
            "»Statistik / Expertenmodus« weiter unten."
        ),
        "warn.consistency.warn": (
            "**Bevölkerungs-Summen leicht inkonsistent**: {features} weichen "
            "2 – 10 % vom Median ab. Details unter »Statistik / Expertenmodus«."
        ),
        "warn.joint_mismatch": (
            "**Joint-Verteilung passt nicht zu den Marginalen**: Summe der "
            "Joint-Counts weicht > 10 % von den Marginal-Summen für {features} "
            "ab. Wahrscheinlich stammen Joint- und Marginal-Daten aus "
            "unterschiedlichen Quellen. Bitte prüfen."
        ),
        "warn.drift_strong": (
            "**Starke Pool-Verzerrung gegenüber der Bevölkerung** "
            "(> 15 Prozentpunkte) bei: {items}{more}. "
            "Der Solver kann das im Rahmen der Quoten ausgleichen, aber bei "
            "kleinem Pool wird er einige Quoten relaxieren müssen. Details und "
            "Farbkennzeichnung unter »Statistik / Expertenmodus« weiter unten."
        ),
        "warn.drift_strong.more": " … (+{n} weitere)",
        "warn.drift_mild": (
            "**Pool weicht spürbar von der Bevölkerung ab** "
            "(5 – 15 pp bei {n} Ausprägung(en)). Details unter "
            "»Statistik / Expertenmodus«."
        ),
        # --- expert mode ---
        "expert.expander": "Statistik / Expertenmodus",
        "expert.intro": (
            "Diagnose-Informationen über Kandidatenpool und Bevölkerungs-Vergleich "
            "— hilfreich, um *vor* der Auslosung systematische Verzerrungen zu "
            "erkennen."
        ),
        "expert.kpi.cands": "Kandidaten",
        "expert.kpi.active": "Aktive Merkmale",
        "expert.kpi.descriptive": "Nur deskriptiv",
        "expert.kpi.ratio": "Panel-/Pool-Quote",
        "expert.consistency.h": "**Konsistenz-Check**",
        "expert.consistency.caption": (
            "Jedes Merkmal wird *intern unabhängig* auf Summe 1 normalisiert "
            "(`share = count / Σ count` pro Merkmal). Dadurch funktioniert das "
            "Tool auch, wenn die Marginalen aus unterschiedlichen Quellen / "
            "Stichjahren stammen — verbirgt aber Inkonsistenzen. Diese Tabelle "
            "zeigt die Roh-Summen *vor* der Normalisierung."
        ),
        "expert.consistency.median": (
            "Median-Gesamtbevölkerung über alle Merkmale: **{median}**. "
            "Toleranz: ±2 % ✓, ±10 % ⚠, darüber ✗."
        ),
        "expert.consistency.empty": (
            "Keine `count`-Werte vorhanden — Konsistenz-Check übersprungen "
            "(es werden direkt die `share`-Werte verwendet)."
        ),
        "expert.joint_marg.caption": "**Joint ↔ Marginalen** (Summen sollten übereinstimmen)",
        "expert.col.feature": "feature",
        "expert.col.sum_count": "Σ count",
        "expert.col.delta_median": "Δ vs. Median (%)",
        "expert.col.status": "Status",
        "expert.col.joint_covers": "Joint deckt",
        "expert.col.sum_joint": "Σ Joint count",
        "expert.col.sum_marg": "Σ Marginal count",
        "expert.col.delta_pct": "Δ (%)",
        "expert.compare.h": (
            "**Verteilungs-Vergleich pro Merkmal** "
            "(Kandidaten-Anteil vs. Bevölkerungs-Anteil)"
        ),
        "expert.compare.caption": (
            "Flagge: **✓** ≤ 5 pp Abweichung, **⚠** 5 – 15 pp (gelb hinterlegt), "
            "**✗** > 15 pp (rot hinterlegt) — gleiche Farb-Konvention wie bei "
            "der Quoten-Realisierung weiter unten."
        ),
        "expert.compare.tvd": (
            "*`{feat}`* — Total Variation Distance "
            "$d_{{TV}} = \\tfrac12 \\sum |p_{{cand}} - p_{{pop}}|$ = "
            "**{tvd:.3f}**  "
            "(0 = perfekt repräsentativ, 1 = vollständig disjunkt)"
        ),
        "expert.compare.col.value": "value",
        "expert.compare.col.n_cand": "n_Kand.",
        "expert.compare.col.share_cand": "Anteil_Kand.",
        "expert.compare.col.share_pop": "Anteil_Bev.",
        "expert.compare.col.delta_pp": "Δ (pp)",
        "expert.compare.col.drift": "Drift",
        "expert.compare.col.expected": "erwartet @ Panel",
        "expert.compare.col.pool_ok": "Pool-OK?",
        "expert.joint.h": "**Joint-Zellen-Abdeckung**",
        "expert.joint.cells_with": "Zellen mit ≥1 Kandidaten",
        "expert.joint.coverage": "Abdeckungsquote",
        "expert.joint.empty_warn": (
            "{n} Joint-Zellen haben **keinen** "
            "passenden Kandidaten — diese können nur durch "
            "Quoten-Relaxation oder Pool-Aufstockung berücksichtigt "
            "werden."
        ),
        "expert.joint.empty_expander": "Leere Zellen ({n})",
        "expert.joint.col.cell": "Zelle",
        "expert.joint.col.expected": "erwartet @ Panel",
        "expert.pool.h": "**Pool-Engpässe**",
        "expert.pool.err": (
            "{n} Merkmals-Ausprägung(en) haben weniger Kandidaten "
            "als die strikte Mindest-Quote verlangt. Der Solver wird hier "
            "automatisch relaxieren (gelb markiert in der Ergebnis-Tabelle "
            "weiter unten)."
        ),
        "expert.pool.col.quota_min": "Quote (min)",
        "expert.pool.col.in_pool": "im Pool",
        "expert.pool.col.deficit": "Defizit",
        "expert.pool.ok": (
            "Alle Marginal-Quoten sind aus dem Pool heraus theoretisch "
            "erfüllbar (keine sofortige Relaxation nötig)."
        ),
        # --- quotas preview ---
        "quotas.h": "Quoten (abgeleitet)",
        "quotas.body": (
            "Für eine Panelgröße $k$ und einen Bevölkerungs-Anteil $\\pi$ wird das "
            "Quoten-Intervall als $[\\lfloor k\\cdot\\pi \\rfloor,\\, \\lceil k\\cdot\\pi \\rceil]$ "
            "gesetzt. Das ist immer ein Bereich der Länge 0 oder 1 — das hält den "
            "Solver auch dann lösbar, wenn die Bevölkerungs-Anteile keine ganzen "
            "Personen ergeben.\n\n"
            "Anpassungen an der Bevölkerungs-Tabelle oben werden hier sofort sichtbar."
        ),
        "quotas.joint_expander": "Joint-Verteilung (Geschlecht×Alter×Kanton) — {n} Zellen",
        "quotas.joint_body": (
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
        ),
        "quotas.joint.col_help": (
            "Auswahl aus `population.csv` plus bereits vorhandene "
            "Werte dieser Dimension."
        ),
        # --- solve ---
        "solve.spinner_members": "Mitgliederpanel wird ausgelost …",
        "solve.spinner_subs": "Ersatzpersonen werden ausgelost …",
        "solve.unsolvable": (
            "**Die Auslosung der Mitglieder ist nicht lösbar.** "
            "Häufige Ursachen: Panelgröße größer als der Kandidatenpool, "
            "Quoten verlangen mehr Personen einer Kategorie als verfügbar, "
            "oder Joint-Verteilung zu fein für den Pool. "
            "\n\nDetails: `{err}`"
        ),
        "solve.unexpected": "**Unerwarteter Fehler bei der Auslosung.**\n\n`{err}`",
        "solve.sub_joint_dropped": (
            "Für die Ersatzpersonen waren die Joint-Quoten nicht erfüllbar — "
            "die Auslosung der Ersatzpersonen erfolgte nur mit den Marginalen. "
            "Joint-Verteilung bleibt für die Mitglieder erzwungen."
        ),
        # --- results ---
        "result.h": "3 · Ergebnis",
        "result.kpi.members": "Mitglieder",
        "result.kpi.subs": "Ersatz",
        "result.kpi.minp": "Min p_i (Mitglieder)",
        "result.kpi.runhash": "Run-Hash",
        "result.relax_expander": "⚠ {n} Quoten-Anpassung(en) — bitte prüfen",
        "result.relax.members": "**Mitglieder:**",
        "result.relax.subs": "**Ersatz:**",
        "result.no_relax": "Alle Quoten wurden ohne Anpassung erfüllt.",
        "result.tab.members": "Mitglieder",
        "result.tab.subs": "Ersatz",
        "result.tab.bounds": "Quoten vs. Ist",
        "result.tab.probs": "Wahrscheinlichkeiten",
        "result.tab.audit": "Audit / Hashes",
        "result.subs.none": "Keine Ersatzpersonen angefordert.",
        "result.bounds.members_h": "**Mitglieder — Quoten-Intervall vs. realisiert**",
        "result.bounds.subs_h": "**Ersatz — Quoten-Intervall vs. realisiert**",
        "result.bounds.caption": (
            "🟡 gelb hinterlegte Zeilen = die Standardgrenzen `lo_default` / "
            "`hi_default` mussten relaxiert werden, damit der Solver lösbar bleibt "
            "(z.B. weil der Kandidatenpool nicht genug Personen einer Kategorie "
            "enthält). 🔴 rot = realisierte Anzahl außerhalb des effektiven "
            "Intervalls (sollte praktisch nie vorkommen)."
        ),
        "result.probs.col_id": "ID",
        "result.probs.col_p": "p_member",
        "result.audit.runhash_h": "**Run-Hash (SHA-256)**",
        "result.audit.parts_h": "**Einzel-Hashes**",
        "result.audit.rows_h": "**Audit-Zeilen**",
        "result.audit.col_key": "Schlüssel",
        "result.audit.col_val": "Wert",
        # --- downloads ---
        "dl.h": "4 · Download",
        "dl.xlsx": "Excel-Workbook (.xlsx)",
        "dl.manifest": "Manifest (.json, inkl. Hashes)",
    },
    "en": {
        # --- page / chrome ---
        "page.title": "Sortition — Citizens' Panel",
        "page.heading": "Sortition — stratified random selection",
        "page.caption": (
            "Prototype: maximin LP + quota-compliant sampling. "
            "Inputs are editable CSVs; every adjustment to the population data "
            "and every quota relaxation is recorded in the audit."
        ),
        # --- sidebar: language ---
        "sidebar.lang": "Sprache / Language",
        # --- data format expander ---
        "fmt.title": "Data format (columns and example rows)",
        "fmt.body": (
            "Three CSV files are supported — all UTF-8, comma-separated, with "
            "the first row as the header. Legacy Excel templates (`.xlsx`) in "
            "the PBD format are still accepted.\n\n"
            "### Flexible schemas\n"
            "Features (gender, age, region, occupation, …) are **not "
            "hard-wired**: you can use any columns in `candidates.csv`, as "
            "long as the same names also appear in `population.csv` as "
            "`feature` values. Language and number of columns are free.\n\n"
            "The column header itself also tolerates synonyms — e.g. "
            "`Anzahl` for `count`, `Anteil` for `share`, `Merkmal` for "
            "`feature`, `Wert` for `value`, `Bemerkung` for `note`, "
            "`Nummer` for `ID` (non-exhaustive list).\n\n"
            "**1 · `candidates.csv` (required)** — one row per person.\n\n"
            "```\n"
            "ID,Geschlecht,Alterskategorie,Kanton,Ausbildung\n"
            "K001,Mann,36-55,Nord,AbiturMeister\n"
            "K002,Frau,16-35,Süd,DualBachelor\n"
            "```\n"
            "Every column except `ID` is a stratification feature. Additional "
            "descriptive columns (e.g. `Email`) are carried through but are "
            "only used for quotas if they also appear in `population.csv`.\n\n"
            "**2 · `population.csv` (required, marginals)** — one row per "
            "feature value. Preferably with a `count` column (number of "
            "people); `share` (proportion 0–1) is also accepted. `note` is "
            "free-form.\n\n"
            "```\n"
            "feature,value,count,note\n"
            "Geschlecht,Mann,31982,\n"
            "Geschlecht,Frau,32640,\n"
            "Alterskategorie,16-35,18223,Stand 2024\n"
            "```\n\n"
            "**3 · `population_joint.csv` (optional, joint distribution)** — "
            "one row per combination. Any number of dimension columns plus "
            "`count` (or `share`).\n\n"
            "```\n"
            "Geschlecht,Alterskategorie,Kanton,count\n"
            "Mann,16-35,Nord,5612\n"
            "Frau,56+,Süd,4933\n"
            "```\n\n"
            "**Do I need file 3?** No — the marginals from file 2 are enough "
            "for a correct draw. The joint file ensures that *combinations* "
            "(e.g. \"young men in the north\") are also realistically "
            "represented in the panel. With a small candidate pool it can "
            "tighten the draw; in that case the tool automatically falls "
            "back to the marginals and notes that."
        ),
        # --- sidebar: inputs ---
        "sidebar.h_inputs": "1 · Inputs",
        "sidebar.source": "Source",
        "sidebar.source.examples": "Use example data",
        "sidebar.source.upload": "Upload your own files",
        "sidebar.source.help": (
            "Example data: bundled CSVs from the included PBD template. "
            "Your own files: upload two (or three) CSVs in the same format."
        ),
        "sidebar.example.none": "No example datasets found.",
        "sidebar.example.label": "Example dataset",
        "sidebar.example.help": (
            "Three curated datasets plus the PBD template. Each demonstrates "
            "a different schema/language — the tool logic adapts automatically."
        ),
        "sidebar.example.missing": "Example data not found at {path}",
        "sidebar.example.readme": "Dataset description",
        "sidebar.example.joint_note": " + joint distribution",
        "sidebar.example.loaded": "Loaded: **{choice}**{joint_note}",
        "sidebar.upload.cand": "Candidate list (.csv or .xlsx)",
        "sidebar.upload.pop": "Population structure — marginals (.csv or .xlsx)",
        "sidebar.upload.joint": "Population structure — joint distribution (optional, .csv)",
        "sidebar.upload.joint.help": (
            "Optional. An extra CSV with the joint distribution of several "
            "features (e.g. gender × age band × region). Provides richer "
            "information than the marginals alone — automatically enabled "
            "as soon as it is uploaded. See »Data format« in the main area."
        ),
        "sidebar.upload.need_more": "Upload at least candidates and marginals to continue.",
        "sidebar.use_joint": "Additionally enforce joint quotas",
        "sidebar.use_joint.help": (
            "When enabled, quotas for every cell of the joint distribution "
            "are also passed to the LP. Otherwise only the marginals are "
            "used. Automatically enabled as soon as a joint CSV is present."
        ),
        "sidebar.h_params": "2 · Parameters",
        "sidebar.panel_size": "Panel size",
        "sidebar.n_subs": "Substitutes",
        "sidebar.seed": "Seed",
        "sidebar.run": "Start draw",
        # --- data load errors ---
        "load.cand_fail": (
            "Could not read the candidate list. At least an `ID` column (or "
            "a synonym like `Nummer`, `Code`) plus one stratification column "
            "are required."
        ),
        "load.pop_fail": (
            "Could not read the population marginals. Expected a CSV with "
            "columns `feature, value, count` (or `share`); optional `note`."
        ),
        "load.pop_table_fail": "Could not load the population CSV into a table.",
        "load.joint_fail": (
            "Joint population CSV could not be read — the draw will continue "
            "with the marginals only. Details: `{err}`"
        ),
        # --- candidates editor ---
        "cand.h": "Candidates (editable)",
        "cand.schema_expander": "Detected schema",
        "cand.schema.active": "- **Active features (quotas)**: {features}",
        "cand.schema.none": "_none_",
        "cand.schema.descriptive": (
            "- **Descriptive only** (in candidates, not in population): {features}"
        ),
        "cand.schema.missing": (
            "Features defined in `population.csv` that are missing from "
            "`candidates.csv` — they cannot be used as quotas: {features}"
        ),
        "cand.no_overlap": (
            "No overlapping features between `candidates.csv` and "
            "`population.csv` were found. Please ensure both files use the "
            "same column / `feature` names (case- and accent-sensitive)."
        ),
        "cand.col.id_help": "Unique candidate identifier.",
        "cand.col.feat_help": (
            "Values come from `population.csv` / existing entries. Add new "
            "values to the population table first."
        ),
        "cand.col.desc_help": "Descriptive only — not used for quotas.",
        "cand.count": "{n} candidates loaded.",
        # --- population editor ---
        "pop.h": "Population structure (editable)",
        "pop.body": (
            "**Input format:** the `count` column holds the number of people "
            "per feature value — exactly as it comes from the official "
            "population tables. You can adjust the numbers directly in the "
            "table, e.g. to load fresh statistics.\n\n"
            "The `share` column (proportion) is derived **automatically** "
            "from the `count` values and normalised to 1 per feature. "
            "`share` is informational only — the solver always uses the "
            "derived shares.\n\n"
            "The `note` column is for internal remarks (e.g. *\"2022 data, "
            "update pending\"*). It does not affect the result but is "
            "carried through into the audit entry."
        ),
        "pop.col.feature": "feature",
        "pop.col.feature_help": (
            "Dropdown with already known features. To add a new feature: "
            "new row, type the field name directly into the `feature` "
            "column (only possible via the pencil button once the row is "
            "active)."
        ),
        "pop.col.value": "value",
        "pop.col.value_help": "Free-form; must be unique within a feature.",
        "pop.col.count": "count (number of people)",
        "pop.col.count_help": "Raw number from the population statistics.",
        "pop.col.share": "share (derived)",
        "pop.col.share_help": "Computed automatically — no input required.",
        "pop.col.note": "note (free-form)",
        "pop.derived_expander": "Derived shares (sanity check)",
        "pop.derived.col_share": "share (derived)",
        # --- top-level consistency warnings ---
        "warn.consistency.err": (
            "**Inconsistent population totals**: {features} differ by more "
            "than 10 % from the median ({median} people). This usually "
            "indicates different reference years, diverging age cutoffs, or "
            "a typo. The tool still proceeds (each feature is normalised to "
            "sum 1 independently), but the result then represents a *mixed "
            "population*. See »Statistics / Expert mode« below for details."
        ),
        "warn.consistency.warn": (
            "**Population totals slightly inconsistent**: {features} differ "
            "by 2 – 10 % from the median. See »Statistics / Expert mode« "
            "for details."
        ),
        "warn.joint_mismatch": (
            "**Joint distribution does not match the marginals**: the sum "
            "of joint counts differs by more than 10 % from the marginal "
            "totals for {features}. Joint and marginal data probably come "
            "from different sources. Please check."
        ),
        "warn.drift_strong": (
            "**Strong pool skew vs. the population** (> 15 percentage "
            "points) at: {items}{more}. The solver can absorb this within "
            "the quota bands, but with a small pool some quotas will have "
            "to be relaxed. Details and colour coding under »Statistics / "
            "Expert mode« below."
        ),
        "warn.drift_strong.more": " … (+{n} more)",
        "warn.drift_mild": (
            "**Pool deviates noticeably from the population** "
            "(5 – 15 pp for {n} value(s)). See »Statistics / Expert mode« "
            "for details."
        ),
        # --- expert mode ---
        "expert.expander": "Statistics / Expert mode",
        "expert.intro": (
            "Diagnostic information about the candidate pool and the "
            "comparison with the population — useful to spot systematic "
            "biases *before* running the draw."
        ),
        "expert.kpi.cands": "Candidates",
        "expert.kpi.active": "Active features",
        "expert.kpi.descriptive": "Descriptive only",
        "expert.kpi.ratio": "Panel / pool ratio",
        "expert.consistency.h": "**Consistency check**",
        "expert.consistency.caption": (
            "Each feature is normalised to sum 1 *independently* "
            "(`share = count / Σ count` per feature). This makes the tool "
            "robust even when marginals come from different sources or "
            "reference years — but it can hide inconsistencies. This table "
            "shows the raw totals *before* normalisation."
        ),
        "expert.consistency.median": (
            "Median total population across all features: **{median}**. "
            "Tolerance: ±2 % ✓, ±10 % ⚠, beyond that ✗."
        ),
        "expert.consistency.empty": (
            "No `count` values present — consistency check skipped "
            "(the `share` values are used directly)."
        ),
        "expert.joint_marg.caption": "**Joint ↔ marginals** (sums should match)",
        "expert.col.feature": "feature",
        "expert.col.sum_count": "Σ count",
        "expert.col.delta_median": "Δ vs. median (%)",
        "expert.col.status": "Status",
        "expert.col.joint_covers": "Joint covers",
        "expert.col.sum_joint": "Σ joint count",
        "expert.col.sum_marg": "Σ marginal count",
        "expert.col.delta_pct": "Δ (%)",
        "expert.compare.h": (
            "**Per-feature distribution comparison** "
            "(candidate share vs. population share)"
        ),
        "expert.compare.caption": (
            "Flag: **✓** ≤ 5 pp deviation, **⚠** 5 – 15 pp (yellow), "
            "**✗** > 15 pp (red) — same colour convention as in the quota "
            "realisation table further down."
        ),
        "expert.compare.tvd": (
            "*`{feat}`* — total variation distance "
            "$d_{{TV}} = \\tfrac12 \\sum |p_{{cand}} - p_{{pop}}|$ = "
            "**{tvd:.3f}**  "
            "(0 = perfectly representative, 1 = completely disjoint)"
        ),
        "expert.compare.col.value": "value",
        "expert.compare.col.n_cand": "n_cand.",
        "expert.compare.col.share_cand": "share_cand.",
        "expert.compare.col.share_pop": "share_pop.",
        "expert.compare.col.delta_pp": "Δ (pp)",
        "expert.compare.col.drift": "Drift",
        "expert.compare.col.expected": "expected @ panel",
        "expert.compare.col.pool_ok": "Pool OK?",
        "expert.joint.h": "**Joint cell coverage**",
        "expert.joint.cells_with": "Cells with ≥1 candidate",
        "expert.joint.coverage": "Coverage rate",
        "expert.joint.empty_warn": (
            "{n} joint cells have **no** matching candidate — these can only "
            "be honoured through quota relaxation or pool top-up."
        ),
        "expert.joint.empty_expander": "Empty cells ({n})",
        "expert.joint.col.cell": "Cell",
        "expert.joint.col.expected": "expected @ panel",
        "expert.pool.h": "**Pool bottlenecks**",
        "expert.pool.err": (
            "{n} feature value(s) have fewer candidates than the strict "
            "minimum quota requires. The solver will relax these "
            "automatically (highlighted yellow in the result table below)."
        ),
        "expert.pool.col.quota_min": "Quota (min)",
        "expert.pool.col.in_pool": "in pool",
        "expert.pool.col.deficit": "Deficit",
        "expert.pool.ok": (
            "All marginal quotas are in principle satisfiable from the pool "
            "(no immediate relaxation needed)."
        ),
        # --- quotas preview ---
        "quotas.h": "Quotas (derived)",
        "quotas.body": (
            "For a panel size $k$ and a population share $\\pi$, the quota "
            "interval is set to $[\\lfloor k\\cdot\\pi \\rfloor,\\, "
            "\\lceil k\\cdot\\pi \\rceil]$. That is always a band of width "
            "0 or 1 — keeping the solver feasible even when the population "
            "shares do not yield whole persons.\n\n"
            "Edits to the population table above are reflected here "
            "immediately."
        ),
        "quotas.joint_expander": "Joint distribution (gender × age × region) — {n} cells",
        "quotas.joint_body": (
            "This table represents the **joint** distribution of "
            "gender × age × region and comes directly from the official "
            "population cross-tab. When enabled (checkbox on the left), the "
            "solver requires a minimum and maximum count per cell in the "
            "panel — the result then mirrors the population structure more "
            "finely than with marginals alone.\n\n"
            "**With a tight candidate pool this can make the substitutes' "
            "draw infeasible.** In that case the tool automatically falls "
            "back to the marginals and notes that above in a warning box."
        ),
        "quotas.joint.col_help": (
            "Choices from `population.csv` plus existing values along this "
            "dimension."
        ),
        # --- solve ---
        "solve.spinner_members": "Drawing the member panel …",
        "solve.spinner_subs": "Drawing the substitutes …",
        "solve.unsolvable": (
            "**The member draw is infeasible.** Common causes: panel size "
            "larger than the candidate pool, quotas demanding more people "
            "of a category than available, or joint distribution too fine "
            "for the pool. \n\nDetails: `{err}`"
        ),
        "solve.unexpected": "**Unexpected error during the draw.**\n\n`{err}`",
        "solve.sub_joint_dropped": (
            "The joint quotas were infeasible for the substitutes — the "
            "substitutes were drawn with the marginals only. The joint "
            "distribution remains enforced for the members."
        ),
        # --- results ---
        "result.h": "3 · Result",
        "result.kpi.members": "Members",
        "result.kpi.subs": "Substitutes",
        "result.kpi.minp": "Min p_i (members)",
        "result.kpi.runhash": "Run hash",
        "result.relax_expander": "⚠ {n} quota adjustment(s) — please review",
        "result.relax.members": "**Members:**",
        "result.relax.subs": "**Substitutes:**",
        "result.no_relax": "All quotas were met without adjustment.",
        "result.tab.members": "Members",
        "result.tab.subs": "Substitutes",
        "result.tab.bounds": "Quotas vs. actual",
        "result.tab.probs": "Probabilities",
        "result.tab.audit": "Audit / hashes",
        "result.subs.none": "No substitutes requested.",
        "result.bounds.members_h": "**Members — quota interval vs. realised**",
        "result.bounds.subs_h": "**Substitutes — quota interval vs. realised**",
        "result.bounds.caption": (
            "🟡 yellow rows = the default bounds `lo_default` / "
            "`hi_default` had to be relaxed so that the solver stays "
            "feasible (e.g. because the candidate pool lacks enough people "
            "in a category). 🔴 red = realised count outside the effective "
            "interval (should virtually never happen)."
        ),
        "result.probs.col_id": "ID",
        "result.probs.col_p": "p_member",
        "result.audit.runhash_h": "**Run hash (SHA-256)**",
        "result.audit.parts_h": "**Component hashes**",
        "result.audit.rows_h": "**Audit rows**",
        "result.audit.col_key": "Key",
        "result.audit.col_val": "Value",
        # --- downloads ---
        "dl.h": "4 · Download",
        "dl.xlsx": "Excel workbook (.xlsx)",
        "dl.manifest": "Manifest (.json, incl. hashes)",
    },
}


def current_lang() -> str:
    """Return the active language code from session state, defaulting to German."""
    if st is None:
        return DEFAULT_LANG
    return st.session_state.get("lang", DEFAULT_LANG)


def t(key: str) -> str:
    """Look up *key* for the current language. Falls back to the key itself."""
    lang = current_lang()
    bundle = TRANSLATIONS.get(lang) or TRANSLATIONS[DEFAULT_LANG]
    if key in bundle:
        return bundle[key]
    # Last-resort fallback so a missing key never crashes the UI.
    return TRANSLATIONS[DEFAULT_LANG].get(key, key)


def join_codes(codes: Iterable[str]) -> str:
    """Helper to format a list of feature names as inline code, comma separated."""
    return ", ".join(f"`{x}`" for x in codes)
