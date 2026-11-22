/*
 * NEW 20 Nov 2026 (ADR-049); reworked 22 Nov 2026 as a topic induction:
 * what it's about, what to expect, what it builds on from the previous
 * grade, and two worked examples (basic, then exam style).
 * `compact` is the small link shown once a conversation has started; the
 * full card is shown on an empty chat, where a new learner lands.
 */
import { useEffect, useRef, useState } from "react";
import { PlayCircle, X } from "lucide-react";
import { mediaUrl } from "../api";

function length(seconds) {
  if (!seconds) return "";
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export default function TopicIntroVideo({ topic, compact = false }) {
  const [open, setOpen] = useState(false);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!topic?.intro_video_url) return null;
  const label = `${topic.name}: topic induction`;

  return (
    <>
      {compact ? (
        <button type="button" className="topic-video-link" onClick={() => setOpen(true)}>
          <PlayCircle size={16} aria-hidden="true" />
          Topic induction <span>{length(topic.intro_video_seconds)}</span>
        </button>
      ) : (
        <button type="button" className="topic-video-card" onClick={() => setOpen(true)}>
          <PlayCircle size={40} aria-hidden="true" />
          <span>
            <strong>Starting {topic.name}?</strong>
            <span>
              Watch the induction: what to expect, what it builds on, and two worked examples ·{" "}
              {length(topic.intro_video_seconds)}
            </span>
          </span>
        </button>
      )}
      {open && (
        <div className="topic-video-overlay" onClick={() => setOpen(false)}>
          <div
            className="topic-video-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={label}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="topic-video-dialog__head">
              <strong>{label}</strong>
              <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Close video">
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            {/* No sound track: the words are on screen (ADR-049) */}
            <video src={mediaUrl(topic.intro_video_url)} controls autoPlay playsInline preload="metadata">
              Your browser can't play this video.
            </video>
          </div>
        </div>
      )}
    </>
  );
}
