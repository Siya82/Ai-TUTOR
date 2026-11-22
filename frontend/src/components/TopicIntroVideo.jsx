/*
 * NEW 20 Nov 2026 (ADR-049); reworked 22 Nov 2026 as a topic induction:
 * what it's about, what to expect, what it builds on from the previous
 * grade, and two worked examples (basic, then exam style).
 * `compact` is the small link shown once a conversation has started; the
 * full card is shown on an empty chat, where a new learner lands.
 */
import { useEffect, useRef, useState } from "react";
import { PlayCircle, Volume2, VolumeX, X } from "lucide-react";
import { mediaUrl } from "../api";

// The learner's voice-over choice, remembered on this device (22 Nov 2026).
// Muting loses nothing: every word is also on screen.
const VOICE_KEY = "thutora.topicVideoVoice";

function voicePreferredOff() {
  try {
    return window.localStorage.getItem(VOICE_KEY) === "off";
  } catch {
    return false; // storage blocked: default to voice on
  }
}

function rememberVoice(off) {
  try {
    window.localStorage.setItem(VOICE_KEY, off ? "off" : "on");
  } catch {
    /* not remembered, but this video still follows the switch */
  }
}

function length(seconds) {
  if (!seconds) return "";
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export default function TopicIntroVideo({ topic, compact = false }) {
  const [open, setOpen] = useState(false);
  const [muted, setMuted] = useState(voicePreferredOff);
  const closeRef = useRef(null);
  const videoRef = useRef(null);

  // keep the player in step with the switch (the muted attribute alone
  // isn't reliable after the video has loaded)
  useEffect(() => {
    if (videoRef.current) videoRef.current.muted = muted;
  }, [muted, open]);

  function setVoice(off) {
    setMuted(off);
    rememberVoice(off);
  }

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
              {topic.intro_video_narrated && (
                <button
                  type="button"
                  className="topic-video-dialog__voice"
                  aria-pressed={!muted}
                  onClick={() => setVoice(!muted)}
                  title={muted ? "Turn the voice-over on" : "Turn the voice-over off (the words stay on screen)"}
                >
                  {muted ? <VolumeX size={18} aria-hidden="true" /> : <Volume2 size={18} aria-hidden="true" />}
                  {muted ? "Voice off" : "Voice on"}
                </button>
              )}
              <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Close video">
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            {/* The words are always on screen, so the voice-over is optional (ADR-049) */}
            <video
              ref={videoRef}
              src={mediaUrl(topic.intro_video_url)}
              controls
              autoPlay
              playsInline
              preload="metadata"
              muted={muted}
              // the player's own mute button counts as the learner's choice too
              onVolumeChange={(e) => {
                if (topic.intro_video_narrated && e.currentTarget.muted !== muted) setVoice(e.currentTarget.muted);
              }}
            >
              Your browser can't play this video.
            </video>
          </div>
        </div>
      )}
    </>
  );
}
