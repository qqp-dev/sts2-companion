// Self-terminating Service Worker
// Automatically purges old CacheStorage, unregisters itself, and reloads active clients

self.addEventListener("install", () => {
  // Activate immediately without waiting for old clients to close
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // 1. Delete all entries in CacheStorage
      if ("caches" in self) {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map((name) => caches.delete(name)));
      }

      // 2. Unregister this service worker
      if (self.registration) {
        await self.registration.unregister();
      }

      // 3. Take control of clients immediately
      if (self.clients && self.clients.claim) {
        await self.clients.claim();
      }

      // 4. Reload all window clients to escape the stale service worker cache
      if (self.clients && self.clients.matchAll) {
        const clients = await self.clients.matchAll({ type: "window" });
        for (const client of clients) {
          if ("navigate" in client) {
            try {
              await client.navigate(client.url);
            } catch {
              // Ignore navigation failure in background/unsupported states
            }
          }
        }
      }
    })()
  );
});

// Pass through all network requests directly to bypass any stale caching
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
