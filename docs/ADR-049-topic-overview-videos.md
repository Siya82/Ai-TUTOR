# ADR-049 — One-minute topic overview videos

**Date:** 20 Nov 2026 · **Status:** Accepted (pilot: Grade 10 Mathematics)

## Context

A learner opening a topic for the first time sees an empty chat. Before they
can ask a good question, they need a quick sense of what the topic is and why
it matters. Siya asked for a short video for every topic, built around the
"5 Ws".

## Decision

Every topic gets a THUTOra-made video of about one minute. It has one scene
for each W, in this order:

| Scene | Content |
|---|---|
| **What** is it? | One or two sentences, with the key formula beside them. |
| **Why** does it matter? | One sentence. |
| **Where** do you see it? | Three everyday South African examples. |
| **Who** uses it? | Careers. |
| **When** do you need it? | What it builds on and what it leads to, taken from the seed's prerequisite chain so it always matches the tutor; plus its final-exam paper. |
| **How** does it work? | A short worked example, revealed one step at a time. |

**Format.**
- 720p, 30 fps.
- **No sound.** The words are on screen, so videos work muted in class, and no
  synthetic voice is needed (a natural-sounding voice wasn't available offline).
  A recorded voice can be added later.
- About **0.5 MB** each, to keep learners' data costs down: 135 topics come to
  about 70 MB in total.

**Text in the repo, videos not.**
- `backend/scripts/topic_videos/content.py` holds the text and is the thing to
  review and edit.
- `render.py` draws each scene as HTML (with KaTeX for maths) using Playwright,
  and joins the scenes with ffmpeg.
- The `.mp4` files go to `backend/media/topic-videos/`, which is gitignored:
  they're big binaries that can be rebuilt from the text.

**In LEARN.**
- `video_resources`, planned since ADR-005, is now used:
  - our videos have `source = "THUTOra"`;
  - `duration_seconds` is new (migration 0023).
- `GET /topics/` adds `intro_video_url` and `intro_video_seconds` to each topic.
- An empty chat shows a "New to <topic>?" card. Once a conversation exists, a
  small "What's this topic about? 1:08" link stays at the top of the transcript,
  so no fixed space is taken on phones (ADR-047).
- The video opens in a dialog (Esc closes it).

**Serving.**
- The API serves `/media/topic-videos/` with no login: it's curriculum, not
  personal data.
- Byte ranges let the player seek.
- `Cache-Control: public, max-age=86400`, and no gzip.
- In production the files go to a Cloud Storage bucket, registered with
  `--base-url` (`docs/RUNBOOK.md`).
- The frontend CSP allows `media-src` from the API and storage.googleapis.com.

**Accuracy.** The text needs a teacher's check before wide use: set
`reviewed_by` in `content.py`. `tests/test_topic_video_content.py` checks:
- every entry is a real seeded topic;
- every entry is complete;
- the maths markup is balanced;
- there is no isiZulu content.

**isiZulu HL** topics get no video until a fluent speaker writes or checks the
text (ADR-021).

## Rollout

1. Pilot: Grade 10 Mathematics, 12 videos (done, 62–70 s each). Siya reviews the
   style and accuracy.
2. Then in batches:
   - Grade 11 and 12 Mathematics;
   - Physical Sciences, Physics (Paper 1) and Chemistry (Paper 2);
   - Accounting;
   - English HL.
3. isiZulu HL once a speaker is involved.

## Commands (from `backend/`)

```powershell
python -m scripts.topic_videos.render --stills --only "Exponents"   # check the layout
python -m scripts.topic_videos.render                               # make the videos (needs Playwright and ffmpeg)
python -m scripts.topic_videos.register                             # link them to topics
```
