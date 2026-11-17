"""
Tests for app/services/school_scope.py's build_scope() (ADR-031). Pure --
no DB -- same as test_class_progress.py.
"""

import uuid

from app.services.school_scope import (
    ALL_SUBJECTS,
    AllocationRow,
    RoleRow,
    SubjectRow,
    build_scope,
)

SCHOOL = uuid.uuid4()
ME = uuid.uuid4()

MATHS_10 = SubjectRow(uuid.uuid4(), "Pure Mathematics", 10)
MATHS_11 = SubjectRow(uuid.uuid4(), "Pure Mathematics", 11)
PHYS_10 = SubjectRow(uuid.uuid4(), "Physical Sciences", 10)
ACC_10 = SubjectRow(uuid.uuid4(), "Accounting", 10)
SUBJECTS = [MATHS_10, MATHS_11, PHYS_10, ACC_10]

CLASS_10A = uuid.uuid4()
CLASS_10B = uuid.uuid4()

AMAHLE, BONGANI, CEBO, DUMI = (uuid.uuid4() for _ in range(4))
LEARNERS = {AMAHLE: 10, BONGANI: 10, CEBO: 10, DUMI: 11}
MEMBERS = {CLASS_10A: {AMAHLE, BONGANI}, CLASS_10B: {CEBO}}


def _role(role, subject_name=None, grade=None):
    return RoleRow(uuid.uuid4(), role, subject_name, grade)


def _alloc(subject, class_id, class_name="10A"):
    return AllocationRow(uuid.uuid4(), subject.id, subject.name, subject.grade, class_id, class_name)


def _scope(roles=(), allocations=(), learners=LEARNERS, members=MEMBERS):
    return build_scope(
        user_id=ME,
        school_id=SCHOOL,
        roles=list(roles),
        allocations=list(allocations),
        school_learners=dict(learners),
        class_members={k: set(v) for k, v in members.items()},
        subjects=SUBJECTS,
    )


def test_no_roles_no_allocations_sees_nothing():
    s = _scope()
    assert s.roster_learner_ids == set()
    assert s.academic_learner_ids() == set()
    assert not s.can_manage_school
    assert s.grantable_roles == []


def test_teacher_sees_only_their_class_and_subject():
    s = _scope(allocations=[_alloc(MATHS_10, CLASS_10A)])
    assert s.roster_learner_ids == {AMAHLE, BONGANI}
    assert s.academic_learner_ids() == {AMAHLE, BONGANI}
    assert s.can_see_subject(AMAHLE, MATHS_10.id)
    assert not s.can_see_subject(AMAHLE, PHYS_10.id)  # not their subject
    assert not s.can_see_subject(CEBO, MATHS_10.id)  # not their class
    assert not s.can_manage_school
    assert s.visible_subject_ids([x.id for x in SUBJECTS]) == {MATHS_10.id}


def test_two_allocations_union_per_learner():
    s = _scope(allocations=[_alloc(MATHS_10, CLASS_10A), _alloc(PHYS_10, CLASS_10A), _alloc(MATHS_10, CLASS_10B, "10B")])
    assert s.subjects_for(AMAHLE) == {MATHS_10.id, PHYS_10.id}
    assert s.subjects_for(CEBO) == {MATHS_10.id}


def test_departmental_head_sees_department_subjects_in_matching_grades():
    s = _scope(roles=[_role("departmental_head", "Pure Mathematics")])
    # every Grade 10 learner for Maths 10, the Grade 11 learner for Maths 11
    assert s.subjects_for(AMAHLE) == {MATHS_10.id}
    assert s.subjects_for(DUMI) == {MATHS_11.id}
    assert not s.can_see_subject(AMAHLE, ACC_10.id)
    assert not s.can_manage_school


def test_departmental_head_limited_to_one_grade():
    s = _scope(roles=[_role("departmental_head", "Pure Mathematics", 11)])
    assert s.academic_learner_ids() == {DUMI}
    assert s.roster_learner_ids == {DUMI}


def test_principal_sees_everything_and_can_grant_below():
    s = _scope(roles=[_role("principal")])
    assert s.roster_learner_ids == set(LEARNERS)
    assert all(s.subjects_for(l) is ALL_SUBJECTS for l in LEARNERS)
    assert s.can_see_subject(DUMI, ACC_10.id)
    assert s.can_manage_school
    assert s.grantable_roles == ["deputy_principal", "departmental_head", "school_admin"]


def test_deputy_cannot_grant_deputy_or_principal():
    s = _scope(roles=[_role("deputy_principal")])
    assert s.whole_school_academic
    assert s.grantable_roles == ["departmental_head", "school_admin"]


def test_school_admin_manages_roster_but_sees_no_marks():
    s = _scope(roles=[_role("school_admin")])
    assert s.roster_learner_ids == set(LEARNERS)
    assert s.academic_learner_ids() == set()
    assert s.can_manage_school
    assert not s.whole_school_academic
    assert s.grantable_roles == []


def test_admin_who_also_teaches_gets_marks_only_for_their_class():
    s = _scope(roles=[_role("school_admin")], allocations=[_alloc(MATHS_10, CLASS_10B, "10B")])
    assert s.roster_learner_ids == set(LEARNERS)
    assert s.academic_learner_ids() == {CEBO}


def test_principal_role_beats_narrower_allocation():
    s = _scope(roles=[_role("principal")], allocations=[_alloc(MATHS_10, CLASS_10A)])
    assert s.subjects_for(AMAHLE) is ALL_SUBJECTS


def test_class_member_from_another_school_is_never_visible():
    outsider = uuid.uuid4()
    s = _scope(allocations=[_alloc(MATHS_10, CLASS_10A)], members={CLASS_10A: {AMAHLE, outsider}})
    assert outsider not in s.roster_learner_ids
    assert outsider not in s.academic_learner_ids()
