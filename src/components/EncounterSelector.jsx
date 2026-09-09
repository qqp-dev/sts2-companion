import React, { useState, useMemo, useEffect, useRef } from "react";

export function EncounterSelector({ isOpen, onClose, onSelect, currentId, encounters }) {
  const [search, setSearch] = useState("");
  const [selectedAct, setSelectedAct] = useState("All");
  const [selectedTier, setSelectedTier] = useState("All");
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const acts = useMemo(() => {
    const set = new Set(encounters.map((e) => e.act).filter(Boolean));
    return ["All", ...Array.from(set).sort()];
  }, [encounters]);

  const tiers = useMemo(() => {
    const set = new Set(encounters.map((e) => e.tier).filter(Boolean));
    return ["All", ...Array.from(set).sort()];
  }, [encounters]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return encounters.filter((enc) => {
      if (selectedAct !== "All" && enc.act !== selectedAct) return false;
      if (selectedTier !== "All" && enc.tier !== selectedTier) return false;
      if (!q) return true;

      const titleMatch = enc.title.toLowerCase().includes(q);
      const idMatch = enc.id.toLowerCase().includes(q);
      const actMatch = enc.act?.toLowerCase().includes(q);
      const tierMatch = enc.tier?.toLowerCase().includes(q);
      const bodyMatch = enc.bodies?.some((b) => b.toLowerCase().includes(q));

      return titleMatch || idMatch || actMatch || tierMatch || bodyMatch;
    });
  }, [encounters, search, selectedAct, selectedTier]);

  if (!isOpen) return null;

  return (
    <div className="selector-overlay" onClick={onClose}>
      <div className="selector-panel" onClick={(e) => e.stopPropagation()}>
        <div className="selector-header">
          <span className="selector-title">Encounters ({filtered.length}/{encounters.length})</span>
          <button className="close-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="search-bar-wrap">
          <input
            ref={inputRef}
            type="search"
            className="search-input"
            placeholder="Search by name, ID, act, or monster…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="filter-chips-row">
          <span style={{ fontSize: "0.7rem", color: "var(--qq-muted)", alignSelf: "center", marginRight: "4px" }}>ACT:</span>
          {acts.map((act) => (
            <button
              key={act}
              className={`filter-chip ${selectedAct === act ? "active" : ""}`}
              onClick={() => setSelectedAct(act)}
            >
              {act}
            </button>
          ))}
        </div>

        <div className="filter-chips-row">
          <span style={{ fontSize: "0.7rem", color: "var(--qq-muted)", alignSelf: "center", marginRight: "4px" }}>TIER:</span>
          {tiers.map((tier) => (
            <button
              key={tier}
              className={`filter-chip ${selectedTier === tier ? "active" : ""}`}
              onClick={() => setSelectedTier(tier)}
            >
              {tier}
            </button>
          ))}
        </div>

        <div className="encounter-list" role="listbox">
          {filtered.length === 0 ? (
            <div style={{ padding: "2rem 1rem", textAlign: "center", color: "var(--qq-muted)" }}>
              No encounters match "{search}".
            </div>
          ) : (
            filtered.map((enc) => {
              const isSel = enc.id === currentId;
              const tierClass = enc.tier ? enc.tier.toLowerCase() : "";
              return (
                <button
                  key={enc.id}
                  className={`encounter-item ${isSel ? "selected" : ""}`}
                  onClick={() => {
                    onSelect(enc.id);
                    onClose();
                  }}
                  role="option"
                  aria-selected={isSel}
                >
                  <div className="encounter-item-head">
                    <span className="encounter-item-title">{enc.title}</span>
                    <span className="encounter-item-stats">{enc.stats}</span>
                  </div>
                  <div className="encounter-item-meta">
                    <span className={`tier-tag ${tierClass}`}>{enc.tier}</span>
                    <span>·</span>
                    <span className="act-tag">{enc.act}</span>
                    {enc.bodies?.length > 1 && (
                      <>
                        <span>·</span>
                        <span className="bodies-tag">{enc.bodies.join(", ")}</span>
                      </>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
