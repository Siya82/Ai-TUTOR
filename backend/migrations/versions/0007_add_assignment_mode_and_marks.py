"""add assignment mode/results_released and per-question marks -- ADR-029

See docs/ADR-029-assignment-mode-and-marks.md. Live-testing ADR-028
surfaced two real gaps: a Test-mode assignment was giving away the
correct answer and AI explanation the instant a student answered it
(no real assessment is possible that way), and every question counted
for exactly one mark with no way for a teacher to weight questions
differently.

assignments.mode ("practice" | "test", default "practice") lets a
teacher choose per assignment whether AI feedback shows immediately
(practice, the only behaviour that existed before this) or is withheld
until the teacher explicitly releases it (test).
assignments.results_released (default false) is that release switch,
flipped once by POST /teach/assignments/{id}/release -- see
app/services/assignments.py's release_assignment_results().
assignment_questions.marks (default 1) is the point value a teacher
assigns to each question when adding it to an assignment; a learner's
total score is the sum of marks for correctly-answered questions.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column("mode", sa.String(20), nullable=False, server_default="practice"),
    )
    op.add_column(
        "assignments",
        sa.Column(
            "results_released", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "assignment_questions",
        sa.Column("marks", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("assignment_questions", "marks")
    op.drop_column("assignments", "results_released")
    op.drop_column("assignments", "mode")
