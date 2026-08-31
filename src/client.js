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

  function identify(node, value) {
    if (value) node.id = value;
    return node;
  }
  function renderBriefing(parent, presentation) {
    const node = section(parent, "Fight briefing", "guide-section briefing-section");
    node.append(el("p", "fight-shape", presentation.briefing.fightShape));
    if (presentation.briefing.lineupCondition) node.append(el("p", "condition-line lineup-condition", presentation.briefing.lineupCondition));
    const highlights = el("div", "briefing-highlights");
    presentation.briefing.highlights.forEach((highlight) => {
      const row = el("article", `briefing-row briefing-${highlight.kind}`);
      heading(row, 3, highlight.headline, "briefing-title");
      row.append(el("p", "briefing-effect", highlight.effect));
      if (highlight.condition) row.append(el("p", "condition-line", `If / when · ${highlight.condition}`));
      if (highlight.clock) row.append(el("p", "clock-line", `Clock · ${highlight.clock}`));
      if (highlight.branch) row.append(el("p", "boundary-note", `Branch · ${highlight.branch}`));
      if (highlight.observation) row.append(el("p", "boundary-note", `Observation · ${highlight.observation}`));
      if (highlight.unresolved) row.append(el("p", "unknown-line", `Unresolved · ${highlight.unresolved}`));
      highlights.append(row);
    });
    node.append(highlights);
  }
  function renderCompactBodies(parent, presentation) {
    const node = section(parent, "Enemies at a glance", "guide-section enemy-summary-section");
    presentation.bodies.forEach((bodyView) => {
      const card = el("article", "enemy-summary-card");
      const head = el("div", "body-head");
      const title = el("div", "body-name-wrap");
      heading(title, 3, bodyView.name, "body-title");
      title.append(el("p", "body-role", bodyView.role));
      head.append(title, el("strong", "hp-meta", bodyView.hp));
      card.append(head);
      if (bodyView.forms.length > 1) {
        const forms = el("div", "compact-forms");
        bodyView.forms.forEach((form) => forms.append(el("p", "form-line", `${form.name} · ${form.hp}`)));
        card.append(forms);
      }
      if (bodyView.keyMechanics.length) {
        const mechanics = el("div", "key-mechanics");
        bodyView.keyMechanics.forEach((mechanic) => {
          const item = el("div", "key-mechanic");
          heading(item, 4, mechanic.headline, "key-title");
          item.append(el("p", "effect-line", mechanic.effect));
          if (mechanic.condition) item.append(el("p", "condition-line", `If / when · ${mechanic.condition}`));
          if (mechanic.unresolved) item.append(el("p", "unknown-line", `Unresolved · ${mechanic.unresolved}`));
          mechanics.append(item);
        });
        card.append(mechanics);
      }
      node.append(card);
    });
  }
  function renderRoster(parent, presentation) {
    const node = identify(section(parent, "Initial lineup grammar", "detail-section roster-section"), presentation.roster.detailRef);
    node.append(el("p", "slot-count", `${presentation.roster.cardinality} initial body slot${presentation.roster.cardinality === "1" ? "" : "s"}`));
    node.append(el("p", "roster-line", presentation.roster.summary));
    node.append(el("p", "boundary-note", presentation.roster.caveat));
  }
  function renderInitialState(card, bodyView) {
    if (!bodyView.initialEffects.length) return;
    const group = el("div", "mechanic-group");
    heading(group, 4, "Opening conditions", "minor-title");
    bodyView.initialEffects.forEach((fact) => {
      const row = identify(el("div", "fact-row"), fact.itemRef);
      row.append(el("p", "effect-line", fact.line));
      if (fact.condition) row.append(el("p", "condition-line", `If / when · ${fact.condition}`));
      if (fact.unresolved) row.append(el("p", "unknown-line", `Unresolved · ${fact.unresolved}`));
      group.append(row);
    });
    card.append(group);
  }
  function renderBehavior(card, bodyView) {
    const group = identify(el("div", "mechanic-group"), bodyView.behavior.itemRef);
    heading(group, 4, "Cycles & forks", "minor-title");
    group.append(el("p", "behavior-line", bodyView.behavior.headline));
    bodyView.behavior.paths.forEach((path) => group.append(el("p", "path-line", path)));
    card.append(group);
  }
  function renderEffects(card, bodyView) {
    if (!bodyView.effects.length) return;
    const group = el("div", "mechanic-group");
    heading(group, 4, "All effect signatures", "minor-title");
    bodyView.effects.forEach((effect) => {
      const effectCard = identify(el("article", "effect-card"), effect.itemRef);
      heading(effectCard, 5, effect.headline, "effect-title");
      const list = el("ol", "effect-list");
      effect.orderedEffects.forEach((item) => list.append(el("li", "effect-line", item.line)));
      effectCard.append(list);
      group.append(effectCard);
    });
    card.append(group);
  }
  function renderBodyDetails(parent, presentation) {
    const node = section(parent, "Enemy mechanics", "detail-section enemies-section");
    presentation.bodies.forEach((bodyView) => {
      const card = identify(el("article", "body-card"), bodyView.detailRef);
      const head = el("div", "body-head");
      const title = el("div", "body-name-wrap");
      heading(title, 3, bodyView.name, "body-title");
      title.append(el("p", "body-role", bodyView.role));
      head.append(title, el("strong", "hp-meta", bodyView.hp));
      card.append(head);
      if (bodyView.hpHasRuntimeInputs) card.append(el("p", "condition-line", "HP condition · checked runtime state selects the value."));
      if (bodyView.forms.length) {
        const forms = el("div", "mechanic-group forms");
        heading(forms, 4, "Possible forms", "minor-title");
        bodyView.forms.forEach((form) => forms.append(identify(el("p", "form-line", `${form.name} · ${form.hp}`), form.itemRef)));
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
    const node = identify(section(parent, "Adds, hatches & summons", "detail-section production-section"), presentation.production.detailRef);
    node.append(el("p", "boundary-note", presentation.production.caveat));
    const possibilities = el("div", "chips");
    presentation.production.possibilities.forEach((name) => possibilities.append(el("span", "chip", name)));
    node.append(possibilities);
    presentation.production.rules.forEach((rule) => {
      const card = el("article", "rule-card");
      heading(card, 3, rule.owner, "rule-title");
      card.append(el("p", "effect-line", rule.cadence));
      card.append(el("p", "condition-line", `If / when · ${rule.condition}`));
      card.append(el("p", "clock-line", `Clock · ${rule.repeat}`));
      rule.attempts.forEach((attempt) => card.append(el("p", "pool-line", attempt)));
      node.append(card);
    });
  }
  function renderEvent(parent, presentation) {
    if (!presentation.event) return;
    const node = identify(section(parent, "Event-fight consequences", "detail-section event-section"), "event-consequences");
    if (!presentation.event.effects.length) node.append(el("p", "quiet", "No checked outside-combat consequence is attached to this fight record."));
    else {
      const list = el("ul", "plain-list");
      presentation.event.effects.forEach((effect) => list.append(el("li", "effect-line", effect)));
      node.append(list);
    }
  }
  function renderLifecycle(parent, presentation) {
    if (!presentation.lifecycle.rules.length && !presentation.lifecycle.mechanics.length) return;
    const node = identify(section(parent, "Death, phases & clocks", "detail-section lifecycle-section"), "lifecycle-overview");
    presentation.lifecycle.rules.forEach((rule) => node.append(el("p", "lifecycle-line", rule)));
    presentation.lifecycle.mechanics.forEach((mechanic) => {
      const card = identify(el("article", "rule-card lifecycle-card"), mechanic.detailRef);
      heading(card, 3, mechanic.family, "rule-title");
      mechanic.branches.forEach((branch) => {
        if (branch.condition && branch.condition !== "always") card.append(el("p", "condition-line", `If / when · ${branch.condition}`));
        const list = el("ol", "effect-list");
        branch.effects.forEach((effect) => list.append(el("li", "effect-line", effect)));
        card.append(list);
        if (branch.repeat) card.append(el("p", "clock-line", `Clock · ${branch.repeat}`));
      });
      node.append(card);
    });
  }
  function renderLimitations(parent, presentation) {
    const node = identify(section(parent, "Limits & unresolved detail", "detail-section limitations-section"), "limitations");
    node.append(el("p", "boundary-note", presentation.limitations.observation));
    presentation.limitations.unknowns.forEach((item) => {
      const row = el("article", "unknown-row");
      heading(row, 3, item.headline, "unknown-title");
      row.append(el("p", "unknown-line", item.detail));
      node.append(row);
    });
  }
  function renderFightDetails(parent, presentation) {
    const content = el("div", "fight-detail-content");
    renderRoster(content, presentation);
    renderBodyDetails(content, presentation);
    renderProduction(content, presentation);
    renderEvent(content, presentation);
    renderLifecycle(content, presentation);
    renderLimitations(content, presentation);
    const disclosure = details("Fight details", content, "fight-details");
    disclosure.id = "fight-details";
    parent.append(disclosure);
  }
  function calloutCard(callout) {
    const card = el("article", "callout-card");
    heading(card, 3, callout.headline, "callout-title");
    card.append(el("p", "effect-line", callout.causalBasis));
    if (callout.condition) card.append(el("p", "condition-line", `If / when · ${callout.condition}`));
    return card;
  }
  function renderCallouts(parent, collection) {
    if (!collection.total) return;
    const node = identify(section(parent, "What changes the fight", "guide-section callouts-section"), "player-notes");
    collection.collapsed.forEach((callout) => node.append(calloutCard(callout)));
    if (collection.hasMore) {
      const all = el("div", "all-callouts");
      collection.all.forEach((callout) => all.append(calloutCard(callout)));
      node.append(details(`Show all ${collection.total} notes`, all, "detail callout-expander"));
    }
  }

  function renderAudit(parent, state, encounter) {
    const content = el("div", "audit-content");
    content.append(el("p", "quiet", "Exact checked records, identifiers, expressions, behavior data and evidence pointers."));
    content.append(details("Authority & observed identity", { authority: state.authority, observation: state.observation }));
    content.append(details("Exact checked encounter record", encounter));
    const disclosure = details("Technical audit", content, "technical-audit");
    disclosure.id = "technical-audit";
    parent.append(disclosure);
  }

  function render(state, nextSignature) {
    root.replaceChildren();
    root.className = `guide-state guide-state-${state.status}`;
    if (state.status !== "selected") {
      const empty = el("section", "empty-state");
      heading(empty, 1, state.status === "unresolved-observation" ? "Unsupported encounter identity" : "No encounter selected");
      empty.append(rawEl("p", "boundary-note", state.error || state.notices?.[0] || "No encounter is available."));
      empty.append(el("p", "quiet", "Choose one checked encounter or wait for a locally observed encounter identity."));
      root.append(empty);
      signature = nextSignature;
      return;
    }
    const encounter = state.encounter, presentation = encounter.presentation;
    if (!presentation) throw new Error("guide presentation unavailable");
    const hero = el("header", "encounter-capsule");
    hero.append(el("p", "eyebrow", `${presentation.context.kind} · ${presentation.context.summary}`));
    heading(hero, 1, encounter.title, "encounter-title");
    hero.append(el("p", "static-contract", "Static guide · encounter identity only, not a live turn"));
    root.append(hero);
    renderVersionBoundary(state, root);
    renderBriefing(root, presentation);
    renderCallouts(root, presentation.callouts);
    renderCompactBodies(root, presentation);
    renderFightDetails(root, presentation);
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
