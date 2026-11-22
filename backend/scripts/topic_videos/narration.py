"""
What the narrator says over each scene of a topic induction video (ADR-049),
in the same order as render.frames_for(): welcome, what it's about (and
why), what to expect, where it comes from, example 1 (question, each step,
answer), example 2 (the same), ready.

Lines without maths are spoken as written. Lines with maths ($...$) take
their spoken version from the entry's "say" block in content.py: a voice
can't read LaTeX, and a learner should hear maths the way a teacher says it.
"""

import re

SUBJECT_SAY = {"Pure Mathematics": "Mathematics"}


def _plain(text: str, override: str | None, where: str) -> str:
    if override:
        return override
    if "$" in text:
        raise ValueError(f"{where} has maths in it and needs a spoken version in 'say': {text!r}")
    return text


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _example(ex: dict, where: str) -> list[str]:
    say = ex.get("say", {})
    steps_say = say.get("steps", [])
    lines = [_plain(ex["q"], say.get("q"), f"{where} question")]
    for i, step in enumerate(ex["steps"]):
        lines.append(_plain(step, steps_say[i] if i < len(steps_say) else None, f"{where} step {i + 1}"))
    lines.append(_plain(ex["a"], say.get("a"), f"{where} answer"))
    return lines


def narration(subject: str, grade: int, topic: str, c: dict) -> list[str]:
    from scripts.topic_videos.render import topic_links  # avoid an import cycle

    subject_say = SUBJECT_SAY.get(subject, subject)
    lines = [
        f"Welcome to {topic}, in Grade {grade} {subject_say}. Here's what you're about to learn.",
        "What it's about. " + _plain(c["what"], None, f"{topic} 'what'")
        + " Why it matters? " + _plain(c["why"], None, f"{topic} 'why'"),
        # one short sentence per item: a long comma list runs together when spoken
        "What to expect. In this topic you'll learn: "
        + " ".join(_plain(x, None, f"{topic} 'expect'").rstrip(".") + "." for x in c["expect"]),
    ]
    builds_on, leads_to = topic_links(subject, grade, topic)
    where = f"Where it comes from. It builds on your Grade {grade - 1} work: " + _join(
        [re.sub(rf"^Grade {grade - 1} ", "", x) for x in c["previous"]]) + "."
    if builds_on:
        where += f" In Grade {grade}, it also uses {_join(builds_on)}."
    if leads_to:
        where += f" Next, it leads to {_join([re.sub(r' [(]Grade (\d+)[)]', r' in Grade \1', t) for t in leads_to])}."
    where += f" In your final exam, it's in {c['paper']}."
    lines.append(where)
    ex1, ex2 = c["examples"]
    first = _example(ex1, f"{topic} example 1")
    first[0] = "Let's warm up with a basic example. " + first[0]
    second = _example(ex2, f"{topic} example 2")
    second[0] = "Now an example like the ones in tests and exams. " + second[0]
    lines += first + second
    lines.append(f"You're ready to start {topic}. If you get stuck, ask THUTOra in LEARN. It explains step by step.")
    return lines
