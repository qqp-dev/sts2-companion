import React, { useEffect, useRef } from "react";

export function GuideView({ payload, encounterId, loading, error }) {
  const guideRef = useRef(null);

  useEffect(() => {
    if (!guideRef.current) return;

    if (error) {
      guideRef.current.replaceChildren();
      guideRef.current.className = "guide-state guide-state-error";
      const section = document.createElement("section");
      section.className = "empty-state";
      const h1 = document.createElement("h1");
      h1.textContent = "Error loading encounter";
      const p = document.createElement("p");
      p.className = "boundary-note";
      p.textContent = String(error.message || error);
      section.append(h1, p);
      guideRef.current.append(section);
      return;
    }

    if (loading || !payload) {
      guideRef.current.replaceChildren();
      guideRef.current.className = "guide-state guide-state-loading";
      const section = document.createElement("section");
      section.className = "empty-state";
      const h1 = document.createElement("h1");
      h1.textContent = "Loading combat guide…";
      const p = document.createElement("p");
      p.className = "quiet";
      p.textContent = "Checked static reference data is being prepared.";
      section.append(h1, p);
      guideRef.current.append(section);
      return;
    }

    if (typeof window !== "undefined" && window.__STS2_RENDER__) {
      window.__STS2_RENDER__(payload, encounterId, guideRef.current);
    }
  }, [payload, encounterId, loading, error]);

  return (
    <main
      id="guide-encounter"
      ref={guideRef}
      data-base-path=""
      className="guide-state"
    >
      <section className="empty-state">
        <h1>Loading combat guide…</h1>
        <p className="quiet">No live combat state is inferred.</p>
      </section>
    </main>
  );
}
