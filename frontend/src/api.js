const API_BASE_URL = "http://localhost:8000";

// Seeded dev data from backend/scripts/seed_dev_data.py
export const DEV_LEARNER_ID = "6a87aa7c-9d68-41ad-9ac8-f5325aec0cf6";

// Real topic IDs, from backend/scripts/seed_dev_data.py and
// seed_additional_topics.py. Only these three are enabled in the UI
// today (see TOPICS list in ChatScreen.jsx) -- the rest of the CAPS
// Grade 10 list exists for wayfinding but has no seeded content yet.
export const TOPIC_IDS = {
  algebra: "d6f49ad0-67ad-4572-bc90-98fd6f09e6c5",
  trigonometry: "0cafa2a1-507e-4d64-b2a9-24c7273a81bf",
  functions: "77771301-c648-4b2b-a5bf-9b21e15bd6f9",
  finance: "fa3993dc-d993-4bb6-ab1b-7e3eb8113a7f",
  exponents: "6d78d964-40a6-4a85-af3e-5e6f9d64d291",
  numberPatterns: "29ac57e6-229f-4880-b5e2-f9bafd6acaaf",
  equationsInequalities: "3e81145d-dacc-4bcc-be34-d7910469f02c",
  statistics: "561ad88a-4388-4a7b-acc1-7efb45a48991",
  probability: "1babf1d1-fc42-46e8-b7eb-f50a912903b7",
  measurement: "36c1bfe3-9b18-4d20-8dc4-9043fc98edba",
};

export async function sendTutorMessage({ message, sessionId, learnerId, topicId }) {
  const payload = {
    learner_id: learnerId || DEV_LEARNER_ID,
    topic_id: topicId || TOPIC_IDS.algebra,
    message,
  };

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
