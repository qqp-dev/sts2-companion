(() => {
  "use strict";
  const root = document.getElementById("source-encounter");
  const basePath = root.dataset.basePath || "/sts2";
  const manualQuery = new URLSearchParams(window.location.search).getAll("encounter");
  const stateUrl = `${basePath}/state${manualQuery.length ? `?encounter=${encodeURIComponent(manualQuery[0])}` : ""}`;
  let signature = "";

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function badge(text, tone = "source") { return el("span", `badge badge-${tone}`, text); }
  function valueText(value) {
    if (value === null) return "null";
    if (typeof value === "string" || typeof value === "boolean" || typeof value === "number") return String(value);
    return "";
  }
  function tree(value, label = null, depth = 0) {
    const wrap = el("div", `tree depth-${Math.min(depth, 4)}`);
    if (value === null || typeof value !== "object") {
      if (label) wrap.append(el("span", "tree-key", `${label}: `));
      wrap.append(el("span", "tree-value", valueText(value)));
      return wrap;
    }
    if (label) wrap.append(el("div", "tree-key", label));
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
  function heading(parent, level, text, className = "") { const node = el(`h${level}`, className, text); parent.append(node); return node; }
  function section(parent, title, className = "capsule-section") {
    const node = el("section", className); heading(node, 2, title, "section-title"); parent.append(node); return node;
  }
  function modeText(mode) {
    if (mode === "manual-reference") return "Manual static reference";
    if (mode === "current-combat") return "Combat encounter identity";
    if (mode === "last-completed-room") return "Completed-room encounter identity";
    return "Static source reference";
  }

  function renderBoundary(state, parent) {
    const strip = el("aside", "boundary-strip");
    const badges = el("div", "badges"); badges.append(badge("STATIC SOURCE"), badge(modeText(state.mode), state.mode === "manual-reference" ? "manual" : "observed"));
    const installed = state.observation?.installedVersion?.version;
    if (!installed) badges.append(badge("VERSION UNKNOWN", "unknown"));
    else badges.append(badge(state.observation.versionMatches ? "VERSION MATCH" : "VERSION MISMATCH", state.observation.versionMatches ? "observed" : "danger"));
    strip.append(badges);
    if (!installed) strip.append(el("p", "boundary-warning", `Installed version unavailable; mechanics are checked for ${state.authority.gameVersion}.`));
    else if (!state.observation.versionMatches) strip.append(el("p", "boundary-warning", `Installed ${installed} differs from checked ${state.authority.gameVersion}. Versioned mechanics are not mixed.`));
    else strip.append(el("p", "boundary-copy", `Checked ${state.authority.gameVersion} · schema ${state.authority.projectionSchemaVersion} · encounter identity only`));
    parent.append(strip);
  }

  function renderRoster(parent, encounter, presentation) {
    const node = section(parent, "Encounter grammar", "capsule-section roster-capsule");
    node.append(el("p", "roster-count", `${presentation.roster.cardinality} initial body slot${presentation.roster.cardinality === "1" ? "" : "s"}`));
    node.append(el("p", "roster-grammar", presentation.roster.summary));
    node.append(el("p", "possibility-note", presentation.roster.caveat));
    node.append(details("Exact roster grammar & placement", { roster: encounter.roster, placement: encounter.placement }));
    if (encounter.observedBodies.length) {
      const observed = el("div", "observed-identities");
      observed.append(el("h3", "minor-title", "Observed identity join"));
      observed.append(el("p", "quiet", "Saved body IDs only; no HP, form, phase, or survivor state is supplied."));
      encounter.observedBodies.forEach((body) => observed.append(el("p", body.resolved ? "identity-row" : "identity-row boundary-warning", body.resolved ? `${body.observedId} → ${body.canonicalModel}` : `${body.observedId} → unresolved identity`)));
      observed.append(details("Exact observed/model identity refs", encounter.observedBodies)); node.append(observed);
    }
  }

  function renderInitialState(card, bodyView, body) {
    if (!bodyView.initialEffects.length) return;
    const initial = el("div", "mechanic-group"); heading(initial, 4, "Initial state", "minor-title");
    bodyView.initialEffects.forEach((fact, index) => {
      const row = el("div", "initial-effect");
      row.append(el("span", "timing-label", fact.timing), el("p", "effect-line", fact.line));
      if (fact.condition) row.append(el("p", "condition-line", `Condition · ${fact.condition}`));
      if (fact.unresolved) row.append(el("p", "unknown-line", `Unknown · ${fact.unresolved}`));
      row.append(details("Exact initial-state fact", body.initialState[index])); initial.append(row);
    }); card.append(initial);
  }

  function renderBehavior(card, bodyView, body) {
    const group = el("div", "mechanic-group behavior-group"); heading(group, 4, "Cycles & forks", "minor-title");
    group.append(el("p", "behavior-headline", bodyView.behavior.headline));
    if (bodyView.behavior.paths.length) {
      const paths = el("div", "behavior-paths"); bodyView.behavior.paths.forEach((path) => paths.append(el("p", "path-line", path)));
      group.append(details("Behavior paths & conditions", paths));
    }
    if (body.graph) group.append(details("Move graph: exact graph & IDs", body.graph)); card.append(group);
  }

  function renderEffects(card, bodyView, body) {
    const group = el("div", "mechanic-group signatures"); heading(group, 4, "Possible effect signatures", "minor-title");
    group.append(el("p", "quiet", "Each card is one static behavior possibility. Numbered lines preserve source operation order."));
    bodyView.effects.forEach((effect) => {
      const effectCard = el("article", "effect-card"); heading(effectCard, 5, effect.label, "effect-title");
      effectCard.append(el("p", "timing-label", `Timing · ${effect.timing}`));
      const list = el("ol", "effect-list"); effect.orderedEffects.forEach((item) => list.append(el("li", "effect-line", item.line))); effectCard.append(list);
      effectCard.append(details("Move possibilities and ordered operations · exact audit", body.moves[effect.moveIndex])); group.append(effectCard);
    }); card.append(group);
  }

  function renderBodies(parent, encounter, presentation) {
    const node = section(parent, "Static mechanics", "capsule-section mechanics-capsule");
    presentation.bodies.forEach((bodyView) => {
      const body = encounter.monsters[bodyView.bodyIndex];
      const card = el("article", "body-card");
      const head = el("div", "body-head"); const title = el("div", ""); heading(title, 3, bodyView.name, "body-title"); title.append(el("p", "body-role", bodyView.role)); head.append(title, el("strong", "hp-pill", bodyView.hp)); card.append(head);
      if (bodyView.hpHasRuntimeInputs) card.append(el("p", "condition-line", "HP condition · state/runtime inputs select values in the exact formula."));
      if (bodyView.forms.length) {
        const forms = el("div", "forms"); heading(forms, 4, "Possible forms", "minor-title");
        bodyView.forms.forEach((form) => forms.append(el("p", "form-line", `${form.name} · ${form.hp}`))); card.append(forms);
      }
      card.append(details("Exact HP formula, forms & model metadata", { model: body.canonicalModel, sourceIdentity: body.sourceIdentity, hp: body.hp, states: body.states }));
      renderInitialState(card, bodyView, body); renderEffects(card, bodyView, body); renderBehavior(card, bodyView, body);
      node.append(card);
    });
    node.append(details("Exact global HP assignment & state rules", encounter.hpContract));
  }

  function renderProduction(parent, encounter, presentation) {
    if (!presentation.production) return;
    const node = section(parent, "Production rules", "capsule-section production-capsule");
    node.append(el("p", "possibility-note", presentation.production.caveat));
    const possibilities = el("div", "chips"); presentation.production.possibilities.forEach((name) => possibilities.append(el("span", "chip", name))); node.append(possibilities);
    presentation.production.rules.forEach((rule) => {
      const card = el("article", "rule-card"); heading(card, 3, rule.owner, "rule-title");
      card.append(el("p", "effect-line", rule.cadence), el("p", "condition-line", `Condition · ${rule.condition}`), el("p", "clock-line", `Repeat/lifetime · ${rule.repeat}`));
      rule.attempts.forEach((attempt) => card.append(el("p", "pool-line", `Pool · ${attempt}`))); node.append(card);
    });
    node.append(details("Exact production pools, slots, post-add effects & refs", encounter.production));
  }

  function renderEvent(parent, encounter, presentation) {
    if (!presentation.event) return;
    const node = section(parent, "Event script", "capsule-section event-capsule");
    node.append(el("p", "behavior-headline", `Turn behavior · ${presentation.event.behavior}`));
    presentation.event.effects.forEach((effect) => node.append(el("p", "effect-line", effect)));
    node.append(el("p", "quiet", `${presentation.event.optionCount} scripted option records · ${presentation.event.transitionCount} encounter transition records`));
    node.append(details("Exact event graph, conditions, outcomes & rewards", encounter.event));
  }

  function renderLifecycle(parent, encounter, presentation) {
    const node = section(parent, "Lifecycle and core boundaries", "capsule-section lifecycle-capsule");
    presentation.lifecycle.rules.forEach((rule) => node.append(el("p", "lifecycle-line", rule)));
    presentation.lifecycle.mechanics.forEach((mechanic) => {
      const card = el("article", "rule-card lifecycle-mechanic"); heading(card, 3, mechanic.family, "rule-title");
      mechanic.branches.forEach((branch) => {
        if (branch.condition) card.append(el("p", "condition-line", `Condition · ${branch.condition}`));
        const list = el("ol", "effect-list"); branch.effects.forEach((effect) => list.append(el("li", "effect-line", effect))); card.append(list);
        if (branch.repeat) card.append(el("p", "clock-line", `Repeat/lifetime · ${branch.repeat}`));
      }); node.append(card);
    });
    node.append(details("Exact removal, dispatch, completion & lifecycle facts", encounter.lifecycle));
  }

  function calloutCard(callout) {
    const card = el("article", "callout-card"); heading(card, 3, callout.headline, "callout-headline");
    card.append(el("p", "callout-cause", callout.causalBasis));
    if (callout.condition) card.append(el("p", "callout-condition", `Condition · ${callout.condition}`));
    card.append(details("Exact callout support", { id: callout.id, language: callout.language, distinctnessKey: callout.distinctnessKey, basis: callout.basis, phaseControl: callout.phaseControl }));
    return card;
  }
  function renderCallouts(parent, collection) {
    const node = section(parent, `Tactical callouts · ${collection.total}`, `capsule-section callouts callouts-${collection.total ? "available" : "empty"}`);
    if (!collection.total) {
      node.append(el("p", "quiet", "No checked editorial callout records are published for this capsule.")); return;
    }
    const count = el("p", "collection-count", `${collection.collapsedCount} of ${collection.total} shown${collection.hasMore ? " · more available below" : ""}`); node.append(count);
    collection.collapsed.forEach((callout) => node.append(calloutCard(callout)));
    if (collection.hasMore) {
      const all = el("div", "all-callouts"); collection.all.forEach((callout) => all.append(calloutCard(callout)));
      node.append(details(`Show all ${collection.total} source-qualified callouts`, all, "detail callout-expander"));
    }
  }

  function renderUnknowns(parent, presentation) {
    const node = section(parent, "Knowledge boundary", "capsule-section unknowns-capsule");
    presentation.unknowns.forEach((item) => {
      const row = el("article", "unknown-card"); heading(row, 3, `Unknown · ${item.headline}`, "unknown-title"); row.append(el("p", "unknown-line", item.detail)); node.append(row);
    });
  }

  function renderAudit(parent, state, encounter) {
    const node = section(parent, "Provenance and evidence", "capsule-section audit-capsule");
    node.append(el("p", "quiet", "Exact source facts, IDs, titles, lane records, and evidence pointers live here—not in the phone thinking window."));
    node.append(details("Authority & observation identity", { authority: state.authority, observation: state.observation, encounterId: encounter.canonicalId, sourceIdentity: encounter.sourceIdentity }));
    if (encounter.conflicts.length || encounter.comparisons.length) node.append(details("Source / legacy comparisons (no precedence)", { conflicts: encounter.conflicts, comparisons: encounter.comparisons }));
    if (encounter.legacyAnnotations.length) node.append(details("Separate legacy / community lane", encounter.legacyAnnotations));
    node.append(details(`${encounter.proof.length} source facts · exact evidence pointers`, encounter.proof));
  }

  function render(state, nextSignature) {
    root.replaceChildren(); root.className = `source-state source-state-${state.status}`;
    if (state.status !== "selected") {
      const empty = el("section", "empty-state");
      heading(empty, 1, state.status === "unresolved-observation" ? "Unsupported encounter identity" : "No encounter selected");
      empty.append(el("p", "boundary-warning", state.error || state.notices?.[0] || "No encounter identity is available."));
      empty.append(el("p", "quiet", "A manual static reference accepts one exact canonical encounter selector.")); root.append(empty); signature = nextSignature; return;
    }
    const encounter = state.encounter, presentation = encounter.presentation;
    if (!presentation) throw new Error("source presentation unavailable");
    const hero = el("header", "encounter-hero");
    hero.append(el("p", "eyebrow", `${presentation.context.kind} · ${presentation.context.summary}`)); heading(hero, 1, encounter.title, "encounter-title");
    hero.append(el("p", "static-contract", "Static mechanics and conditional possibilities · no live turn prediction")); root.append(hero);
    renderBoundary(state, root);
    renderRoster(root, encounter, presentation);
    renderBodies(root, encounter, presentation);
    renderProduction(root, encounter, presentation);
    renderEvent(root, encounter, presentation);
    renderLifecycle(root, encounter, presentation);
    renderUnknowns(root, presentation);
    renderCallouts(root, presentation.callouts);
    renderAudit(root, state, encounter);
    signature = nextSignature;
  }

  async function poll() {
    try {
      const response = await fetch(stateUrl, { cache: "no-store", headers: { Accept: "application/json" } });
      const state = await response.json(); const next = JSON.stringify(state); if (next !== signature) render(state, next);
    } catch { /* Preserve the last honest rendered state across transient reads. */ }
  }
  poll(); window.setInterval(poll, 4000);
})();
