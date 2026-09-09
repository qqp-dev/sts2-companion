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

function getInitialLiveMode() {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    return !params.has("encounter");
  }
  return true;
}

export function App() {
  const [isLiveMode, setIsLiveMode] = useState(getInitialLiveMode);
  const [selectedId, setSelectedId] = useState(getInitialId);
  const [liveState, setLiveState] = useState(null);
  const [isOffline, setIsOffline] = useState(false);
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
        setIsLiveMode(false);
      } else if (!params.has("encounter")) {
        setIsLiveMode(true);
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

  // Poll /api/state in live mode every 1.5s (1500ms)
  useEffect(() => {
    if (!isLiveMode) return;

    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch("/api/state");
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        if (cancelled) return;
        setIsOffline(false);
        setLiveState(data);
        if (data && (data.status === "combat" || data.status === "last") && data.encounterId) {
          if (encounterIndex.some((e) => e.id === data.encounterId)) {
            setSelectedId((prev) => (prev !== data.encounterId ? data.encounterId : prev));
          }
        }
      } catch {
        if (cancelled) return;
        // Quietly degrade to offline reference mode without console errors or broken UI
        setIsOffline(true);
      }
    }

    poll();
    const interval = setInterval(poll, 1500);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isLiveMode]);

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
    setIsLiveMode(false);
    setSelectedId(id);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("encounter", id);
      window.history.pushState({}, "", url.toString());
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const resumeLive = useCallback(() => {
    setIsLiveMode(true);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.delete("encounter");
      window.history.pushState({}, "", url.pathname + (url.search ? url.search : ""));
    }
    if (liveState && (liveState.status === "combat" || liveState.status === "last") && liveState.encounterId) {
      if (encounterIndex.some((e) => e.id === liveState.encounterId)) {
        setSelectedId(liveState.encounterId);
      }
    }
  }, [liveState]);

  const switchToManual = useCallback(() => {
    setIsLiveMode(false);
    if (typeof window !== "undefined" && selectedId) {
      const url = new URL(window.location.href);
      url.searchParams.set("encounter", selectedId);
      window.history.pushState({}, "", url.toString());
    }
  }, [selectedId]);

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

  // Determine status indicator text, class, and description
  let statusKey = "idle";
  let statusLabel = "[LIVE · Idle]";
  let statusTitle = "Live connected · waiting for combat";

  if (!isLiveMode) {
    statusKey = "manual";
    statusLabel = "[Manual]";
    statusTitle = "Manual static reference mode";
  } else if (isOffline) {
    statusKey = "offline";
    statusLabel = "[Offline Reference]";
    statusTitle = "PC disconnected — offline reference mode";
  } else if (liveState?.status === "combat") {
    statusKey = "combat";
    statusLabel = "[LIVE · Combat]";
    statusTitle = `Active combat: ${liveState.encounterId}`;
  } else if (liveState?.status === "last") {
    statusKey = "last";
    statusLabel = "[LIVE · Last Fight]";
    statusTitle = `Last completed combat: ${liveState.encounterId}`;
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a href="./" onClick={(e) => { e.preventDefault(); resumeLive(); }}>
          <img src="icons/icon.svg" alt="StS2" width="20" height="20" style={{ verticalAlign: "middle" }} />
          <span>StS2 Companion</span>
        </a>

        <div className="header-controls">
          <div className="mode-pill" role="group" aria-label="Tracking mode">
            <button
              type="button"
              className={`mode-btn ${isLiveMode ? "active" : ""}`}
              onClick={resumeLive}
              aria-pressed={isLiveMode}
            >
              Live
            </button>
            <button
              type="button"
              className={`mode-btn ${!isLiveMode ? "active" : ""}`}
              onClick={switchToManual}
              aria-pressed={!isLiveMode}
            >
              Manual
            </button>
          </div>

          <span
            className={`status-indicator status-${statusKey}`}
            title={statusTitle}
            onClick={!isLiveMode ? resumeLive : switchToManual}
            role="button"
            tabIndex={0}
            style={{ cursor: "pointer" }}
          >
            <span className="status-dot"></span>
            {statusLabel}
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

