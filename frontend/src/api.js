/*
 * REBUILD NOTE (8 Nov 2026, step 7): the recovered version of this file
 * hardcoded a DEV_LEARNER_ID and a TOPIC_IDS map of specific UUIDs from
 * the original (now-gone) database -- REBUILD_SPEC.md Section 3 flagged
 * this exact problem ("Dev-environment IDs will not transfer") and
 * recommended fetching them dynamically instead. fetchTopics() and
 * fetchLearners() below do that, against the two new endpoints added
 * in this same step (backend/app/routers/topics.py, learners.py).
 */

const API_BASE_URL = "http://localhost:8000";

async function getJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with status ${response.status}`);
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

/** All seeded learners, e.g. [{ id, display_name, grade, preferred_modality }, ...]. */
export function fetchLearners() {
  return getJson("/learners/");
}

/*
 * NEW 13 Nov 2026 (ADR-016, student file attachments). Uploads a single
 * file ahead of the message it'll go with -- the upload happens first
 * so the composer can show a preview (including any extraction_warning,
 * e.g. a scanned PDF with no text layer) before the student actually
 * sends their question. Returns the backend's AttachmentUploadResponse:
 * { id, kind, original_filename, extraction_warning }.
 */
export async function uploadAttachment(file, learnerId) {
  if (!learnerId) {
    throw new Error("uploadAttachment requires a real learnerId.");
  }

  const formData = new FormData();
  formData.append("learner_id", learnerId);
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/attachments/`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Upload failed with status ${response.status}`);
  }

  return response.json();
}

export async function sendTutorMessage({ message, sessionId, learnerId, topicId, attachmentIds }) {
  if (!learnerId || !topicId) {
    throw new Error("sendTutorMessage requires a real learnerId and topicId (fetch them first).");
  }

  const payload = { learner_id: learnerId, topic_id: topicId, message };
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}
