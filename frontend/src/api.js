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
function httpError(message, status) {
  const err = new Error(message);
  err.status = status;
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

/** All seeded subjects, e.g. [{ id, name, grade }, ...]. NEW 12 Nov 2026, multi-subject support. */
export function fetchSubjects() {
  return getJson("/subjects/");
}

/** All seeded topics, e.g. [{ id, subject_id, name, caps_reference, prerequisite_id }, ...]. */
export function fetchTopics() {
  return getJson("/topics/");
}

/**
 * All seeded learners, e.g. [{ id, display_name, grade, preferred_modality }, ...].
 * NOT used by the student chat flow since ADR-017 (a student's own
 * learner comes from login()/fetchMe() instead) -- kept for a future
 * teacher/admin dashboard that needs to list learners.
 */
export function fetchLearners() {
  return getJson("/learners/");
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
      response.status
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
      response.status
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
  const formData = new FormData();
  formData.append("file", file);

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

  const formData = new FormData();
  formData.append("file", file);

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

export async function sendTutorMessage({ message, sessionId, topicId, attachmentIds, token }) {
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
