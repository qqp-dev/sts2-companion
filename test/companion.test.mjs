import assert from "node:assert/strict";
import { createServer, request as httpRequest } from "node:http";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { encounterFor, encounterIds, scaleMechanicsText, scaleRange, scaledEncounter } from "../src/book.mjs";
import { createSts2Handler } from "../src/http.mjs";
import { apply, inject, name } from "../src/plugin.mjs";
import { createStateReader, parseLog, parseSave } from "../src/state.mjs";

const fixture = (name) => readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf8");

function request(server, path, method = "GET") {
  const address = server.address();
  return new Promise((resolve, reject) => {
    const req = httpRequest({ host: "127.0.0.1", port: address.port, path, method, agent: false }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.on("error", reject);
    req.end();
  });
}

async function withServer(handler, run) {
  const server = createServer((req, res) => handler(req, res));
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try { await run(server); }
  finally { server.closeAllConnections?.(); await new Promise((resolve) => server.close(resolve)); }
}

test("combat start and completion derive current versus last combat", () => {
  assert.deepEqual(parseLog(fixture("combat.log")), { status: "combat", encounterId: "DECIMILLIPEDE_ELITE" });
  assert.deepEqual(parseLog(fixture("completed.log")), { status: "last", encounterId: "DECIMILLIPEDE_ELITE" });
});

test("save history chooses the final monster, elite, or boss room", () => {
  assert.deepEqual(parseSave(fixture("current_run_mp.save")), {
    status: "last",
    encounterId: "DECIMILLIPEDE_ELITE",
    monsterIds: ["DECIMILLIPEDE_FRONT", "DECIMILLIPEDE_MIDDLE", "DECIMILLIPEDE_BACK"],
    actId: "HIVE",
    roomType: "elite",
  });
});

test("an idle log falls back to save history", () => {
  const dir = mkdtempSync(join(tmpdir(), "sts2-state-"));
  try {
    const logPath = join(dir, "godot.log");
    const savePath = join(dir, "current_run_mp.save");
    writeFileSync(logPath, fixture("idle.log"));
    writeFileSync(savePath, fixture("current_run_mp.save"));
    const state = createStateReader({ logPath, savePath }).read();
    assert.equal(state.status, "last");
    assert.equal(state.encounterId, "DECIMILLIPEDE_ELITE");
    assert.equal(state.source, "save");
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

test("A10 two-player Act 1 HP is scaled from the stored A8 range", () => {
  const deci = encounterFor("DECIMILLIPEDE_ELITE");
  assert.deepEqual(deci.lineup[0].hpA8, [46, 52]);
  assert.deepEqual(scaleRange([46, 52], { players: 2, act: 1, kind: "elite" }), [101, 114]);
});

test("attacks do not MP-scale while block and general buffs use their categories", () => {
  assert.equal(
    scaleMechanicsText("Deals 7 damage. Gains 2 Strength. Gains 18 Block.", { players: 2, act: 2, kind: "elite" }),
    "Deals 7 damage. Gains 4 Strength. Gains 36 Block.",
  );
  assert.equal(
    scaleMechanicsText("Deal 10 damage. Gains 22 Block and Vital Spark 3.", { players: 2, act: 2, kind: "elite" }),
    "Deal 10 damage. Gains 44 Block and Vital Spark 7.",
  );
  assert.equal(
    scaleMechanicsText("Removes 2 Strength from the player. Gains 2 Strength.", { players: 2, act: 2, kind: "elite" }),
    "Removes 2 Strength from the player. Gains 4 Strength.",
  );
  const louse = scaledEncounter(encounterFor("LOUSE_PROGENITOR_NORMAL"));
  assert.equal(louse.lineup[0].startsWithA9, "Curl Up 18");
  assert.equal(louse.lineup[0].startsWith, "Curl Up 43");
  assert.ok(encounterIds.length >= 80);
});

test("newest rotated godot log wins when godot.log is stale", () => {
  const root = mkdtempSync(join(tmpdir(), "sts2-rotate-"));
  try {
    const logs = join(root, "logs");
    mkdirSync(logs);
    const current = join(logs, "godot.log");
    const rotated = join(logs, "godot2026-01-01.log");
    writeFileSync(current, "Godot boot only\n");
    writeFileSync(rotated, "Creating NCombatRoom with mode=ActiveCombat encounter=MAWLER_NORMAL.\n");
    utimesSync(current, new Date(1_000), new Date(1_000));
    utimesSync(rotated, new Date(2_000), new Date(2_000));
    const state = createStateReader({ root }).read();
    assert.equal(state.status, "combat");
    assert.equal(state.encounterId, "MAWLER_NORMAL");
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("unknown encounter remains a successful visible page and state", async () => {
  const reader = { read: () => ({ status: "combat", encounterId: "EVENT_ODDBALL_ENCOUNTER", monsterIds: [] }) };
  const handler = createSts2Handler(reader);
  await withServer(handler, async (server) => {
    const page = await request(server, "/sts2");
    assert.equal(page.status, 200);
    assert.match(page.body, /EVENT_ODDBALL_ENCOUNTER/);
    assert.match(page.headers["content-security-policy"], /default-src 'none'/);
    assert.equal(page.headers["cache-control"], "no-store");
    const state = await request(server, "/sts2/state");
    assert.equal(state.status, 200);
    assert.equal(JSON.parse(state.body).encounterId, "EVENT_ODDBALL_ENCOUNTER");
  });
});

test("handler methods, exact routes, and prefix behavior are bounded", async () => {
  const handler = createSts2Handler({ read: () => ({ status: "idle", encounterId: null, monsterIds: [] }) });
  await withServer(handler, async (server) => {
    assert.equal((await request(server, "/sts2/other")).status, 404);
    assert.equal((await request(server, "/sts2", "POST")).status, 405);
    const head = await request(server, "/sts2/state", "HEAD");
    assert.equal(head.status, 200);
    assert.equal(head.body, "");
  });
});

test("plugin identity, injection, loopback refusal, and prefix registration", () => {
  assert.equal(name, "sts2-companion");
  assert.deepEqual(inject, ["webServer"]);
  assert.throws(() => apply({ webServer: { host: "0.0.0.0" } }), /non-loopback/);

  let route;
  let disposed = false;
  const ctx = {
    webServer: { host: "127.0.0.1", register(value) { route = value; return () => { disposed = true; }; } },
    effect(fn) { const cleanup = fn(); cleanup(); },
  };
  apply(ctx, { logPath: "/missing/godot.log", savePath: "/missing/current_run_mp.save" });
  assert.equal(route.kind, "prefix");
  assert.equal(route.path, "/sts2");
  assert.equal(typeof route.handler, "function");
  assert.equal(disposed, true);
});
