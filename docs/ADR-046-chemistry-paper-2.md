# ADR-046 — Chemistry (Paper 2) in Physical Sciences

**Date:** 19 Nov 2026 · **Status:** Accepted

## Context

CAPS Physical Sciences is one subject with six knowledge areas, examined in
two papers: Paper 1 Physics and Paper 2 Chemistry. THUTOra's Physical
Sciences topics (ADR-013/022) were all physics, so learners were covered for
only half of the subject. Grade 11 was also missing two physics topics:
geometrical optics and 2D/3D wavefronts.

## Decision

- **Keep one subject.** Schools timetable, allocate teachers and report on
  "Physical Sciences", not on Physics and Chemistry separately.
- **Topics get a `section`** (migration 0021): "Physics (Paper 1)" or
  "Chemistry (Paper 2)" for Physical Sciences, empty for other subjects.
  LEARN's topic list shows the two headings.
- **New topics** (`scripts/chemistry_content.py`). Each has prerequisites,
  including links back to earlier grades, so diagnosis works across grades.
  - Grade 10: Classification of Matter; States of Matter and the KMT; The
    Atom; The Periodic Table; Chemical Bonding; Physical and Chemical
    Change; Representing Chemical Change; Reactions in Aqueous Solution;
    Quantitative Aspects of Chemical Change; The Hydrosphere.
  - Grade 11: Atomic Combinations and Molecular Structure; Intermolecular
    Forces; Ideal Gases; Quantitative Aspects of Chemical Change; Energy
    and Chemical Change; Acids and Bases; Redox Reactions; The Lithosphere;
    plus the physics topics Geometrical Optics and 2D and 3D Wavefronts.
  - Grade 12: Organic Molecules; Rate and Extent of Reaction; Chemical
    Equilibrium; Acids and Bases; Electrochemical Reactions; The Chemical
    Industry.
- **Questions:** 4 practice questions per new topic (100 in total). Numeric
  answers are re-computed in `tests/test_question_bank_extra.py`.
- **Textbook:** every new topic maps to its chapter in Siyavula's
  Everything Science (CC BY), so the ADR-041 side panel and page-cited
  answers work. Grade 11 acid-base and redox share "Types of reactions".
- **Notation:** chemistry topics add a rule to the tutor's instructions.
  Formulas and reaction equations are written in plain text with
  subscripts (2H₂ + O₂ → 2H₂O), never in `$$…$$`, because MathGuard would
  check them as algebra. Calculations stay in `$$…$$`, so they're still
  verified.
- **Keyboard:** chemistry topics get subscripts, charges, → and ⇌, ΔH,
  mol/dm³ and °C.

## Consequences

- Existing installs: the migration marks current Physical Sciences topics
  as physics. Re-running the seed adds the chemistry topics and questions.
  Re-running `scripts/ingest_books.py` links the chapters (and embeds them
  if `OPENAI_API_KEY` is set).
- Prerequisite links stay within each paper; cross-paper links (e.g.
  quantitative chemistry needing Maths) can be added later.
- The chemistry content still needs a check by a Physical Sciences teacher,
  like the rest of the question bank.
