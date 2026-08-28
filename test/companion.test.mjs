import assert from "node:assert/strict";
import { createServer, request as httpRequest } from "node:http";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { bookMeta, encounterFor, encounterIds, scaleMechanicsText, scaleRange, scaledEncounter } from "../src/book.mjs";
import { createSts2Handler } from "../src/http.mjs";
import { apply, inject, name } from "../src/plugin.mjs";
import { createStateReader, parseLog, parseReleaseInfo, parseSave } from "../src/state.mjs";

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

test("v0.111.0 Axebot article values and Stock cycle are authoritative", () => {
  const axebot = encounterFor("AXEBOTS_NORMAL");
  const moves = Object.fromEntries(axebot.lineup[0].moves.map((move) => [move.name, move.textA9]));
  assert.equal(moves["Hammer Uppercut"], "Deals 18 damage. Applies 2 Weak and 2 Frail.");
  assert.equal(moves["The One-Two"], "Deals 11×2 damage.");
  assert.equal(axebot.lineup[0].pattern.type, "cycle");
  assert.match(axebot.lineup[0].pattern.text, /Hammer Uppercut.*The One-Two/i);
  assert.ok(axebot.rules.some((rule) => /\+10 Max HP/i.test(rule)));
});

test("v0.111.0 Exoskeleton and Entomancer A8 HP fixtures", () => {
  assert.deepEqual(encounterFor("EXOSKELETONS_WEAK").lineup[0].hpA8, [26, 30]);
  assert.deepEqual(encounterFor("EXOSKELETONS_NORMAL").lineup[0].hpA8, [26, 30]);
  assert.deepEqual(encounterFor("ENTOMANCER_ELITE").lineup[0].hpA8, [165]);
});

test("all remaining v0.111.0 Enemies patch magnitudes win", () => {
  const move = (encounterId, moveName) => encounterFor(encounterId).lineup[0].moves.find((item) => item.name === moveName).textA9;
  assert.equal(move("MECHA_KNIGHT_ELITE", "Flamethrower"), "Deals 12 damage. Adds 4 Burn to your hand.");
  assert.equal(encounterFor("GLOBE_HEAD_NORMAL").lineup[0].startsWithA9, "Galvanic 8");
  assert.equal(move("LOUSE_PROGENITOR_NORMAL", "Curl and Grow"), "Gains 18 Block. Gains 7 Strength.");
  assert.equal(move("SOUL_FYSH_BOSS", "De-Gas"), "Deals 18 damage.");
});

test("book provenance targets the public beta and never uses the fabricated pattern stub", () => {
  assert.equal(bookMeta.targetVersion, "v0.111.0");
  assert.equal(bookMeta.targetBranch, "public-beta");
  assert.match(bookMeta.harvestedAt, /Z$/);
  assert.ok(bookMeta.wikiPages.length >= 70);
  assert.match(bookMeta.patchPage.title, /V0\.111\.0/);
  for (const id of encounterIds) {
    for (const body of encounterFor(id).lineup) {
      assert.notEqual(body.pattern.text, "Uses the listed moves; exact opener and repeat constraints vary.");
    }
  }
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

test("article Death Blow intent is retained as an extra rule", () => {
  const fog = encounterFor("LIVING_FOG_NORMAL");
  const gasBomb = fog.lineup.find((body) => body.displayName === "Gas Bomb");
  assert.equal(gasBomb.moves[0].intent, "Death Blow");
  assert.ok(fog.rules.some((rule) => /Death Blow:.*Dies/i.test(rule)));
});

test("startsWith scales HP and general buffs but not durations or counts", () => {
  const lag = scaledEncounter(encounterFor("LAGAVULIN_MATRIARCH_BOSS"));
  assert.equal(lag.lineup[0].startsWithA9, "Plating 12; Asleep 3");
  assert.equal(lag.lineup[0].startsWith, "Plating 26; Asleep 3");

  const beetle = scaledEncounter(encounterFor("SLUMBERING_BEETLE_NORMAL"));
  assert.equal(beetle.lineup[0].startsWithA9, "Plating 18; Slumber 3");
  assert.equal(beetle.lineup[0].startsWith, "Plating 43; Slumber 3");

  const gremlin = scaledEncounter(encounterFor("GREMLIN_MERC_NORMAL"));
  assert.equal(gremlin.lineup[0].startsWithA9, "Surprise 1; Thievery 20");
  assert.equal(gremlin.lineup[0].startsWith, "Surprise 1; Thievery 20");

  const aeon = scaledEncounter(encounterFor("AEONGLASS_BOSS"));
  assert.equal(aeon.lineup[0].startsWithA9, "Withering Presence; Artifact 3");
  assert.equal(aeon.lineup[0].startsWith, "Withering Presence; Artifact 3");

  const deci = scaledEncounter(encounterFor("DECIMILLIPEDE_ELITE"));
  assert.equal(deci.lineup[0].startsWith, "Reattach 60");
});

test("Gains PowerName N HP thresholds scale like Vital Spark", () => {
  const beast = scaledEncounter(encounterFor("CEREMONIAL_BEAST_BOSS"));
  assert.deepEqual(beast.lineup[0].hp, [576]);
  assert.equal(
    beast.lineup[0].moves[0].sourceA9,
    "Gains Plow 160. When its HP drops to that amount, it becomes Stunned and loses all Strength.",
  );
  assert.equal(
    beast.lineup[0].moves[0].text,
    "Gains Plow 352. When its HP drops to that amount, it becomes Stunned and loses all Strength.",
  );
  assert.equal(
    scaleMechanicsText("Gains Plow 160. When its HP drops to that amount.", { players: 2, act: 1, kind: "boss" }),
    "Gains Plow 352. When its HP drops to that amount.",
  );
});

test("Glory Doormaker is a known A10 2P book encounter", () => {
  const door = encounterFor("DOORMAKER_BOSS");
  assert.equal(door.act, "Glory");
  assert.equal(door.kind, "boss");
  assert.equal(door.lineup[0].displayName, "Doormaker");
  assert.deepEqual(door.lineup[0].hpA8, [512]);
  const scaled = scaledEncounter(door);
  assert.equal(scaled.known, true);
  assert.deepEqual(scaled.lineup[0].hp, [1331]);
  assert.ok(scaled.rules.some((rule) => /Door spawns first/i.test(rule)));
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

test("release_info is local, injectable, and limited to version and branch", () => {
  assert.deepEqual(parseReleaseInfo('{"version":"v0.111.0","branch":"v0.111.0","commit":"ignored"}'), {
    version: "v0.111.0",
    branch: "v0.111.0",
  });
  const dir = mkdtempSync(join(tmpdir(), "sts2-release-"));
  try {
    const releaseInfoPath = join(dir, "release_info.json");
    writeFileSync(releaseInfoPath, '{"version":"v0.111.0","branch":"v0.111.0"}');
    const state = createStateReader({
      logPath: join(dir, "missing.log"),
      savePath: join(dir, "missing.save"),
      releaseInfoPath,
    }).read();
    assert.deepEqual(state.releaseInfo, { version: "v0.111.0", branch: "v0.111.0" });
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

test("version mismatch and leftover unknown pattern are visible known-unknowns", async () => {
  const mismatch = {
    status: "combat",
    encounterId: "OVICOPTER_NORMAL",
    monsterIds: [],
    releaseInfo: { version: "v0.110.1", branch: "v0.110.1" },
  };
  await withServer(createSts2Handler({ read: () => mismatch }), async (server) => {
    const page = await request(server, "/sts2");
    assert.equal(page.status, 200);
    assert.match(page.body, /Version mismatch/);
    assert.match(page.body, /Book v0\.111\.0 · public-beta/);
    assert.match(page.body, /Game v0\.110\.1 · v0\.110\.1/);
    assert.match(page.body, /known unknown · pattern/);
    assert.match(page.body, /Tough Egg waits while its Hatch timer/i);
  });
});

test("unknown encounter remains a successful visible page and state", async () => {
  const reader = { read: () => ({ status: "combat", encounterId: "EVENT_ODDBALL_ENCOUNTER", monsterIds: ["MYSTERY_BODY"] }) };
  const handler = createSts2Handler(reader);
  await withServer(handler, async (server) => {
    const page = await request(server, "/sts2");
    assert.equal(page.status, 200);
    assert.match(page.body, /EVENT_ODDBALL_ENCOUNTER/);
    assert.match(page.body, /MYSTERY_BODY/);
    assert.match(page.body, /HP unknown/);
    assert.match(page.body, /Version unknown/);
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
