# ADR-032: E-book library, reader and "Ask THUTOra about this"

**Status:** Accepted
**Date:** 17 November 2026

## Context

Siya asked how learners could study from e-books and ask THUTOra whenever
they don't understand something. Two questions had to be settled first:
which books THUTOra may legally use, and how a question about a page reaches
the tutor.

**Licensing (THUTOra is a commercial product):**

- **Siyavula** Mathematics and Physical Sciences, Grades 10–12 (also Life
  Sciences Grade 10): branded editions are CC-BY-ND; **unbranded editions are
  CC-BY 3.0**, which allows commercial use with attribution. The unbranded
  CC-BY editions are what this feature is built for.
- **DBE "Mind the Gap"** study guides state they may not be sold or used for
  commercial purposes. Excluded unless the DBE gives written permission or a
  province contracts THUTOra.
- **Commercial publishers' e-books** (Via Afrika, Oxford, Pearson, ...) need a
  licensing agreement. Possible later per school, under that school's own
  licence.

This is not legal advice. Before launch, confirm the licence printed in each
downloaded file and ideally get written confirmation from Siyavula.

## Decision

### Data (migration 0009)

- `books`: title, subject (and so grade), publisher, licence, attribution text,
  source URL, file name, page count.
- `book_pages`: the extracted text of every page. Used for the text-only
  (low-data) view, for selecting text to ask about, and as the passage the
  tutor receives.
- `book_topic_ranges`: optional page ranges per CAPS topic. They let the
  reader pick the right tutor topic for a page, and they decide which pages
  are embedded for retrieval.

Book PDFs live in `backend/content_sources/books/` and are **not committed**
(large, and licensed content). They're gitignored.

### Ingestion (`scripts/ingest_books.py`)

A `BOOKS` manifest lists each expected file with its title, subject, grade,
licence, attribution, source URL and optional topic page ranges. The script:

1. extracts every page's text with `pypdf` (already a dependency) and upserts
   `books`/`book_pages`;
2. stores the topic page ranges;
3. if `OPENAI_API_KEY` is set, chunks and embeds the pages inside mapped
   ranges into `content_chunks` with sources like
   `"Everything Maths Grade 10 (Siyavula), p. 87"`. Without the key it skips
   this step and says so; the reader and "Ask" still work.

`--outline <file>` prints each page's first line so the topic page ranges can
be filled in quickly. `--manifest <json>` swaps in a different manifest (used
for testing).

Retrieval (ADR-021) now labels every chunk with its source, so the tutor can
say "see p. 87" even when asked from the ordinary chat.

### API (`/books`)

- `GET /books`: books at or below the learner's grade (ADR-026 rule).
  Teachers see all.
- `GET /books/{id}`: details and topic ranges.
- `GET /books/{id}/pages/{n}`: page text, plus the mapped topic if any.
- `GET /books/{id}/pages/{n}/pdf`: **that one page** as a small PDF (cut out
  with `pypdf`), so a learner downloads a page, not a 7–15 MB book.

Grade access is enforced on every endpoint, not only in the list.

### Asking about a page

`POST /tutor/message` takes an optional `book_context`
(`book_id`, `page_number`, optional `selected_text`). The server loads the
page text **itself** (never trusting client-sent page text), checks the
learner may see that book, and puts the passage in front of the learner's
message for that turn: book title, page number, the page text, and what they
highlighted. Only a short summary ("Reading <title>, p. N: highlighted '…'")
is stored in the chat history, the same way attachments are handled
(ADR-016). MathGuard and diagnosis run exactly as for any other message.

### Learner UI

A **Library** view next to Chat and Assignments:

- book list grouped by grade and subject;
- a reader with page navigation, the page rendered from its one-page PDF
  (`pdfjs-dist`), and a **Text** toggle for a low-data, selectable view;
- **Ask THUTOra about this page**, or select text in the Text view and ask
  about the selection. Either way the learner lands in the chat with a book
  chip attached to their question, and a "Back to p. N" link returns them to
  the same page;
- the licence attribution is shown under every page (a CC-BY requirement).

## Consequences

- Nothing appears in the Library until the PDFs are downloaded and
  `ingest_books.py` is run. The session that built this couldn't download
  them (shell network access is restricted).
- Topic page ranges need filling in by hand once per book (`--outline`
  helps). Until then: pages still read and "Ask" still works (the reader uses
  the learner's selected topic, or the first topic of the book's subject),
  but page-cited retrieval only covers mapped ranges.
- Scanned pages with no text layer can't be selected or sent as text. The
  learner can still photograph them and use attachments (ADR-016).

## Not done

- Teacher features: assigning a chapter as reading, and "most-asked pages"
  analytics.
- Search inside a book; bookmarks; reading progress.
- Offline caching for poor connectivity.

## Addendum (17 Nov 2026): ePub, and a licence gate on import

**What changed the plan.** The first PDFs downloaded from Siyavula were all
the **branded CC BY-ND** editions (CC BY-ND 4.0 for Maths Gr 10, CC BY-ND 3.0
for the others), not CC BY. Siyavula offers the **CC BY (unbranded)** editions
as **ePub**. Siya chose (via `AskUserQuestion`, "Recommended") to switch to
the CC BY ePubs rather than use the ND PDFs while asking Siyavula for
permission. The science PDFs' text layers were also poor (words run together),
which the ePubs avoid.

**ePub support** (`app/services/epub.py`, standard library only, because new
pip installs are blocked on the dev laptop):

- Reads `META-INF/container.xml` → OPF → spine; non-linear items (e.g. the
  nav document) are skipped.
- An ePub has no printed pages, so each book is split into **sections** at
  h1–h3. Each section is stored as a `BookPage`: `page_number` is the section
  number, plus new `title` and `html` columns (migration 0010, which also adds
  `books.format`). When a split falls inside open elements, they're closed and
  re-opened so every section is well-formed. Heading-only stubs are carried
  forward and short notes are folded back.
- **HTML is rebuilt from an allow-list** at import time: no scripts, styles,
  links, iframes, forms or event-handler attributes. Remote or missing images
  are replaced by their alt text, so there are no tracking pixels. Local
  images become `<img data-asset="…">` and are fetched through the new
  authenticated `GET /books/{id}/assets?path=…`, which serves only image types
  and only members of that book's own zip. MathML is kept, since browsers
  render it natively.
- The section text sent to the tutor uses MathML's TeX annotation where
  present (`$a^m \times a^n = a^{m+n}$`), and figure alt text.
- Questions about an ePub cite the section ("the section 'Laws of
  exponents'") instead of a page number. Retrieval chunks are labelled the
  same way.

**Licence gate.** `ingest_books.py` now reads each book's own licence
statement (PDF front pages, or the ePub's `dc:rights` plus front matter) and
**only imports CC BY / CC BY-SA**. ND/NC books are refused with an
explanation; `--allow-restricted` exists for local testing only. The stored
licence and the attribution shown under every section come from what the book
says, not from the manifest. If no licence statement is found, the manifest's
expected licence is used with a warning. The manifest now lists `.epub` files.

**Reader.** For ePubs the reader shows the section's HTML (selectable, so
there's no separate Text mode) with a section picker as the table of contents.
"Ask THUTOra about this section" and "Ask about what I highlighted" work as
before. PDFs keep working exactly as before for any CC BY PDF.
