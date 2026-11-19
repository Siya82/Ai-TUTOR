/*
 * THUTOra service worker (NEW 19 Nov 2026, ADR-035: installable, low-data).
 *
 * Caches only the app itself (HTML shell, JS/CSS bundles, icons), so a learner
 * on prepaid data downloads it once and it opens instantly afterwards, even
 * on a poor connection. It deliberately never caches API responses: they
 * hold learners' personal data and must always be fresh.
 *
 * - /assets/* (hashed file names, never change): cache first.
 * - Page navigations: network first, falling back to the cached shell when
 *   offline, so the app still opens and shows its own "can't reach" message.
 */
const CACHE = "thutora-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/thutora-logo.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // the API lives on another origin: never touched

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("/", copy));
          return res;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  if (url.pathname.startsWith("/assets/") || SHELL.includes(url.pathname)) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(req, copy));
            }
            return res;
          })
      )
    );
  }
});
