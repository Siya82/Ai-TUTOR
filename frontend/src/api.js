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
/*
 * NEW 19 Nov 2026 (code review 19 Nov #5, #9). Tokens are renewed every 30
 * minutes (and replaced when a password changes) WITHOUT re-rendering the
 * app: screens keep passing the token they were given at login, and every
 * request swaps in the newest token issued in its place.
 */
const renewedTokens = new Map();
export function liveToken(token) {
  let t = token;
  for (let i = 0; i < 50 && renewedTokens.has(t); i += 1) t = renewedTokens.get(t);
  return t;
}
let tokenRenewedHandler = null;
export function setTokenRenewedHandler(handler) {
  tokenRenewedHandler = handler;
}
export function replaceToken(oldToken, newToken) {
  if (oldToken && newToken && oldToken !== newToken) {
    renewedTokens.set(liveToken(oldToken), newToken);
    tokenRenewedHandler?.(newToken); // App keeps it for the next page load
  }
}

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
  const headers = token ? { Authorization: `Bearer ${liveToken(token)}` } : undefined;
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

// NEW 19 Nov 2026 (code review 19 Nov #12): search instead of one huge list
export async function searchSchools(q) {
  const response = await fetch(`${API_BASE_URL}/schools/?q=${encodeURIComponent(q)}`);
  if (!response.ok) throw httpError(`Couldn't search schools (${response.status})`, response.status, { quiet: true });
  return response.json();
}
export async function fetchSchool(id) {
  const response = await fetch(`${API_BASE_URL}/schools/${id}`);
  return response.ok ? response.json() : null;
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
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { Authorization: `Bearer ${liveToken(token)}` },
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
    { headers: { Authorization: `Bearer ${liveToken(token)}` } }
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
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { Authorization: `Bearer ${liveToken(token)}` },
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
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${liveToken(token)}` },
    body: JSON.stringify({ confirm_name: confirmName }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw httpError(formatErrorDetail(body.detail, "Delete failed"), response.status);
  }
  return response.json();
}

/*
 * NEW 19 Nov 2026 (ADR-038): CONNECT -- parents, and school notices.
 */
export function fetchMyChildren(token) {
  return getJson("/parent/children", token);
}
export function fetchChildOverview(token, learnerId) {
  return getJson(`/parent/children/${learnerId}/overview`, token);
}
export function fetchChildSummary(token, learnerId, lang) {
  return getJson(`/parent/children/${learnerId}/summary?lang=${encodeURIComponent(lang)}`, token);
}
export function fetchParentNotices(token) {
  return getJson("/parent/notices", token);
}
export function acknowledgeNotice(token, noticeId) {
  return postJson(`/parent/notices/${noticeId}/ack`, token, {});
}
export function fetchLearnerParents(token, learnerId) {
  return getJson(`/school/learners/${learnerId}/parents`, token);
}
export function addLearnerParent(token, learnerId, body) {
  return postJson(`/school/learners/${learnerId}/parents`, token, body);
}
export function removeLearnerParent(token, learnerId, parentUserId) {
  return deleteJson(`/school/learners/${learnerId}/parents/${parentUserId}`, token);
}
export function fetchSchoolNotices(token) {
  return getJson("/school/notices", token);
}
export function postSchoolNotice(token, body) {
  return postJson("/school/notices", token, body);
}
export function deleteSchoolNotice(token, noticeId) {
  return deleteJson(`/school/notices/${noticeId}`, token);
}

/*
 * NEW 19 Nov 2026 (ADR-039): INSIGHTS for circuit/district officials.
 */
export function fetchInsightsScope(token) {
  return getJson("/insights/scope", token);
}
export function fetchInsightsOverview(token, circuitId) {
  return getJson(`/insights/overview${circuitId ? `?circuit_id=${circuitId}` : ""}`, token);
}
export function fetchInsightsSchool(token, schoolId) {
  return getJson(`/insights/schools/${schoolId}`, token);
}

// NEW 19 Nov 2026 (ADR-041): the textbook chapter(s) linked to a topic.
export function fetchChaptersForTopic(token, topicId) {
  return getJson(`/books/for-topic/${topicId}`, token);
}

/*
 * NEW 19 Nov 2026 (ADR-043): guardian contacts, parent self-sign-up by
 * cellphone (only for numbers on the school's records), and viewers
 * (e.g. a grandparent) invited by a parent/guardian.
 */
async function sendJson(method, path, token, body) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${liveToken(token)}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: JSON.stringify(body) });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw httpError(
      formatErrorDetail(errorBody.detail, `${method} ${path} failed with status ${response.status}`),
      response.status,
      { quiet: !token }
    );
  }
  return response.status === 204 ? null : response.json();
}
export function fetchGuardians(token, learnerId) {
  return getJson(`/school/learners/${learnerId}/guardians`, token);
}
export function addGuardian(token, learnerId, body) {
  return sendJson("POST", `/school/learners/${learnerId}/guardians`, token, body);
}
export function updateGuardian(token, learnerId, guardianId, body) {
  return sendJson("PUT", `/school/learners/${learnerId}/guardians/${guardianId}`, token, body);
}
export function removeGuardian(token, learnerId, guardianId) {
  return deleteJson(`/school/learners/${learnerId}/guardians/${guardianId}`, token);
}
export async function fetchSignupAvailable(schoolId) {
  const q = schoolId ? `?school_id=${encodeURIComponent(schoolId)}` : "";
  const response = await fetch(`${API_BASE_URL}/connect/signup/available${q}`);
  if (!response.ok) return { enabled: false };
  return response.json();
}
export function startParentSignup(schoolId, cellphone) {
  return sendJson("POST", "/connect/signup/start", null, { school_id: schoolId, cellphone });
}
export function verifyParentSignup({ schoolId, cellphone, code, password, fullName }) {
  return sendJson("POST", "/connect/signup/verify", null, {
    school_id: schoolId,
    cellphone,
    code,
    password,
    full_name: fullName || null,
  });
}
export function redeemViewerInvite({ schoolId, code, password }) {
  return sendJson("POST", "/connect/viewer/redeem", null, { school_id: schoolId, code, password });
}
export function fetchViewers(token, learnerId) {
  return getJson(`/parent/children/${learnerId}/viewers`, token);
}
export function inviteViewer(token, learnerId, { viewerName, relationship }) {
  return sendJson("POST", `/parent/children/${learnerId}/viewers/invite`, token, {
    viewer_name: viewerName,
    relationship,
  });
}
export function removeViewer(token, learnerId, viewerUserId) {
  return deleteJson(`/parent/children/${learnerId}/viewers/${viewerUserId}`, token);
}

/*
 * NEW 19 Nov 2026 (ADR-044): THUTOra ADMIN -- school overview, profile and
 * settings, and the public "Register your school" request.
 */
export function fetchSchoolOverview(token) {
  return getJson("/school/overview", token);
}
export function fetchSchoolProfile(token) {
  return getJson("/school/profile", token);
}
export function saveSchoolProfile(token, body) {
  return sendJson("PUT", "/school/profile", token, body);
}
export async function fetchRegistrationOptions() {
  const response = await fetch(`${API_BASE_URL}/schools/registrations/options`);
  return response.ok ? response.json() : { provinces: [], roles: [] };
}
export function registerSchool(body) {
  return sendJson("POST", "/schools/registrations", null, body);
}

/*
 * NEW 19 Nov 2026 (code review 19 Nov #2, #7): look at a learner's answers,
 * correct a mark; edit / close / duplicate / delete an assignment.
 */
export function fetchLearnerAnswers(token, assignmentId, learnerId) {
  return getJson(`/teach/assignments/${assignmentId}/learners/${learnerId}/answers`, token);
}
export function overrideMark(token, assignmentId, attemptId, isCorrect, note) {
  return sendJson("POST", `/teach/assignments/${assignmentId}/attempts/${attemptId}/mark`, token, {
    is_correct: isCorrect,
    note: note || null,
  });
}
export function editAssignment(token, assignmentId, { title, instructions, dueAt }) {
  return sendJson("PATCH", `/teach/assignments/${assignmentId}`, token, {
    title,
    instructions: instructions || null,
    due_at: dueAt ? new Date(dueAt).toISOString() : null,
  });
}
export function closeAssignment(token, assignmentId, reopen = false) {
  return sendJson("POST", `/teach/assignments/${assignmentId}/close${reopen ? "?reopen=true" : ""}`, token, {});
}
export function duplicateAssignment(token, assignmentId) {
  return sendJson("POST", `/teach/assignments/${assignmentId}/duplicate`, token, {});
}
export function deleteAssignment(token, assignmentId) {
  return deleteJson(`/teach/assignments/${assignmentId}`, token);
}

// NEW 19 Nov 2026 (code review 19 Nov #5): renew a still-valid login.
export async function refreshToken(token) {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${liveToken(token)}` },
  });
  if (!response.ok) throw httpError("Session expired", response.status, { quiet: true });
  const { access_token: fresh } = await response.json();
  replaceToken(token, fresh);
  return fresh;
}

// NEW 19 Nov 2026 (code review 19 Nov #3, #5, #6): learner usage, history, progress
export function fetchTutorUsage(token) {
  return getJson("/tutor/usage", token);
}
export function fetchTutorSessions(token) {
  return getJson("/tutor/sessions", token);
}
export function fetchTutorSessionMessages(token, sessionId) {
  return getJson(`/tutor/sessions/${sessionId}/messages`, token);
}
export function fetchMyProgress(token) {
  return getJson("/me/progress", token);
}

// NEW 19 Nov 2026 (code review 19 Nov #8, #11)
export function editPerson(token, userId, body) {
  return sendJson("PATCH", `/school/users/${userId}`, token, body);
}
export function fetchAuditTrail(token) {
  return getJson("/school/audit", token);
}
