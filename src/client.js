(() => {
  "use strict";
  const root = document.getElementById("guide-encounter");
  if (!root) return;
  const basePath = root.dataset.basePath || "/sts2";
  const manualQuery = new URLSearchParams(window.location.search).getAll("encounter");
  const stateUrl = `${basePath}/state${manualQuery.length ? `?encounter=${encodeURIComponent(manualQuery[0])}` : ""}`;
  const COLLAPSED_IMPLEMENTATION_WORDS = /\b(?:formula|AST)\b|\b(?:MONSTER|POWER|CARD|ENCOUNTER)\.|\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/;
  let signature = "";

  function guideText(value) {
    const rendered = String(value ?? "");
    return COLLAPSED_IMPLEMENTATION_WORDS.test(rendered)
      ? "Checked detail is available in Technical audit."
      : rendered;
  }
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = guideText(text);
    return node;
  }
  function rawEl(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function rawValue(value) {
    if (value === null) return "null";
    if (["string", "boolean", "number"].includes(typeof value)) return String(value);
    return "";
  }
  function tree(value, label = null, depth = 0) {
    const wrap = rawEl("div", `tree depth-${Math.min(depth, 4)}`);
    if (value === null || typeof value !== "object") {
      if (label) wrap.append(rawEl("span", "tree-key", `${label}: `));
      wrap.append(rawEl("span", "tree-value", rawValue(value)));
      return wrap;
    }
    if (label) wrap.append(rawEl("div", "tree-key", label));
    if (Array.isArray(value)) value.forEach((item, index) => wrap.append(tree(item, `[${index + 1}]`, depth + 1)));
    else Object.entries(value).forEach(([key, item]) => wrap.append(tree(item, key, depth + 1)));
    return wrap;
  }
  function details(title, content, className = "detail") {
    const node = el("details", className);
    node.append(el("summary", "detail-title", title));
    node.append(content instanceof Node ? content : tree(content));
    return node;
  }
  function heading(parent, level, value, className = "") {
    const node = el(`h${level}`, className, value);
    parent.append(node);
    return node;
  }
  function section(parent, title, className = "guide-section") {
    const node = el("section", className);
    heading(node, 2, title, "section-title");
    parent.append(node);
    return node;
  }

  function renderVersionBoundary(state, parent) {
    const installed = state.observation?.installedVersion?.version;
    if (installed && state.observation.versionMatches) return;
    const warning = el("aside", "version-warning");
    warning.append(el("strong", "", installed ? "Version mismatch" : "Version unknown"));
    warning.append(el("span", "", installed
      ? `Installed ${installed} differs from checked ${state.authority.gameVersion}; mechanics are not mixed.`
      : `Installed version is unavailable; mechanics are checked for ${state.authority.gameVersion}.`));
    parent.append(warning);
  }

  function renderRoster(parent, presentation) {
    const node = section(parent, "Possible roster", "guide-section roster-section");
    node.append(el("p", "slot-count", `${presentation.roster.cardinality} initial body slot${presentation.roster.cardinality === "1" ? "" : "s"}`));
    node.append(el("p", "roster-line", presentation.roster.summary));
    node.append(el("p", "boundary-note", presentation.roster.caveat));
  }
  function renderInitialState(card, bodyView) {
    if (!bodyView.initialEffects.length) return;
    const group = el("div", "mechanic-group");
    heading(group, 4, "Starts with", "minor-title");
    bodyView.initialEffects.forEach((fact) => {
      const row = el("div", "fact-row");
      row.append(el("p", "effect-line", fact.line));
      if (fact.condition) row.append(el("p", "condition-line", `When · ${fact.condition}`));
      if (fact.unresolved) row.append(el("p", "unknown-line", `Unresolved · ${fact.unresolved}`));
      group.append(row);
    });
    card.append(group);
  }
  function renderBehavior(card, bodyView) {
    const group = el("div", "mechanic-group");
    heading(group, 4, "Opener, cycle & forks", "minor-title");
    group.append(el("p", "behavior-line", bodyView.behavior.headline));
    bodyView.behavior.paths.forEach((path) => group.append(el("p", "path-line", path)));
    card.append(group);
  }
  function renderEffects(card, bodyView) {
    if (!bodyView.effects.length) return;
    const group = el("div", "mechanic-group");
    heading(group, 4, "Effect signatures", "minor-title");
    bodyView.effects.forEach((effect) => {
      const effectCard = el("article", "effect-card");
      heading(effectCard, 5, effect.label, "effect-title");
      const list = el("ol", "effect-list");
      effect.orderedEffects.forEach((item) => list.append(el("li", "effect-line", item.line)));
      effectCard.append(list);
      group.append(effectCard);
    });
    card.append(group);
  }
  function renderBodies(parent, encounter, presentation) {
    const node = section(parent, "Enemies & forms", "guide-section enemies-section");
    presentation.bodies.forEach((bodyView) => {
      const card = el("article", "body-card");
      const head = el("div", "body-head");
      const title = el("div", "body-name-wrap");
      heading(title, 3, bodyView.name, "body-title");
      title.append(el("p", "body-role", bodyView.role));
      head.append(title, el("strong", "hp-pill", bodyView.hp));
      card.append(head);
      if (bodyView.hpHasRuntimeInputs) card.append(el("p", "condition-line", "HP condition · checked runtime state selects the value."));
      if (bodyView.forms.length) {
        const forms = el("div", "mechanic-group forms");
        heading(forms, 4, "Possible forms", "minor-title");
        bodyView.forms.forEach((form) => forms.append(el("p", "form-line", `${form.name} · ${form.hp}`)));
        card.append(forms);
      }
      renderInitialState(card, bodyView);
      renderBehavior(card, bodyView);
      renderEffects(card, bodyView);
      node.append(card);
    });
  }
  function renderProduction(parent, presentation) {
    if (!presentation.production) return;
    const node = section(parent, "Adds, hatches & summons", "guide-section production-section");
    node.append(el("p", "boundary-note", presentation.production.caveat));
    const possibilities = el("div", "chips");
    presentation.production.possibilities.forEach((name) => possibilities.append(el("span", "chip", name)));
    node.append(possibilities);
    presentation.production.rules.forEach((rule) => {
      const card = el("article", "rule-card");
      heading(card, 3, rule.owner, "rule-title");
      card.append(el("p", "effect-line", rule.cadence));
      card.append(el("p", "condition-line", `When · ${rule.condition}`));
      card.append(el("p", "clock-line", `Clock · ${rule.repeat}`));
      rule.attempts.forEach((attempt) => card.append(el("p", "pool-line", attempt)));
      node.append(card);
    });
  }
  function renderEvent(parent, presentation) {
    if (!presentation.event || !presentation.event.effects.length) return;
    const node = section(parent, "Event-fight consequences", "guide-section event-section");
    const list = el("ul", "plain-list");
    presentation.event.effects.forEach((effect) => list.append(el("li", "effect-line", effect)));
    node.append(list);
  }
  function renderLifecycle(parent, presentation) {
    if (!presentation.lifecycle.rules.length && !presentation.lifecycle.mechanics.length) return;
    const node = section(parent, "Death, phases & clocks", "guide-section lifecycle-section");
    presentation.lifecycle.rules.forEach((rule) => node.append(el("p", "lifecycle-line", rule)));
    presentation.lifecycle.mechanics.forEach((mechanic) => {
      const card = el("article", "rule-card lifecycle-card");
      heading(card, 3, mechanic.family, "rule-title");
      mechanic.branches.forEach((branch) => {
        if (branch.condition && branch.condition !== "always") card.append(el("p", "condition-line", `When · ${branch.condition}`));
        const list = el("ol", "effect-list");
        branch.effects.forEach((effect) => list.append(el("li", "effect-line", effect)));
        card.append(list);
        if (branch.repeat) card.append(el("p", "clock-line", `Clock · ${branch.repeat}`));
      });
      node.append(card);
    });
  }
  function renderUnknowns(parent, presentation) {
    const node = section(parent, "What is not observed", "guide-section unknowns-section");
    presentation.unknowns.forEach((item) => {
      const row = el("article", "unknown-row");
      heading(row, 3, item.headline, "unknown-title");
      row.append(el("p", "unknown-line", item.detail));
      node.append(row);
    });
  }
  function calloutCard(callout) {
    const card = el("article", "callout-card");
    heading(card, 3, callout.headline, "callout-title");
    card.append(el("p", "effect-line", callout.causalBasis));
    if (callout.condition) card.append(el("p", "condition-line", `When · ${callout.condition}`));
    return card;
  }
  function renderCallouts(parent, collection) {
    if (!collection.total) return;
    const node = section(parent, "Checked editorial callouts", "guide-section callouts-section");
    collection.collapsed.forEach((callout) => node.append(calloutCard(callout)));
    if (collection.hasMore) {
      const all = el("div", "all-callouts");
      collection.all.forEach((callout) => all.append(calloutCard(callout)));
      node.append(details(`Show all ${collection.total} callouts`, all, "detail callout-expander"));
    }
  }
  function renderAudit(parent, state, encounter) {
    const content = el("div", "audit-content");
    content.append(el("p", "quiet", "Exact checked records, identifiers, expressions, behavior data and evidence pointers."));
    content.append(details("Authority & observed identity", { authority: state.authority, observation: state.observation }));
    content.append(details("Exact checked encounter record", encounter));
    parent.append(details("Technical audit", content, "technical-audit"));
  }

  function render(state, nextSignature) {
    root.replaceChildren();
    root.className = `guide-state guide-state-${state.status}`;
    if (state.status !== "selected") {
      const empty = el("section", "empty-state");
      heading(empty, 1, state.status === "unresolved-observation" ? "Unsupported encounter identity" : "No encounter selected");
      empty.append(el("p", "boundary-note", state.error || state.notices?.[0] || "No encounter is available."));
      empty.append(el("p", "quiet", "Choose one checked encounter or wait for a locally observed encounter identity."));
      root.append(empty);
      signature = nextSignature;
      return;
    }
    const encounter = state.encounter, presentation = encounter.presentation;
    if (!presentation) throw new Error("guide presentation unavailable");
    const hero = el("header", "encounter-hero");
    hero.append(el("p", "eyebrow", `${presentation.context.kind} · ${presentation.context.summary}`));
    heading(hero, 1, encounter.title, "encounter-title");
    hero.append(el("p", "static-contract", "Checked static combat guide · no live turn prediction"));
    root.append(hero);
    renderVersionBoundary(state, root);
    renderRoster(root, presentation);
    renderBodies(root, encounter, presentation);
    renderProduction(root, presentation);
    renderEvent(root, presentation);
    renderLifecycle(root, presentation);
    renderUnknowns(root, presentation);
    renderCallouts(root, presentation.callouts);
    renderAudit(root, state, encounter);
    signature = nextSignature;
  }
  async function poll() {
    try {
      const response = await fetch(stateUrl, { cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) return;
      const state = await response.json();
      const next = JSON.stringify(state);
      if (next !== signature) render(state, next);
    } catch { /* Preserve the last honest guide across transient local read failures. */ }
  }
  poll();
  window.setInterval(poll, 4000);
})();
