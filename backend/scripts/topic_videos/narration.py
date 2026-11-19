"""
What the narrator says over each scene of a topic video (ADR-049), in the
same order as render.frames_for(): title, what, why, where, who, when, the
worked example (question, each step, answer), close.

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


def _careers(word: str) -> str:
    """'Accountants' -> 'accountants' mid-sentence; leave acronyms ('GIS analysts')."""
    return word if word[:2].isupper() else word[0].lower() + word[1:]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def narration(subject: str, grade: int, topic: str, c: dict) -> list[str]:
    from scripts.topic_videos.render import topic_links  # avoid an import cycle

    say = c.get("say", {})
    where_say = say.get("where", {})
    lines = [
        f"{topic}. Grade {grade} {SUBJECT_SAY.get(subject, subject)}. Here's what it's about, in about a minute.",
        "What is it? " + _plain(c["what"], say.get("what"), f"{topic} 'what'"),
        "Why does it matter? " + _plain(c["why"], say.get("why"), f"{topic} 'why'"),
        "Where do you see it? "
        + " ".join(_plain(w, where_say.get(i), f"{topic} 'where' {i}").rstrip(".") + "." for i, w in enumerate(c["where"])),
        "Who uses it? " + _join([_careers(w) for w in c["who"]]) + ".",
    ]
    builds_on, leads_to = topic_links(subject, grade, topic)
    when = "When do you need it? "
    when += f"It builds on {_join(builds_on)}" if builds_on else "It's a good place to start"
    if leads_to:
        when += f", and leads to {_join([re.sub(r' \(Grade (\d+)\)', r' in Grade \1', t) for t in leads_to])}"
    when += f". In your final exam, it's in {c['paper']}."
    lines.append(when)
    how = c["how"]
    lines.append("Here's an example. " + _plain(how["q"], say.get("q"), f"{topic} question"))
    steps_say = say.get("steps", [])
    for i, step in enumerate(how["steps"]):
        lines.append(_plain(step, steps_say[i] if i < len(steps_say) else None, f"{topic} step {i + 1}"))
    lines.append(_plain(how["a"], say.get("a"), f"{topic} answer"))
    lines.append(f"Now it's your turn. Open {topic} in LEARN, and ask THUTOra your first question.")
    return lines
