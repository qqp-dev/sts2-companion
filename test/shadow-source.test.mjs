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
const clientSource = readFileSync(new URL("../src/source-client.js", import.meta.url), "utf8");
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
    getElementById: (id) => id === "source-encounter" ? root : null,
    createElement: (tagName) => {
      if (tagName === pendingFailure) { pendingFailure = null; throw new Error(`transient ${tagName} creation failure`); }
      return new TestNode(tagName);
    },
  };
  const window = {
    location: { search: "?encounter=AXEBOTS_NORMAL" },
    setInterval: (callback) => { interval = callback; return 1; },
  };
  const fetch = async () => ({ json: async () => structuredClone(payload) });
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
  assert.doesNotMatch(root.textContent, /DECIMILLIPEDE_(?:FRONT|MIDDLE|BACK) · unresolved/);
  for (const position of ["FRONT", "MIDDLE", "BACK"]) assert.match(root.textContent, new RegExp(`DECIMILLIPEDE_${position} → MONSTER\.DECIMILLIPEDE_SEGMENT_${position}`));
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

test("canonical source-first HTTP has exact routes, compatibility aliases, security, and query handling", async () => {
  const parsed = parsedRoomState("AXEBOTS_NORMAL", ["MONSTER.AXEBOT"]);
  const reader = { read: () => parsed };
  await withServer(createSts2Handler(reader, { sourceAdapter: adapter }), async (server) => {
    for (const path of ["/sts2", "/sts2/state", "/sts2/client.js"]) {
      const get = await request(server, path); const head = await request(server, path, "HEAD");
      assert.equal(get.status, 200); assert.equal(head.status, 200); assert.equal(head.body, "");
      assert.equal(Number(get.headers["content-length"]), Buffer.byteLength(get.body)); assert.equal(head.headers["content-length"], get.headers["content-length"]);
      assert.equal(get.headers["cache-control"], "no-store"); assert.match(get.headers["content-security-policy"], /default-src 'none'/); assert.equal(get.headers["x-frame-options"], "DENY");
    }
    const page = await request(server, "/sts2");
    assert.match(page.body, /<title>StS2 Companion<\/title>/);
    assert.match(page.body, /src="\/sts2\/client\.js"/);
    assert.doesNotMatch(page.body, /legacy rollback|non-default|source shadow/i);
    const json = await request(server, "/sts2/state"); assert.ok(Buffer.byteLength(json.body) < 600_001);
    const capsule = JSON.parse(json.body); assert.equal(capsule.encounter.canonicalId, "AXEBOTS_NORMAL");
    assert.deepEqual(capsule.encounter.observedBodies, [{ observedId: "AXEBOT", observedWireId: "MONSTER.AXEBOT", canonicalModel: "MONSTER.AXEBOT", resolved: true }]);

    for (const [alias, canonical] of [["/sts2/source", "/sts2"], ["/sts2/source/state", "/sts2/state"], ["/sts2/source/client.js", "/sts2/client.js"]]) {
      const aliased = await request(server, alias), primary = await request(server, canonical);
      assert.equal(aliased.status, 200); assert.equal(aliased.body, primary.body);
    }
    assert.equal((await request(server, "/sts2?encounter=TEST_SUBJECT_BOSS")).status, 200);
    assert.equal((await request(server, "/sts2?encounter=NOPE")).status, 404);
    assert.equal((await request(server, "/sts2?encounter=A&encounter=B")).status, 400);
    const injection = await request(server, "/sts2?encounter=%3Cscript%3Ealert(1)%3C/script%3E"); assert.equal(injection.status, 404); assert.match(injection.headers["content-type"], /^text\/plain/);
    assert.equal((await request(server, "/sts2", "POST")).status, 405); assert.equal((await request(server, "/sts2/nope")).status, 404);
  });
});

test("bad projection fails canonical source routes closed while legacy rollback remains available", async () => {
  const bad = createSourceAdapter({ projection: project((p) => { p.schemaVersion = 99; }) });
  const parsed = parsedRoomState("AXEBOTS_NORMAL", ["MONSTER.AXEBOT"]);
  const reader = { read: () => parsed };
  const legacyPaths = ["/sts2/legacy", "/sts2/legacy/state", "/sts2/legacy/client.js"];
  const baseline = new Map();
  await withServer(createSts2Handler(reader, { sourceAdapter: adapter }), async (server) => {
    for (const path of legacyPaths) baseline.set(path, await request(server, path));
  });
  await withServer(createSts2Handler(reader, { sourceAdapter: bad }), async (server) => {
    for (const path of ["/sts2", "/sts2/state", "/sts2/client.js", "/sts2/source", "/sts2/source/state", "/sts2/source/client.js"]) {
      const response = await request(server, path); assert.equal(response.status, 503); assert.match(response.body, /source projection unavailable/);
    }
    for (const path of legacyPaths) {
      const response = await request(server, path); const healthy = baseline.get(path);
      assert.equal(response.status, 200); assert.equal(response.body, healthy.body);
      for (const header of ["content-type", "content-length", "cache-control", "content-security-policy"]) assert.equal(response.headers[header], healthy.headers[header]);
    }
    assert.equal(JSON.parse((await request(server, "/sts2/legacy/state")).body).encounterId, "AXEBOTS_NORMAL");
    assert.match((await request(server, "/sts2/legacy")).body, /legacy rollback/i);
  });
});

test("shadow client is DOM text-only and manual polling retains the selector", () => {
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write/.test(clientSource));
  assert.match(clientSource, /\.textContent = String\(text\)/); assert.match(clientSource, /getAll\("encounter"\)/);
  assert.match(clientSource, /encodeURIComponent\(manualQuery\[0\]\)/); assert.match(clientSource, /setInterval\(poll/);
  assert.match(clientSource, /`\$\{basePath\}\/state/); assert.doesNotMatch(clientSource, /\/source\/state/);
});

test("shadow client renders move-bearing capsules through proof", async () => {
  const capsule = adapter.view(state(), "AXEBOTS_NORMAL");
  const { root } = await runShadowClient(capsule);
  for (const section of ["Move possibilities and ordered operations", "Move graph:", "Lifecycle and core boundaries", "Provenance and evidence"]) {
    assert.match(root.textContent, new RegExp(section));
  }
});

test("Battleworn phone surface exposes its clock and exact lifecycle audit payload", async () => {
  const capsule = adapter.view(state(), "BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER");
  const { root } = await runShadowClient(capsule);
  for (const text of [
    "Event Combat · Battle Time Limit", "After Side Turn End", "Countdown · decrement Battleworn Dummy Time Limit by 1",
    "set RanOutOfTime = true", "escape through the checked removal graph and remove the creature node",
    "ordinary centralized victory check", "Exact removal, dispatch, completion & lifecycle facts",
    "battleTimeLimit", "LIFECYCLE.EVENT.BATTLEWORN.TIMEOUT", "removeCreatureNode", "ordinaryCentralizedVictoryByRef",
  ]) assert.match(root.textContent, new RegExp(text));
  assert.doesNotMatch(JSON.stringify(capsule.encounter.lifecycle.mechanics), /BATTLEWORN_DUMMY_EVENT_V[23]_ENCOUNTER|DENSE_VEGETATION/);
});

test("shadow client retries an unchanged payload after a render failure", async () => {
  const capsule = adapter.view(state(), "AXEBOTS_NORMAL");
  const client = await runShadowClient(capsule, { failCreateOnce: "article" });
  assert.doesNotMatch(client.root.textContent, /Provenance and evidence/);
  await client.pollAgain();
  assert.match(client.root.textContent, /Provenance and evidence/);
});

const qualifications = Object.freeze({ playerControllable: true, nonObvious: true, materiallyUseful: true, ordinaryStateRobust: true, sourceSupported: true, causallyExplainable: true, distinct: true });
function candidate(id, rank, language = "static-conditional") {
  return { id, distinctnessKey: `MECHANIC.${id}`, language, headline: `${id}: when the source condition holds, the controlled choice changes the effect`, condition: "when the checked source condition holds", causalBasis: "the controllable choice changes the cited consequence", rank, qualifications, basis: { factRefs: [`FACT.${id}`], conditionRefs: [`CONDITION.${id}`], causalRefs: [`CAUSE.${id}`] } };
}
test("callout contract preserves evidence-gated 0, 1, and 3 collections with visible subset count", () => {
  const zero = compileCalloutCollection([]); assert.equal(zero.total, 0); assert.match(zero.emptyReason, /0 source-qualified/);
  const one = compileCalloutCollection([candidate("ONE", 1)]); assert.equal(one.total, 1); assert.equal(one.hasMore, false);
  const three = compileCalloutCollection([candidate("THREE", 3), candidate("ONE", 1), candidate("TWO", 2)], {}, { collapsedLimit: 1 });
  assert.deepEqual(three.all.map((row) => row.id), ["ONE", "TWO", "THREE"]); assert.equal(three.total, 3); assert.equal(three.collapsedCount, 1); assert.equal(three.hasMore, true); assert.equal(three.expandPathRequired, true);
});

test("shadow renderer supports honest 0, 1, and 3 callouts with one expand path to every record", async () => {
  const renderCount = async (count) => {
    const capsule = structuredClone(adapter.view(state(), "AXEBOTS_NORMAL"));
    const candidates = Array.from({ length: count }, (_, index) => candidate(`VISIBLE_${index + 1}`, index + 1));
    capsule.encounter.presentation.callouts = compileCalloutCollection(candidates, {}, { collapsedLimit: 1 });
    return (await runShadowClient(capsule)).root;
  };
  const descendants = (node, result = []) => {
    for (const child of node.children ?? []) if (child && typeof child === "object") { result.push(child); descendants(child, result); }
    return result;
  };

  const zero = await renderCount(0);
  assert.match(zero.textContent, /Tactical callouts · 0/);
  assert.doesNotMatch(zero.textContent, /VISIBLE_1/);

  const one = await renderCount(1), oneNodes = descendants(one);
  assert.match(one.textContent, /Tactical callouts · 1/);
  assert.match(one.textContent, /1 of 1 shown/);
  const oneCards = oneNodes.filter((node) => node.className === "callout-card");
  assert.equal(oneCards.length, 1);
  assert.ok(oneCards[0].children.filter((node) => node.tagName !== "details").length <= 3, "one callout uses at most three visible text rows");
  assert.match(one.textContent, /FACT.VISIBLE_1/);

  const three = await renderCount(3), threeNodes = descendants(three);
  assert.match(three.textContent, /Tactical callouts · 3/);
  assert.match(three.textContent, /1 of 3 shown · more available below/);
  assert.match(three.textContent, /Show all 3 source-qualified callouts/);
  for (const id of ["VISIBLE_1", "VISIBLE_2", "VISIBLE_3"]) {
    assert.match(three.textContent, new RegExp(id));
    assert.match(three.textContent, new RegExp(`FACT\.${id}`));
  }
  assert.equal(threeNodes.filter((node) => node.className.includes("callout-expander")).length, 1);
  const threeCards = threeNodes.filter((node) => node.className === "callout-card");
  assert.equal(threeCards.length, 4, "one collapsed card plus all three in the single expansion");
  assert.ok(threeCards.every((card) => card.children.filter((node) => node.tagName !== "details").length <= 3));
});

test("shadow renderer keeps version mismatch and unsupported observation boundaries visible", async () => {
  const mismatch = structuredClone(adapter.view(state(), "AXEBOTS_NORMAL"));
  mismatch.observation.installedVersion.version = "v9.9.9"; mismatch.observation.versionMatches = false;
  const { root } = await runShadowClient(mismatch);
  assert.match(root.textContent, /VERSION MISMATCH/);
  assert.match(root.textContent, /Installed v9\.9\.9 differs from checked v0\.111\.0/);

  const unresolved = adapter.view(state("NOT_A_CHECKED_ENCOUNTER", "combat"));
  const failed = await runShadowClient(unresolved);
  assert.match(failed.root.textContent, /Unsupported encounter identity/);
  assert.match(failed.root.textContent, /has no checked source identity/);
});

test("callout language, distinctness, basis, and phase-control causality are enforced", () => {
  assert.equal(compileCalloutCollection([candidate("STATIC", 1)], { observationRefs: [] }).total, 1);
  const live = compileCalloutCollection([candidate("NOW", 1, "live-imperative")]); assert.equal(live.total, 0); assert.match(live.rejected[0].reason, /current observed-state/);
  assert.equal(compileCalloutCollection([candidate("NOW", 1, "live-imperative")], { hasCurrentObservation: true, observationRefs: ["OBS.NOW"] }).total, 1);
  const duplicate = candidate("DUP", 2); duplicate.distinctnessKey = "MECHANIC.STATIC";
  const deduped = compileCalloutCollection([candidate("STATIC", 1), duplicate]); assert.equal(deduped.total, 1); assert.deepEqual(deduped.deduplicated.map((row) => row.id), ["DUP"]);
  const phase = candidate("STAGGER", 1); phase.mechanic = "phase-control"; phase.phaseControl = { controllableChoice: "choose the cited phase-control action", staggeredEffect: "keeps the two cited attacks on separate turns", synchronizedSpikeAvoided: "avoids moving both attacks onto the cited turn", mechanismRefs: ["FACT.PHASE", "CAUSE.STAGGER"] };
  assert.equal(compileCalloutCollection([phase]).all[0].phaseControl.mechanismRefs.length, 2);
  const missingBasis = candidate("BAD", 1); missingBasis.basis.factRefs = [];
  assert.throws(() => compileCalloutCollection([missingBasis]), /factRefs/);
});

test("README is concise and names canonical, compatibility, rollback, and authority boundaries", () => {
  const readme = readFileSync(new URL("../README.md", import.meta.url), "utf8"); assert.ok(Buffer.byteLength(readme) < 10_000);
  for (const text of ["docs/source-migration-ledger.md", "docs/source-world-model.md", "docs/decision-projection.md", "http://127.0.0.1:3082/sts2", "https://qq-box.tail580136.ts.net/sts2", "`/sts2/source` is a compatibility alias", "`/sts2/legacy`"]) assert.ok(readme.includes(text), text);
  assert.doesNotMatch(readme, /existing stable page remains the default|never switch `?\/sts2`? to source-first|source shadow.{0,40}opt-in/i);
  const decision = readFileSync(new URL("../docs/decision-projection.md", import.meta.url), "utf8");
  assert.match(decision, /Canonical `\/sts2`.*checked[\s\S]{0,160}compact projection/);
  assert.match(decision, /`\/sts2\/source` (?:is|remains) a compatibility alias/);
  assert.match(decision, /`\/sts2\/legacy`[^.]{0,100}(?:non-default|not the primary product)/);
  assert.doesNotMatch(decision, /existing stable page remains the default|source shadow.{0,40}opt-in|legacy[^.]{0,80}(?:is|remains) (?:the )?default/i);
  assert.ok(readFileSync(new URL("../docs/source-migration-ledger.md", import.meta.url), "utf8").length > 40_000);
});
