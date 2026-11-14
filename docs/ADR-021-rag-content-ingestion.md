# ADR-021: Real RAG content ingestion and retrieval (isiZulu/English Home Language first)

**Status:** Accepted
**Date:** 14 November 2026

## Context

Siya live-tested isiZulu Home Language content (ADR-020) against a real past-paper
matching exercise ("1.6 Qondanisa uHlu A noHlu B" -- match idiomatic isiZulu
expressions to the emotion/attitude they express). The tutor got some matches
wrong, some right. This is the first real, concrete evidence of exactly the risk
ADR-020 flagged loudly but couldn't yet fix: isiZulu accuracy depends on fluency,
and nothing in the system actually grounds the tutor in real isiZulu source
material -- `content_chunks` has existed as an empty table with
`PLACEHOLDER_EMBEDDING = [0.0] * 1536` zero-vectors since the project's first
report, and `scripts/ingest_content.py` was a named-but-never-built placeholder
(REBUILD_SPEC.md Section 8).

Two complications surfaced while scoping the fix, both resolved via
`AskUserQuestion` with Siya directly rather than assumed:

1. **No past papers on hand.** Siya doesn't have source material to supply
   directly -- it has to be sourced publicly.
2. **Grade 10 isiZulu papers aren't centrally published.** South Africa's DBE
   publishes only **NSC (Grade 12 matric) past papers** centrally, on
   education.gov.za. Grade 10/11 papers are provincial/school-level and only
   surface via third-party aggregator sites (Mabumbe, Funza, SAexampapers,
   studypapers.co.za, NexiStudy) whose redistribution rights aren't established.
   Siya's explicit choice: **use official Grade 12 NSC papers for grounding now**,
   accepting that this grounds general isiZulu grammar/literary-device/idiom
   knowledge (which is real and does carry across grades -- the same observation
   that justified ADR-020's shared-CAPS-skeleton architecture in the first place),
   not grade-exact exam content. This is explicitly NOT claimed to directly fix
   the exact "Qondanisa" exercise shown -- the specific 2023 Nov Grade 12 papers
   checked do not contain that exact exercise type. It is a general accuracy
   backstop, not a targeted patch for that one screenshot.

This is also the first time this project stores an API key for a provider other
than Anthropic, and the first time a chunking/embedding/retrieval pipeline exists
at all.

## Decision

**Embeddings provider: OpenAI `text-embedding-3-small`, called via raw `httpx`
rather than the `openai` SDK.** `content_chunks.embedding` has been a
`pgvector(1536)` column since the schema was first built -- 1536 is exactly
`text-embedding-3-small`'s (and legacy `ada-002`'s) output dimension, which is
almost certainly why 1536 was chosen originally. This decision therefore reuses
the provider the schema already implied, rather than introducing an arbitrary
new one. `httpx` is already a dependency (`requirements.txt`); adding the full
`openai` SDK for a single endpoint wasn't worth a new dependency. New setting:
`OPENAI_API_KEY` in `backend/.env`, optional (defaults to `None` in
`app/core/config.py`) so the app keeps starting and serving every existing
tutor turn unchanged for anyone who hasn't set it.

**Ingestion: `backend/scripts/ingest_content.py`, reading real local files only.**
The script does NOT fabricate isiZulu (or any) source text -- it reads PDFs you
place under a new `backend/content_sources/` directory (git-ignored, like
`uploads/attachments`), extracts text with `pypdf` (already a dependency),
chunks on paragraph boundaries (~1000 chars, ~150 overlap, hard-splitting an
oversized single paragraph rather than dropping text), embeds each chunk via
OpenAI, and writes `ContentChunk` rows. A `MANIFEST` list maps each expected
local filename to the `(subject_name, grade, topic_name)` it grounds -- for now,
six files (2023 November isiZulu HL NSC Papers 1/2/3 + their three memos),
each mapped to one of the three Home Language topics it's actually relevant to
(Language Structures and Conventions / Literature / Writing and Presenting).
Idempotent by `(topic_id, source)`, same discipline as
`ensure_placeholder_content_chunk()`; a MANIFEST entry whose file hasn't been
downloaded yet is skipped with a clear message, not an error.

**I could not download the source PDFs myself.** Claude's web-fetching tools
return a processed answer to a prompt, not raw file bytes, and the standing
rule against reaching for `curl`/`requests` as an alternative when the sanctioned
tool doesn't do exactly what's needed applies here. Getting genuine, unparaphrased
isiZulu source text into the pipeline requires the real PDF bytes, which only
Siya downloading them (or attaching them to chat) can provide -- a WebFetch
summary of a PDF is still, in the end, Claude's own paraphrase, which would
quietly reintroduce the exact unverified-content risk this ADR exists to
reduce. The six official URLs (all under education.gov.za, same
`tabid=4682&portalid=0&mid=12651`) are listed as comments directly above
`MANIFEST` in `ingest_content.py` so they don't need to be re-found.

**Retrieval: plain-Python cosine-distance ranking, not a pgvector SQL `ORDER BY`.**
`app/services/retrieval.py`'s `get_grounding_text()` loads a topic's real
(non-placeholder) chunks and ranks them in Python. At today's content volume
(a handful of chunks per topic) this is simpler to read and unit-test than
wiring up pgvector's SQLAlchemy comparator methods, at the cost of not scaling
past a small number of chunks per topic -- an explicit, bounded tradeoff, not an
oversight (see Open items).

**Wiring: a deliberate, documented doubled diagnosis call, not a change to
`tutor_orchestration.py`'s DB-free contract.** `prepare_tutor_turn()` has always
been pure/DB-free by design (its own docstring). Knowing which topic will
actually be taught (needed to look up that topic's grounding) requires running
`diagnose_root_gap()` -- but `prepare_tutor_turn()` already runs that internally,
one step after accepting its inputs. Rather than threading a DB session through
the orchestration layer, `routers/tutor.py`'s `send_tutor_message()` now calls
`diagnose_root_gap()` itself first (cheap -- pure Python over an already-fetched,
short prerequisite chain), uses the result to fetch `grounding_text` via
`get_grounding_text()`, then calls `prepare_tutor_turn()` as before, which runs
diagnosis again internally. Two calls to a cheap pure function, in exchange for
keeping the orchestration layer's existing purity guarantee intact.

**Failure mode: grounding lookup failures never break a tutor turn.**
`get_grounding_text()` catches `EmbeddingsNotConfiguredError` and `httpx.HTTPError`
internally and returns `None` (meaning: fall back to the existing
"not yet wired" placeholder) rather than letting a missing key or an OpenAI
outage take down `/tutor/message` entirely. Availability was chosen over
grounding on purpose here.

**`build_tutor_system_prompt()` gets a new optional `grounding_text` parameter.**
When set (real content was found and embedded), it replaces
`_build_rag_grounding_placeholder()`'s notice; when `None` (every topic except
the ones actually ingested), behaviour is byte-for-byte identical to before --
`test_tutor_prompt.py`'s existing assertions about `"content_chunks"` appearing
in the prompt still pass unchanged for every call that doesn't pass
`grounding_text`.

## Consequences

- `app/core/config.py`: new optional `openai_api_key` field.
- `app/services/embeddings.py` (new): `embed_texts()`/`embed_text()`, raw
  `httpx` call to OpenAI, `EmbeddingsNotConfiguredError`.
- `app/services/retrieval.py` (new): `get_grounding_text()`, plus the pure
  `_cosine_distance()`/`_format_grounding_text()` helpers.
- `app/services/tutor.py`: `build_tutor_system_prompt()` gained
  `grounding_text: str | None = None`.
- `app/services/tutor_orchestration.py`: `prepare_tutor_turn()` gained
  `grounding_text: str | None = None`, forwarded through unchanged.
- `app/routers/tutor.py`: `send_tutor_message()` now runs `diagnose_root_gap()`
  once itself before calling `prepare_tutor_turn()`, to fetch grounding for the
  topic that will actually be taught.
- `backend/scripts/ingest_content.py` (new): the real ingestion pipeline,
  `MANIFEST`-driven, documented above.
- `backend/content_sources/` (new, git-ignored, not created by this commit --
  Siya creates it when he downloads the PDFs): where the six source PDFs go.
- New tests: `test_embeddings.py`, `test_retrieval.py`, `test_ingest_content.py`
  -- all pure-logic (chunking, cosine distance, formatting), no DB/network, same
  posture as every other DB-touching module's test coverage in this project.
- `requirements.txt`: **no change** -- `httpx` and `pypdf` were already
  dependencies.

## Open items (explicitly not done, not silently dropped)

- **The six source PDFs are not yet downloaded or ingested.** This ADR and the
  code are ready; `scripts/ingest_content.py` has not been run against real
  files yet. Siya needs to: download the six PDFs from the URLs listed in
  `ingest_content.py`'s own comments, save them under
  `backend/content_sources/` with the exact filenames the `MANIFEST` expects,
  add `OPENAI_API_KEY` to `backend/.env`, then run
  `python -m scripts.ingest_content` from `backend/`.
- **English Home Language has no equivalent ingestion yet.** The `MANIFEST`
  only covers isiZulu HL; English HL's accuracy risk is lower (not a second-
  language-fluency problem the way isiZulu is) but the architecture generalizes
  immediately -- add English HL entries to `MANIFEST` once a source is picked.
- **This does not resolve the specific "Qondanisa" exercise shown.** The 2023
  Nov Grade 12 papers checked don't contain that exact exercise type -- this is
  general grounding, not a targeted fix. If idiom-matching exercises specifically
  turn out to still be weak after ingestion, that's a real signal the Grade-12-
  source approach has a gap Grade-10-specific material would close, and sourcing
  that (through a trusted aggregator, or material Siya obtains directly) becomes
  its own future decision.
- **Licensing of official past papers for product use is an open question, not
  resolved here.** Personal/educational past-paper use is extremely common and
  broadly tolerated; embedding extracted content into a product's database and
  serving it back through a paid(-ish) tutoring product is a notch beyond that.
  Not blocking this build, but Siya should be aware of it as a real
  consideration, not an assumption that it's fine.
- **Retrieval ranks in plain Python, not via a pgvector SQL `ORDER BY`.** Fine
  at today's volume (a handful of chunks per topic); revisit once a topic's
  ingested-chunk count makes an in-Python sort the wrong tool.
- **Not live-tested against a real Claude call yet.** Same handoff as every
  previous content addition -- needs Siya's local DB/backend to actually run
  `ingest_content.py` and then a real `/tutor/message` call.
- **No automatic placeholder cleanup.** Placeholder `ContentChunk` rows for a
  topic are not deleted once real content is ingested -- they're simply excluded
  from retrieval by their `source` prefix (`PLACEHOLDER_SOURCE_PREFIX` in
  `retrieval.py`). Leaving them in place costs nothing and avoids a silent
  delete; revisit if they ever become confusing noise in the table.
