# ADR-001: Core Technology Stack

**Status:** Accepted
**Date:** 2026-07-31
**Author:** Siyabonga Zondi

## Context

Building a pilot AI tutor covering CAPS Grade 10 Pure Mathematics and Physical
Science. Needs to run cheaply (near-zero infrastructure cost during pilot),
reuse existing engineering skills, and support Retrieval-Augmented Generation
(RAG) so the tutor is grounded in actual CAPS content rather than an LLM's
general knowledge.

## Decision

| Layer | Choice | Alternatives considered |
|---|---|---|
| Backend framework | FastAPI (Python 3.12) | Django (heavier, more opinionated than needed for an API-only service) |
| Database | PostgreSQL 16 + `pgvector` extension | Separate vector DB (Pinecone/Weaviate) — rejected to avoid a second system to operate during a free-tier pilot |
| AI provider | Anthropic Claude API | OpenAI — Claude chosen for stronger step-by-step/Socratic tutoring behaviour and existing familiarity |
| Content/ETL pipeline | Apache Hop + dbt | Custom Python scripts only — Hop/dbt reused deliberately since this is already production tooling for the author |
| Frontend | React + Vite, PWA | Flutter — deferred; web PWA reaches more devices with less pilot effort, offline/native app is a v2 concern |
| Hosting | Oracle Cloud Free Tier + Coolify | Azure/AWS — rejected on pilot cost grounds, consistent with the Ithemba Transport project |

## Consequences

- **Positive:** single database to operate (Postgres does both relational
  state and vector search), stack overlaps heavily with existing skills
  (FastAPI/Postgres/Hop/dbt/React from Ithemba Transport), infrastructure
  cost during pilot is effectively zero.
- **Negative:** `pgvector` is less mature than dedicated vector databases at
  large scale — acceptable at pilot scale (low thousands of content chunks),
  will need revisiting if the platform scales to multiple grades/subjects
  and provinces.
- **Negative:** tying the pilot to a single LLM vendor (Anthropic) creates
  vendor dependency — acceptable for a pilot; a provider abstraction layer
  should be added before any production commitment.

## Status of related decisions

- Grade/subject scope: Grade 10, Pure Mathematics + Physical Science
  (see project README for rationale — lower stakes than Grade 12, high
  content overlap between the two subjects, full DBE material available).
