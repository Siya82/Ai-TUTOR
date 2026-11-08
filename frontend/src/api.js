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

/** All seeded topics, e.g. [{ id, name, caps_reference, prerequisite_id }, ...]. */
export function fetchTopics() {
  return getJson("/topics/");
}

/** All seeded learners, e.g. [{ id, display_name, grade, preferred_modality }, ...]. */
export function fetchLearners() {
  return getJson("/learners/");
}

export async function sendTutorMessage({ message, sessionId, learnerId, topicId }) {
  if (!learnerId || !topicId) {
    throw new Error("sendTutorMessage requires a real learnerId and topicId (fetch them first).");
  }

  const payload = { learner_id: learnerId, topic_id: topicId, message };
  if (sessionId) {
    payload.session_id = sessionId;
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
