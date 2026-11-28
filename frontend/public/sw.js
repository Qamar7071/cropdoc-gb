/* CropDoc GB service worker: makes the app installable and the shell available offline.
   API calls (/api/*) are NEVER cached: predictions and history always come from the server. */
const CACHE = "cropdoc-shell-v3";
const SHELL = ["/", "/manifest.webmanifest", "/icons/logo.svg", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (event.request.mode === "navigate") {
    // network first for pages, fall back to the cached shell when offline
    event.respondWith(fetch(event.request).catch(() => caches.match("/")));
    return;
  }
  if (/^\/(assets|examples|library|icons)\//.test(url.pathname)) {
    // cache first for static files (hashed assets, example and library photos)
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ||
          fetch(event.request).then((response) => {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(event.request, copy));
            return response;
          }),
      ),
    );
  }
});
