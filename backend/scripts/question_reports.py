"""
deep scan M8: review teachers' reports about bank questions.

    python -m scripts.question_reports list
    python -m scripts.question_reports hide <report-ref>      # take the question out of the bank
    python -m scripts.question_reports dismiss <report-ref>   # the question is fine
    python -m scripts.question_reports fixed <report-ref>     # you corrected it in the seed data

<report-ref> is the start of the report id that `list` shows.
"""

import argparse
import asyncio

from sqlalchemy import String, cast, select

from app.core.clock import utcnow_naive
from app.core.database import async_session_factory
from app.models import Question, QuestionReport, School, Topic


async def main(args) -> None:
    async with async_session_factory() as db:
        if args.cmd == "list":
            rows = (
                await db.execute(
                    select(QuestionReport, Question, Topic.name, School.name)
                    .join(Question, Question.id == QuestionReport.question_id)
                    .join(Topic, Topic.id == Question.topic_id)
                    .join(School, School.id == QuestionReport.school_id, isouter=True)
                    .order_by(QuestionReport.created_at.desc())
                )
            ).all()
            for r, q, topic, school in rows:
                print(f"{str(r.id)[:8]}  [{r.status}{', hidden' if q.is_hidden else ''}]  {topic} -- {school or '-'}")
                print(f"    Q: {q.text}\n    A: {q.model_answer}\n    Report: {r.reason}\n")
            print(f"{len(rows)} report(s)")
            return
        matches = (
            await db.execute(select(QuestionReport).where(cast(QuestionReport.id, String).ilike(f"{args.ref.lower()}%")))
        ).scalars().all()
        if len(matches) != 1:
            raise SystemExit(f"{len(matches)} reports match {args.ref!r}")
        report = matches[0]
        if args.cmd == "hide":
            (await db.get(Question, report.question_id)).is_hidden = True
        report.status = {"hide": "hidden", "dismiss": "dismissed", "fixed": "fixed"}[args.cmd]
        report.resolved_at = utcnow_naive()
        await db.commit()
        print(f"Report {args.ref}: {report.status}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for c in ("hide", "dismiss", "fixed"):
        sub.add_parser(c).add_argument("ref")
    asyncio.run(main(p.parse_args()))
