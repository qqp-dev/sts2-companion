import React, { useState, useEffect, useCallback } from "react";
import { encounterIndex, loadEncounterView } from "./data/views.js";
import { GuideView } from "./components/GuideView.jsx";
import { EncounterSelector } from "./components/EncounterSelector.jsx";

const DEFAULT_ENCOUNTER_ID = "CEREMONIAL_BEAST_BOSS";

function getInitialId() {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const queryId = params.get("encounter");
    if (queryId && encounterIndex.some((e) => e.id === queryId)) {
      return queryId;
    }
  }
  return DEFAULT_ENCOUNTER_ID;
}

export function App() {
  const [selectedId, setSelectedId] = useState(getInitialId);
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isOfflineReady, setIsOfflineReady] = useState(false);

  // Sync with URL popstate (browser back/forward)
  useEffect(() => {
    function handlePopState() {
      const params = new URLSearchParams(window.location.search);
      const queryId = params.get("encounter");
      if (queryId && encounterIndex.some((e) => e.id === queryId)) {
        setSelectedId(queryId);
      }
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // Check service worker offline ready
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.ready.then(() => setIsOfflineReady(true));
    }
  }, []);

  // Load encounter payload whenever selectedId changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    loadEncounterView(selectedId)
      .then((data) => {
        if (!cancelled) {
          setPayload(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const selectEncounter = useCallback((id) => {
    setSelectedId(id);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("encounter", id);
      window.history.pushState({}, "", url.toString());
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  // Quick navigation helpers
  const currentIndex = encounterIndex.findIndex((e) => e.id === selectedId);

  const prevEncounter = () => {
    const prevIdx = (currentIndex - 1 + encounterIndex.length) % encounterIndex.length;
    selectEncounter(encounterIndex[prevIdx].id);
  };

  const nextEncounter = () => {
    const nextIdx = (currentIndex + 1) % encounterIndex.length;
    selectEncounter(encounterIndex[nextIdx].id);
  };

  const randomEncounter = () => {
    let randIdx = Math.floor(Math.random() * encounterIndex.length);
    if (randIdx === currentIndex && encounterIndex.length > 1) {
      randIdx = (randIdx + 1) % encounterIndex.length;
    }
    selectEncounter(encounterIndex[randIdx].id);
  };

  const currentMeta = encounterIndex[currentIndex] || { title: selectedId, act: "", tier: "" };

  return (
    <div className="app-shell">
      <header className="site-header">
        <a href="./" onClick={(e) => { e.preventDefault(); selectEncounter(DEFAULT_ENCOUNTER_ID); }}>
          <img src="icons/icon.svg" alt="StS2" width="20" height="20" style={{ verticalAlign: "middle" }} />
          <span>StS2 Companion</span>
        </a>

        <div className="header-controls">
          <span className="offline-badge" title="All 89 checked encounters are stored locally in the browser">
            <span className="offline-dot"></span>
            Offline PWA
          </span>

          <button
            className="search-trigger-btn"
            onClick={() => setIsSelectorOpen(true)}
            aria-label="Search Encounters"
          >
            🔍 Encounters ({encounterIndex.length})
          </button>
        </div>
      </header>

      <div className="guide-shell">
        <GuideView
          payload={payload}
          encounterId={selectedId}
          loading={loading}
          error={error}
        />
      </div>

      <nav className="bottom-nav" aria-label="Quick Encounter Navigation">
        <button className="nav-btn" onClick={prevEncounter} aria-label="Previous Encounter">
          ‹ Prev
        </button>
        <div className="nav-center">
          <span style={{ color: "var(--qq-accent)", fontWeight: 700 }}>{currentIndex + 1}</span>
          <span style={{ color: "var(--qq-muted)" }}> / {encounterIndex.length}</span>
        </div>
        <button className="nav-btn" onClick={randomEncounter} aria-label="Random Encounter">
          🎲 Random
        </button>
        <button className="nav-btn" onClick={nextEncounter} aria-label="Next Encounter">
          Next ›
        </button>
      </nav>

      <EncounterSelector
        isOpen={isSelectorOpen}
        onClose={() => setIsSelectorOpen(false)}
        onSelect={selectEncounter}
        currentId={selectedId}
        encounters={encounterIndex}
      />
    </div>
  );
}
