(() => {
  "use strict";
  const root = document.getElementById("encounter");
  let signature = "";
  const basePath = root.dataset.basePath || "/sts2";

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text);
    return node;
  }
  function range(values) {
    if (!Array.isArray(values) || values.length === 0) return "?";
    return values.length === 1 ? String(values[0]) : `${values[0]}–${values[1]}`;
  }
  function listSection(parent, title, values) {
    if (!Array.isArray(values) || values.length === 0) return;
    const section = el("section", "notes");
    section.append(el("h2", "section-title", title));
    const list = el("ul");
    for (const value of values) list.append(el("li", "note", value));
    section.append(list); parent.append(section);
  }
  function bodyCard(body) {
    const card = el("article", "body-card");
    const heading = el("div", "body-heading");
    heading.append(el("h2", "body-name", `${body.count > 1 ? `${body.count}× ` : ""}${body.displayName}`));
    heading.append(el("div", body.hp ? "hp" : "hp unknown-field", body.hp ? `${range(body.hp)} HP` : "HP unknown"));
    card.append(heading);
    if (body.role) card.append(el("div", "role", body.role));
    if (body.monsterId) card.append(el("div", "monster-id", body.monsterId));
    if (body.startsWith) card.append(el("div", "starts", `Starts · ${body.startsWith}`));
    const pattern = el("div", body.pattern?.type === "unknown" || !body.pattern ? "pattern unknown-field" : "pattern");
    pattern.append(el("span", "pattern-type", body.pattern?.type === "unknown" || !body.pattern
      ? "known unknown · pattern" : body.pattern.type.replaceAll("-", " ")));
    pattern.append(document.createTextNode(` ${body.pattern?.text ?? "Pattern data is missing."}`));
    card.append(pattern);
    for (const flag of body.sourceFlags ?? []) card.append(el("div", "source-flag", flag));
    const moves = el("div", "moves");
    for (const move of body.moves ?? []) {
      const row = el("div", "move");
      const name = el("strong", "move-name", move.name);
      if (move.intent) name.append(el("small", "move-intent", move.intent));
      row.append(name);
      row.append(el("span", "move-text", move.text));
      moves.append(row);
    }
    card.append(moves);
    return card;
  }
  function versionCard(version) {
    const book = version?.book ?? {};
    const installed = version?.installed;
    const bookLabel = `Book ${book.version ?? "unknown"} · ${book.branch ?? "unknown branch"}`;
    if (!installed) {
      const card = el("div", "version-card known-unknown");
      card.append(el("strong", "", "Version unknown"));
      card.append(el("span", "", `${bookLabel} · installed release_info.json unreadable`));
      return card;
    }
    const card = el("div", `version-card ${version.matches === false ? "version-mismatch" : "version-match"}`);
    card.append(el("strong", "", version.matches === false ? "Version mismatch" : "Version match"));
    card.append(el("span", "", `${bookLabel} · Game ${installed.version ?? "unknown"} · ${installed.branch ?? "unknown branch"}`));
    return card;
  }
  function render(state) {
    signature = JSON.stringify(state);
    root.replaceChildren();
    root.className = `state state-${state.status}`;
    if (state.status === "idle") {
      root.append(versionCard(state.version));
      const idle = el("div", "idle");
      idle.append(el("div", "idle-mark", "◇"));
      idle.append(el("h1", "idle-title", "No run / no combat"));
      idle.append(el("p", "idle-copy", "Start a fight in Slay the Spire 2. This page will update automatically."));
      root.append(idle);
      return;
    }
    const book = state.encounter;
    const header = el("header", "encounter-header");
    header.append(el("div", "status-badge", state.status === "combat" ? "IN COMBAT" : "LAST COMBAT"));
    header.append(el("h1", "encounter-name", book?.name ?? state.encounterId));
    header.append(el("div", "encounter-id", state.encounterId));
    const meta = [book?.act, book?.kind, "A10 · 2 players"].filter(Boolean).join(" · ");
    header.append(el("div", "meta", meta));
    root.append(header);
    root.append(versionCard(state.version));
    if (!book?.known) {
      root.append(el("div", "unknown", "No local book entry for this encounter yet. The raw encounter identity is still shown."));
      for (const body of book?.lineup ?? []) root.append(bodyCard({ ...body, moves: [] }));
      return;
    }
    const scale = book.scale;
    root.append(el("div", "scale-note", `HP & buffs ×${scale.hpAndBuff.toFixed(1)} · Block ×${scale.block} · Attacks unscaled`));
    const cards = el("div", "cards");
    for (const body of book.lineup) cards.append(bodyCard(body));
    root.append(cards);
    listSection(root, "Death & extra rules", book.rules);
    listSection(root, "Timing", book.timing);
    root.append(el("footer", "source", "Source values: wiki.gg · A8 HP · A9 moves · rendered for A10 / 2P"));
  }
  async function poll() {
    try {
      const response = await fetch(`${basePath}/state`, { cache: "no-store" });
      if (!response.ok) return;
      const state = await response.json();
      const next = JSON.stringify(state);
      if (next !== signature) render(state);
    } catch { /* the next poll can recover */ }
  }
  window.setInterval(poll, 1500);
  poll();
})();
