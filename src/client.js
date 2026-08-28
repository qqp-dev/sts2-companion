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
    section.append(list);
    parent.append(section);
  }
  function bodyCard(body, showRawId = false) {
    const card = el("article", "body-card");
    const heading = el("div", "body-heading");
    heading.append(el("h2", "body-name", `${body.count > 1 ? `${body.count}× ` : ""}${body.displayName}`));
    heading.append(el("div", body.hp ? "hp" : "hp unknown-field", body.hp ? `${range(body.hp)} HP` : "HP unknown"));
    card.append(heading);
    if (body.role) card.append(el("div", "role", body.role));
    if (showRawId && body.monsterId) card.append(el("div", "monster-id", body.monsterId));
    for (const flag of body.sourceFlags ?? []) card.append(el("div", "source-flag", flag));
    if (body.startsWith) card.append(el("div", "starts", `starts · ${body.startsWith}`));
    const pattern = el("div", body.pattern?.type === "unknown" || !body.pattern ? "pattern unknown-field" : "pattern");
    pattern.append(el("span", "pattern-type", body.pattern?.type === "unknown" || !body.pattern
      ? "known unknown · pattern" : body.pattern.type.replaceAll("-", " ")));
    pattern.append(document.createTextNode(` ${body.pattern?.text ?? "Pattern data is missing."}`));
    card.append(pattern);
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
    const bookLabel = `book ${book.version ?? "unknown"} · ${book.branch ?? "unknown branch"}`;
    if (!installed?.version) {
      const card = el("div", "version-card known-unknown");
      card.append(el("strong", "", "version unknown"));
      card.append(el("span", "", `${bookLabel} · installed release_info.json unreadable`));
      return card;
    }
    const installedLabel = `game ${installed.version} · ${installed.branch ?? "unknown branch"}`;
    if (version.matches === false) {
      const card = el("div", "version-card version-mismatch");
      card.append(el("strong", "", "version mismatch"));
      card.append(el("span", "", `${bookLabel} · ${installedLabel}`));
      return card;
    }
    if (version.matches === true) return null;
    const card = el("div", "version-card known-unknown");
    card.append(el("strong", "", "version unknown"));
    card.append(el("span", "", `${bookLabel} · ${installedLabel} · comparison unavailable`));
    return card;
  }
  function appendVersion(parent, version) {
    const card = versionCard(version);
    if (card) parent.append(card);
  }
  function render(state) {
    signature = JSON.stringify(state);
    root.replaceChildren();
    root.className = `state state-${state.status}`;
    if (state.status === "idle") {
      appendVersion(root, state.version);
      const idle = el("div", "idle");
      idle.append(el("p", "idle-copy", "no run / no combat · waiting for the next fight"));
      root.append(idle);
      return;
    }
    const book = state.encounter;
    const label = state.status === "combat" ? "combat" : "last";
    const header = el("header", "encounter-header");
    const status = el("div", `status-line status-${label}`);
    const dot = el("i", "status-dot");
    dot.setAttribute("aria-hidden", "true");
    status.append(dot);
    status.append(document.createTextNode(label));
    header.append(status);
    header.append(el("h1", "encounter-name", book?.name ?? state.encounterId));
    if (!book?.known && state.encounterId) header.append(el("div", "encounter-id", state.encounterId));
    const meta = [book?.act, book?.kind].filter(Boolean).join(" · ");
    header.append(el("div", "meta", meta));
    root.append(header);
    appendVersion(root, state.version);
    if (!book?.known) {
      root.append(el("div", "unknown", "No local book entry for this encounter yet. Raw encounter and monster identities are shown."));
      for (const body of book?.lineup ?? []) root.append(bodyCard({ ...body, moves: [] }, true));
      return;
    }
    const cards = el("div", "cards");
    for (const body of book.lineup) cards.append(bodyCard(body));
    root.append(cards);
    listSection(root, "death & extra rules", book.rules);
    listSection(root, "timing", book.timing);
    const source = el("footer", "source");
    const scale = book.scale;
    source.append(el("div", "scale-note", `scaling · hp & buffs ×${scale.hpAndBuff.toFixed(1)} · block ×${scale.block} · attacks unscaled`));
    source.append(el("div", "", "source values · wiki.gg · a8 hp · a9 moves · rendered for a10 / 2p"));
    root.append(source);
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
