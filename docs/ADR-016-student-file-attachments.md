# ADR-016: Students can attach a photo, PDF, or Word document to a tutor message

**Status:** Accepted
**Date:** 2026-11-13

## Context

Siya asked for students to be able to paste/attach files (images, PDF,
Word) into THUTOra's own chat (this was originally raised, then
clarified, after a side conversation about Claude's own chat UI that
turned out to be about a different thing entirely). The real-world
case this serves directly: a student photographs a worksheet or a
printed past-paper question and wants THUTOra to work through it,
rather than re-typing the problem by hand -- especially valuable for
anything with a diagram (circuits, geometry) that's awkward to type at
all. Explicit decisions from the user: support all common formats
(image, PDF, Word, "even paste"), build this now rather than after the
planned Grade 12 content expansion, and persist attachments linked to
the learner/session rather than treating them as throwaway.

## Decision

### Three supported kinds, handled differently on purpose

- **Images** (PNG/JPEG/WEBP/GIF): sent to Claude directly as a vision
  content block. No server-side extraction at all -- a photographed
  worksheet's handwriting, diagrams, and layout carry real information
  that OCR-to-text would throw away; Claude's own multimodal input
  reads the image directly, which is strictly better here and needs no
  extra dependency.
- **PDF**: text extracted server-side via `pypdf` (new dependency).
  Kept to text extraction rather than also betting on the Anthropic
  SDK's own PDF/document content-block support, since the pinned SDK
  version (`anthropic==0.39.0`) predates reliable availability of that
  feature and this project's own "near-zero pilot cost" stack
  philosophy (ADR-001) favors the simpler, already-proven
  path. **Known, documented limitation, same discipline as MathGuard's
  own honest gaps:** a scanned/image-only PDF with no text layer (a
  real, common case for photographed past papers saved as one PDF)
  yields no usable text. This is surfaced to the student as an
  explicit, honest message asking them to attach a photo of each page
  instead -- never silently sent as empty content.
- **Word (.docx)**: text extracted server-side via `python-docx` (new
  dependency). Least likely format for a student's own upload, more
  likely for content the Siya side seeds later; included because the
  user asked for "all of them."

### "Even paste" -- what this can and can't mean

Browsers only let a webpage read an actual file object off a paste
event for an **image** (a screenshot or a copied picture) -- a PDF or
.docx file cannot be pasted from the OS clipboard into a web page;
that always requires a file picker or drag-and-drop, there is no
browser API that exposes an arbitrary file through `paste`. So "paste"
is wired specifically for images (matching the single most valuable
real case -- a phone screenshot of a worksheet), and PDF/Word
attachment goes through a file-picker button plus drag-and-drop onto
the composer. This is a real browser limitation, not an
implementation shortcut, and is called out here so it isn't mistaken
for a gap later.

### Persistence

A new `attachments` table (`id`, `learner_id`, `session_id` nullable,
`message_id` nullable, `original_filename`, `content_type`, `kind`,
`storage_path`, `extracted_text` nullable, `extraction_warning`
nullable, `created_at`). An attachment is uploaded via its own
endpoint (`POST /attachments`, multipart) *before* the student's
message is sent -- the composer shows a preview/confirmation first --
so `session_id`/`message_id` start null and get backfilled onto the
row once `POST /tutor/message` actually creates the resulting
`TutorMessage`. Files are stored on local disk under
`backend/uploads/attachments/<uuid>/<original filename>` (one
uuid-named subfolder per upload, so two students' same-named
`worksheet.pdf` never collide and the filename itself can never be
used to traverse outside the upload root) -- consistent with this
project's existing near-zero-infra stack; this directory is
git-ignored, same treatment as any other runtime data.

### Wiring into the tutor turn

`TutorMessageRequest` gains an optional `attachment_ids: list[UUID]`.
`send_tutor_message` loads the referenced `Attachment` rows (filtered
by the request's own `learner_id`, since there's still no auth --
REBUILD_SPEC.md step 8 -- this is a basic sanity check, not a security
boundary) and builds the Claude-bound content for *that turn only* as
a list of content blocks (image blocks and/or extraction-text blocks)
followed by the student's own text -- built by a new, deliberately
pure, DB-free function, `build_attachment_content_blocks()` in the new
`app/services/attachments.py`, so it can be unit tested the same way
every other service module here already is (no DB, no network).

The *persisted* `TutorMessage.content` stores a plain-text summary
instead (e.g. `[Attached: worksheet.pdf]` plus the student's own
question) rather than the rich block list -- conversation history
replay to Claude on later turns only needs enough text to stay
coherent, not the original image bytes resent every turn, which would
otherwise re-spend tokens/cost on every image on every subsequent
message in the same session.

## Consequences

- New dependencies: `pypdf`, `python-docx` -- both lightweight, pure-
  Python-plus-C-extension packages, no new infrastructure.
- MathGuard is unaffected: it still only ever reads `$$...$$` blocks
  out of Claude's own reply text, regardless of what kind of content
  (text, image) produced that reply.
- No auth exists yet (step 8, still deferred), so attachment access is
  only loosely scoped by `learner_id` in the request body, not a real
  permission check -- acceptable for the current unauthenticated pilot
  stage, same posture as every other endpoint in this app, but a real
  gap to close whenever step 8 happens.
- Scanned/image-only PDFs are a known, explicit "ask for a photo
  instead" limitation, not silently broken -- consistent with this
  project's standing discipline of surfacing a limitation honestly
  (MathGuard's Euclidean Geometry proof gap is the precedent) rather
  than pretending something works when it doesn't.
- Not done in this pass: virus/malware scanning of uploads, a cleanup/
  retention job for the `uploads/` directory, and multi-file-per-
  message UI polish beyond "attach one file, see a preview, send."
