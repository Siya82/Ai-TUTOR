// NEW 8 Nov 2026, step 7 -- never recovered; App.jsx existed but nothing
// actually mounted it to the DOM.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "katex/dist/katex.min.css";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);

// NEW 19 Nov 2026 (ADR-035): installable app + cached app shell (public/sw.js).
// Production builds only -- in development the service worker would serve
// stale code while you edit.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* not fatal: the app works without it */
    });
  });
}
