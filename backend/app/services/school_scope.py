"""
Who a school staff member may see and act on (ADR-031).

NEW 17 Nov 2026. Every TEACH endpoint used to scope by school_id alone,
so any staff account saw every learner in its school. Access now comes
from two sources:

- Teaching allocations (teacher + subject + class): the learners in that
  class, for that subject only.
- Staff roles: principal / deputy_principal (whole school, all subjects),
  departmental_head (a subject name, optionally one grade: learners in the
  matching grade(s), for the matching subjects), school_admin (whole-school
  roster for data entry, but NO academic data).

A person's access is the union of everything they hold.

Split like class_progress.py / admin.py: `build_scope()` is pure (unit
tested with plain rows), `load_scope()` does the queries.

Vocabulary used throughout:
- "roster" visibility = may see that the learner exists (name, grade,
  student number). Needed to manage classes and accounts.
- "academic" visibility = may see that learner's attempts/marks/risk and
  assign them work -- always for a SET of subject ids, or ALL subjects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ClassMember,
    Learner,
    SchoolClass,
    StaffRole,
    Subject,
    TeachingAllocation,
    User,
)

PRINCIPAL = "principal"
DEPUTY_PRINCIPAL = "deputy_principal"
DEPARTMENTAL_HEAD = "departmental_head"
SCHOOL_ADMIN = "school_admin"
SCHOOL_ROLES = (PRINCIPAL, DEPUTY_PRINCIPAL, DEPARTMENTAL_HEAD, SCHOOL_ADMIN)

ROLE_LABELS = {
    PRINCIPAL: "Principal",
    DEPUTY_PRINCIPAL: "Deputy principal",
    DEPARTMENTAL_HEAD: "Departmental head",
    SCHOOL_ADMIN: "School admin",
}

# Who may grant which role (ADR-031: only within your own scope and below).
# Principal itself is granted only by Zynora onboarding (scripts/provision_school.py).
GRANTABLE_BY = {
    PRINCIPAL: (DEPUTY_PRINCIPAL, DEPARTMENTAL_HEAD, SCHOOL_ADMIN),
    DEPUTY_PRINCIPAL: (DEPARTMENTAL_HEAD, SCHOOL_ADMIN),
}

WHOLE_SCHOOL_ACADEMIC_ROLES = {PRINCIPAL, DEPUTY_PRINCIPAL}
MANAGE_SCHOOL_ROLES = {PRINCIPAL, DEPUTY_PRINCIPAL, SCHOOL_ADMIN}


class _All:
    """Sentinel: every subject. Distinct from an empty set (no subjects)."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ALL_SUBJECTS"


ALL_SUBJECTS = _All()


# --- plain row types fed to build_scope() ----------------------------------


@dataclass(frozen=True)
class RoleRow:
    id: UUID
    role: str
    subject_name: Optional[str] = None
    grade: Optional[int] = None


@dataclass(frozen=True)
class AllocationRow:
    id: UUID
    subject_id: UUID
    subject_name: str
    grade: int
    class_id: UUID
    class_name: str


@dataclass(frozen=True)
class SubjectRow:
    id: UUID
    name: str
    grade: int


@dataclass
class StaffScope:
    user_id: UUID
    school_id: UUID
    roles: list[RoleRow]
    allocations: list[AllocationRow]
    roster_learner_ids: set[UUID]
    # learner_id -> ALL_SUBJECTS or a set of subject ids
    academic: dict[UUID, object] = field(default_factory=dict)

    # -- role queries --
    @property
    def role_names(self) -> set[str]:
        return {r.role for r in self.roles}

    @property
    def can_manage_school(self) -> bool:
        return bool(self.role_names & MANAGE_SCHOOL_ROLES)

    @property
    def whole_school_academic(self) -> bool:
        return bool(self.role_names & WHOLE_SCHOOL_ACADEMIC_ROLES)

    @property
    def grantable_roles(self) -> list[str]:
        out: list[str] = []
        for r in self.role_names:
            for g in GRANTABLE_BY.get(r, ()):
                if g not in out:
                    out.append(g)
        return [r for r in SCHOOL_ROLES if r in out]

    # -- learner queries --
    def can_see_roster(self, learner_id: UUID) -> bool:
        return learner_id in self.roster_learner_ids

    def academic_learner_ids(self) -> set[UUID]:
        return {lid for lid, subj in self.academic.items() if subj is ALL_SUBJECTS or subj}

    def subjects_for(self, learner_id: UUID):
        """ALL_SUBJECTS, a set of subject ids, or an empty set (no access)."""
        return self.academic.get(learner_id, set())

    def can_see_subject(self, learner_id: UUID, subject_id: UUID) -> bool:
        subj = self.subjects_for(learner_id)
        return subj is ALL_SUBJECTS or subject_id in subj

    def visible_subject_ids(self, all_subject_ids: Iterable[UUID]) -> set[UUID]:
        """Every subject this person may see for at least one learner -- used
        to filter subject/topic pickers in the UI."""
        if self.whole_school_academic:
            return set(all_subject_ids)
        out: set[UUID] = set()
        for subj in self.academic.values():
            if subj is not ALL_SUBJECTS:
                out |= subj
        return out


def build_scope(
    *,
    user_id: UUID,
    school_id: UUID,
    roles: list[RoleRow],
    allocations: list[AllocationRow],
    school_learners: dict[UUID, int],  # learner_id -> grade, every student in the school
    class_members: dict[UUID, set[UUID]],  # class_id -> learner ids
    subjects: list[SubjectRow],
) -> StaffScope:
    """Pure. Combines every grant into roster + academic visibility."""
    role_names = {r.role for r in roles}
    roster: set[UUID] = set()
    academic: dict[UUID, object] = {}

    def grant(learner_id: UUID, subject_ids) -> None:
        current = academic.get(learner_id)
        if current is ALL_SUBJECTS:
            return
        if subject_ids is ALL_SUBJECTS:
            academic[learner_id] = ALL_SUBJECTS
            return
        academic[learner_id] = (current or set()) | set(subject_ids)

    if role_names & (WHOLE_SCHOOL_ACADEMIC_ROLES | {SCHOOL_ADMIN}):
        roster |= set(school_learners)
    if role_names & WHOLE_SCHOOL_ACADEMIC_ROLES:
        for lid in school_learners:
            grant(lid, ALL_SUBJECTS)

    # Departmental head: subjects with this name (and grade, if limited),
    # for every learner in the school whose grade matches that subject row.
    for r in roles:
        if r.role != DEPARTMENTAL_HEAD or not r.subject_name:
            continue
        matching = [
            s for s in subjects
            if s.name == r.subject_name and (r.grade is None or s.grade == r.grade)
        ]
        for s in matching:
            for lid, grade in school_learners.items():
                if grade == s.grade:
                    roster.add(lid)
                    grant(lid, {s.id})

    # Teaching allocations: that class's learners, that subject.
    for a in allocations:
        for lid in class_members.get(a.class_id, set()):
            if lid in school_learners:  # never leak across schools
                roster.add(lid)
                grant(lid, {a.subject_id})

    return StaffScope(
        user_id=user_id,
        school_id=school_id,
        roles=roles,
        allocations=allocations,
        roster_learner_ids=roster,
        academic={k: v for k, v in academic.items() if v is ALL_SUBJECTS or v},
    )


async def load_scope(db: AsyncSession, user: User) -> StaffScope:
    """Five small queries; fine at school size (hundreds to low thousands of learners)."""
    roles = [
        RoleRow(id=r.id, role=r.role, subject_name=r.subject_name, grade=r.grade)
        for r in (
            await db.execute(
                select(StaffRole).where(
                    StaffRole.user_id == user.id, StaffRole.school_id == user.school_id
                )
            )
        ).scalars()
    ]
    alloc_rows = (
        await db.execute(
            select(TeachingAllocation, Subject, SchoolClass)
            .join(Subject, TeachingAllocation.subject_id == Subject.id)
            .join(SchoolClass, TeachingAllocation.class_id == SchoolClass.id)
            .where(
                TeachingAllocation.teacher_user_id == user.id,
                TeachingAllocation.school_id == user.school_id,
            )
            .order_by(SchoolClass.grade, SchoolClass.name, Subject.name)
        )
    ).all()
    allocations = [
        AllocationRow(
            id=a.id,
            subject_id=s.id,
            subject_name=s.name,
            grade=s.grade,
            class_id=c.id,
            class_name=c.name,
        )
        for a, s, c in alloc_rows
    ]
    school_learners = {
        lid: grade
        for lid, grade in (
            await db.execute(
                select(Learner.id, Learner.grade)
                .join(User, Learner.user_id == User.id)
                .where(User.school_id == user.school_id, User.role == "student")
            )
        ).all()
    }
    class_ids = {a.class_id for a in allocations}
    class_members: dict[UUID, set[UUID]] = {}
    if class_ids:
        for cid, lid in (
            await db.execute(
                select(ClassMember.class_id, ClassMember.learner_id).where(
                    ClassMember.class_id.in_(class_ids)
                )
            )
        ).all():
            class_members.setdefault(cid, set()).add(lid)
    subjects = [
        SubjectRow(id=s.id, name=s.name, grade=s.grade)
        for s in (await db.execute(select(Subject))).scalars()
    ]
    return build_scope(
        user_id=user.id,
        school_id=user.school_id,
        roles=roles,
        allocations=allocations,
        school_learners=school_learners,
        class_members=class_members,
        subjects=subjects,
    )
