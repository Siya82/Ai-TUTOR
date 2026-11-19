/*
 * REBUILD NOTE (8 Nov 2026, step 7): the recovered version of this file
 * hardcoded a DEV_LEARNER_ID and a TOPIC_IDS map of specific UUIDs from
 * the original (now-gone) database -- REBUILD_SPEC.md Section 3 flagged
 * this exact problem ("Dev-environment IDs will not transfer") and
 * recommended fetching them dynamically instead. fetchTopics() and
 * fetchLearners() below do that, against the two new endpoints added
 * in this same step (backend/app/routers/topics.py, learners.py).
 *
 * UPDATED 14 Nov 2026 (ADR-017, student login): learner_id is no longer
 * passed by the frontend at all -- the backend resolves it from the
 * Authorization bearer token instead (app/core/security.py). login(),
 * fetchMe(), and changePassword() below are the new auth calls;
 * uploadAttachment()/sendTutorMessage() now take a token instead of a
 * learnerId.
 */

import { shrinkImageIfNeeded } from "./utils/shrinkImage";

const API_BASE_URL = "http://localhost:8000";

// FIX 13 Nov 2026 (ADR-016): FastAPI's `detail` is a plain string for a
// raised HTTPException, but for a pydantic validation error (422) it's
// a LIST of {loc, msg, type} objects -- `new Error(thatArray)` used to
// stringify straight to the useless literal "[object Object]". This
// turns either shape into one readable line.
function formatErrorDetail(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "string" ? d : d.msg || JSON.stringify(d)))
      .join("; ");
  }
  return fallback;
}

// NEW 14 Nov 2026 (ADR-017): every thrown error below carries the HTTP
// status (where there is one) as `.status`, so a caller can tell a 401
// (expired/invalid token -- time to log out again) apart from any
// other failure without string-matching the message.
// UPDATED 17 Nov 2026 (code review #14): a 401 on any authenticated call
// means the session is over (expired, password changed elsewhere, or the
// account was deactivated). Rather than every screen handling that itself
// (several didn't), App registers one handler that logs out with a notice.
// Login and change-password pass quiet=true: their 401 means "wrong
// password", not "session over".
let onUnauthorized = null;
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

function httpError(message, status, { quiet = false } = {}) {
  const err = new Error(message);
  err.status = status;
  if (status === 401 && !quiet && onUnauthorized) onUnauthorized();
  return err;
}

async function getJson(path, token) {
  const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `GET ${path} failed with status ${response.status}`),
      response.status
    );
  }
  return response.json();
}

/**
 * Subjects at or below the logged-in learner's own grade, e.g.
 * [{ id, name, grade }, ...]. NEW 12 Nov 2026, multi-subject support.
 * UPDATED 15 Nov 2026 (grade-scoped visibility, ADR-026): now requires
 * a token -- the backend resolves the learner from it and filters to
 * their own grade and below, so a student can no longer see (or pick)
 * a subject from a grade ahead of their own.
 */
export function fetchSubjects(token) {
  return getJson("/subjects/", token);
}

/**
 * Topics at or below the logged-in learner's own grade, e.g.
 * [{ id, subject_id, name, caps_reference, prerequisite_id }, ...].
 * UPDATED 15 Nov 2026 (grade-scoped visibility, ADR-026): same change
 * as fetchSubjects() -- now requires a token and is grade-filtered.
 */
export function fetchTopics(token) {
  return getJson("/topics/", token);
}


/** All schools, e.g. [{ id, name }, ...] -- for the login screen's school picker. NEW 14 Nov 2026 (ADR-017). */
export function fetchSchools() {
  return getJson("/schools/");
}

/*
 * NEW 14 Nov 2026 (ADR-017, student login). Returns the backend's
 * LoginResponse: { access_token, token_type, must_change_password,
 * learner: {...}, school: {...} }.
 */
export async function login({ schoolId, studentNumber, password }) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ school_id: schoolId, student_number: studentNumber, password }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `Login failed with status ${response.status}`),
      response.status,
      { quiet: true }
    );
  }
  return response.json();
}

/**
 * NEW 14 Nov 2026 (ADR-017). Re-hydrates a stored token on page load --
 * returns { learner, school, must_change_password }, or throws if the
 * token is missing/expired/invalid (the caller should treat that as
 * "not logged in" and show the login screen again).
 */
export function fetchMe(token) {
  return getJson("/auth/me", token);
}

/** NEW 14 Nov 2026 (ADR-017). First-login (or any-time) password change. */
export async function changePassword({ token, currentPassword, newPassword }) {
  const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `Password change failed with status ${response.status}`),
      response.status,
      { quiet: true }
    );
  }
  return response.json();
}

/*
 * NEW 15 Nov 2026 (ADR-024, teacher dashboard access + bulk student
 * provisioning). Three teacher-only admin calls, all requiring a
 * teacher-role token (a student token gets a 403 from the backend).
 * Used by TeacherAdminScreen.jsx.
 */

/** This teacher's own school's students: [{ learner_id, user_id, display_name, grade, student_number, created_at }, ...]. */
export function fetchAdminStudents(token) {
  return getJson("/admin/students", token);
}

/**
 * Provisions one student. Returns the backend's StudentCreateResult,
 * including `temp_password` -- shown to the teacher exactly once, since
 * (same as provision_student() itself) this is the only point it's
 * ever visible outside the student's own head.
 */
export async function createStudent({ token, displayName, grade, studentNumber }) {
  const payload = { display_name: displayName, grade };
  if (studentNumber) payload.student_number = studentNumber;

  const response = await fetch(`${API_BASE_URL}/admin/students`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `Creating student failed with status ${response.status}`),
      response.status
    );
  }
  return response.json();
}

/**
 * Bulk-provisions students from a CSV file (columns: display_name,
 * grade, optional student_number). Returns the backend's
 * BulkStudentUploadResponse: { created: [...], errors: [{row, message}] }
 * -- a 200 with some rows in `errors` is the normal "partial success"
 * shape, not a thrown error; this only throws for a whole-file problem
 * (e.g. missing columns), which the backend reports as a 400.
 */
export async function bulkCreateStudents({ token, file }) {
  // NEW 17 Nov 2026 (code review #3): shrink big phone photos first.
  const toSend = await shrinkImageIfNeeded(file);
  const formData = new FormData();
  formData.append("file", toSend);

  const response = await fetch(`${API_BASE_URL}/admin/students/bulk`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `Bulk upload failed with status ${response.status}`),
      response.status
    );
  }
  return response.json();
}

/*
 * NEW 13 Nov 2026 (ADR-016, student file attachments). Uploads a single
 * file ahead of the message it'll go with -- the upload happens first
 * so the composer can show a preview (including any extraction_warning,
 * e.g. a scanned PDF with no text layer) before the student actually
 * sends their question. Returns the backend's AttachmentUploadResponse:
 * { id, kind, original_filename, extraction_warning }.
 *
 * FIX 14 Nov 2026 (ADR-017): takes a bearer token instead of a
 * learnerId -- the backend resolves the learner from the token now.
 */
export async function uploadAttachment(file, token) {
  if (!token) {
    throw new Error("uploadAttachment requires an auth token.");
  }

  // NEW 17 Nov 2026 (code review #3): shrink big phone photos first.
  const toSend = await shrinkImageIfNeeded(file);
  const formData = new FormData();
  formData.append("file", toSend);

  const response = await fetch(`${API_BASE_URL}/attachments/`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `Upload failed with status ${response.status}`),
      response.status
    );
  }

  return response.json();
}

export async function sendTutorMessage({ message, sessionId, topicId, attachmentIds, bookContext, token }) {
  if (!token || !topicId) {
    throw new Error("sendTutorMessage requires an auth token and a real topicId (fetch them first).");
  }

  const payload = { topic_id: topicId, message };
  if (sessionId) {
    payload.session_id = sessionId;
  }
  // NEW 13 Nov 2026 (ADR-016): ids returned by uploadAttachment() for
  // any files the student attached to this message, in the order they
  // attached them.
  if (attachmentIds && attachmentIds.length > 0) {
    payload.attachment_ids = attachmentIds;
  }
  // NEW 17 Nov 2026 (ADR-032): asking from the e-book reader. The server
  // loads the page text itself; only the highlight is sent from here.
  if (bookContext) {
    payload.book_context = {
      book_id: bookContext.bookId,
      page_number: bookContext.pageNumber,
      selected_text: bookContext.selectedText || undefined,
    };
  }

  const response = await fetch(`${API_BASE_URL}/tutor/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `Request failed with status ${response.status}`),
      response.status
    );
  }

  return response.json();
}


/*
 * NEW 15 Nov 2026 (ADR-028, assignments). Teacher-side assignment
 * authoring/scoring calls, used by the new "Assignments" tab in
 * TeacherAdminScreen.jsx, and the matching learner-side calls used by
 * a new assignments view in ChatScreen.jsx. All teacher calls require
 * a teacher-role token; all learner calls require a student-role
 * token -- same posture as the existing admin/* calls above.
 */

async function postJson(path, token, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `POST ${path} failed with status ${response.status}`),
      response.status
    );
  }
  return response.status === 204 ? null : response.json();
}

// NEW 17 Nov 2026 (code review #13): PATCH, for renaming a class.
async function patchJson(path, token, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `PATCH ${path} failed with status ${response.status}`),
      response.status
    );
  }
  return response.json();
}

/**
 * A teacher-authored question, reusable across any number of future
 * assignments. Returns the backend's CustomQuestionResult.
 */
export function createCustomQuestion({ token, topicId, text, modelAnswer }) {
  return postJson("/teach/questions", token, {
    topic_id: topicId,
    text,
    model_answer: modelAnswer,
  });
}

/**
 * Creates an assignment from a set of {questionId, marks} pairs (from
 * createCustomQuestion() above, or fetchBankQuestions() below -- a
 * reused seeded/bank question works exactly like a freshly-authored
 * one here) and a set of learner ids (from this teacher's own roster,
 * fetchAdminStudents() above). mode is "practice" (default -- AI
 * feedback shows immediately) or "test" (withheld until
 * releaseAssignmentResults() is called -- ADR-029). dueAt is an ISO
 * string or omitted. Returns the backend's AssignmentSummary.
 */
export function createAssignment({
  token,
  title,
  instructions,
  dueAt,
  mode,
  questions,
  learnerIds,
  classIds, // NEW 17 Nov 2026 (ADR-031): whole classes, expanded on the server
}) {
  const payload = {
    title,
    questions: questions.map((q) => ({ question_id: q.id, marks: q.marks })),
    learner_ids: learnerIds || [],
    class_ids: classIds || [],
  };
  if (instructions) payload.instructions = instructions;
  if (dueAt) payload.due_at = dueAt;
  if (mode) payload.mode = mode;
  return postJson("/teach/assignments", token, payload);
}

/** This teacher's own assignments: a list of AssignmentSummary. */
export function fetchTeachAssignments(token) {
  return getJson("/teach/assignments", token);
}

/**
 * One assignment's full detail, including every question (with its
 * model_answer -- this is the teacher-facing view) and a per-student
 * completion/score breakdown (AssignmentDetail).
 */
export function fetchTeachAssignment(token, assignmentId) {
  return getJson(`/teach/assignments/${assignmentId}`, token);
}

/**
 * NEW (ADR-029). Flips a Test-mode assignment's results_released
 * switch so every targeted student's withheld mark/feedback becomes
 * visible. Returns the updated AssignmentSummary.
 */
export function releaseAssignmentResults(token, assignmentId) {
  return postJson(`/teach/assignments/${assignmentId}/release`, token, {});
}

/*
 * NEW 17 Nov 2026 (ADR-030, TEACH class progress dashboard). Teacher-only
 * reads of the /api/v1/dashboard/* router (ADR-024 gated it; this is the
 * first UI to actually call it). Used by components/ProgressPanel.jsx.
 */

/** Class summary + per-learner risk/accuracy + per-topic class accuracy. `grade` optional. */
export function fetchClassProgress(token, grade, classId) {
  const params = new URLSearchParams();
  if (grade) params.set("grade", grade);
  if (classId) params.set("class_id", classId); // NEW 17 Nov 2026 (ADR-031)
  const query = params.toString() ? `?${params}` : "";
  return getJson(`/api/v1/dashboard/progress${query}`, token);
}

/** One learner's drill-down: per-topic mastery, recent misconceptions, risk assessments. */
export function fetchLearnerProgress(token, learnerId) {
  return getJson(`/api/v1/dashboard/learners/${learnerId}`, token);
}

/**
 * NEW (ADR-029). The reusable question bank for one topic -- every
 * seeded CAPS question plus this teacher's own previously-authored
 * custom ones -- so CreateAssignmentForm can offer "add an existing
 * question" alongside "write a new one".
 */
export function fetchBankQuestions(token, topicId) {
  return getJson(`/teach/questions?topic_id=${topicId}`, token);
}

/**
 * Assignments issued to the logged-in student, with a computed
 * status ("not_started" | "in_progress" | "completed") per
 * assignment: a list of LearnerAssignmentSummary.
 */
export function fetchMyAssignments(token) {
  return getJson("/assignments", token);
}

/**
 * One assignment's questions for the logged-in student -- NEVER
 * includes model_answer (app/schemas/assignments.py's
 * LearnerQuestionItem) -- plus this student's own prior answer,
 * mark, and feedback for each question already attempted.
 */
export function fetchMyAssignment(token, assignmentId) {
  return getJson(`/assignments/${assignmentId}`, token);
}

/**
 * Submits one answer to one question of one assignment. This is the
 * real submit -> AI-mark -> Attempt-write flow (ADR-028) -- returns
 * { question_id, is_correct, feedback } the moment marking completes.
 */
export function submitAssignmentAnswer({ token, assignmentId, questionId, learnerResponse }) {
  return postJson(`/assignments/${assignmentId}/questions/${questionId}/answer`, token, {
    learner_response: learnerResponse,
  });
}

/*
 * NEW 17 Nov 2026 (ADR-031, school roles and scoping). The /school/*
 * router: the logged-in staff member's scope, classes, staff, roles and
 * teaching allocations. Every check is enforced on the server; these
 * only drive what TeacherAdminScreen.jsx/SchoolPanel.jsx show.
 */

async function deleteJson(path, token) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `DELETE ${path} failed with status ${response.status}`),
      response.status
    );
  }
  return response.status === 204 ? null : response.json();
}

/** Roles, allocations and permissions of the logged-in staff member. */
export function fetchSchoolMe(token) {
  return getJson("/school/me", token);
}

export function fetchClasses(token) {
  return getJson("/school/classes", token);
}

export function fetchClassDetail(token, classId) {
  return getJson(`/school/classes/${classId}`, token);
}

export function createClass(token, { name, grade }) {
  return postJson("/school/classes", token, { name, grade: Number(grade) });
}

export function addClassMembers(token, classId, learnerIds) {
  return postJson(`/school/classes/${classId}/members`, token, { learner_ids: learnerIds });
}

export function removeClassMember(token, classId, learnerId) {
  return deleteJson(`/school/classes/${classId}/members/${learnerId}`, token);
}

export function fetchStaff(token) {
  return getJson("/school/staff", token);
}

/** Returns { user_id, display_name, staff_number, temp_password } -- password shown once. */
export function createStaff(token, { displayName, staffNumber }) {
  const body = { display_name: displayName };
  if (staffNumber) body.staff_number = staffNumber;
  return postJson("/school/staff", token, body);
}

export function grantStaffRole(token, userId, { role, subjectName, grade }) {
  const body = { role };
  if (subjectName) body.subject_name = subjectName;
  if (grade) body.grade = Number(grade);
  return postJson(`/school/staff/${userId}/roles`, token, body);
}

export function revokeStaffRole(token, roleId) {
  return deleteJson(`/school/roles/${roleId}`, token);
}

export function createAllocation(token, { teacherUserId, subjectId, classId }) {
  return postJson("/school/allocations", token, {
    teacher_user_id: teacherUserId,
    subject_id: subjectId,
    class_id: classId,
  });
}

/** NEW: several subjects x grades/classes for one teacher. items: [{ subjectId, classId|null }] */
export function createAllocationsBulk(token, teacherUserId, items) {
  return postJson("/school/allocations/bulk", token, {
    teacher_user_id: teacherUserId,
    items: items.map((i) => ({ subject_id: i.subjectId, class_id: i.classId || null })),
  });
}

export function deleteAllocation(token, allocationId) {
  return deleteJson(`/school/allocations/${allocationId}`, token);
}

/*
 * NEW 17 Nov 2026 (ADR-032, e-book library). Learners see books at or
 * below their grade; the server checks the grade on every call.
 */

export function fetchBooks(token) {
  return getJson("/books/", token);
}

export function fetchBook(token, bookId) {
  return getJson(`/books/${bookId}`, token);
}

/** { page_number, page_count, text, has_text, topic_id, topic_name, attribution } */
export function fetchBookPage(token, bookId, pageNumber) {
  return getJson(`/books/${bookId}/pages/${pageNumber}`, token);
}

/** That single page as a small PDF (ArrayBuffer), for rendering with pdf.js. */
export async function fetchBookPagePdf(token, bookId, pageNumber) {
  const response = await fetch(`${API_BASE_URL}/books/${bookId}/pages/${pageNumber}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `Page PDF failed with status ${response.status}`),
      response.status
    );
  }
  return response.arrayBuffer();
}

/** NEW (ADR-032 ePub addendum): an image inside an ePub, as a Blob (needs the auth header, so it can't be a plain <img src>). */
export async function fetchBookAsset(token, bookId, assetPath) {
  const response = await fetch(
    `${API_BASE_URL}/books/${bookId}/assets?path=${encodeURIComponent(assetPath)}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  if (!response.ok) throw httpError(`Image failed with status ${response.status}`, response.status);
  return response.blob();
}

/*
 * NEW 17 Nov 2026 (code review #13): account and year-end admin.
 */
export function resetUserPassword(token, userId) {
  return postJson(`/school/users/${userId}/reset-password`, token, {});
}

export function setUserActive(token, userId, active) {
  return postJson(`/school/users/${userId}/active`, token, { active });
}

export function promoteLearners(token, grade) {
  return postJson("/school/learners/promote", token, { grade });
}

export function renameClass(token, classId, name) {
  return patchJson(`/school/classes/${classId}`, token, { name });
}

export function deleteClass(token, classId) {
  return deleteJson(`/school/classes/${classId}`, token);
}

/*
 * NEW 19 Nov 2026 (ADR-035): learner home-language setting.
 */
export async function fetchHomeLanguages() {
  const response = await fetch(`${API_BASE_URL}/auth/home-languages`);
  if (!response.ok) throw httpError("Couldn't load languages", response.status, { quiet: true });
  return response.json();
}

export async function setHomeLanguage(token, homeLanguage) {
  const response = await fetch(`${API_BASE_URL}/auth/me/home-language`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ home_language: homeLanguage }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw httpError(formatErrorDetail(body.detail, "Couldn't save your language"), response.status);
  }
  return response.json();
}

/*
 * NEW 19 Nov 2026 (ADR-036): the teacher's Today panel.
 */
export function fetchToday(token) {
  return getJson("/teach/today", token);
}

export function createTodayPractice(token, topicId, learnerIds) {
  return postJson("/teach/today/practice", token, { topic_id: topicId, learner_ids: learnerIds });
}

/*
 * NEW 19 Nov 2026 (ADR-037): POPIA -- consent, export, delete.
 */
export function fetchConsent(token, learnerId) {
  return getJson(`/school/learners/${learnerId}/consent`, token);
}

export function recordConsent(token, learnerId, { givenByName, relationship, method }) {
  return postJson(`/school/learners/${learnerId}/consent`, token, {
    given_by_name: givenByName,
    relationship_to_learner: relationship,
    method,
  });
}

export function withdrawConsent(token, learnerId) {
  return postJson(`/school/learners/${learnerId}/consent/withdraw`, token, {});
}

export async function downloadLearnerExport(token, learnerId) {
  const response = await fetch(`${API_BASE_URL}/school/learners/${learnerId}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw httpError(formatErrorDetail(body.detail, "Export failed"), response.status);
  }
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  return { blob: await response.blob(), fileName: match ? match[1] : "thutora_learner.json" };
}

export async function deleteLearnerData(token, learnerId, confirmName) {
  const response = await fetch(`${API_BASE_URL}/school/learners/${learnerId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ confirm_name: confirmName }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw httpError(formatErrorDetail(body.detail, "Delete failed"), response.status);
  }
  return response.json();
}
