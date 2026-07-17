/* Minimal pass-through service worker.
   Deliberately does NOT cache the shell — iOS PWAs strand users on broken
   shells for days if the SW serves stale HTML. Its only job is to satisfy the
   "installable PWA" requirement. */
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => {
  // Pass every request straight to the network. No caching.
  e.respondWith(fetch(e.request));
});
