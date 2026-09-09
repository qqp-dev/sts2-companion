import React from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";

import "./guide.css";
import "./client.js";
import { App } from "./App.jsx";

// Register Service Worker for 100% offline PWA caching
registerSW({ immediate: true });

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
