import assert from "node:assert/strict";
import { createServer, request as httpRequest } from "node:http";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";

import { compileCalloutCollection } from "../src/decision-callouts.mjs";
import { createSts2Handler } from "../src/http.mjs";
import { createSourceAdapter, internals as adapterInternals } from "../src/source-adapter.mjs";
import { normalizeMonsterWireIdForState, parseSave } from "../src/state.mjs";

const artifact = JSON.parse(readFileSync(new URL("../data/encounter-facts-v0.111.0.json", import.meta.url), "utf8"));
const clientSource = readFileSync(new URL("../src/client.js", import.meta.url), "utf8");
const project = (mutate = () => {}) => { const value = structuredClone(artifact); mutate(value); return value; };
const checkedProject = (mutate) => {
  const value = project(mutate); value.metadata.payloadSha256 = adapterInternals.payloadDigest(value.payload); return value;
};
const fixture = (name) => readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf8");
const state = (encounterId = null, status = encounterId ? "combat" : "idle", monsterIds = []) => ({
  status, encounterId, monsterIds, actId: encounterId ? "GLORY" : null,
  roomType: encounterId ? "monster" : null, source: encounterId ? "log" : null,
  releaseInfo: { version: "v0.111.0", branch: "public-beta", commit: "41cef1ea" },
});
const parsedRoomState = (encounterId, monsterIds, roomType = "monster") => parseSave({
  acts: [{ id: "ACT.GLORY" }],
  map_point_history: [[{ rooms: [{ room_type: roomType, model_id: `ENCOUNTER.${encounterId}`, monster_ids: monsterIds }] }]],
});
function request(server, path, method = "GET") {
  return new Promise((resolve, reject) => {
    const req = httpRequest({ host: "127.0.0.1", port: server.address().port, path, method, agent: false }, (res) => {
      const chunks = []; res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString("utf8") }));
    }); req.on("error", reject); req.end();
  });
}
async function withServer(handler, run) {
  const server = createServer(handler); await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try { await run(server); } finally { server.closeAllConnections?.(); await new Promise((resolve) => server.close(resolve)); }
}

async function runShadowClient(payload, { failCreateOnce = null } = {}) {
  class TestNode {
    constructor(tagName) { this.tagName = tagName; this.children = []; this.dataset = {}; this.className = ""; this._text = ""; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this._text = ""; this.children = children; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map((child) => child?.textContent ?? String(child)).join(""); }
  }
  const root = new TestNode("main"); root.dataset.basePath = "/sts2";
  let pendingFailure = failCreateOnce; let interval;
  const document = {
    getElementById: (id) => id === "guide-encounter" ? root : null,
    createElement: (tagName) => {
      if (tagName === pendingFailure) { pendingFailure = null; throw new Error(`transient ${tagName} creation failure`); }
      return new TestNode(tagName);
    },
  };
  const window = {
    location: { search: "?encounter=AXEBOTS_NORMAL" },
    setInterval: (callback) => { interval = callback; return 1; },
  };
  const fetch = async () => ({ ok: true, json: async () => structuredClone(payload) });
  runInNewContext(clientSource, { document, window, fetch, Node: TestNode, URLSearchParams, encodeURIComponent });
  await new Promise((resolve) => setImmediate(resolve));
  return { root, pollAgain: async () => { await interval(); } };
}

let adapter;
test.before(() => { adapter = createSourceAdapter({ projection: artifact }); assert.equal(adapter.available, true, adapter.error); });

test("checked schema 11 adapter is immutable, deterministic, and joins exact observed identity", () => {
  const observed = state("BOWLBUGS_NORMAL", "combat", ["MONSTER.BOWLBUG_ROCK", "MONSTER.BOWLBUG_EGG", "MONSTER.BOWLBUG_SILK"]);
  assert.deepEqual(adapter.resolveObserved(observed), { kind: "current-combat", encounterId: "BOWLBUGS_NORMAL" });
  assert.equal(adapter.resolveObserved(state("bowlbugs_normal")).kind, "unresolved-observation");
  const first = adapter.view(observed); const second = adapter.view(observed);
  assert.equal(JSON.stringify(first), JSON.stringify(second)); assert.ok(Object.isFrozen(first.encounter.monsters[0].moves));
  assert.equal(first.mode, "current-combat"); assert.deepEqual(first.encounter.observedBodies.map((row) => row.canonicalModel), observed.monsterIds);
  assert.equal(first.authority.projectionSchemaVersion, 11); assert.equal(first.authority.dllSha256, "2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f");
});

test("real parser output resolves bare AXEBOT through the shared reader normalization", () => {
  const parsed = parsedRoomState("AXEBOTS_NORMAL", ["MONSTER.AXEBOT"]);
  assert.deepEqual(parsed.monsterIds, ["AXEBOT"]);
  assert.equal(normalizeMonsterWireIdForState("MONSTER.AXEBOT"), "AXEBOT");
  assert.deepEqual(adapter.view(parsed).observation.observedBodies, [{
    observedId: "AXEBOT", observedWireId: "MONSTER.AXEBOT", canonicalModel: "MONSTER.AXEBOT", resolved: true,
  }]);
});

test("real parsed Decimillipede IDs follow checked wire-to-canonical rows", async () => {
  const projection = checkedProject((value) => {
    const entries = value.payload.sourceFacts.observationIdentities.entries;
    for (const position of ["FRONT", "MIDDLE", "BACK"]) {
      const row = entries.find((entry) => entry.canonicalMonster === `MONSTER.DECIMILLIPEDE_SEGMENT_${position}`);
      row.observedId = `MONSTER.DECIMILLIPEDE_${position}`;
    }
  });
  const sourceMapped = createSourceAdapter({ projection });
  assert.equal(sourceMapped.available, true, sourceMapped.error);
  const parsed = parseSave(fixture("current_run_mp.save"));
  const bodies = sourceMapped.view(parsed).observation.observedBodies;
  assert.deepEqual(bodies.map((row) => row.observedId), ["DECIMILLIPEDE_FRONT", "DECIMILLIPEDE_MIDDLE", "DECIMILLIPEDE_BACK"]);
  assert.deepEqual(bodies.map((row) => row.observedWireId), ["MONSTER.DECIMILLIPEDE_FRONT", "MONSTER.DECIMILLIPEDE_MIDDLE", "MONSTER.DECIMILLIPEDE_BACK"]);
  assert.deepEqual(bodies.map((row) => row.canonicalModel), ["MONSTER.DECIMILLIPEDE_SEGMENT_FRONT", "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE", "MONSTER.DECIMILLIPEDE_SEGMENT_BACK"]);
  assert.ok(bodies.every((row) => row.resolved));
  const { root } = await runShadowClient(sourceMapped.view(parsed));
  assert.doesNotMatch(collapsedText(root), /DECIMILLIPEDE_(?:FRONT|MIDDLE|BACK)|MONSTER\.DECIMILLIPEDE/);
  for (const position of ["FRONT", "MIDDLE", "BACK"]) {
    assert.match(root.textContent, new RegExp(`DECIMILLIPEDE_${position}`));
    assert.match(root.textContent, new RegExp(`MONSTER\.DECIMILLIPEDE_SEGMENT_${position}`));
  }
});

test("exact-wire fixtures remain explicit while unknown, case, and fuzzy reader IDs stay unresolved", () => {
  const exact = adapter.view(state("AXEBOTS_NORMAL", "combat", ["MONSTER.AXEBOT"])).observation.observedBodies[0];
  assert.deepEqual(exact, { observedId: "MONSTER.AXEBOT", observedWireId: "MONSTER.AXEBOT", canonicalModel: "MONSTER.AXEBOT", resolved: true });
  const parsed = parsedRoomState("AXEBOTS_NORMAL", ["MONSTER.UNKNOWN", "MONSTER.axebot", "MONSTER.AXEBOTS", "MONSTER.AXE_BOT"]);
  const bodies = adapter.view(parsed).observation.observedBodies;
  assert.deepEqual(bodies.map((row) => row.observedId), ["UNKNOWN", "axebot", "AXEBOTS", "AXE_BOT"]);
  assert.ok(bodies.every((row) => !row.resolved && row.observedWireId === null && row.canonicalModel === null));
});

test("manual selectors are exact, bounded, and remain static instead of following observation", () => {
  const live = state("BOWLBUGS_NORMAL", "combat", ["MONSTER.BOWLBUG_ROCK"]);
  assert.equal(adapter.view(live, "AXEBOTS_NORMAL").encounter.canonicalId, "AXEBOTS_NORMAL");
  assert.equal(adapter.view(live, "AXEBOTS_NORMAL").mode, "manual-reference");
  assert.deepEqual(adapter.view(live, "AXEBOTS_NORMAL").encounter.observedBodies, []);
  assert.equal(adapter.view(live, "axebots_normal").status, "unknown-selector");
  assert.equal(adapter.view(live, "x".repeat(161)).status, "invalid-selector");
});

test("fixed and variable rosters do not turn all possible models into one lineup", () => {
  const fixed = adapter.view(state(), "AXEBOTS_NORMAL").encounter;
  assert.deepEqual(fixed.roster.cardinality, { minimum: 1, maximum: 1 });
  assert.deepEqual(fixed.roster.possibleInitialBodies, ["MONSTER.AXEBOT"]);
  const random = adapter.view(state(), "BOWLBUGS_NORMAL").encounter;
  assert.deepEqual(random.roster.cardinality, { minimum: 3, maximum: 3 });
  assert.equal(random.roster.grammar.children[1].kind, "filteredChoice");
  assert.equal(random.roster.grammar.children[1].count, 2);
  assert.equal(random.roster.possibleInitialBodies.length, 4);
  assert.deepEqual(random.observedBodies, []);
  assert.match(JSON.stringify(adapter.view(state(), "BOWLBUGS_NORMAL").notices), /separate sets/);
});

test("producer keeps initial, observed, and produced body sets separate with checked rules", () => {
  const view = adapter.view(state("FABRICATOR_NORMAL", "combat", ["MONSTER.FABRICATOR", "MONSTER.ZAPBOT"]));
  assert.deepEqual(view.encounter.roster.possibleInitialBodies, ["MONSTER.FABRICATOR"]);
  assert.deepEqual(view.encounter.observedBodies.map((row) => row.canonicalModel), ["MONSTER.FABRICATOR", "MONSTER.ZAPBOT"]);
  assert.deepEqual([...view.encounter.production.producedBodies].sort(), ["MONSTER.GUARDBOT", "MONSTER.NOISEBOT", "MONSTER.STABBOT", "MONSTER.ZAPBOT"]);
  assert.ok(Object.keys(view.encounter.production.rules).length > 0);
  assert.ok(!JSON.stringify(view.encounter.roster.grammar).includes("ZAPBOT"));
});

test("event, formula/state, ordered operation, graph, unknown, conflict, and proof sections are rich", () => {
  const event = adapter.view(state(), "DENSE_VEGETATION_EVENT_ENCOUNTER").encounter.event;
  assert.equal(event.canonicalEvent, "EVENT.DENSE_VEGETATION"); assert.ok(event.scripts.effects.length >= 1);
  const subject = adapter.view(state(), "TEST_SUBJECT_BOSS").encounter.monsters.find((row) => row.canonicalModel === "MONSTER.TEST_SUBJECT");
  assert.equal(subject.name.kind, "localizedTemplate"); assert.equal(subject.states.length, 3);
  assert.match(JSON.stringify(subject.name.inputs), /stateVariable/);
  assert.match(JSON.stringify(adapter.view(state(), "TEST_SUBJECT_BOSS").encounter.hpContract.stateRuleRegistry), /testSubjectPhase/);
  const axebotView = adapter.view(state(), "AXEBOTS_NORMAL"); const axebot = axebotView.encounter.monsters[0];
  assert.ok(axebot.moves.every((move) => move.operations.every((op, index) => op.order === index)));
  assert.ok(axebot.graph.edges.length > 0); assert.ok(axebot.graph.initial.length > 1);
  assert.ok(axebotView.encounter.conflicts.some((row) => row.left.lane === "source" && row.right.lane === "legacy"));
  assert.ok(axebotView.encounter.legacyAnnotations.every((row) => row.lane === "LEGACY / COMMUNITY"));
  assert.ok(axebotView.encounter.proof.every((row) => row.lane === "source" && row.evidence.every((proof) => proof.pointers.length)));
  assert.deepEqual(axebotView.encounter.callouts, []);
});

test("schema 10 compatibility is explicit while arbitrary and mismatched majors fail", () => {
  const tenProjection = project((p) => { p.schemaVersion = 10; p.metadata.generator.version = "10.0.0"; p.payload.sourceFacts.lifecycle.status = "sourceCompleteE2d2a"; p.payload.additiveFutureField = { ignored: true }; });
  tenProjection.metadata.payloadSha256 = adapterInternals.payloadDigest(tenProjection.payload);
  const ten = createSourceAdapter({ projection: tenProjection });
  assert.equal(ten.available, true, ten.error); assert.equal(ten.schemaVersion, 10);
  for (const [schema, generator] of [[12, "12.0.0"], [10, "11.0.0"], [11, "10.0.0"]]) {
    const bad = createSourceAdapter({ projection: project((p) => { p.schemaVersion = schema; p.metadata.generator.version = generator; }) });
    assert.equal(bad.available, false); assert.match(bad.error, /schema|generator/);
  }
});

test("observation mapping validation and reader normalization collisions fail closed", () => {
  const entries = (value) => value.payload.sourceFacts.observationIdentities.entries;
  const mutations = [
    (value) => { delete entries(value)[0].observedId; },
    (value) => { entries(value)[0].canonicalMonster = null; },
    (value) => { entries(value)[0].identityKind = "state"; },
    (value) => { entries(value)[0].factId = entries(value)[1].factId; },
    (value) => { entries(value)[0].sourceType = entries(value)[1].sourceType; },
    (value) => { entries(value)[0].observedId = "CARD.AEONGLASS"; },
    (value) => { entries(value)[0].observedId = "MONSTER."; },
    (value) => { entries(value)[1].observedId = entries(value)[0].observedId; },
    (value) => { entries(value)[1].canonicalMonster = entries(value)[0].canonicalMonster; },
    (value) => { value.payload.sourceFacts.observationIdentities.matchingPolicy.wirePrefixes[0].prefix = "MODEL."; },
  ];
  for (const mutate of mutations) {
    const bad = createSourceAdapter({ projection: checkedProject(mutate) });
    assert.equal(bad.available, false); assert.match(bad.error, /observation|wire|duplicate/);
  }
  const row = { observedId: "MONSTER.AXEBOT", canonicalMonster: "MONSTER.AXEBOT", identityKind: "model" };
  assert.throws(() => adapterInternals.buildStateModelObservationIndex(new Map([
    ["MONSTER.AXEBOT", row], ["AXEBOT", { ...row, observedId: "AXEBOT" }],
  ])), /normalization collision AXEBOT/);
});

test("projection corruption and structural mutations fail closed", () => {
  const mutations = [
    (p) => { p.payload.readiness.runtimeScopes.encounterProjection.ready = false; },
    (p) => { p.payload.readiness.runtimeScopes.encounterProjection.status = "mystery"; },
    (p) => { p.payload.sourceFacts.lifecycle.status = "partial"; },
    (p) => { p.payload.sourceFacts.production.productionSemantics.status = "partial"; },
    (p) => { p.payload.sourceFacts.eventScripts.invocationSummary.unresolved = 1; },
    (p) => { p.metadata.requiredCoverage[0].unresolved = 1; },
    (p) => { p.payload.sourceFacts.encounters.ordinary[1].canonicalId = p.payload.sourceFacts.encounters.ordinary[0].canonicalId; },
    (p) => { p.payload.sourceFacts.graphs[0].graphId = p.payload.sourceFacts.graphs[1].graphId; },
    (p) => { p.payload.sourceFacts.moves[0].graphId = "GRAPH.MISSING"; },
    (p) => { p.payload.sourceFacts.observationIdentities.entries.pop(); },
    (p) => { p.payload.factReferences[1].factId = p.payload.factReferences[0].factId; },
    (p) => { p.payload.evidence[1].evidenceId = p.payload.evidence[0].evidenceId; },
    (p) => { p.metadata.game.version = "v0.112.0"; },
  ];
  for (const mutate of mutations) assert.equal(createSourceAdapter({ projection: project(mutate) }).available, false);
  const dir = mkdtempSync(join(tmpdir(), "sts2-shadow-"));
  try { const path = join(dir, "bad.json"); writeFileSync(path, '{"schemaVersion":'); assert.match(createSourceAdapter({ projectionPath: path }).error, /corrupt JSON/); }
  finally { rmSync(dir, { recursive: true, force: true }); }
});

test("HTTP exposes exactly one HTML view and two bounded implementation endpoints", async () => {
  const parsed = parsedRoomState("AXEBOTS_NORMAL", ["MONSTER.AXEBOT"]);
  await withServer(createSts2Handler({ read: () => parsed }, { sourceAdapter: adapter }), async (server) => {
    for (const path of ["/sts2", "/sts2/state", "/sts2/client.js"]) {
      const get = await request(server, path); const head = await request(server, path, "HEAD");
      assert.equal(get.status, 200, path); assert.equal(head.status, 200, path); assert.equal(head.body, "");
      assert.equal(Number(get.headers["content-length"]), Buffer.byteLength(get.body));
      assert.equal(head.headers["content-length"], get.headers["content-length"]);
      assert.equal(get.headers["cache-control"], "no-store");
      assert.match(get.headers["content-security-policy"], /default-src 'none'/);
      assert.equal(get.headers["x-frame-options"], "DENY");
    }
    const page = await request(server, "/sts2");
    assert.match(page.headers["content-type"], /^text\/html/);
    assert.match(page.body, /<title>StS2 Companion<\/title>/);
    assert.match(page.body, /src="\/sts2\/client\.js"/);
    const json = await request(server, "/sts2/state");
    assert.ok(Buffer.byteLength(json.body) <= 600_000);
    assert.equal(JSON.parse(json.body).encounter.canonicalId, "AXEBOTS_NORMAL");
    const client = await request(server, "/sts2/client.js"); assert.ok(Buffer.byteLength(client.body) <= 100_000);

    for (const removed of [
      "/sts2/", "/sts2/source", "/sts2/source/", "/sts2/source/state", "/sts2/source/client.js", "/sts2/source/nested",
      "/sts2/legacy", "/sts2/legacy/", "/sts2/legacy/state", "/sts2/legacy/client.js", "/sts2/legacy/nested",
    ]) {
      const get = await request(server, removed); const head = await request(server, removed, "HEAD");
      assert.equal(get.status, 404, removed); assert.equal(head.status, 404, removed); assert.equal(head.body, "");
      assert.match(get.headers["content-type"], /^text\/plain/);
    }
    assert.equal((await request(server, "/sts2?encounter=TEST_SUBJECT_BOSS")).status, 200);
    assert.equal((await request(server, "/sts2?encounter=NOPE")).status, 404);
    assert.equal((await request(server, "/sts2?encounter=A&encounter=B")).status, 400);
    assert.equal((await request(server, "/sts2", "POST")).status, 405);
    assert.equal((await request(server, "/sts2/nope")).status, 404);
  });
});

test("projection failure closes only the three implementation paths; removed views stay 404", async () => {
  const unavailable = createSourceAdapter({ projection: { nope: true } }); assert.equal(unavailable.available, false);
  await withServer(createSts2Handler({ read: () => state("AXEBOTS_NORMAL") }, { sourceAdapter: unavailable }), async (server) => {
    for (const path of ["/sts2", "/sts2/state", "/sts2/client.js"]) assert.equal((await request(server, path)).status, 503, path);
    for (const path of ["/sts2/source", "/sts2/source/state", "/sts2/legacy", "/sts2/legacy/state"]) assert.equal((await request(server, path)).status, 404, path);
  });
});

test("guide client is DOM-text-only and selector polling is stable", () => {
  assert.doesNotMatch(clientSource, /innerHTML|outerHTML|insertAdjacentHTML|document\.write/);
  assert.match(clientSource, /textContent = guideText\(text\)/);
  assert.match(clientSource, /getAll\("encounter"\)/);
  assert.match(clientSource, /encodeURIComponent\(manualQuery\[0\]\)/);
  assert.match(clientSource, /`\$\{basePath\}\/state/);
  assert.match(clientSource, /setInterval\(poll/);
  assert.doesNotMatch(clientSource, /\/source\/state|\/legacy/);
});

function collapsedText(node) {
  if (!node || typeof node !== "object") return String(node ?? "");
  if (node.tagName === "details") {
    const summary = node.children.find((child) => child?.tagName === "summary");
    return summary ? collapsedText(summary) : "";
  }
  return node._text + node.children.map(collapsedText).join(" ");
}
function descendants(node, result = []) {
  for (const child of node.children ?? []) { if (child && typeof child === "object") { result.push(child); descendants(child, result); } }
  return result;
}

test("collapsed DOM is practical while one Technical audit retains exact raw records", async () => {
  const payload = adapter.view(state(), "AXEBOTS_NORMAL");
  const { root } = await runShadowClient(payload);
  const collapsed = collapsedText(root);
  for (const heading of ["Possible roster", "Enemies & forms", "Opener, cycle & forks", "Effect signatures", "Death, phases & clocks", "What is not observed", "Technical audit"])
    assert.match(collapsed, new RegExp(heading));
  assert.doesNotMatch(collapsed, /MONSTER\.|BOOT_UP_MOVE|Boot Up|\bformula\b|\bgraph\b/i);
  assert.doesNotMatch(collapsed, /Checked editorial callouts|0 callouts/i);
  assert.match(root.textContent, /MONSTER\.AXEBOT/);
  assert.match(root.textContent, /BOOT_UP_MOVE/);
  assert.equal(descendants(root).filter((node) => node.className === "technical-audit").length, 1);
});

test("complex collapsed fixtures preserve practical lifecycle semantics without debug leakage", async () => {
  const fixtures = [
    ["BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER", [/Event fight clock/, /record that the event fight ran out of time/, /escape and leave the fight/]],
    ["TEST_SUBJECT_BOSS", [/completed respawns = 1/, /Adaptable revival/, /Test Subject death/]],
    ["OVICOPTER_NORMAL", [/reduce Hatch by 1/, /hatch with 19–22 HP below A8; 20–23 HP at A8\+/]],
    ["WATERFALL_GIANT_BOSS", [/remember Steam Eruption's current amount/, /snapshotted Steam Eruption amount/]],
    ["LIVING_FOG_NORMAL", [/perform Gas Bomb's checked attack/]],
  ];
  for (const [id, required] of fixtures) {
    const { root } = await runShadowClient(adapter.view(state(), id)); const collapsed = collapsedText(root);
    required.forEach((pattern) => assert.match(collapsed, pattern, id));
    assert.doesNotMatch(collapsed, /\b(?:MONSTER|POWER|SOURCE|RUNTIME)\.|\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b|ShouldPower|HasAmalgamDied|\bformula\b|\bAST\b|\bgraph\b/i, id);
  }
});

test("unchanged payload is retried after a transient render failure", async () => {
  const payload = adapter.view(state(), "AXEBOTS_NORMAL");
  const client = await runShadowClient(payload, { failCreateOnce: "article" });
  assert.doesNotMatch(collapsedText(client.root), /Technical audit/);
  await client.pollAgain();
  assert.match(collapsedText(client.root), /Technical audit/);
});

const qualifications = Object.freeze({ playerControllable: true, nonObvious: true, materiallyUseful: true, ordinaryStateRobust: true, sourceSupported: true, causallyExplainable: true, distinct: true });
function candidate(id, rank, language = "static-conditional") {
  return { id, distinctnessKey: `MECHANIC.${id}`, language, headline: `Editorial note ${rank}: the controlled choice changes the checked effect`, condition: "when the checked condition holds", causalBasis: "the controllable choice changes the cited consequence", rank, qualifications, basis: { factRefs: [`FACT.${id}`], conditionRefs: [`CONDITION.${id}`], causalRefs: [`CAUSE.${id}`] } };
}

test("renderer gives 0 callouts no chrome and preserves 1/3 expansion semantics", async () => {
  const renderCount = async (count) => {
    const payload = structuredClone(adapter.view(state(), "AXEBOTS_NORMAL"));
    const candidates = Array.from({ length: count }, (_, index) => candidate(`VISIBLE_${index + 1}`, index + 1));
    payload.encounter.presentation.callouts = compileCalloutCollection(candidates, {}, { collapsedLimit: 1 });
    return (await runShadowClient(payload)).root;
  };
  const zero = await renderCount(0); assert.doesNotMatch(collapsedText(zero), /callout/i);
  const one = await renderCount(1); assert.match(collapsedText(one), /Checked editorial callouts/); assert.match(collapsedText(one), /Editorial note 1/);
  const three = await renderCount(3); const collapsed = collapsedText(three);
  assert.match(collapsed, /Editorial note 1/); assert.match(collapsed, /Show all 3 callouts/);
  assert.doesNotMatch(collapsed, /Editorial note [23]/);
  assert.match(three.textContent, /Editorial note 2/); assert.match(three.textContent, /Editorial note 3/);
  assert.equal(descendants(three).filter((node) => node.className.includes("callout-expander")).length, 1);
});

test("version mismatch and unsupported observation boundaries stay honest", async () => {
  const mismatch = structuredClone(adapter.view(state(), "AXEBOTS_NORMAL"));
  mismatch.observation.installedVersion.version = "v9.9.9"; mismatch.observation.versionMatches = false;
  const rendered = await runShadowClient(mismatch);
  assert.match(collapsedText(rendered.root), /Version mismatch/);
  assert.match(collapsedText(rendered.root), /Installed v9\.9\.9 differs from checked v0\.111\.0/);
  const unresolved = await runShadowClient(adapter.view(state("NOT_A_CHECKED_ENCOUNTER", "combat")));
  assert.match(collapsedText(unresolved.root), /Unsupported encounter identity/);
  assert.match(collapsedText(unresolved.root), /Checked detail is available in Technical audit/);
  assert.doesNotMatch(collapsedText(unresolved.root), /NOT_A_CHECKED_ENCOUNTER/);
});

test("callout evidence, language, distinctness, and causality gates remain enforced", () => {
  assert.equal(compileCalloutCollection([candidate("STATIC", 1)], { observationRefs: [] }).total, 1);
  const live = compileCalloutCollection([candidate("NOW", 1, "live-imperative")]); assert.equal(live.total, 0); assert.match(live.rejected[0].reason, /current observed-state/);
  assert.equal(compileCalloutCollection([candidate("NOW", 1, "live-imperative")], { hasCurrentObservation: true, observationRefs: ["OBS.NOW"] }).total, 1);
  const duplicate = candidate("DUP", 2); duplicate.distinctnessKey = "MECHANIC.STATIC";
  assert.equal(compileCalloutCollection([candidate("STATIC", 1), duplicate]).total, 1);
  const missing = candidate("BAD", 1); missing.basis.factRefs = [];
  assert.throws(() => compileCalloutCollection([missing]), /factRefs/);
});

test("README and decision contract document only the one product view", () => {
  const readme = readFileSync(new URL("../README.md", import.meta.url), "utf8");
  const decision = readFileSync(new URL("../docs/decision-projection.md", import.meta.url), "utf8");
  assert.ok(Buffer.byteLength(readme) < 10_000);
  for (const text of ["http://127.0.0.1:3082/sts2", "https://qq-box.tail580136.ts.net/sts2", "docs/decision-projection.md", "Technical audit"])
    assert.ok(readme.includes(text), text);
  for (const document of [readme, decision]) {
    assert.doesNotMatch(document, /\/sts2\/(?:source|legacy)|compatibility alias|rollback view|legacy rollback/i);
  }
  assert.match(decision, /`\/sts2` consumes the checked compact projection/);
});
