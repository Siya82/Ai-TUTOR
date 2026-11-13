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
 *
 * UPDATED 13 Nov 2026 (ADR-016, student file attachments): a student
 * can now attach a photo, PDF, or Word document to a question -- via
 * the paperclip button, drag-and-drop onto the composer, or (images
 * only -- a browser paste event only ever carries a real file for an
 * image, never a PDF/docx) pasting straight into the text box. Each
 * file uploads immediately via POST /attachments so its preview chip
 * (and any extraction_warning, e.g. a scanned PDF with no text layer)
 * shows before the student actually sends their question.
 */

import { useEffect, useRef, useState } from "react";
import { fetchLearners, fetchSubjects, fetchTopics, sendTutorMessage, uploadAttachment } from "../api";
import { speak, stopSpeaking, pauseSpeaking, resumeSpeaking } from "../utils/tts";
import ModalitySwitcher from "./ModalitySwitcher";
import SubjectPicker from "./SubjectPicker";
import TopicPicker from "./TopicPicker";
import MarkdownMessage from "./MarkdownMessage";
import MathVerifiedBadge from "./MathVerifiedBadge";
import SymbolKeyboard from "./SymbolKeyboard";

function topicNameById(topics, id) {
  const topic = topics.find((t) => t.id === id);
  return topic ? topic.name : id;
}

function subjectNameById(subjects, id) {
  const subject = subjects.find((s) => s.id === id);
  return subject ? subject.name : null;
}

// Three states instead of a play/stop boolean, since pause/resume
// (distinct from stop/cancel) is the whole point of this update: a
// learner who wants to read instead of listen pauses, rather than
// losing their place and having to replay from the start.
const PLAYBACK = { IDLE: "idle", PLAYING: "playing", PAUSED: "paused" };

// NEW 13 Nov 2026 (ADR-016). Mirrors the accept list the attach button
// and drop zone both use -- kept in one place rather than repeated.
const ACCEPTED_ATTACHMENT_TYPES =
  "image/png,image/jpeg,image/jpg,image/webp,image/gif,application/pdf,.docx";

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
    [PLAXBACK.PAUSED]: "▶ Resume",
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

// NEW 13 Nov 2026 (ADR-016). Small badge text per attachment kind, used
// both in the pending-attachment chips and on a sent user message.
const ATTACHMENT_KIND_LABEL = { image: "Image", pdf: "PDF", docx: "Word" };

function AttachmentChip({ attachment, onRemove }) {
  const { original_filename, kind, uploading, error, extraction_warning } = attachment;
  return (
    <div
      className={
        "attachment-chip" +
        (error ? " attachment-chip--error" : "") +
        (extraction_warning ? " attachment-chip--warning" : "")
      }
    >
      <span className="attachment-chip__name">
        {uploading ? "Uploading…" : ATTACHMENT_KIND_LABEL[kind] ? `${ATTACHMENT_KIND_LABEL[kind]}: ` : ""}
        {original_filename}
      </span>
      {error && <span className="attachment-chip__detail">{error}</span>}
      {extraction_warning && !error && <span className="attachment-chip__detail">{extraction_warning}</span>}
      {onRemove && (
        <button type="button" className="attachment-chip__remove" onClick={onRemove} aria-label={`Remove ${original_filename}`}>
          ×
        </button>
      )}
    </div>
  );
}

export default function ChatScreen() {
  const [learners, setLearners] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [topics, setTopics] = useState([]);
  const [learnerId, setLearnerId] = useState(null);
  const [subjectId, setSubjectId] = useState(null);
  const [topicId, setTopicId] = useState(null);
  const [modality, setModality] = useState("text");
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [sendError, setSendError] = useState(null);
  // NEW 13 Nov 2026 (ADR-016): files attached to the question currently
  // being composed -- each entry starts as { tempId, original_filename,
  // uploading: true } and is filled in with the backend's { id, kind,
  // extraction_warning } once POST /attachments returns, or { error }
  // if the upload failed.
  const [pendingAttachments, setPendingAttachments] = useState([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const transcriptRef = useRef(null);
  const draftInputRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const [fetchedLearners, fetchedSubjects, fetchedTopics] = await Promise.all([
          fetchLearners(),
          fetchSubjects(),
          fetchTopics(),
        ]);
        setLearners(fetchedLearners);
        setSubjects(fetchedSubjects);
        setTopics(fetchedTopics);
        if (fetchedLearners.length > 0) setLearnerId(fetchedLearners[0].id);
        // Default to Pure Mathematics, Grade 10 specifically when it's seeded,
        // rather than whichever subject happens to sort first alphabetically
        // (NEW 12 Nov 2026, multi-subject support -- keeps the existing
        // default experience for the one subject that was already live
        // before Physical Sciences). UPDATED 13 Nov 2026: Grade 11 Pure
        // Mathematics now shares the same name, so matching on name alone
        // was no longer specific enough to guarantee landing on Grade 10 --
        // now matches both name AND grade explicitly.
        if (fetchedSubjects.length > 0) {
          const defaultSubject =
            fetchedSubjects.find((s) => s.name === "Pure Mathematics" && s.grade === 10) ||
            fetchedSubjects[0];
          setSubjectId(defaultSubject.id);
          const firstTopicForSubject = fetchedTopics.find((t) => t.subject_id === defaultSubject.id);
          if (firstTopicForSubject) setTopicId(firstTopicForSubject.id);
        }
        if (fetchedLearners.length === 0 || fetchedSubjects.length === 0 || fetchedTopics.length === 0) {
          setLoadError(
            "No seeded learners/subjects/topics found. Run backend/scripts/seed_dev_data.py against your database first."
          );
        }
      } catch (err) {
        setLoadError(`Could not reach the backend at http://localhost:8000 (${err.message}). Is uvicorn running?`);
      }
    })();
  }, []);

  // When the subject changes, jump the topic to the first one in that
  // subject instead of leaving a stale topic from the previous subject
  // selected (NEW 12 Nov 2026, multi-subject support).
  const topicsForSubject = topics.filter((t) => t.subject_id === subjectId);

  const handleSubjectChange = (newSubjectId) => {
    setSubjectId(newSubjectId);
    const firstTopic = topics.find((t) => t.subject_id === newSubjectId);
    setTopicId(firstTopic ? firstTopic.id : null);
  };

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

  // NEW 13 Nov 2026 (ADR-016). Shared by the paperclip button's file
  // input, drag-and-drop onto the composer, and clipboard image paste.
  // Uploads each file immediately so its chip (and extraction_warning)
  // shows before the student sends their question -- the ADR's
  // "upload happens before the message" persistence model.
  const handleFilesSelected = (fileList) => {
    const files = Array.from(fileList || []);
    if (files.length === 0 || !learnerId) return;

    files.forEach((file) => {
      const tempId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      setPendingAttachments((prev) => [
        ...prev,
        { tempId, original_filename: file.name, uploading: true },
      ]);

      uploadAttachment(file, learnerId)
        .then((result) => {
          setPendingAttachments((prev) =>
            prev.map((a) => (a.tempId === tempId ? { ...a, ...result, uploading: false } : a))
          );
        })
        .catch((err) => {
          setPendingAttachments((prev) =>
            prev.map((a) => (a.tempId === tempId ? { ...a, uploading: false, error: err.message } : a))
          );
        });
    });
  };

  const removePendingAttachment = (tempId) => {
    setPendingAttachments((prev) => prev.filter((a) => a.tempId !== tempId));
  };

  const handleAttachButtonClick = () => fileInputRef.current?.click();

  const handleFileInputChange = (e) => {
    handleFilesSelected(e.target.files);
    e.target.value = ""; // allow re-selecting the same file name later
  };

  const handleComposerDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleComposerDragLeave = () => setIsDragOver(false);

  const handleComposerDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFilesSelected(e.dataTransfer.files);
  };

  // A browser only ever puts a real file on a paste event for an image
  // -- a PDF or .docx can't be pasted from the OS clipboard this way,
  // it always needs the file picker or drag-and-drop above (ADR-016).
  // Ordinary text paste is untouched: this only fires handleFilesSelected
  // when the clipboard actually carried a file.
  const handleDraftPaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const files = [];
    for (const item of items) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length > 0) {
      handleFilesSelected(files);
    }
  };

  const attachmentsUploading = pendingAttachments.some((a) => a.uploading);
  const readyAttachments = pendingAttachments.filter((a) => a.id && !a.error);

  const handleSend = async (e) => {
    e.preventDefalt();
    const text = draft.trim();
    if ((!text && readyAttachments.length === 0) || !learnerId || !topicId || sending || attachmentsUploading) {
      return;
    }

    setSending(true);
    setSendError(null);
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text,
        attachments: readyAttachments.map((a) => ({ original_filename: a.original_filename, kind: a.kind })),
      },
    ]);
    setDraft("");
    const attachmentIds = readyAttachments.map((a) => a.id);
    setPendingAttachments([]);

    try {
      const response = await sendTutorMessage({ message: text, sessionId, learnerId, topicId, attachmentIds });
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
        <SubjectPicker
          subjects={subjects}
          selectedSubjectId={subjectId}
          onChange={handleSubjectChange}
          disabled={sending}
        />
        <TopicPicker topics={topicsForSubject} selectedTopicId={topicId} onChange={setTopicId} disabled={sending} />
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
            <div key={i} className="chat-message chat-message--user">
              {m.attachments && m.attachments.length > 0 && (
                <div className="attachment-chip-row attachment-chip-row--sent">
                  {m.attachments.map((a, j) => (
                    <AttachmentChip key={j} attachment={a} />
                  ))}
                </div>
              )}
              {m.text}
            </div>
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

      {pendingAttachments.length > 0 && (
        <div className="attachment-chip-row">
          {pendingAttachments.map((a) => (
            <AttachmentChip key={a.tempId} attachment={a} onRemove={() => removePendingAttachment(a.tempId)} />
          ))}
        </div>
      )}

      <form
        className={"chat-screen__composer" + (isDragOver ? " chat-screen__composer--dragover" : "")}
        onSubmit={handleSend}
        onDragOver={handleComposerDragOver}
        onDragLeave={handleComposerDragLeave}
        onDrop={handleComposerDrop}
      >
        <input
          type="file"
          ref={fileInputRef}
          className="chat-screen__file-input"
          multiple
          accept={ACCEPTED_ATTACHMENT_TYPES}
          onChange={handleFileInputChange}
        />
        <button
          type="button"
          className="chat-screen__attach-button"
          onClick={handleAttachButtonClick}
          disabled={sending || !learnerId}
          title="Attach a photo, PDF, or Word document"
          aria-label="Attach a file"
        >
          📎
        </button>
        <input
          ref={draftInputRef}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPaste={handleDraftPaste}
          placeholder={
            subjectNameById(subjects, subjectId)
              ? `Ask THUTOra a ${subjectNameById(subjects, subjectId)} question… (or attach/paste a photo of your work)`
              : "Ask THUTOra a question…"
          }
          disabled={sending || !learnerId || !topicId}
        />
        <button
          type="submit"
          disabled={
            sending ||
            attachmentsUploading ||
            (!draft.trim() && readyAttachments.length === 0) ||
            !learnerId ||
            !topicId
          }
        >
          Send
        </button>
      </form>
    </div>
  );
}
