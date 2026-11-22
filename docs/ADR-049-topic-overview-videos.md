# ADR-049 — Topic induction videos

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
- The words are on screen, so videos work muted in class. Narration was added
  later (see "Narration" below).
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

## Reworked as topic inductions (22 Nov 2026)

Siya asked for each video to be an **induction** to a topic the learner is
about to start. It now has seven scenes and runs 77–94 s:

| Scene | Content |
|---|---|
| Welcome | Topic, grade, subject, exam paper. |
| What it's about | The big idea, the key formula, and one line on why it matters. |
| What to expect | The 4–6 things the topic covers (CAPS sub-topics). |
| Where it comes from | The previous grade's work it builds on, what it uses in this grade, and what it leads to. |
| Example 1 | A basic warm-up, revealed step by step. |
| Example 2 | An exam-style question, revealed step by step. |
| Ready? | Pointer to ask THUTOra. |

How the "where it comes from" scene is filled:
- **Previous grade.** It comes from `previous` in `content.py`. For Grade 10
  that's CAPS Senior Phase (Grade 9) work, which THUTOra doesn't hold as
  topics. For Grades 11–12 it will name the previous grade's THUTOra topic.
- **Leads to.** It puts the same topic one grade up first, e.g.
  "Trigonometry (Grade 11)", followed by this grade's topics that build on it.

Where/Who were dropped to keep the focus on the induction. Narration follows
the same seven scenes, with one sentence per "expect" item so it doesn't run
together.

## Narration (added 20 Nov 2026)

Siya asked for a voice. It uses **Azure neural voices**, with South African
English: `en-ZA-LeahNeural` (female) and `en-ZA-LukeNeural` (male). There
are isiZulu voices for later. The free F0 tier allows 0.5 million characters
a month, and all 135 videos come to about 145,000.

- **Spoken script.** `narration.py` builds one spoken line per scene. Lines
  with maths use the entry's `say` block, which writes the maths the way a
  teacher reads it ("x squared, minus five x, plus six"); a voice can't read
  LaTeX. A test checks there's a line for every scene and that no maths
  markup is left.
- **Making the audio.** `voice.py` calls Azure from a developer machine. The
  sandbox can't reach Azure, and the API never does.
  - The key goes in `backend/.env` (`AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`).
  - Each line is saved as an mp3, and unchanged lines aren't sent again.
  - "THUTOra" is said through an SSML alias (`BRAND_ALIAS`); adjust it if the
    sample sounds wrong.
- **Fitting the video to the voice.** `render.py --voice <name>` makes each
  scene last as long as its narration plus a short pause, and never less than
  the reading time. The audio is AAC 48 kbps mono, so a voiced video is about
  0.9 MB.
- **On-screen text stays.** It still works muted in class, and for learners
  who are hard of hearing.

## Voice on / off (22 Nov 2026)

A learner can switch the voice-over off.
- **The switch.** "Voice on / Voice off" in the video window
  (`aria-pressed`).
- **It's remembered** on the device, in localStorage, so a learner who prefers
  quiet doesn't mute every video. If storage is blocked, the switch still
  works for the video that's playing.
- **The player's own mute button** counts as the same choice.
- **Shown only where there's a voice.** `video_resources.has_narration`
  (migration 0024) is set by `register.py` from the manifest's `voice`, and
  `GET /topics/` returns it as `intro_video_narrated`.
- **Nothing is lost when muted:** every spoken line is also on screen.

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
