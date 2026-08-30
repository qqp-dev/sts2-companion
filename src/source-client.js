(() => {
  "use strict";
  const root = document.getElementById("source-encounter");
  const basePath = root.dataset.basePath || "/sts2";
  const manualQuery = new URLSearchParams(window.location.search).getAll("encounter");
  const stateUrl = `${basePath}/source/state${manualQuery.length ? `?encounter=${encodeURIComponent(manualQuery[0])}` : ""}`;
  let signature = "";

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function badge(text, lane = text.toLowerCase()) { return el("span", `badge badge-${lane}`, text); }
  function valueText(value) {
    if (value === null) return "null";
    if (typeof value === "string") return value;
    if (typeof value === "boolean" || typeof value === "number") return String(value);
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
    if (Array.isArray(value)) {
      value.forEach((item, index) => wrap.append(tree(item, `[${index + 1}]`, depth + 1)));
    } else {
      Object.entries(value).forEach(([key, item]) => wrap.append(tree(item, key, depth + 1)));
    }
    return wrap;
  }
  function exprText(expr) {
    if (!expr || typeof expr !== "object") return valueText(expr);
    switch (expr.kind) {
      case "constant": return `${valueText(expr.value)}${expr.valueType ? ` (${expr.valueType})` : ""}`;
      case "stateVariable":
      case "runtimeInput": return `${expr.kind}: ${expr.name}${expr.domain ? " · bounded domain below" : ""}`;
      case "reference": return `source reference: ${expr.reference}`;
      case "ascensionSelect": return `ascension ≥ ${expr.threshold} ? ${exprText(expr.atOrAbove)} : ${exprText(expr.below)}`;
      case "arithmetic": return `(${(expr.operands || []).map(exprText).join(` ${expr.operator || "op"} `)})`;
      case "range": return `${exprText(expr.minimum)} … ${exprText(expr.maximum)}`;
      case "convert": return `${exprText(expr.expression)} as ${expr.toType || expr.valueType || "declared type"}`;
      case "conditional": return `if ${exprText(expr.condition)} then ${exprText(expr.whenTrue)} else ${exprText(expr.whenFalse)}`;
      case "compare": return `compare ${(expr.operands || []).map(exprText).join(` ${expr.operator || "with"} `)}`;
      default: return `${expr.kind || "structured value"}${expr.name ? `: ${expr.name}` : ""}`;
    }
  }
  function details(title, content, open = false) {
    const node = el("details", "detail"); node.open = open;
    node.append(el("summary", "detail-title", title));
    if (content instanceof Node) node.append(content); else node.append(tree(content));
    return node;
  }
  function section(parent, title, lane = "SOURCE") {
    const node = el("section", "source-section");
    const heading = el("div", "section-heading"); heading.append(el("h2", "", title), badge(lane, lane.toLowerCase().split(" ")[0]));
    node.append(heading); parent.append(node); return node;
  }
  function bodyName(body) {
    if (body.name.kind === "localizedText") return body.name.text;
    return `${body.name.template} · runtime template input unresolved`;
  }
  function renderRoster(parent, encounter) {
    const node = section(parent, "Initial roster grammar");
    node.append(el("p", "lead", `${encounter.roster.cardinality.minimum}–${encounter.roster.cardinality.maximum} initial bodies. Choices below are possibilities, not a simultaneous lineup.`));
    const possible = el("div", "chips"); encounter.roster.possibleInitialBodies.forEach((id) => possible.append(el("span", "chip", id)));
    node.append(possible, details("Exact selection grammar", encounter.roster.grammar));
    if (encounter.observedBodies.length) {
      const observed = section(parent, "Bodies reported by observation", "OBSERVED");
      observed.append(el("p", "lead", "Exact checked identity joins from the state reader; this is not HP, intent, phase, or survivor inference."));
      encounter.observedBodies.forEach((body) => observed.append(el("div", body.resolved ? "observed-row" : "observed-row unknown", body.resolved ? `${body.observedId} → ${body.canonicalModel}` : `${body.observedId} · unresolved`)));
    }
  }
  function renderMonster(parent, body) {
    const card = el("article", "monster-card");
    const head = el("div", "monster-head"); head.append(el("h3", "", bodyName(body)), el("span", "model-id", body.canonicalModel)); card.append(head);
    const hp = el("div", "mechanic-line"); hp.append(el("strong", "", "HP expression · "), el("span", "formula", exprText(body.hp.expression))); card.append(hp);
    if (body.name.kind === "localizedTemplate") card.append(details("Name template inputs", body.name.inputs));
    card.append(details("HP formula and A8 single-player contract", body.hp, true));
    if (body.states.length) {
      const stateWrap = el("div", "subsection"); stateWrap.append(el("h4", "", "State variants · not observed from model ID"));
      body.states.forEach((state) => {
        const name = state.displayName.kind === "localizedText" ? state.displayName.text : `${state.displayName.template} · runtime template input`;
        stateWrap.append(el("div", "state-row", `${name} · ${state.stateId} · HP state ${state.hpState}`));
      }); card.append(stateWrap);
    }
    if (body.initialState.length) {
      const initial = el("div", "subsection"); initial.append(el("h4", "", "Initial Powers / state / hooks"));
      body.initialState.forEach((fact) => {
        const row = el("div", "operation");
        row.append(el("strong", "", `${fact.order.stageOrder}.${fact.order.sourceOrder} ${fact.effect.kind}`));
        row.append(el("span", "", `${fact.effect.model || fact.effect.member || "structured effect"} · ${exprText(fact.baseValue.expression)}`));
        if (fact.runtimeInputs.length) row.append(el("span", "unknown", `UNKNOWN runtime inputs · ${fact.runtimeInputs.join(", ")}`));
        initial.append(row);
      }); card.append(initial);
    }
    if (body.moves.length) {
      const moveList = el("div", "moves"); moveList.append(el("h4", "", "Move possibilities and ordered operations"));
      body.moves.forEach((move) => {
        const title = move.title.text || `UNKNOWN title · ${move.stateId}`;
        const moveNode = el("details", "move-detail"); const summary = el("summary", "move-summary", title);
        if (move.intents.length) summary.append(el("span", "intent", move.intents.map((intent) => intent.kind).join(" + ")));
        moveNode.append(summary);
        if (!move.title.text) moveNode.append(el("p", "unknown", "Source title is classified but not resolved; the move ID is audit metadata, not explanation."));
        move.operations.forEach((operation) => {
          const row = el("div", "operation"); row.append(el("strong", "", `${operation.order + 1}. ${operation.kind}`));
          const pieces = [operation.target, operation.model, operation.value ? exprText(operation.value) : null, operation.selection?.kind, operation.condition ? exprText(operation.condition) : null].filter(Boolean);
          row.append(el("span", "", pieces.join(" · ") || operation.transition || "structured operation"));
          row.append(details("Exact operation", operation)); moveNode.append(row);
        });
        moveNode.append(details("Intent structures", move.intents), el("div", "fact-ref", move.factId)); moveList.append(moveNode);
      }); card.append(moveList);
    }
    if (body.graph) card.append(details("Move graph: initial candidates, conditions, randomness, follow-ups", body.graph));
    parent.append(card);
  }
  function renderProduction(parent, production) {
    if (!production) return;
    const node = section(parent, "Produced bodies and production rules");
    node.append(el("p", "lead", "These bodies can be produced after initialization. They are not members of the initial lineup unless the roster grammar says so."));
    const chips = el("div", "chips"); production.producedBodies.forEach((id) => chips.append(el("span", "chip produced", id))); node.append(chips);
    if (production.pools.length) node.append(details("Production pools", production.pools, true));
    Object.entries(production.rules).forEach(([name, rows]) => node.append(details(name.replaceAll(/([A-Z])/g, " $1"), rows)));
  }
  function renderEvent(parent, event) {
    if (!event) return; const node = section(parent, "Event turn machine and script");
    node.append(el("p", "lead", `${event.canonicalEvent} · static event mechanics; no current event choice or turn is observed.`));
    node.append(details("Turn-machine classification", event.turnMachine, true));
    Object.entries(event.scripts).forEach(([name, rows]) => node.append(details(name, rows)));
  }
  function renderWarnings(parent, encounter) {
    if (encounter.knownUnknowns.length) {
      const node = section(parent, "Known unknowns affecting this capsule", "UNKNOWN");
      encounter.knownUnknowns.forEach((item) => node.append(details(`${item.unknownId} · ${item.status}`, item, true)));
    }
    if (encounter.conflicts.length || encounter.comparisons.length) {
      const node = section(parent, "Source / legacy lane comparisons", "UNKNOWN");
      node.append(el("p", "lead", "Both lanes remain visible. No precedence is applied."));
      encounter.conflicts.forEach((item) => node.append(details(`Conflict · ${item.family}`, item, true)));
      encounter.comparisons.forEach((item) => node.append(details(`Comparison · ${item.family}`, item)));
    }
    if (encounter.legacyAnnotations.length) {
      const node = section(parent, "Legacy / community annotations", "LEGACY");
      node.append(el("p", "lead", "Separate annotation lane; never used to fill source mechanics."));
      encounter.legacyAnnotations.forEach((item) => node.append(details(item.factId, item)));
    }
  }
  function render(state, nextSignature) {
    root.replaceChildren(); root.className = `source-state source-state-${state.status}`;
    const authority = el("header", "source-header");
    const badges = el("div", "badges"); badges.append(badge("SOURCE"), badge("STATIC", "unknown"));
    if (state.mode === "manual-reference") badges.append(badge("MANUAL REFERENCE", "manual"));
    else if (state.mode === "current-combat" || state.mode === "last-completed-room") badges.append(badge("OBSERVED ID", "observed"));
    const installed = state.observation?.installedVersion?.version;
    if (!installed) badges.append(badge("VERSION UNKNOWN", "unknown"));
    else badges.append(badge(state.observation.versionMatches ? "VERSION MATCH" : "VERSION MISMATCH", state.observation.versionMatches ? "observed" : "unknown"));
    authority.append(badges, el("div", "authority-line", `${state.authority.gameVersion} · projection schema ${state.authority.projectionSchemaVersion} · source-only shadow`));
    authority.append(el("div", "authority-line", `observation ${state.observation?.status || "idle"} · ${state.observation?.source || "no source"} · ${state.observation?.freshness || "unknown freshness"}${installed ? ` · installed ${installed}` : ""}`)); root.append(authority);
    if (state.status !== "selected") {
      const idle = el("section", "empty"); idle.append(el("h1", "", state.status === "unresolved-observation" ? "Unknown observed encounter" : "No encounter selected"));
      idle.append(el("p", "", state.error || state.notices?.[0] || "No encounter.")); root.append(idle); signature = nextSignature; return;
    }
    const encounter = state.encounter; const hero = el("section", "hero");
    hero.append(el("div", "eyebrow", `${encounter.kind} · ${state.mode.replaceAll("-", " ")}`), el("h1", "", encounter.title), el("div", "canonical", `${encounter.canonicalId} · ${encounter.sourceIdentity}`));
    state.notices.forEach((notice) => hero.append(el("p", "notice", notice))); root.append(hero);
    const placement = section(root, "Placement");
    encounter.placement.memberships.forEach((row) => placement.append(el("div", "placement", `${row.actId} · ${row.tier} · ${row.roomClass} · ${row.poolId}`)));
    renderRoster(root, encounter); renderProduction(root, encounter.production);
    const hpContract = section(root, "HP assignment, scaling, and state-rule contracts");
    hpContract.append(el("p", "lead", encounter.hpContract.scope), details("Exact global HP/state contract", encounter.hpContract));
    const bodies = section(root, "Monster mechanics"); encounter.monsters.forEach((body) => renderMonster(bodies, body));
    renderEvent(root, encounter.event);
    const lifecycle = section(root, "Lifecycle and core boundaries"); lifecycle.append(el("p", "lead", `${encounter.lifecycle.status} · source refs available; dependency statuses below remain authoritative.`), details("Core lifecycle facts", encounter.lifecycle), el("p", "unknown", "No live HP, phase, listener state, PendingLoss, or turn boundary is observed."));
    const tactics = section(root, `Source-qualified tactical callouts · ${encounter.callouts.length}`);
    tactics.append(el("p", "lead", "No checked editorial callout records are available. Empty means 0 source-qualified records, not a quota and not advice."));
    renderWarnings(root, encounter);
    const proof = section(root, "Provenance and evidence"); proof.append(details(`${encounter.proof.length} affected source facts · expand for exact pointers`, encounter.proof));
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
