# 01 — Existing Implementation

This folder holds the artefacts that describe the current procedure, exactly as
they were provided:

The actual workbook is not included in the public repo.

The workbook is a thoughtful manual implementation of the procedure described
in the slides. The notes below are written from a software‑engineering point
of view and are meant as discussion points for a possible tool, not as a
critique of the methodology.

## Workbook structure

| Sheet | Content |
|---|---|
| `VerfügbareTeilnehmer` | 71 candidates (ID, Geschlecht, Alterskategorie, Kanton, Ausbildung, Profil) — left side before the draw, right side after |
| `Bevölkerungsstruktur` | Population of the German‑speaking Community: age × sex × municipality × nationality, plus an education marginal |
| `Kriterien` | Target shares per attribute value, target counts for 30 members + 15 substitutes, "Rundung OK" check |
| `KombinationOM`, `LosungOM` | Per‑profile target counts and draw for the **ordentliche Mitglieder** |
| `KombinationEK`, `LosungEK` | Same for the **Ersatzkandidaten** |

## How the workbook computes the targets

For each (sex, age, region, education) profile, the workbook computes a target
share as the **product of the four population marginals**:

$$p_{\text{profile}} = p_{\text{sex}}\cdot p_{\text{age}}\cdot p_{\text{region}}\cdot p_{\text{edu}}$$

Multiplied by the panel size this gives a fractional target per profile, which
is then rounded to an integer. The right‑hand "Losung" tables mirror the
allocation back onto individual candidates.

This is a clean, transparent approach and it is easy to follow inside Excel —
which is a real strength when the result has to be defended in a political
setting.

## Observations from a software point of view

These are the points that stood out while reading the workbook. Each one comes
with a short note on what could be done about it; concrete proposals live in
[../02-simple-excel-improvements/](../02-simple-excel-improvements/) and
[../03-gui-tool/](../03-gui-tool/).

### 1. Joint distribution is approximated by independent marginals

Multiplying the four marginals assumes the four attributes are statistically
independent. They are usually not — education in particular tends to correlate
with age and region. Slide 2 of the deck notes a related limitation
(*"La distribution du niveau de formation correspond à la population d'au
moins 25 ans"*) and slide 5 explicitly mentions the combinatorial explosion
that makes a full joint approach hard.

`Bevölkerungsstruktur` already contains a true cross‑tab of age × sex ×
municipality, so a partial improvement is possible without new data: use the
joint share where the data allow, fall back to a marginal correction for
education.

### 2. Profiles with zero available candidates

A handful of profiles have no willing candidate at all (e.g. *Frau 16‑35 Süd
GrundschuleLehre*, *Mann 36‑55 Süd GrundschuleLehre*, …). The workbook leaves
their `Ausgewählt` at 0 and continues, which means the seat is silently lost
and the marginals drift slightly. On the supplied example the marginals still
come out clean (15/15, 18/12, …) because the dataset is small and the
proportions happen to align; on a larger run it is worth making the
reallocation rule explicit.

### 3. The opposite — asking for more people than exist

The mirror case: a rounded per‑cell target can in principle exceed the number
of willing people in that cell. A `MIN(target, available)` clamp plus an
explicit reallocation step would make this safe by construction.

### 4. Independent rounding does not guarantee a sum of 30

Each marginal is rounded with `ROUND(...)` independently. The workbook's
`Rundung: OK` check passes on the sample data because the numbers happen to
land near halves and thirds. On a larger dataset, independently rounded
marginals will not always sum to 30 (resp. 15) simultaneously. A consistent
method such as **Hamilton / largest remainders** or an ILP would make this
guarantee structural.

### 5. The actual random draw inside each profile

Slide 4 describes the procedure as two steps: (a) determine the 30 profiles,
(b) **draw at random** among the volunteers matching each profile. In the
workbook the right‑hand "after draw" table is currently a copy of the
left‑hand one — when a profile contains more volunteers than seats, the first
ones in list order would effectively be chosen. The Flanigan et al. paper
referenced on slide 7 exists precisely to handle this fairly; a seeded random
draw (or the LEXIMIN algorithm) would close this gap.

### 6. Members and substitutes are computed independently

`KombinationOM` / `LosungOM` and `KombinationEK` / `LosungEK` are independent.
Nothing structurally prevents the same person from ending up in both lists, or
the substitute draw from being suboptimal given the chosen members. A small
amount of glue could chain them.

### 7. Reproducibility and audit trail

Excel `RAND()` reshuffles on every recalculation, so a draw cannot be replayed
exactly. For a public, legitimacy‑critical process it would help a lot to
record: a fixed random seed, a hash of the candidate list, and the solver
version that produced the result.

### 8. Region grouping is implicit

Candidates carry `Kanton ∈ {Nord, Süd}`, but `Bevölkerungsstruktur` lists nine
municipalities. The Nord/Süd grouping rule lives outside the workbook, so it
has to be re‑applied manually whenever the population data is refreshed. A
small mapping sheet would make this explicit.

---

The next two folders propose ways to address these points: the
[simple Excel improvements](../02-simple-excel-improvements/) stay inside the
workbook, while the [GUI tool sketch](../03-gui-tool/) describes what a
stand‑alone application could look like.
