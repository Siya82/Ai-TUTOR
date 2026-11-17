"""
School structure API (ADR-031): who I am and what I can see, classes and
their members, staff accounts, staff roles, and teaching allocations.

NEW 17 Nov 2026. Everything here is school-scoped (the caller's own school
only) and every write is checked on the server:

- Managing the school (classes, members, staff accounts, allocations):
  principal, deputy principal or school admin.
- Granting/revoking roles: only roles below your own (school_scope.GRANTABLE_BY).
  Principal is never grantable here -- Zynora onboarding creates it
  (scripts/provision_school.py).
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_staff_scope, get_current_teacher
from app.models import (
    ClassMember,
    Learner,
    School,
    SchoolClass,
    StaffRole,
    Subject,
    TeachingAllocation,
    User,
)
from app.schemas.school import (
    ActiveUpdate,
    ClassUpdate,
    PasswordResetResult,
    PromoteRequest,
    PromoteResult,
    AllocationBulkCreate,
    AllocationBulkResult,
    AllocationCreate,
    AllocationOut,
    ClassCreate,
    ClassDetail,
    ClassMemberOut,
    ClassMembersAdd,
    ClassSummary,
    RoleGrant,
    RoleOut,
    SchoolMe,
    StaffCreate,
    StaffCreateResult,
    StaffOut,
)
from app.services.auth import generate_temp_password, hash_password, provision_teacher
from app.services.school_scope import (
    DEPARTMENTAL_HEAD,
    ROLE_LABELS,
    SCHOOL_ROLES,
    StaffScope,
)

router = APIRouter(prefix="/school", tags=["school"])


def _require_manage(scope: StaffScope) -> None:
    if not scope.can_manage_school:
        raise HTTPException(
            status_code=403,
            detail="Only the principal, deputy principal or school admin can manage the school",
        )


def _role_out(r) -> RoleOut:
    return RoleOut(
        id=r.id,
        role=r.role,
        label=ROLE_LABELS.get(r.role, r.role),
        subject_name=r.subject_name,
        grade=r.grade,
    )


async def _allocations(db: AsyncSession, school_id: uuid.UUID, **filters) -> list[AllocationOut]:
    stmt = (
        select(TeachingAllocation, Subject, SchoolClass, User)
        .join(Subject, TeachingAllocation.subject_id == Subject.id)
        .outerjoin(SchoolClass, TeachingAllocation.class_id == SchoolClass.id)
        .join(User, TeachingAllocation.teacher_user_id == User.id)
        .where(TeachingAllocation.school_id == school_id)
        .order_by(Subject.grade, Subject.name, SchoolClass.name.nullsfirst())
    )
    if "class_ids" in filters:
        stmt = stmt.where(TeachingAllocation.class_id.in_(filters["class_ids"]))
    if "teacher_ids" in filters:
        stmt = stmt.where(TeachingAllocation.teacher_user_id.in_(filters["teacher_ids"]))
    return [
        AllocationOut(
            id=a.id,
            subject_id=s.id,
            subject_name=s.name,
            grade=s.grade,
            class_id=c.id if c else None,
            class_name=c.name if c else None,
            teacher_user_id=u.id,
            teacher_name=u.display_name or u.student_number,
        )
        for a, s, c, u in (await db.execute(stmt)).all()
    ]


async def _class_in_school(db: AsyncSession, class_id: uuid.UUID, scope: StaffScope) -> SchoolClass:
    cls = await db.get(SchoolClass, class_id)
    if cls is None or cls.school_id != scope.school_id:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


async def _staff_in_school(db: AsyncSession, user_id: uuid.UUID, scope: StaffScope) -> User:
    user = await db.get(User, user_id)
    if user is None or user.school_id != scope.school_id or user.role != "teacher":
        raise HTTPException(status_code=404, detail="Staff member not found")
    return user


# --- me ---------------------------------------------------------------------


@router.get("/me", response_model=SchoolMe)
async def me(
    user: User = Depends(get_current_teacher),
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> SchoolMe:
    """What the logged-in staff member holds and may do -- drives which tabs
    and pickers the TEACH UI shows. The server still enforces everything."""
    school = await db.get(School, user.school_id)
    all_subject_ids = (await db.execute(select(Subject.id))).scalars().all()
    return SchoolMe(
        user_id=user.id,
        display_name=user.display_name,
        staff_number=user.student_number,
        school_id=school.id,
        school_name=school.name,
        roles=[_role_out(r) for r in scope.roles],
        allocations=await _allocations(db, user.school_id, teacher_ids=[user.id]),
        can_manage_school=scope.can_manage_school,
        whole_school_academic=scope.whole_school_academic,
        grantable_roles=scope.grantable_roles,
        visible_subject_ids=sorted(scope.visible_subject_ids(all_subject_ids), key=str),
        has_academic_access=bool(scope.academic_learner_ids()) or scope.whole_school_academic
        or any(r.role == DEPARTMENTAL_HEAD for r in scope.roles) or bool(scope.allocations),
    )


# --- classes ----------------------------------------------------------------


async def _class_summaries(db: AsyncSession, classes: list[SchoolClass], scope: StaffScope) -> list[ClassSummary]:
    if not classes:
        return []
    ids = [c.id for c in classes]
    counts = dict(
        (
            await db.execute(
                select(ClassMember.class_id, func.count(ClassMember.id))
                .where(ClassMember.class_id.in_(ids))
                .group_by(ClassMember.class_id)
            )
        ).all()
    )
    allocs = await _allocations(db, scope.school_id, class_ids=ids)
    # Whole-grade allocations cover every class in that grade, so show them too.
    whole_grade = [a for a in await _allocations(db, scope.school_id) if a.class_id is None]
    return [
        ClassSummary(
            id=c.id,
            name=c.name,
            grade=c.grade,
            member_count=counts.get(c.id, 0),
            allocations=[a for a in allocs if a.class_id == c.id]
            + [a for a in whole_grade if a.grade == c.grade],
        )
        for c in classes
    ]


@router.get("/classes", response_model=list[ClassSummary])
async def list_classes(
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> list[ClassSummary]:
    """School managers and whole-school roles see every class; everyone else
    sees the classes they are allocated to teach."""
    stmt = select(SchoolClass).where(SchoolClass.school_id == scope.school_id)
    if not (scope.can_manage_school or scope.whole_school_academic):
        allocated = {a.class_id for a in scope.allocations if a.class_id is not None}
        whole_grades = {a.grade for a in scope.allocations if a.class_id is None}
        if not allocated and not whole_grades:
            return []
        # A whole-grade allocation covers every class in that grade.
        stmt = stmt.where(or_(SchoolClass.id.in_(allocated), SchoolClass.grade.in_(whole_grades)))
    classes = (await db.execute(stmt.order_by(SchoolClass.grade, SchoolClass.name))).scalars().all()
    return await _class_summaries(db, classes, scope)


@router.post("/classes", response_model=ClassSummary)
async def create_class(
    payload: ClassCreate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> ClassSummary:
    _require_manage(scope)
    name = payload.name.strip()
    clash = (
        await db.execute(
            select(SchoolClass.id).where(
                SchoolClass.school_id == scope.school_id, func.lower(SchoolClass.name) == name.lower()
            )
        )
    ).first()
    if clash:
        raise HTTPException(status_code=400, detail=f"A class called {name} already exists")
    cls = SchoolClass(school_id=scope.school_id, name=name, grade=payload.grade)
    db.add(cls)
    await db.commit()
    return ClassSummary(id=cls.id, name=cls.name, grade=cls.grade, member_count=0, allocations=[])


@router.get("/classes/{class_id}", response_model=ClassDetail)
async def get_class(
    class_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> ClassDetail:
    cls = await _class_in_school(db, class_id, scope)
    if not (
        scope.can_manage_school
        or scope.whole_school_academic
        or class_id in {a.class_id for a in scope.allocations}
        or cls.grade in {a.grade for a in scope.allocations if a.class_id is None}
    ):
        raise HTTPException(status_code=404, detail="Class not found")
    summary = (await _class_summaries(db, [cls], scope))[0]
    members = (
        await db.execute(
            select(Learner, User)
            .join(ClassMember, ClassMember.learner_id == Learner.id)
            .join(User, Learner.user_id == User.id)
            .where(ClassMember.class_id == class_id)
            .order_by(Learner.display_name)
        )
    ).all()
    return ClassDetail(
        **summary.model_dump(),
        members=[
            ClassMemberOut(
                learner_id=l.id, display_name=l.display_name, grade=l.grade, student_number=u.student_number
            )
            for l, u in members
        ],
    )


@router.post("/classes/{class_id}/members", response_model=ClassDetail)
async def add_members(
    class_id: uuid.UUID,
    payload: ClassMembersAdd,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> ClassDetail:
    _require_manage(scope)
    cls = await _class_in_school(db, class_id, scope)
    learners = (
        await db.execute(
            select(Learner)
            .join(User, Learner.user_id == User.id)
            .where(
                Learner.id.in_(payload.learner_ids),
                User.school_id == scope.school_id,
                User.role == "student",
            )
        )
    ).scalars().all()
    if len(learners) != len(set(payload.learner_ids)):
        raise HTTPException(status_code=400, detail="One or more students are not in this school")
    wrong_grade = [l.display_name for l in learners if l.grade != cls.grade]
    if wrong_grade:
        raise HTTPException(
            status_code=400,
            detail=f"{cls.name} is a Grade {cls.grade} class; not in Grade {cls.grade}: "
            + ", ".join(wrong_grade),
        )
    existing = set(
        (await db.execute(select(ClassMember.learner_id).where(ClassMember.class_id == class_id)))
        .scalars()
        .all()
    )
    for l in learners:
        if l.id not in existing:
            db.add(ClassMember(class_id=class_id, learner_id=l.id))
    await db.commit()
    return await get_class(class_id, scope, db)


@router.delete("/classes/{class_id}/members/{learner_id}", response_model=ClassDetail)
async def remove_member(
    class_id: uuid.UUID,
    learner_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> ClassDetail:
    _require_manage(scope)
    await _class_in_school(db, class_id, scope)
    await db.execute(
        delete(ClassMember).where(ClassMember.class_id == class_id, ClassMember.learner_id == learner_id)
    )
    await db.commit()
    return await get_class(class_id, scope, db)


# --- staff ------------------------------------------------------------------


@router.get("/staff", response_model=list[StaffOut])
async def list_staff(
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> list[StaffOut]:
    _require_manage(scope)
    staff = (
        await db.execute(
            select(User)
            .where(User.school_id == scope.school_id, User.role == "teacher")
            .order_by(User.display_name, User.student_number)
        )
    ).scalars().all()
    roles = (
        await db.execute(select(StaffRole).where(StaffRole.school_id == scope.school_id))
    ).scalars().all()
    allocs = await _allocations(db, scope.school_id)
    return [
        StaffOut(
            user_id=u.id,
            display_name=u.display_name,
            staff_number=u.student_number,
            is_active=bool(u.is_active),
            roles=[_role_out(r) for r in roles if r.user_id == u.id],
            allocations=[a for a in allocs if a.teacher_user_id == u.id],
        )
        for u in staff
    ]


@router.post("/staff", response_model=StaffCreateResult)
async def create_staff(
    payload: StaffCreate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> StaffCreateResult:
    """Creates a staff (teacher) login. It can see nothing until it is given
    an allocation or a role -- shown once, like student temp passwords."""
    _require_manage(scope)
    school = await db.get(School, scope.school_id)
    staff_number = (payload.staff_number or "").strip() or None
    if staff_number:
        clash = (
            await db.execute(
                select(User.id).where(User.school_id == school.id, User.student_number == staff_number)
            )
        ).first()
        if clash:
            raise HTTPException(status_code=400, detail=f"Number {staff_number} is already in use at this school")
    try:
        user, temp_password = await provision_teacher(db, school=school, staff_number=staff_number)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    user.display_name = payload.display_name.strip()
    await db.commit()
    return StaffCreateResult(
        user_id=user.id,
        display_name=user.display_name,
        staff_number=user.student_number,
        temp_password=temp_password,
    )


@router.post("/staff/{user_id}/roles", response_model=RoleOut)
async def grant_role(
    user_id: uuid.UUID,
    payload: RoleGrant,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> RoleOut:
    if payload.role not in SCHOOL_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {payload.role}")
    if payload.role not in scope.grantable_roles:
        raise HTTPException(status_code=403, detail=f"You can't grant the {ROLE_LABELS[payload.role]} role")
    target = await _staff_in_school(db, user_id, scope)

    subject_name = None
    grade = None
    if payload.role == DEPARTMENTAL_HEAD:
        subject_name = (payload.subject_name or "").strip()
        if not subject_name:
            raise HTTPException(status_code=400, detail="A departmental head needs a subject")
        stmt = select(Subject.id).where(Subject.name == subject_name)
        if payload.grade is not None:
            stmt = stmt.where(Subject.grade == payload.grade)
        if not (await db.execute(stmt)).first():
            raise HTTPException(status_code=400, detail="No such subject (at that grade)")
        grade = payload.grade

    dup = (
        await db.execute(
            select(StaffRole.id).where(
                StaffRole.user_id == target.id,
                StaffRole.role == payload.role,
                StaffRole.subject_name.is_(None) if subject_name is None else StaffRole.subject_name == subject_name,
                StaffRole.grade.is_(None) if grade is None else StaffRole.grade == grade,
            )
        )
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="That role is already granted")

    role = StaffRole(
        user_id=target.id,
        school_id=scope.school_id,
        role=payload.role,
        subject_name=subject_name,
        grade=grade,
        granted_by_user_id=scope.user_id,
    )
    db.add(role)
    await db.commit()
    return _role_out(role)


@router.delete("/roles/{role_id}", status_code=204)
async def revoke_role(
    role_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    role = await db.get(StaffRole, role_id)
    if role is None or role.school_id != scope.school_id:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.user_id == scope.user_id:
        raise HTTPException(status_code=403, detail="You can't remove your own role")
    if role.role not in scope.grantable_roles:
        raise HTTPException(status_code=403, detail=f"You can't remove the {ROLE_LABELS.get(role.role, role.role)} role")
    await db.delete(role)
    await db.commit()


# --- allocations ------------------------------------------------------------


async def _add_allocation(
    db: AsyncSession, scope: StaffScope, teacher: User, subject_id: uuid.UUID, class_id: Optional[uuid.UUID]
) -> AllocationOut:
    """Validates and adds one allocation (not committed). Raises
    HTTPException with a readable reason when it can't be added."""
    subject = await db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    cls = None
    if class_id is not None:
        cls = await _class_in_school(db, class_id, scope)
        if subject.grade != cls.grade:
            raise HTTPException(
                status_code=400,
                detail=f"{cls.name} is Grade {cls.grade} but {subject.name} Grade {subject.grade} was chosen",
            )
    where_class = (
        TeachingAllocation.class_id.is_(None) if class_id is None else TeachingAllocation.class_id == class_id
    )
    dup = (
        await db.execute(
            select(TeachingAllocation.id).where(
                TeachingAllocation.teacher_user_id == teacher.id,
                TeachingAllocation.subject_id == subject.id,
                where_class,
            )
        )
    ).first()
    target = cls.name if cls else f"the whole of Grade {subject.grade}"
    if dup:
        raise HTTPException(status_code=400, detail=f"{subject.name} for {target} is already allocated")
    alloc = TeachingAllocation(
        school_id=scope.school_id, teacher_user_id=teacher.id, subject_id=subject.id, class_id=class_id
    )
    db.add(alloc)
    await db.flush()
    return AllocationOut(
        id=alloc.id,
        subject_id=subject.id,
        subject_name=subject.name,
        grade=subject.grade,
        class_id=cls.id if cls else None,
        class_name=cls.name if cls else None,
        teacher_user_id=teacher.id,
        teacher_name=teacher.display_name or teacher.student_number,
    )


@router.post("/allocations", response_model=AllocationOut)
async def create_allocation(
    payload: AllocationCreate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> AllocationOut:
    """One subject to one class -- or, with no class_id, to the whole grade."""
    _require_manage(scope)
    teacher = await _staff_in_school(db, payload.teacher_user_id, scope)
    out = await _add_allocation(db, scope, teacher, payload.subject_id, payload.class_id)
    await db.commit()
    return out


@router.post("/allocations/bulk", response_model=AllocationBulkResult)
async def create_allocations_bulk(
    payload: AllocationBulkCreate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> AllocationBulkResult:
    """NEW 17 Nov 2026: several subjects across several grades/classes for one
    teacher in one step. Each item is checked on its own; ones that can't be
    added (already allocated, wrong grade) are reported, not fatal."""
    _require_manage(scope)
    teacher = await _staff_in_school(db, payload.teacher_user_id, scope)
    created: list[AllocationOut] = []
    skipped: list[str] = []
    for item in payload.items:
        try:
            created.append(await _add_allocation(db, scope, teacher, item.subject_id, item.class_id))
        except HTTPException as exc:
            skipped.append(str(exc.detail))
    await db.commit()
    return AllocationBulkResult(created=created, skipped=skipped)


@router.delete("/allocations/{allocation_id}", status_code=204)
async def delete_allocation(
    allocation_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_manage(scope)
    alloc = await db.get(TeachingAllocation, allocation_id)
    if alloc is None or alloc.school_id != scope.school_id:
        raise HTTPException(status_code=404, detail="Allocation not found")
    await db.delete(alloc)
    await db.commit()


# --- account and year-end admin (code review #13, 17 Nov 2026) ------------------


async def _user_in_school(db: AsyncSession, user_id: uuid.UUID, scope: StaffScope) -> User:
    user = await db.get(User, user_id)
    if user is None or user.school_id != scope.school_id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _may_manage_account(db: AsyncSession, user: User, scope: StaffScope) -> bool:
    """School management may manage any account in the school; a teacher may
    reset the password of a learner on their own roster (a forgotten
    password is usually noticed in class)."""
    if scope.can_manage_school:
        return True
    if user.role != "student":
        return False
    learner = (await db.execute(select(Learner).where(Learner.user_id == user.id))).scalar_one_or_none()
    return learner is not None and scope.can_see_roster(learner.id)


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResult)
async def reset_password(
    user_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> PasswordResetResult:
    """
    Issues a new one-time password for a learner or staff member who forgot
    theirs. They must choose a new one at next login, and any session they
    still have open ends (token_version).
    """
    user = await _user_in_school(db, user_id, scope)
    if user.id == scope.user_id:
        raise HTTPException(status_code=400, detail="Use Change password for your own account")
    if not await _may_manage_account(db, user, scope):
        raise HTTPException(status_code=403, detail="You can't reset this person's password")
    temp = generate_temp_password()
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    user.token_version = (user.token_version or 0) + 1
    await db.commit()
    return PasswordResetResult(user_id=user.id, temp_password=temp)


@router.post("/users/{user_id}/active", status_code=204)
async def set_active(
    user_id: uuid.UUID,
    payload: ActiveUpdate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Deactivate (or reactivate) a learner or staff member who has left. Their
    data stays; they just can't log in, and a learner drops out of rosters,
    progress and new assignments.
    """
    _require_manage(scope)
    user = await _user_in_school(db, user_id, scope)
    if user.id == scope.user_id:
        raise HTTPException(status_code=400, detail="You can't deactivate your own account")
    user.is_active = payload.active
    if not payload.active:
        user.token_version = (user.token_version or 0) + 1
    await db.commit()


@router.post("/learners/promote", response_model=PromoteResult)
async def promote_learners(
    payload: PromoteRequest,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> PromoteResult:
    """
    Year end: every active learner in `grade` moves up one grade. Classes
    belong to a grade, so promoted learners leave their old classes (put
    them in next year's classes afterwards). Grade 12 isn't promoted --
    deactivate leavers instead.
    """
    _require_manage(scope)
    learners = (
        await db.execute(
            select(Learner)
            .join(User, Learner.user_id == User.id)
            .where(
                User.school_id == scope.school_id,
                User.role == "student",
                User.is_active.is_(True),
                Learner.grade == payload.grade,
            )
        )
    ).scalars().all()
    ids = [l.id for l in learners]
    removed = 0
    if ids:
        old_class_ids = (
            await db.execute(
                select(SchoolClass.id).where(
                    SchoolClass.school_id == scope.school_id, SchoolClass.grade == payload.grade
                )
            )
        ).scalars().all()
        if old_class_ids:
            result = await db.execute(
                delete(ClassMember).where(
                    ClassMember.learner_id.in_(ids), ClassMember.class_id.in_(old_class_ids)
                )
            )
            removed = result.rowcount or 0
        for learner in learners:
            learner.grade = payload.grade + 1
    await db.commit()
    return PromoteResult(promoted=len(ids), removed_from_classes=removed)


@router.patch("/classes/{class_id}", response_model=ClassSummary)
async def rename_class(
    class_id: uuid.UUID,
    payload: ClassUpdate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> ClassSummary:
    _require_manage(scope)
    cls = await _class_in_school(db, class_id, scope)
    name = payload.name.strip()
    clash = (
        await db.execute(
            select(SchoolClass.id).where(
                SchoolClass.school_id == scope.school_id,
                func.lower(SchoolClass.name) == name.lower(),
                SchoolClass.id != cls.id,
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(status_code=400, detail=f"A class called {name} already exists")
    cls.name = name
    await db.commit()
    return (await _class_summaries(db, [cls], scope))[0]


@router.delete("/classes/{class_id}", status_code=204)
async def delete_class(
    class_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deletes the class, its member list and its subject allocations. The
    learners themselves, and all their work, are untouched."""
    _require_manage(scope)
    cls = await _class_in_school(db, class_id, scope)
    await db.execute(delete(ClassMember).where(ClassMember.class_id == cls.id))
    await db.execute(delete(TeachingAllocation).where(TeachingAllocation.class_id == cls.id))
    await db.delete(cls)
    await db.commit()
