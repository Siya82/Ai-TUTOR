# ADR-009: Remove Apache Hop — dbt for Transformation Only, Plain Python for Ingestion

**Status:** Accepted
**Date:** 2026-08-02
**Amends:** ADR-001 (which specified "Apache Hop + dbt" for the content pipeline)

## Context

ADR-001 chose Apache Hop + dbt for the content/ETL pipeline, reasoning
that it reused existing production tooling. Product owner requested
removing Apache Hop and using dbt only.

## Decision

Remove Apache Hop. **Important scope clarification, not just a
substitution:** Hop and dbt were not doing the same job, so removing Hop
changes what handles the content ingestion pipeline, not just which tool
does it.

| Task | Old plan | New plan |
|---|---|---|
| Extract text from CAPS PDFs (syllabus, past papers) | Apache Hop | Plain Python script (`scripts/ingest_content.py` — not yet built) |
| Call embedding API, chunk text | Apache Hop | Same Python script |
| Load chunks + embeddings into `content_chunks` (pgvector) | Apache Hop | Same Python script |
| SQL-based transformations on data already in Postgres (e.g. mastery rollups for the teacher dashboard, aggregate views) | dbt | dbt — unchanged, this was always dbt's actual job |

dbt operates on data already loaded into a warehouse via SQL `SELECT`
models — it has no native PDF-extraction or embedding-API capability.
Treating dbt as a drop-in replacement for Hop's extraction role would
have been incorrect; what actually changes is that ingestion becomes a
small, direct Python script instead of a visual ETL tool pipeline.

## Consequences

- **Simpler pilot infrastructure**: one fewer service to run/maintain on
  Oracle Cloud Free Tier — a real practical win for a solo-maintained
  pilot, independent of the tooling debate.
- **Ingestion pipeline is now just Python**: easier to version-control,
  test, and reason about for a small, well-defined one-time/periodic job
  (ingest a fixed set of CAPS PDFs), versus standing up Hop's runtime for
  what is, at pilot scale, a fairly small extraction task.
- **dbt's role is now accurately scoped**: transformation only, on data
  already in Postgres. This was always dbt's actual capability — ADR-001
  slightly overstated its role by bundling it with Hop under one "content
  pipeline" line.
- No dbt models exist yet (content ingestion hasn't started — CAPS PDF
  sourcing remains an open task), so this is a documentation/scope
  correction, not a migration of existing work.
