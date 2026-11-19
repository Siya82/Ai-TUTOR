"""ADR-049: the topic video text matches the curriculum it describes."""

import re

from scripts.seed_dev_data import SUBJECTS
from scripts.topic_videos.content import CONTENT
from scripts.topic_videos.render import topic_links, video_slug


def test_every_entry_is_a_real_seeded_topic():
    for (subject, grade), topics in CONTENT.items():
        spec = next(s for s in SUBJECTS if s["name"] == subject and s["grade"] == grade)
        seeded = {name for name, _ in spec["topics"]}
        assert set(topics) <= seeded, set(topics) - seeded


def test_entries_are_complete_and_maths_is_balanced():
    for topics in CONTENT.values():
        for name, c in topics.items():
            assert c["what"] and c["why"] and len(c["where"]) == 3 and c["who"], name
            assert c["paper"] in ("Paper 1", "Paper 2"), name
            assert c["how"]["q"] and c["how"]["steps"] and c["how"]["a"], name
            texts = [c["what"], c["why"], *c["where"], c["how"]["q"], *c["how"]["steps"], c["how"]["a"]]
            for t in texts:
                assert t.count("$") % 2 == 0, f"{name}: unbalanced $ in {t!r}"
            assert "isiZulu" not in name  # ADR-021: never invented isiZulu text


def test_links_and_slugs():
    assert topic_links("Pure Mathematics", 10, "Exponents") == (["Algebraic Expressions"], ["Number Patterns", "Finance, Growth and Decay"])
    assert video_slug("Pure Mathematics", 10, "Finance, Growth and Decay") == "g10-pure-mathematics-finance-growth-and-decay"
    assert re.fullmatch(r"[a-z0-9-]+", video_slug("Physical Sciences", 11, "2D & 3D Wavefronts"))
