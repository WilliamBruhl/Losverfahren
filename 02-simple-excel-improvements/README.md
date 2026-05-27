# 02 — Simple Improvements to the Existing Excel Workbook

This folder collects **small, local changes** that could be made directly to
the existing workbook. The goal is to keep the current Excel‑based workflow
intact while addressing the observations listed in
[../01-existing-implementation/](../01-existing-implementation/).

Each suggestion below maps back to one of the numbered observations. They are
roughly ordered from "lowest effort, highest value" to "nice to have".

## Generated artefacts

A first prototype of these improvements is already included:

- [patch_workbook.py](patch_workbook.py) — Python script (uses `openpyxl`,
  no other dependencies) that reads
  [../01-existing-implementation/PBD_Losung-Template.xlsx](../01-existing-implementation/PBD_Losung-Template.xlsx),
  applies suggestions A–G, and writes a patched workbook.
- [PBD_Losung-Patched.xlsx](PBD_Losung-Patched.xlsx) — the resulting workbook.
  The original sheets are kept untouched; the new logic lives in additional
  sheets:
  - `GemeindeMapping` — Nord/Süd table (A),
  - `KombinationOM_v2` / `KombinationEK_v2` — target table with `Verfügbar`,
    `Ziel (fraktional)`, `Ziel (Hamilton)`, `Ziel (geklemmt)`, `Differenz`
    columns (B + C + D),
  - `LosungOM_v2` / `LosungEK_v2` — the drawn members / substitutes (E + F),
  - `Audit` — timestamp, seed, SHA‑256 hash of the candidate list, target vs
    realised marginals, reallocation log (G).

Run it with:

```bash
python 02-simple-excel-improvements/patch_workbook.py --seed 20260527
```

Same input + same seed always produces the same panel.

## Proposed edits

### A. `GemeindeMapping` sheet — addresses observation 8

Add a small sheet listing each municipality and its Nord/Süd assignment, and
derive the population marginals from it via `SUMIF`. The grouping rule then
lives inside the workbook and survives a population‑data refresh.

### B. Joint age × sex × region target shares — addresses observation 1

`Bevölkerungsstruktur` already contains a true cross‑tab of age × sex ×
municipality. Build a pivot of joint shares and use them as targets for the
three‑dimensional combination; keep education as a marginal correction (since
only marginal data is available). This is a partial fix — it does not solve
the full joint problem, but it removes the easy part of the independence
assumption.

### C. Availability clamp + deficit reallocation — addresses observations 2 and 3

In `KombinationOM`:

1. Replace each per‑profile `Ausgewählt` with `MIN(target, Verfügbar)`.
2. Sum the resulting deficit into a "to reallocate" bucket.
3. Distribute the deficit to the nearest non‑empty cell along an explicit
   rule (e.g. same sex+age first, then same sex, then same region, …).

This makes the workbook's behaviour at the edges of the data explicit and
documented, instead of an emergent property of the rounding.

### D. Consistent integer rounding — addresses observation 4

Replace independent `ROUND` calls on the marginals with **Hamilton's
largest‑remainders** method, so that the rounded counts sum to 30 (resp. 15)
by construction. This can be done as a small helper table inside `Kriterien`.

### E. Seeded random draw inside each profile — addresses observations 5 and 7

For every profile with `target < Verfügbar`, the workbook should draw `target`
candidates uniformly at random from the matching volunteers. Two options:

- **Pure Excel:** add a `Seed` cell and a helper column that computes a
  reproducible pseudo‑random rank per candidate (e.g.
  `=MOD(SHA256(ID & Seed), 1e9)`); pick the lowest‑ranked `target` per
  profile. This keeps the workbook self‑contained.
- **Small Python / VBA helper:** a single script that reads the workbook,
  performs the seeded draw, and writes the results back. Slightly more setup
  but easier to maintain.

Either option makes the draw reproducible: same input + same seed ⇒ same
panel.

### F. Substitutes drawn from the remainder — addresses observation 6

Run the same procedure for the substitutes on the pool **minus the already
drawn members**. With option E in place this is a one‑line change.

### G. `Audit` sheet — addresses observation 7

A new sheet recording, per draw:

- timestamp,
- random seed,
- a hash of the candidate list (so any later edit is detectable),
- target vs realised marginals,
- the list of drawn IDs (members and substitutes).

This gives anyone reviewing the result enough information to replay and
verify it.

## What this track does *not* do

This track keeps the **product‑of‑marginals** structure of the workbook (with
the partial joint improvement in B). It does **not** implement the LEXIMIN
algorithm of Flanigan et al. — that is the topic of
[../03-gui-tool/](../03-gui-tool/).

## Suggested order of work

1. G — `Audit` sheet (purely additive, no risk to existing formulas)
2. A — `GemeindeMapping`
3. E — seeded random draw inside profiles
4. F — substitutes from the remainder
5. C — availability clamp + reallocation
6. D — Hamilton rounding
7. B — joint age × sex × region target shares
