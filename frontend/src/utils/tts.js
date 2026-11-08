// Thin wrapper around the browser's built-in Web Speech API.
// No external service, no API cost -- works entirely client-side.

let currentUtterance = null;

function cleanForSpeech(text) {
  return text
    // Step dividers -> spoken transition instead of "dash dash dash"
    .replace(/\n\s*---\s*\n/g, ". Next step. ")
    .replace(/^---$/gm, ". Next step. ")
    // Markdown/LaTeX symbols that shouldn't be read literally
    .replace(/\$\$?/g, "")
    .replace(/[#*_`]/g, "")
    .replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, "$1 over $2")
    // Emoji and other pictographic symbols (checkmarks, etc.)
    .replace(/\p{Extended_Pictographic}/gu, "")
    // Collapse any extra whitespace left behind by the above
    .replace(/[ \t]+/g, " ")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

// `onEnd` (added 8 Nov 2026, step 7, backward-compatible -- every
// existing call site that only passes `text` behaves exactly as
// before) lets a caller know when speech actually finishes, instead
// of only ever reacting to its own "stop" button click.
export function speak(text, onEnd) {
  if (!("speechSynthesis" in window)) {
    console.warn("Speech synthesis not supported in this browser.");
    return;
  }

  stopSpeaking();

  const cleanText = cleanForSpeech(text);

  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.rate = 0.95;
  if (onEnd) {
    utterance.onend = onEnd;
  }
  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  currentUtterance = null;
}

// Added 8 Nov 2026: pause/resume (distinct from stop/cancel) so a
// learner can pause mid-explanation -- e.g. to read ahead at their own
// pace -- without losing their place and having to replay from the
// start. The Web Speech API supports this natively via
// speechSynthesis.pause()/resume(); cancel() (stopSpeaking, above)
// discards the utterance entirely and can't be resumed.
export function pauseSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.pause();
  }
}

export function resumeSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.resume();
  }
}
