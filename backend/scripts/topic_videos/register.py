"""
Links the rendered topic videos (ADR-049) to their topics, so LEARN shows
them. Safe to run again: it updates rows rather than adding duplicates.
Run from backend/ after the seed and after rendering (or after copying
the .mp4 files and manifest.json into media/topic-videos/):

    python -m scripts.topic_videos.register

In production the files live in a Cloud Storage bucket (docs/RUNBOOK.md);
store their public address instead of the API path:

    python -m scripts.topic_videos.register --base-url https://storage.googleapis.com/<bucket>/topic-videos

Curriculum content, so it runs in every environment, like the seed.
"""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models import Subject, Topic, VideoResource
from app.routers.topics import THUTORA_VIDEO_SOURCE


async def register(base_url: str = "") -> None:
    folder = Path(settings.topic_video_dir)
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        print(f"No {manifest_path} -- render the videos first (python -m scripts.topic_videos.render).")
        return
    manifest = json.loads(manifest_path.read_text())
    added = updated = missing = 0
    async with async_session_factory() as db:
        for filename, m in manifest.items():
            if not base_url and not (folder / filename).exists():
                print(f"  skipped {filename}: file not found")
                missing += 1
                continue
            topic = (
                await db.execute(
                    select(Topic)
                    .join(Subject, Topic.subject_id == Subject.id)
                    .where(Subject.name == m["subject"], Subject.grade == m["grade"], Topic.name == m["topic"])
                )
            ).scalar_one_or_none()
            if topic is None:
                print(f"  skipped {filename}: no topic {m['topic']!r} in {m['subject']} Grade {m['grade']} (run the seed?)")
                missing += 1
                continue
            row = (
                await db.execute(
                    select(VideoResource).where(
                        VideoResource.topic_id == topic.id, VideoResource.source == THUTORA_VIDEO_SOURCE
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                row = VideoResource(topic_id=topic.id, source=THUTORA_VIDEO_SOURCE)
                db.add(row)
                added += 1
            else:
                updated += 1
            row.title = f"{m['topic']}: topic induction"
            row.url = f"{base_url.rstrip('/')}/{filename}" if base_url else f"/media/topic-videos/{filename}"
            row.duration_seconds = m["seconds"]
            row.duration_minutes = max(1, round(m["seconds"] / 60))
        await db.commit()
    print(f"Topic videos: {added} added, {updated} updated, {missing} skipped.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="", help="where the files are hosted, if not on the API")
    asyncio.run(register(ap.parse_args().base_url))
