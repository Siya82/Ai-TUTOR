/*
 * The main chat UI. REBUILD_SPEC.md Section 3: "ChatScreen.jsx (the
 * actual chat UI, confirmed ~11KB in the original repo) was never read
 * into any session transcript -- only its existence and role (App.jsx
 * renders it as the whole app) are known," along with a one-line
 * description of each of the four teaching modalities. This is a
 * genuine rebuild from that description, not a recovery of lost code --
 * every interaction/layout decision below is this rebuild's own,
 * documented as such in docs/BUILD_LOG.md's step 7 entry.
 */

import { useEffect, useRef, useState } from "react";
import { fetchLearners, fetchTopics, sendTutorMessage } from "../api";
import { speak, stopSpeaking } from "../utils/tts";
import ModalitySwitcher from "./ModalitySwitcher";
import TopicPicker from "./TopicPicker";
import MarkdownMessage from "./MarkdownMessage";
import StepReveal from "./StepReveal";
import NumberLineSVG, { extractSimplifiedInequality } from "./NumberLineSVG";
import MathVerifiedBadge from "./MathVerifiedBadge";

function topicNameById(topics, id) {
  const topic = topics.find((t) => t.id === id);
  return topic ? topic.name : id;
}

function AssistantMessage({ message, topics }) {
  const { reply, modality, mathVerified, verificationWarnings, redirected, reasoningTrace, topicId, requestedTopicId } = message;
  // Lazy initial state (not a setState call inside the effect body) --
  // avoids the react-hooks/set-state-in-effect warning for what is
  // really just "this message's initial speaking state depends on the
  // modality it was created with," not a derived-state update.
  const [speaking, setSpeaking] = useState(modality === "audio");

  useEffect(() => {
    if (modality === "audio") {
      speak(reply, () => setSpeaking(false));
    }
    return () => stopSpeaking();
    // Only ever auto-speak once, right when this message is first rendered.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleToggleSpeech = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
    } else {
      setSpeaking(true);
      speak(reply, () => setSpeaking(false));
    }
  };

  const inequalitySolution = modality === "visual" ? extractSimplifiedInequality(reply) : null;

  return (
    <div className="chat-message chat-message--assistant">
      {redirected && (
        <div className="redirect-note">
          <strong>Teaching:</strong> {topicNameById(topics, topicId)}{" "}
          <span className="redirect-note__because">
            (you asked about {topicNameById(topics, requestedTopicId)} -- a foundational gap was found first)
          </span>
          {reasoningTrace && reasoningTrace.length > 0 && (
            <details>
              <summary>Why?</summary>
              <ul>
                {reasoningTrace.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {modality === "animated" ? (
        <StepReveal text={reply} />
      ) : (
        <MarkdownMessage text={reply} />
      )}

      {modality === "audio" && (
        <button type="button" className="speaker-toggle" onClick={handleToggleSpeech}>
          {speaking ? "⏹ Stop reading" : "🔊 Read aloud"}
        </button>
      )}

      {modality === "visual" && inequalitySolution && (
        <NumberLineSVG solution={inequalitySolution} />
      )}

      <MathVerifiedBadge mathVerified={mathVerified} verificationWarnings={verificationWarnings} />
    </div>
  );
}

export default function ChatScreen() {
  const [learners, setLearners] = useState([]);
  const [topics, setTopics] = useState([]);
  const [learnerId, setLearnerId] = useState(null);
  const [topicId, setTopicId] = useState(null);
  const [modality, setModality] = useState("text");
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [sendError, setSendError] = useState(null);
  const transcriptRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const [fetchedLearners, fetchedTopics] = await Promise.all([fetchLearners(), fetchTopics()]);
        setLearners(fetchedLearners);
        setTopics(fetchedTopics);
        if (fetchedLearners.length > 0) setLearnerId(fetchedLearners[0].id);
        if (fetchedTopics.length > 0) setTopicId(fetchedTopics[0].id);
        if (fetchedLearners.length === 0 || fetchedTopics.length === 0) {
          setLoadError(
            "No seeded learners/topics found. Run backend/scripts/seed_dev_data.py against your database first."
          );
        }
      } catch (err) {
        setLoadError(`Could not reach the backend at http://localhost:8000 (${err.message}). Is uvicorn running?`);
      }
    })();
  }, []);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !learnerId || !topicId || sending) return;

    setSending(true);
    setSendError(null);
    setMessages((prev) => [...prev, { role: "user", text }]);
    setDraft("");

    try {
      const response = await sendTutorMessage({ message: text, sessionId, learnerId, topicId });
      setSessionId(response.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          reply: response.reply,
          modality,
          mathVerified: response.math_verified,
          verificationWarnings: response.verification_warnings,
          redirected: response.redirected,
          reasoningTrace: response.reasoning_trace,
          topicId: response.topic_id,
          requestedTopicId: response.requested_topic_id,
        },
      ]);
    } catch (err) {
      setSendError(err.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat-screen">
      <header className="chat-screen__header">
        <div className="chat-screen__brand">
          THUTOra<span className="chat-screen__brand-dot">.</span>
        </div>
        <ModalitySwitcher modality={modality} onChange={setModality} />
      </header>

      <div className="chat-screen__controls">
        <TopicPicker topics={topics} selectedTopicId={topicId} onChange={setTopicId} disabled={sending} />
        {learners.length > 0 && (
          <span className="chat-screen__learner">Learner: {learners.find((l) => l.id === learnerId)?.display_name}</span>
        )}
      </div>

      {loadError && <div className="chat-screen__error">{loadError}</div>}

      <div className="chat-screen__transcript" ref={transcriptRef}>
        {messages.length === 0 && !loadError && (
          <div className="chat-screen__empty">Ask a question to get started.</div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="chat-message chat-message--user">{m.text}</div>
          ) : (
            <AssistantMessage key={i} message={m} topics={topics} />
          )
        )}
        {sending && <div className="chat-message chat-message--assistant chat-message--pending">Thinking…</div>}
      </div>

      {sendError && <div className="chat-screen__error">{sendError}</div>}

      <form className="chat-screen__composer" onSubmit={handleSend}>
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask THUTOra a maths question…"
          disabled={sending || !learnerId || !topicId}
        />
        <button type="submit" disabled={sending || !draft.trim() || !learnerId || !topicId}>
          Send
        </button>
      </form>
    </div>
  );
}
