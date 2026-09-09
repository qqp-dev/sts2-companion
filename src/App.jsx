import React, { useState, useEffect, useCallback, useMemo } from "react";
import { encounterIndex, loadEncounterView } from "./data/views.js";
import { GuideView } from "./components/GuideView.jsx";

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
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);

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

  // Filtered encounters for discreet manual search lookup
  const filteredEncounters = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return encounterIndex.filter(
      (enc) =>
        enc.title.toLowerCase().includes(q) ||
        enc.id.toLowerCase().includes(q) ||
        enc.act?.toLowerCase().includes(q) ||
        enc.tier?.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  // Determine status indicator text, class, and description
  let statusKey = "idle";
  let statusLabel = "[LIVE · Idle]";
  let statusTitle = "Live connected · waiting for combat";

  if (!isLiveMode) {
    statusKey = "manual";
    statusLabel = "[Manual]";
    statusTitle = "Manual static reference mode · click to resume LIVE";
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
        <div className="header-brand">
          <a
            href="./"
            className="site-title-link"
            onClick={(e) => {
              e.preventDefault();
              resumeLive();
            }}
          >
            <span className="site-title">StS2 Companion</span>
          </a>

          <button
            type="button"
            className={`live-pill status-${statusKey} ${isLiveMode ? "active" : "manual"}`}
            onClick={resumeLive}
            title={statusTitle}
            aria-label={statusTitle}
          >
            <span className="status-dot" />
            <span className="live-label">LIVE</span>
          </button>
        </div>

        <div className="header-search-wrap">
          <input
            type="search"
            className="header-search"
            placeholder="Search encounters…"
            value={searchQuery}
            onChange={(e) => {
              const val = e.target.value;
              setSearchQuery(val);
              const match = encounterIndex.find(
                (enc) =>
                  enc.title.toLowerCase() === val.trim().toLowerCase() ||
                  enc.id.toLowerCase() === val.trim().toLowerCase()
              );
              if (match) {
                selectEncounter(match.id);
                setSearchQuery("");
              }
            }}
            onFocus={() => setIsSearchFocused(true)}
            onBlur={() => setTimeout(() => setIsSearchFocused(false), 200)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && filteredEncounters.length > 0) {
                selectEncounter(filteredEncounters[0].id);
                setSearchQuery("");
                e.target.blur();
              } else if (e.key === "Escape") {
                setSearchQuery("");
                e.target.blur();
              }
            }}
            aria-label="Search Encounters"
          />

          {isSearchFocused && searchQuery.trim().length > 0 && filteredEncounters.length > 0 && (
            <div className="search-dropdown" role="listbox">
              {filteredEncounters.slice(0, 8).map((enc) => (
                <button
                  key={enc.id}
                  type="button"
                  className="search-dropdown-item"
                  onMouseDown={() => {
                    selectEncounter(enc.id);
                    setSearchQuery("");
                  }}
                >
                  <span className="dropdown-title">{enc.title}</span>
                  <span className="dropdown-stats">{enc.stats}</span>
                </button>
              ))}
            </div>
          )}
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
    </div>
  );
}

