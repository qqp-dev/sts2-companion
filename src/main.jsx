import React from "react";
import { createRoot } from "react-dom/client";
import "./guide.css";
import "./client.js";
import { App } from "./App.jsx";

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
