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

export function speak(text) {
  if (!("speechSynthesis" in window)) {
    console.warn("Speech synthesis not supported in this browser.");
    return;
  }

  stopSpeaking();

  const cleanText = cleanForSpeech(text);

  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.rate = 0.95;
  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  currentUtterance = null;
}
