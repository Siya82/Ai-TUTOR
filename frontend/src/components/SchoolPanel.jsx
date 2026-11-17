/*
 * NEW 17 Nov 2026 (ADR-031, school roles and scoping). The "School" tab
 * of TeacherAdminScreen.jsx -- shown only to the principal, deputy
 * principal and school admin (me.can_manage_school). Two sections:
 *
 *   - Classes: create a class, add/remove its learners (same grade only),
 *     see which teacher teaches which subject to it.
 *   - Staff: create staff logins (temp password shown once), grant/revoke
 *     roles below your own, and allocate teachers to subject + class.
 *
 * The server enforces every rule here (403/400 with a readable message);
 * this screen only hides what the caller can't do.
 */

import { useEffect, useRef, useState } from "react";
import {
  addClassMembers,
  createAllocationsBulk,
  createClass,
  createStaff,
  deleteAllocation,
  fetchClassDetail,
  fetchClasses,
  fetchStaff,
  fetchSubjects,
  grantStaffRole,
  removeClassMember,
  revokeStaffRole,
} from "../api";

const ROLE_LABELS = {
  principal: "Principal",
  deputy_principal: "Deputy principal",
  departmental_head: "Departmental head",
  school_admin: "School admin",
};

const GRADES = [8, 9, 10, 11, 12];

function useLatest(fn) {
  const ref = useRef(fn);
  useEffect(() => {
    ref.current = fn;
  }, [fn]);
  return ref;
}

export default function SchoolPanel({ token, onLogout, me, students, onChanged }) {
  const [section, setSection] = useState("classes");
  const [classes, setClasses] = useState([]);
  const [staff, setStaff] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const onLogoutRef = useLatest(onLogout);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchClasses(token), fetchStaff(token), fetchSubjects(token)])
      .then(([c, s, subj]) => {
        if (cancelled) return;
        setClasses(c);
        setStaff(s);
        setSubjects(subj);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) {
          onLogoutRef.current();
          return;
        }
        setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey, onLogoutRef]);

  const reload = () => {
    setReloadKey((k) => k + 1);
    onChanged?.();
  };

  // Wraps an action: shows its error, logs out on 401, reloads on success.
  const run = async (fn) => {
    setError(null);
    try {
      const result = await fn();
      reload();
      return result;
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return undefined;
      }
      setError(err.message);
      return undefined;
    }
  };

  return (
    <div className="admin-panel">
      <div className="progress-filter" role="tablist" aria-label="School setup sections">
        {[
          ["classes", "Classes"],
          ["staff", "Staff"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`progress-filter__chip${section === id ? " progress-filter__chip--active" : ""}`}
            onClick={() => setSection(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="admin-screen__error">{error}</div>}

      {section === "classes" && (
        <ClassesSection token={token} classes={classes} students={students} run={run} />
      )}
      {section === "staff" && (
        <StaffSection
          token={token}
          me={me}
          staff={staff}
          classes={classes}
          subjects={subjects}
          run={run}
        />
      )}
    </div>
  );
}

// --- Classes -----------------------------------------------------------------

function ClassesSection({ token, classes, students, run }) {
  const [name, setName] = useState("");
  const [grade, setGrade] = useState(10);
  const [openClassId, setOpenClassId] = useState(null);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    const created = await run(() => createClass(token, { name: name.trim(), grade }));
    if (created) {
      setName("");
      setOpenClassId(created.id);
    }
  };

  return (
    <>
      <form className="admin-form admin-form--inline" onSubmit={handleCreate}>
        <label className="admin-form__field">
          <span>New class name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. 10A" />
        </label>
        <label className="admin-form__field">
          <span>Grade</span>
          <select value={grade} onChange={(e) => setGrade(Number(e.target.value))}>
            {GRADES.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!name.trim()}>
          Create class
        </button>
      </form>

      {classes.length === 0 ? (
        <p className="admin-screen__muted">No classes yet. Create one above, then add its learners.</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Class</th>
              <th>Grade</th>
              <th>Learners</th>
              <th>Taught by</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {classes.map((c) => (
              <tr key={c.id}>
                <td className="progress-table__name">{c.name}</td>
                <td>{c.grade}</td>
                <td>{c.member_count}</td>
                <td>
                  {c.allocations.length === 0 ? (
                    <span className="admin-screen__muted">No teacher allocated</span>
                  ) : (
                    c.allocations.map((a) => (
                      <div key={a.id}>
                        {a.subject_name} — {a.teacher_name}
                        {!a.class_id && <span className="admin-screen__muted"> (whole grade)</span>}
                      </div>
                    ))
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="admin-screen__link-button"
                    onClick={() => setOpenClassId(openClassId === c.id ? null : c.id)}
                  >
                    {openClassId === c.id ? "Close" : "Manage learners"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {openClassId && (
        <ClassMembersEditor
          key={openClassId}
          token={token}
          classId={openClassId}
          students={students}
          run={run}
        />
      )}
    </>
  );
}

function ClassMembersEditor({ token, classId, students, run }) {
  const [detail, setDetail] = useState(null);
  const [selected, setSelected] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchClassDetail(token, classId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, classId, version]);

  if (loadError) return <div className="admin-screen__error">{loadError}</div>;
  if (!detail) return <p className="admin-screen__muted">Loading class…</p>;

  const memberIds = new Set(detail.members.map((m) => m.learner_id));
  const candidates = students.filter((s) => s.grade === detail.grade && !memberIds.has(s.learner_id));

  const toggle = (id) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const handleAdd = async () => {
    const result = await run(() => addClassMembers(token, classId, selected));
    if (result) {
      setSelected([]);
      setVersion((v) => v + 1);
    }
  };

  const handleRemove = async (learnerId) => {
    const result = await run(() => removeClassMember(token, classId, learnerId));
    if (result) setVersion((v) => v + 1);
  };

  return (
    <div className="admin-form">
      <h3 className="admin-screen__subheading">
        {detail.name} · Grade {detail.grade} · {detail.members.length} learner(s)
      </h3>
      {detail.members.length === 0 ? (
        <p className="admin-screen__muted">No learners in this class yet.</p>
      ) : (
        <ul className="school-list">
          {detail.members.map((m) => (
            <li key={m.learner_id} className="school-list__item">
              <span>
                {m.display_name} <span className="admin-screen__muted">({m.student_number})</span>
              </span>
              <button
                type="button"
                className="admin-screen__link-button"
                onClick={() => handleRemove(m.learner_id)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <fieldset className="admin-form__fieldset">
        <legend>Add Grade {detail.grade} learners</legend>
        {candidates.length === 0 ? (
          <p className="admin-screen__muted">
            Every Grade {detail.grade} learner is already in this class, or there are none yet.
          </p>
        ) : (
          candidates.map((s) => (
            <label key={s.learner_id} className="admin-form__checkbox-row">
              <input
                type="checkbox"
                checked={selected.includes(s.learner_id)}
                onChange={() => toggle(s.learner_id)}
              />
              {s.display_name}
              {s.classes?.length > 0 && (
                <span className="admin-screen__muted"> — in {s.classes.join(", ")}</span>
              )}
            </label>
          ))
        )}
      </fieldset>
      <button
        type="button"
        className="admin-form__primary-button"
        onClick={handleAdd}
        disabled={selected.length === 0}
      >
        Add {selected.length || ""} learner{selected.length === 1 ? "" : "s"}
      </button>
    </div>
  );
}

// --- Staff -------------------------------------------------------------------

function StaffSection({ token, me, staff, classes, subjects, run }) {
  const [name, setName] = useState("");
  const [staffNumber, setStaffNumber] = useState("");
  const [created, setCreated] = useState(null);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    const result = await run(() =>
      createStaff(token, { displayName: name.trim(), staffNumber: staffNumber.trim() || undefined })
    );
    if (result) {
      setCreated(result);
      setName("");
      setStaffNumber("");
    }
  };

  return (
    <>
      <form className="admin-form admin-form--inline" onSubmit={handleCreate}>
        <label className="admin-form__field">
          <span>New staff member's name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ms N. Mkhize" />
        </label>
        <label className="admin-form__field">
          <span>Staff number (optional)</span>
          <input
            value={staffNumber}
            onChange={(e) => setStaffNumber(e.target.value)}
            placeholder="auto-generated if blank"
          />
        </label>
        <button type="submit" disabled={!name.trim()}>
          Create login
        </button>
      </form>

      {created && (
        <div className="admin-result">
          <p className="admin-result__title">
            Login created for {created.display_name}. Share these details with them; the password is
            shown only once and must be changed at first login. They can't see any learners until you
            allocate them a class or give them a role below.
          </p>
          <dl className="admin-result__details">
            <dt>Staff number</dt>
            <dd>{created.staff_number}</dd>
            <dt>Temporary password</dt>
            <dd className="admin-result__password">{created.temp_password}</dd>
          </dl>
        </div>
      )}

      <div className="staff-cards">
        {staff.map((s) => (
          <StaffCard
            key={s.user_id}
            token={token}
            me={me}
            member={s}
            classes={classes}
            subjects={subjects}
            run={run}
          />
        ))}
      </div>
    </>
  );
}

function StaffCard({ token, me, member, classes, subjects, run }) {
  const [mode, setMode] = useState(null); // "role" | "allocate" | null
  const [notice, setNotice] = useState(null);
  const isMe = member.user_id === me.user_id;
  const canRevoke = (role) => !isMe && me.grantable_roles.includes(role.role);

  return (
    <div className="staff-card">
      <div className="staff-card__header">
        <div>
          <div className="progress-table__name">
            {member.display_name || "(no name)"} {isMe && <span className="admin-screen__muted">(you)</span>}
          </div>
          <div className="admin-screen__muted">Staff number {member.staff_number}</div>
        </div>
      </div>

      <div className="staff-card__row">
        <span className="staff-card__label">Roles</span>
        <div className="staff-card__chips">
          {member.roles.length === 0 && <span className="admin-screen__muted">Teacher only</span>}
          {member.roles.map((r) => (
            <span key={r.id} className="chip">
              {r.label}
              {r.subject_name ? `: ${r.subject_name}` : ""}
              {r.grade ? ` (Gr ${r.grade})` : ""}
              {canRevoke(r) && (
                <button
                  type="button"
                  className="chip__remove"
                  aria-label={`Remove ${r.label}`}
                  onClick={() => run(() => revokeStaffRole(token, r.id))}
                >
                  ×
                </button>
              )}
            </span>
          ))}
        </div>
      </div>

      <div className="staff-card__row">
        <span className="staff-card__label">Teaches</span>
        <div className="staff-card__chips">
          {member.allocations.length === 0 && <span className="admin-screen__muted">No classes</span>}
          {member.allocations.map((a) => (
            <span key={a.id} className="chip">
              {a.subject_name} · {a.class_name || `Grade ${a.grade} (whole grade)`}
              <button
                type="button"
                className="chip__remove"
                aria-label={`Remove ${a.subject_name} ${a.class_name}`}
                onClick={() => run(() => deleteAllocation(token, a.id))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>

      {notice && <div className="admin-screen__muted">{notice}</div>}

      <div className="staff-card__actions">
        <button
          type="button"
          className="admin-screen__link-button"
          onClick={() => setMode(mode === "allocate" ? null : "allocate")}
        >
          Allocate subjects / grades
        </button>
        {me.grantable_roles.length > 0 && !isMe && (
          <button
            type="button"
            className="admin-screen__link-button"
            onClick={() => setMode(mode === "role" ? null : "role")}
          >
            Give a role
          </button>
        )}
      </div>

      {mode === "allocate" && (
        <AllocateForm
          classes={classes}
          subjects={subjects}
          onSubmit={async (items) => {
            const result = await run(() => createAllocationsBulk(token, member.user_id, items));
            if (result) {
              setNotice(
                `Added ${result.created.length} allocation${result.created.length === 1 ? "" : "s"}.` +
                  (result.skipped.length ? ` Skipped: ${result.skipped.join("; ")}.` : "")
              );
              if (result.created.length) setMode(null);
            }
          }}
        />
      )}
      {mode === "role" && (
        <RoleForm
          grantable={me.grantable_roles}
          subjects={subjects}
          onSubmit={async (payload) => {
            const ok = await run(() => grantStaffRole(token, member.user_id, payload));
            if (ok) setMode(null);
          }}
        />
      )}
    </div>
  );
}

// UPDATED 17 Nov 2026: one teacher can be given several subjects across
// several grades in one step -- to a whole grade (every learner in it, no
// classes needed) or to specific classes in those grades.
function AllocateForm({ classes, subjects, onSubmit }) {
  const [subjectNames, setSubjectNames] = useState([]);
  const [grades, setGrades] = useState([]);
  const [target, setTarget] = useState("grade"); // "grade" | "classes"
  const [classIds, setClassIds] = useState([]);

  const allNames = [...new Set(subjects.map((s) => s.name))].sort();
  const gradesForNames = [
    ...new Set(subjects.filter((s) => subjectNames.includes(s.name)).map((s) => s.grade)),
  ].sort((a, b) => a - b);
  const classesForGrades = classes.filter((c) => grades.includes(c.grade));

  const toggle = (list, setList, value) =>
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

  // Every (subject row, class|whole grade) pair the choices add up to.
  const items = [];
  const missing = [];
  for (const name of subjectNames) {
    for (const g of grades) {
      const subject = subjects.find((s) => s.name === name && s.grade === g);
      if (!subject) {
        missing.push(`${name} isn't offered in Grade ${g}`);
        continue;
      }
      if (target === "grade") {
        items.push({ subjectId: subject.id, classId: null, label: `${name} · Grade ${g} (whole grade)` });
      } else {
        for (const c of classesForGrades.filter((cl) => cl.grade === g && classIds.includes(cl.id))) {
          items.push({ subjectId: subject.id, classId: c.id, label: `${name} · ${c.name}` });
        }
      }
    }
  }

  return (
    <div className="admin-form allocate-form">
      <fieldset className="admin-form__fieldset">
        <legend>Subjects</legend>
        {allNames.map((n) => (
          <label key={n} className="admin-form__checkbox-row">
            <input type="checkbox" checked={subjectNames.includes(n)} onChange={() => toggle(subjectNames, setSubjectNames, n)} />
            {n}
          </label>
        ))}
      </fieldset>

      <fieldset className="admin-form__fieldset">
        <legend>Grades</legend>
        {subjectNames.length === 0 ? (
          <p className="admin-screen__muted">Pick at least one subject first.</p>
        ) : (
          gradesForNames.map((g) => (
            <label key={g} className="admin-form__checkbox-row">
              <input type="checkbox" checked={grades.includes(g)} onChange={() => toggle(grades, setGrades, g)} />
              Grade {g}
            </label>
          ))
        )}
      </fieldset>

      <fieldset className="admin-form__fieldset">
        <legend>Teach to</legend>
        <label className="admin-form__checkbox-row">
          <input type="radio" name="alloc-target" checked={target === "grade"} onChange={() => setTarget("grade")} />
          The whole grade (every learner in it)
        </label>
        <label className="admin-form__checkbox-row">
          <input type="radio" name="alloc-target" checked={target === "classes"} onChange={() => setTarget("classes")} />
          Specific classes
        </label>
        {target === "classes" &&
          (classesForGrades.length === 0 ? (
            <p className="admin-screen__muted">
              {grades.length ? "No classes in those grades yet — create them in the Classes section." : "Pick grades first."}
            </p>
          ) : (
            classesForGrades.map((c) => (
              <label key={c.id} className="admin-form__checkbox-row allocate-form__class">
                <input type="checkbox" checked={classIds.includes(c.id)} onChange={() => toggle(classIds, setClassIds, c.id)} />
                {c.name} (Grade {c.grade})
              </label>
            ))
          ))}
      </fieldset>

      {(items.length > 0 || missing.length > 0) && (
        <div className="admin-screen__muted">
          {items.length > 0 && <>Will add: {items.map((i) => i.label).join(", ")}.</>}
          {missing.length > 0 && <> Not possible: {missing.join("; ")}.</>}
        </div>
      )}

      <button
        type="button"
        className="admin-form__primary-button"
        disabled={items.length === 0}
        onClick={() => onSubmit(items)}
      >
        Allocate {items.length || ""}
      </button>
    </div>
  );
}

function RoleForm({ grantable, subjects, onSubmit }) {
  const [role, setRole] = useState(grantable[0] || "");
  const [subjectName, setSubjectName] = useState("");
  const [grade, setGrade] = useState("");
  const subjectNames = [...new Set(subjects.map((s) => s.name))].sort();
  const gradesForSubject = subjects
    .filter((s) => s.name === subjectName)
    .map((s) => s.grade)
    .sort((a, b) => a - b);
  const needsSubject = role === "departmental_head";

  return (
    <div className="admin-form admin-form--inline">
      <label className="admin-form__field">
        <span>Role</span>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {grantable.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r] || r}
            </option>
          ))}
        </select>
      </label>
      {needsSubject && (
        <>
          <label className="admin-form__field">
            <span>Subject (department)</span>
            <select
              value={subjectName}
              onChange={(e) => {
                setSubjectName(e.target.value);
                setGrade("");
              }}
            >
              <option value="">Choose…</option>
              {subjectNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-form__field">
            <span>Grade</span>
            <select value={grade} onChange={(e) => setGrade(e.target.value)} disabled={!subjectName}>
              <option value="">All grades</option>
              {gradesForSubject.map((g) => (
                <option key={g} value={g}>
                  Grade {g}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      <button
        type="button"
        className="admin-form__primary-button"
        disabled={!role || (needsSubject && !subjectName)}
        onClick={() =>
          onSubmit({ role, subjectName: needsSubject ? subjectName : undefined, grade: needsSubject ? grade : undefined })
        }
      >
        Give role
      </button>
      {needsSubject && (
        <p className="admin-screen__muted">
          For a department covering several subjects (e.g. Mathematics and Physical Sciences), give
          this role once per subject.
        </p>
      )}
    </div>
  );
}
