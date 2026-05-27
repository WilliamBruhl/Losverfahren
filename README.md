# Losverfahren — Notes & Software Ideas for Stratified Sortition

This repository is a small **set of software‑engineering notes and prototypes**
written as a friendly suggestion for anyone else working on the
*tirage au sort* / *Auslosung* of members for a citizens' assembly.

It does **not** replace the existing methodology, which was developed by people
with much more expertise on the political‑science side of deliberative panels.
It is intended as **inspiration** for how some of the manual steps could be
supported with software, and how a small tool could make the same draw faster,
more reproducible, and easier to audit.

## Goal of stratified sortition (one paragraph)

Given a **population structure** (distributions of age, sex, place of
residence, education, …) and a **pool of candidates who accepted the
invitation**, the goal is to select a small panel (e.g. 30 members + 30
substitutes) that

1. **reflects the underlying population** as closely as possible on every
   stratifying attribute, and
2. is **as fair as possible**, i.e. every candidate gets as close to an equal
   selection probability as the quota constraints allow.

The references below (Flanigan et al. 2021; Sortition Foundation; panelot) all
work on exactly this problem.

---

## Repository layout

The repository is split into three folders so each piece can be read on its
own:

| Folder | Contents |
|---|---|
| [01-existing-implementation/](01-existing-implementation/) | The current Excel workbook and the slide deck explaining the procedure, plus a short walk‑through and a few observations from a software point of view. |
| [02-simple-excel-improvements/](02-simple-excel-improvements/) | **Track A** — small, local improvements that could be added directly to the existing workbook (no new tool required). |
| [03-gui-tool/](03-gui-tool/) | **Track B** — sketch of a stand‑alone GUI tool intended for admin staff, reusing existing open‑source code where possible. |

The two tracks are **complementary**: Track A is meant as a quick win that
keeps the current Excel‑based workflow; Track B is a longer‑term suggestion
that would replace it.

---

## Background and references

- Flanigan, B., Gölz, P., Gupta, A., Hennig, B., & Procaccia, A. D. (2021).
  *Fair algorithms for selecting citizens' assemblies.* **Nature** 596,
  548–552. https://www.nature.com/articles/s41586-021-03788-6
- **Panelot** — hosted reference implementation: https://panelot.org
- **Sortition Foundation** — services and methodology:
  https://www.sortitionfoundation.org/services
- **stratification‑app** — open‑source implementation (MIT) used by panelot /
  the Sortition Foundation: https://github.com/sortitionfoundation/stratification-app
- Replication code for the Nature paper:
  https://github.com/pgoelz/citizensassemblies-replication

---

## A note on tone

The observations in [01-existing-implementation/](01-existing-implementation/)
are written from a software‑engineering angle — things like reproducibility,
auditability, and what happens at the edges of the data. They are **not** a
critique of the methodological choices behind the workbook, several of which
are explicitly discussed in the accompanying slide deck (e.g. the limited
availability of joint cross‑tabs in the official statistics). They are simply
the kind of points a software person would want to discuss before turning the
procedure into a tool.
