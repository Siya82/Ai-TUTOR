/*
 * The main chat UI. REBUILD_SPEC.md Section 3: "ChatScreen.jsx (the
 * actual chat UI, confirmed ~11KB in the original repo) was never read
 * into any session transcript -- only its existence and role (App.jsx
 * renders it as the whole app) are known," along with a one-line
 * description of each of the four teaching modalities. This is a
 * genuine rebuild from that description, not a recovery of lost code --
 * every interaction/layout decision below is this rebuild's own,
 * documented as such in docs/BUILD_LOG.md's step 7 entry.
 *
 * UPDATED 8 Nov 2026: narrowed from four modalities to Text + Audio
 * after live testing showed Animated and Visual weren't adding
 * anything distinct over Audio -- same content, just more motion/
 * graphics around it. Audio gained proper pause/resume (not just
 * stop), specifically so a learner who'd rather read can pause
 * without losing their place. See BUILD_LOG.md.
 */

import { useEffect, useRef, useState } from "react";
import { fetchLearners, fetchTopics, sendTutorMessage } from "../api";
import { speak, stopSpeaking, pauseSpeaking, resumeSpeaking } from "../utils/tts";
import ModalitySwitcher from "./ModalitySwitcher";
import TopicPicker from "./TopicPicker";
import MarkdownMessage from "./MarkdownMessage";
import MathVerifiedBadge from "./MathVerifiedBadge";
import SymbolKeyboard from "./SymbolKeyboard";

function topicNameById(topics, id) {
  const topic = topics.find((t) => t.id === id);
  return topic ? topic.name : id;
}

// Three states instead of a play/stop boolean, since pause/resume
// (distinct from stop/cancel) is the whole point of this update: a
// learner who wants to read instead of listen pauses, rather than
// losing their place and having to replay from the start.
const PLAYBACK = { IDLE: "idle", PLAYING: "playing", PAUSED: "paused" };

function AssistantMessage({ message, topics }) {
  const { reply, modality, mathVerified, verificationWarnings, redirected, reasoningTrace, topicId, requestedTopicId } = message;
  // Lazy initial state (not a setState call inside the effect body) --
  // avoids the react-hooks/set-state-in-effect warning for what is
  // really just "this message's initial playback state depends on the
  // modality it was created with," not a derived-state update.
  const [playback, setPlayback] = useState(modality === "audio" ? PLAYBACK.PLAYING : PLAYBACK.IDLE);

  useEffect(() => {
    if (modality === "audio") {
      speak(reply, () => setPlayback(PLAYBACK.IDLE));
    }
    return () => stopSpeaking();
    // Only ever auto-speak once, right when this message is first rendered.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePlaybackClick = () => {
    if (playback === PLAYBACK.PLAYING) {
      pauseSpeaking();
      setPlayback(PLAYBACK.PAUSED);
    } else if (playback === PLAYBACK.PAUSED) {
      resumeSpeaking();
      setPlayback(PLAYBACK.PLAYING);
    } else {
      setPlayback(PLAYBACK.PLAYING);
      speak(reply, () => setPlayback(PLAYBACK.IDLE));
    }
  };

  const playbackLabel = {
    [PLAYBACK.PLAYING]: "⏸ Pause",
    [PLAYBACK.PAUSED]: "▶ Resume",
    [PLAYBACK.IDLE]: "🔊 Read aloud",
  }[playback];

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

      <MarkdownMessage text={reply} />

      {modality === "audio" && (
        <button type="button" className="speaker-toggle" onClick={handlePlaybackClick}>
          {playbackLabel}
        </button>
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
  const draftInputRef = useRef(null);

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

  // Inserts a symbol at the composer's current cursor position (or
  // replaces a selection), then restores focus/cursor there -- added
  // after live testing showed a standard keyboard has no sin/cos/tan,
  // theta, root, pi, etc., and that the right symbol set depends on
  // the topic (see SymbolKeyboard.jsx).
  const insertSymbol = (token) => {
    const el = draftInputRef.current;
    if (!el) {
      setDraft((d) => d + token);
      return;
    }
    const start = el.selectionStart ?? draft.length;
    const end = el.selectionEnd ?? draft.length;
    const next = draft.slice(0, start) + token + draft.slice(end);
    setDraft(next);
    requestAnimationFrame(() => {
      el.focus();
      const pos = start + token.length;
      el.setSelectionRange(pos, pos);
    });
  };

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

      <SymbolKeyboard
        topicName={topics.find((t) => t.id === topicId)?.name}
        onInsert={insertSymbol}
      />

      <form className="chat-screen__composer" onSubmit={handleSend}>
        <input
          ref={draftInputRef}
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
