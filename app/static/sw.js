const CACHE_NAME = "aegispass-selfservice-v1";
const ASSETS = [
  "/login",
  "/static/css/style.css?v=3",
  "/static/js/app.js?v=3",
  "/static/brand/viseal.png",
  "/static/brand/background.png",
  "/static/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return (
        cached ||
        fetch(event.request).catch(() => {
          if (event.request.destination === "document") {
            return caches.match("/login");
          }
        })
      );
    })
  );
});
