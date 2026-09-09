import React from "react";
import { createRoot } from "react-dom/client";
import "./guide.css";
import "./client.js";
import { App } from "./App.jsx";

// Active Cache & Service Worker Purge: actively unregister all workers and purge CacheStorage
export async function purgeServiceWorkersAndCaches(
  targetNavigator = typeof navigator !== "undefined" ? navigator : null,
  targetCaches = typeof caches !== "undefined" ? caches : null
) {
  try {
    if (targetNavigator && "serviceWorker" in targetNavigator) {
      const registrations = await targetNavigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((reg) => reg.unregister()));
    }
    if (targetCaches) {
      const keys = await targetCaches.keys();
      await Promise.all(keys.map((key) => targetCaches.delete(key)));
    }
  } catch {
    // Ignore errors during purge
  }
}

purgeServiceWorkersAndCaches();

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
