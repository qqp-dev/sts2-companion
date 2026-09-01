(() => {
  "use strict";
  const root = document.getElementById("guide-encounter");
  if (!root) return;
  const basePath = root.dataset.basePath || "/sts2";
  const manualQuery = new URLSearchParams(window.location.search).getAll("encounter");
  const stateUrl = `${basePath}/state${manualQuery.length ? `?encounter=${encodeURIComponent(manualQuery[0])}` : ""}`;
  const COLLAPSED_IMPLEMENTATION_WORDS = /\b(?:formula|AST)\b|\b(?:MONSTER|POWER|CARD|ENCOUNTER|SOURCE|RUNTIME)\.|\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/;
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

  function selectionLabel(state, encounter) {
    if (state.mode === "manual-reference") return "Manual · Static reference";
    if (state.mode === "current-combat" || state.observation?.status === "combat") return "Combat · Static reference";
    if (state.mode === "last-completed-room" || state.observation?.status === "last") return "Last fight · Static reference";
    return "Static reference";
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
  function renderRosterCapsule(hero, presentation) {
    const initialBodies = presentation.bodies.filter((body) => body.role.includes("possible initial body"));
    const simple = presentation.roster.cardinality === "1"
      && initialBodies.length === 1 && presentation.roster.summary === initialBodies[0].name;
    if (simple) return;
    const roster = el("aside", "roster-capsule");
    roster.append(el("span", "capsule-label", `${presentation.roster.cardinality} possible initial`));
    roster.append(el("span", "roster-line", presentation.roster.summary));
    roster.append(el("span", "boundary-note", "Alternatives are possibilities, not a simultaneous lineup."));
    hero.append(roster);
  }

  function renderInitialState(card, bodyView) {
    if (!bodyView.initialEffects.length) return;
    const group = el("div", "mechanic-group starts-group");
    heading(group, 4, "Starts with", "minor-title");
    bodyView.initialEffects.forEach((fact) => {
      const row = el("div", "fact-row");
      row.append(el("p", "effect-line", fact.line));
      if (fact.condition) row.append(el("p", "condition-line", `When · ${fact.condition}`));
      if (fact.unresolved) row.append(el("p", "unknown-line", `Needs · ${fact.unresolved}`));
      group.append(row);
    });
    card.append(group);
  }
  function renderEffects(card, bodyView) {
    if (!bodyView.effects.length) return;
    const group = el("div", "mechanic-group effects-group");
    heading(group, 4, "Effects", "minor-title");
    bodyView.effects.forEach((effect) => {
      const effectRow = el("article", "effect-row");
      effectRow.append(el("span", "sequence-marker", String(effect.marker)));
      const list = el("ol", "effect-list");
      effect.orderedEffects.forEach((item) => list.append(el("li", "effect-line", item.line)));
      effectRow.append(list);
      group.append(effectRow);
    });
    card.append(group);
  }
  function renderBehavior(card, bodyView) {
    const group = el("div", "mechanic-group behavior-group");
    heading(group, 4, "Pattern", "minor-title");
    group.append(el("p", "behavior-line", bodyView.behavior.headline));
    bodyView.behavior.paths.forEach((path) => group.append(el("p", "path-line", path)));
    card.append(group);
  }
  function renderForms(card, bodyView) {
    if (!bodyView.forms.length) return;
    const forms = el("div", "mechanic-group forms");
    heading(forms, 4, "Forms / phases", "minor-title");
    bodyView.forms.forEach((form) => forms.append(el("p", "form-line", `${form.name} · ${form.hp}`)));
    card.append(forms);
  }
  function renderProductionRule(parent, rule) {
    const card = el("article", "rule-card production-rule");
    card.append(el("p", "effect-line", rule.cadence));
    card.append(el("p", "condition-line", `When · ${rule.condition}`));
    card.append(el("p", "clock-line", `Clock · ${rule.repeat}`));
    rule.attempts.forEach((attempt) => card.append(el("p", "pool-line", attempt)));
    parent.append(card);
  }
  function renderBodyProduction(card, bodyView, presentation) {
    if (!presentation.production) return;
    const rules = presentation.production.rules.filter((rule) => rule.ownerIndex === bodyView.bodyIndex);
    if (!rules.length) return;
    const group = el("div", "mechanic-group production-group");
    heading(group, 4, "Produces", "minor-title");
    group.append(el("p", "boundary-note", `${presentation.production.possibilities.join(" / ")} · possible produced bodies, not initial bodies.`));
    rules.forEach((rule) => renderProductionRule(group, rule));
    card.append(group);
  }
  function renderLifecycleMechanic(parent, mechanic) {
    const card = el("article", "rule-card lifecycle-card");
    heading(card, 4, mechanic.family, "rule-title");
    mechanic.branches.forEach((branch) => {
      if (branch.condition) card.append(el("p", "condition-line", `When · ${branch.condition}`));
      const list = el("ol", "effect-list");
      branch.effects.forEach((effect) => list.append(el("li", "effect-line", effect)));
      if (branch.effects.length) card.append(list);
      if (branch.repeat) card.append(el("p", "clock-line", `Clock · ${branch.repeat}`));
    });
    parent.append(card);
  }
  function renderBodyLifecycle(card, bodyView, presentation) {
    const mechanics = presentation.lifecycle.mechanics.filter((mechanic) => mechanic.bodyIndexes.includes(bodyView.bodyIndex));
    if (!mechanics.length) return;
    const group = el("div", "mechanic-group lifecycle-group");
    heading(group, 4, "Death / lifecycle", "minor-title");
    mechanics.forEach((mechanic) => renderLifecycleMechanic(group, mechanic));
    card.append(group);
  }
  function calloutCard(callout) {
    const card = el("article", "callout-card");
    heading(card, 4, callout.headline, "callout-title");
    card.append(el("p", "effect-line", callout.causalBasis));
    if (callout.condition) card.append(el("p", "condition-line", `When · ${callout.condition}`));
    return card;
  }
  function renderBodyCallouts(card, bodyView, collection) {
    const callouts = collection.all.filter((callout) => callout.bodyIndex === bodyView.bodyIndex);
    if (!callouts.length) return;
    const group = el("div", "mechanic-group callouts-group");
    callouts.forEach((callout) => group.append(calloutCard(callout)));
    card.append(group);
  }
  function renderBodies(parent, presentation) {
    const cards = el("section", "body-list");
    presentation.bodies.forEach((bodyView) => {
      const card = el("article", "body-card");
      const head = el("div", "body-head");
      const title = el("div", "body-name-wrap");
      heading(title, 2, bodyView.name, "body-title");
      title.append(el("p", "body-role", bodyView.role));
      head.append(title, el("strong", "hp-pill", bodyView.hp));
      card.append(head);
      if (bodyView.hpNote) card.append(el("p", "hp-note", bodyView.hpNote));
      renderInitialState(card, bodyView);
      renderEffects(card, bodyView);
      renderBehavior(card, bodyView);
      renderForms(card, bodyView);
      renderBodyProduction(card, bodyView, presentation);
      renderBodyLifecycle(card, bodyView, presentation);
      renderBodyCallouts(card, bodyView, presentation.callouts);
      cards.append(card);
    });
    parent.append(cards);
  }

  function renderEvent(parent, presentation) {
    if (!presentation.event || !presentation.event.effects.length) return;
    const node = section(parent, "Event consequences", "guide-section event-section");
    const list = el("ul", "plain-list");
    presentation.event.effects.forEach((effect) => list.append(el("li", "effect-line", effect)));
    node.append(list);
  }
  function renderEncounterRules(parent, presentation) {
    const mechanics = presentation.lifecycle.mechanics.filter((mechanic) => mechanic.bodyIndexes.length === 0);
    if (!presentation.lifecycle.rules.length && !mechanics.length) return;
    const node = section(parent, "Encounter rules", "guide-section lifecycle-section");
    const list = el("ul", "plain-list");
    presentation.lifecycle.rules.forEach((rule) => list.append(el("li", "lifecycle-line", rule)));
    if (presentation.lifecycle.rules.length) node.append(list);
    mechanics.forEach((mechanic) => renderLifecycleMechanic(node, mechanic));
  }
  function renderUnroutedProduction(parent, presentation) {
    if (!presentation.production) return;
    const rules = presentation.production.rules.filter((rule) => rule.ownerIndex === null);
    if (!rules.length) return;
    const node = section(parent, "Produced bodies", "guide-section production-section");
    node.append(el("p", "boundary-note", presentation.production.caveat));
    rules.forEach((rule) => renderProductionRule(node, rule));
  }
  function renderUnknowns(parent, presentation) {
    if (!presentation.unknowns.length) return;
    const content = el("div", "unknown-content");
    presentation.unknowns.forEach((item) => {
      const row = el("article", "unknown-row");
      heading(row, 3, item.headline, "unknown-title");
      row.append(el("p", "unknown-line", item.detail));
      content.append(row);
    });
    parent.append(details(`Known source gaps · ${presentation.unknowns.length}`, content, "known-gaps"));
  }
  function renderGlobalCallouts(parent, collection) {
    const all = collection.all.filter((callout) => callout.bodyIndex === null);
    if (!all.length) return;
    const node = section(parent, "TACTIC / WATCH", "guide-section callouts-section");
    const visibleIds = new Set(collection.collapsed.filter((callout) => callout.bodyIndex === null).map((callout) => callout.id));
    const visible = all.filter((callout) => visibleIds.has(callout.id));
    (visible.length ? visible : all.slice(0, 1)).forEach((callout) => node.append(calloutCard(callout)));
    if (all.length > 1) {
      const expanded = el("div", "all-callouts");
      all.forEach((callout) => expanded.append(calloutCard(callout)));
      node.append(details(`Show all ${all.length} callouts`, expanded, "detail callout-expander"));
    }
  }
  function renderAudit(parent, state, encounter) {
    const content = el("div", "audit-content");
    content.append(el("p", "quiet", "Exact checked source records, symbolic expressions, retained reference records, merge provenance, behavior data, callout basis, conflicts, and evidence pointers."));
    content.append(details("Authority & observed identity", { authority: state.authority, sourceAuthority: encounter.sourceAuthority, observation: state.observation }));
    if (encounter.reference) content.append(details("Exact retained wiki/reference record", encounter.reference));
    if (encounter.presentation?.audit?.mergeProvenance) content.append(details("Best-available merge provenance", encounter.presentation.audit.mergeProvenance));
    if (encounter.presentation?.callouts?.all?.length) content.append(details("Editorial callout records", encounter.presentation.callouts));
    const checked = { ...encounter }; delete checked.presentation; delete checked.reference;
    content.append(details("Exact checked source encounter record", checked));
    parent.append(details("Technical audit", content, "technical-audit"));
  }

  function renderPrimaryHero(parent, state, encounter, primary) {
    const hero = el("header", "encounter-hero primary-hero");
    heading(hero, 1, String(encounter.title).toUpperCase(), "encounter-title");
    hero.append(el("p", "encounter-stats", primary.header.stats));
    hero.append(el("p", "encounter-placement", primary.header.placement));
    hero.append(el("p", "selection-context", selectionLabel(state, encounter)));
    parent.append(hero);
  }
  function renderPrimarySection(parent, phase) {
    const sectionNode = el("section", "phase-section");
    const head = el("header", "phase-head");
    if (phase.number) head.append(el("span", "phase-number", phase.number));
    heading(head, 2, phase.title, "phase-title");
    sectionNode.append(head);
    if (phase.note) sectionNode.append(el("p", "phase-note", phase.note));
    phase.rows.forEach((row) => {
      if (!row.detail) return;
      const line = el("p", row.cue ? "sequence-row" : "sequence-row sequence-row-uncued");
      if (row.cue) {
        line.append(el("strong", "sequence-cue", row.cue));
        line.append(el("span", "sequence-detail", ` · ${row.detail}`));
      } else {
        line.append(el("span", "sequence-detail", row.detail));
      }
      sectionNode.append(line);
    });
    if (phase.marker) {
      const marker = el("p", "threshold-line");
      marker.append(el("strong", "threshold-label", phase.marker.label));
      marker.append(el("span", "threshold-detail", ` · ${phase.marker.detail}`));
      sectionNode.append(marker);
    }
    if (phase.repeat) sectionNode.append(el("p", "repeat-line", phase.repeat));
    parent.append(sectionNode);
    if (phase.transitionAfter) parent.append(el("div", "phase-transition", "↓"));
  }
  function renderPrimaryCallouts(parent, bodyIndex, collection) {
    const all = collection.all.filter((callout) => callout.bodyIndex === bodyIndex);
    if (!all.length) return;
    const visibleIds = new Set(collection.collapsed.filter((callout) => callout.bodyIndex === bodyIndex).map((callout) => callout.id));
    const visible = all.filter((callout) => visibleIds.has(callout.id));
    (visible.length ? visible : all.slice(0, 1)).forEach((callout) => parent.append(calloutCard(callout)));
  }
  function renderPrimaryBodies(parent, primary, callouts) {
    const list = el("div", "primary-body-list");
    const showBodyHeaders = primary.bodies.length > 1;
    primary.bodies.forEach((body) => {
      const bodyNode = el("section", "primary-body");
      if (showBodyHeaders) {
        const head = el("header", "primary-body-head");
        heading(head, 2, body.name, "body-title");
        head.append(el("p", "body-meta", `${body.hp} HP · ${body.role}`));
        bodyNode.append(head);
      }
      if (body.setup) bodyNode.append(el("p", "setup-line", body.setup));
      body.sections.forEach((phase) => renderPrimarySection(bodyNode, phase));
      body.watch.forEach((watch) => {
        const line = el("p", "watch-line");
        line.append(el("strong", "watch-label", "Watch:"));
        line.append(el("span", "watch-detail", ` ${watch}`));
        bodyNode.append(line);
      });
      renderPrimaryCallouts(bodyNode, body.bodyIndex, callouts);
      list.append(bodyNode);
    });
    parent.append(list);
  }
  function renderPrimaryNotes(parent, primary) {
    if (!primary.notes.length) return;
    const notes = el("section", "reference-notes");
    primary.notes.forEach((note) => {
      const line = el("p", "reference-note");
      line.append(el("strong", "reference-note-label", "Rule:"));
      line.append(el("span", "", ` ${note}`));
      notes.append(line);
    });
    parent.append(notes);
  }
  function renderPrimaryFooter(parent, primary) {
    const footer = el("footer", "guide-footer");
    footer.append(el("p", "provenance-line", primary.provenance.label));
    parent.append(footer);
  }

  function render(state, nextSignature) {
    root.replaceChildren();
    root.className = `guide-state guide-state-${state.status}`;
    if (state.status !== "selected") {
      const empty = el("section", "empty-state");
      heading(empty, 1, state.status === "unresolved-observation" ? "Unsupported encounter identity" : "No encounter selected");
      empty.append(rawEl("p", "boundary-note", state.error || state.notices?.[0] || "No encounter is available."));
      empty.append(el("p", "quiet", "Choose one exact checked encounter or wait for a locally observed encounter identity."));
      root.append(empty);
      signature = nextSignature;
      return;
    }
    const encounter = state.encounter, presentation = encounter.presentation;
    if (!presentation) throw new Error("guide presentation unavailable");
    if (presentation.primary) {
      renderPrimaryHero(root, state, encounter, presentation.primary);
      renderVersionBoundary(state, root);
      renderPrimaryBodies(root, presentation.primary, presentation.callouts);
      renderPrimaryNotes(root, presentation.primary);
      renderGlobalCallouts(root, presentation.callouts);
      renderPrimaryFooter(root, presentation.primary);
      renderAudit(root, state, encounter);
      signature = nextSignature;
      return;
    }
    const hero = el("header", "encounter-hero");
    const selection = selectionLabel(state, encounter);
    hero.append(state.mode === "manual-reference"
      ? rawEl("p", "selection-context", selection)
      : el("p", "selection-context", selection));
    heading(hero, 1, encounter.title, "encounter-title");
    hero.append(el("p", "eyebrow", `${presentation.context.summary} · ${presentation.context.kind}`));
    renderRosterCapsule(hero, presentation);
    hero.append(el("p", "static-contract", "Static reference · no live turn state, HP/Block/Powers, intent/target, phase/counter, lineup, or timer."));
    root.append(hero);
    renderVersionBoundary(state, root);
    renderBodies(root, presentation);
    renderUnroutedProduction(root, presentation);
    renderEvent(root, presentation);
    renderEncounterRules(root, presentation);
    renderGlobalCallouts(root, presentation.callouts);
    renderUnknowns(root, presentation);
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
  window.setInterval(poll, 1500);
})();
