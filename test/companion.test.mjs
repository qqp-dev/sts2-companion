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
  assert.equal(moves["Boot Up"], "Gains 15 Block and 4/8 Strength.");
  assert.equal(axebot.lineup[0].pattern.type, "cycle");
  assert.match(axebot.lineup[0].pattern.text, /Hammer Uppercut.*The One-Two/i);
  assert.ok(axebot.rules.some((rule) => /\+10 Max HP/i.test(rule)));
});

test("slash spawn alternatives each scale (Axebot Boot Up 4/8 → 9/19)", () => {
  const axebot = scaledEncounter(encounterFor("AXEBOTS_NORMAL"));
  const boot = axebot.lineup[0].moves.find((move) => move.name === "Boot Up");
  assert.equal(boot.sourceA9, "Gains 15 Block and 4/8 Strength.");
  assert.equal(boot.text, "Gains 30 Block and 9/19 Strength.");
  assert.equal(
    scaleMechanicsText("Gains 15 Block and 4/8 Strength.", { players: 2, act: 3, kind: "hallway" }),
    "Gains 30 Block and 9/19 Strength.",
  );
});

test("last-body pattern prose does not swallow wiki chrome", () => {
  const nectar = encounterFor("BOWLBUGS_NORMAL").lineup.find((body) => body.displayName === "Bowlbug (Nectar)");
  assert.equal(nectar.pattern.text, "Opens with Thrash, then uses Buff once, then uses Thrash every turn after.");
  assert.equal(
    encounterFor("THE_OBSCURA_NORMAL").lineup.find((body) => body.displayName === "Parafright").pattern.text,
    "Uses Slam every turn.",
  );
  for (const id of ["TUNNELER_NORMAL", "TUNNELER_WEAK", "PHROG_PARASITE_ELITE", "BOWLBUGS_NORMAL", "THE_OBSCURA_NORMAL"]) {
    for (const body of encounterFor(id).lineup) {
      assert.doesNotMatch(body.pattern.text, /Enemy2Nav|Category:/);
    }
  }
  for (const id of encounterIds) {
    for (const body of encounterFor(id).lineup) {
      assert.doesNotMatch(body.pattern.text, /Enemy2Nav|Category:/);
    }
  }
});

test("Test Subject tabber chrome is excluded from every phase pattern", () => {
  const subject = encounterFor("TEST_SUBJECT_BOSS");
  for (const body of subject.lineup) {
    assert.doesNotMatch(body.pattern.text, /\|-\||Type\s*=\s*Boss|Power Infobox/i);
  }
});

test("scaled pattern prose matches rendered HP and buff magnitudes", () => {
  const decimillipede = scaledEncounter(encounterFor("DECIMILLIPEDE_ELITE"));
  for (const body of decimillipede.lineup) {
    assert.match(body.pattern.text, /Reattach to revive with 60 HP/i);
    assert.doesNotMatch(body.pattern.text, /revive with 25 HP/i);
  }

  const subject = scaledEncounter(encounterFor("TEST_SUBJECT_BOSS"));
  assert.match(subject.lineup[0].pattern.text, /Enrage 7/i);
  assert.doesNotMatch(subject.lineup[0].pattern.text, /Enrage 3/i);
  for (const body of subject.lineup.slice(1)) {
    assert.match(body.pattern.text, new RegExp(`Revives with ${body.hp[0]} HP`, "i"));
    assert.doesNotMatch(body.pattern.text, /Revives with (?:212|313) HP/i);
  }

  const effigy = scaledEncounter(encounterFor("BYGONE_EFFIGY_ELITE"));
  const body = effigy.lineup[0];
  const wake = body.moves.find((move) => move.name === "Wake");
  assert.match(body.pattern.text, /gains 22 Strength/i);
  assert.match(wake.text, /Gains 22 Strength/i);
  assert.doesNotMatch(body.pattern.text, /gains 10 Strength/i);
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

test("opener and added buff prose scales without changing removed buffs", () => {
  assert.equal(
    scaleMechanicsText(
      "Starts with Enrage 3. Starts Asleep with 12 Plating. Adds 3 Steam Eruption. Has gained 2 Strength. Removes 2 Strength.",
      { players: 2, act: 3, kind: "boss" },
    ),
    "Starts with Enrage 7. Starts Asleep with 31 Plating. Adds 7 Steam Eruption. Has gained 5 Strength. Removes 2 Strength.",
  );
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

test("Decimillipede timing scales Reattach HP like rules", () => {
  const deci = scaledEncounter(encounterFor("DECIMILLIPEDE_ELITE"));
  assert.ok(deci.rules.some((rule) => /revive with 60 HP/i.test(rule)));
  assert.ok(deci.timing.some((line) => /revive with 60 HP/i.test(line)));
  assert.ok(deci.timing.every((line) => !/revive with 25 HP/i.test(line)));
  assert.ok(deci.rules.every((rule) => !/revive with 25 HP/i.test(rule)));
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

test("qq chrome is black and square and omits matching version chrome", async () => {
  const matching = {
    status: "combat",
    encounterId: "DECIMILLIPEDE_ELITE",
    monsterIds: ["DECIMILLIPEDE_FRONT", "DECIMILLIPEDE_MIDDLE", "DECIMILLIPEDE_BACK"],
    releaseInfo: { version: "v0.111.0", branch: "public-beta" },
  };
  await withServer(createSts2Handler({ read: () => matching }), async (server) => {
    const page = await request(server, "/sts2");
    assert.equal(page.status, 200);
    assert.match(page.body, /<meta name="theme-color" content="#000">/);
    assert.match(page.body, /--page:#000;/);
    assert.match(page.body, /background:#000;/);
    assert.match(page.body, /color:#e8e8e8;/);
    assert.match(page.body, /font-family:"Geist UI",ui-sans-serif,system-ui/);
    assert.match(page.body, /--chrome-size:1rem;/);
    assert.match(page.body, /<div class="status-line status-combat"><i class="status-dot"[^>]*><\/i>combat<\/div>/);
    assert.match(page.body, /\.status-combat\{color:var\(--combat\)\}/);
    assert.match(page.body, /--combat:#f7ce74;/);
    assert.match(page.body, /<footer class="source"><div class="scale-note">scaling ·/);
    assert.match(page.body, /<div class="starts">starts ·/);
    assert.doesNotMatch(page.body, /IN COMBAT|LAST COMBAT|status-badge/);
    assert.doesNotMatch(page.body, /border-radius:99rem|gradient|box-shadow/);
    assert.doesNotMatch(page.body, /<div class="version-card|version-match/i);
    assert.doesNotMatch(page.body, /DECIMILLIPEDE_ELITE|DECIMILLIPEDE_FRONT/);
    assert.equal(page.body.match(/a10 · 2p/g)?.length, 1);

    const client = await request(server, "/sts2/client.js");
    assert.equal(client.status, 200);
    assert.match(client.body, /version\.matches === true\) return null/);
    assert.match(client.body, /showRawId && body\.monsterId/);
    assert.doesNotMatch(client.body, /IN COMBAT|LAST COMBAT|status-badge/);
  });
});

test("idle and last states use quiet lowercase chrome", async () => {
  let current = { status: "idle", encounterId: null, monsterIds: [], releaseInfo: null };
  await withServer(createSts2Handler({ read: () => current }), async (server) => {
    const idle = await request(server, "/sts2");
    assert.match(idle.body, /<p class="idle-copy">no run \/ no combat · waiting for the next fight<\/p>/);
    assert.match(idle.body, /version unknown/);
    assert.doesNotMatch(idle.body, /idle-mark|idle-title|◇/);

    current = {
      status: "last",
      encounterId: "AXEBOTS_NORMAL",
      monsterIds: ["AXEBOT"],
      releaseInfo: { version: "v0.111.0", branch: "public-beta" },
    };
    const last = await request(server, "/sts2");
    assert.match(last.body, /<div class="status-line status-last"><i class="status-dot"[^>]*><\/i>last<\/div>/);
    assert.match(last.body, /\.status-last\{color:var\(--muted\)\}/);
    assert.doesNotMatch(last.body, /LAST COMBAT|AXEBOTS_NORMAL|class="monster-id"|<div class="version-card/);
  });
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
    assert.match(page.body, /version mismatch/);
    assert.match(page.body, /book v0\.111\.0 · public-beta/);
    assert.match(page.body, /game v0\.110\.1 · v0\.110\.1/);
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
    assert.match(page.body, /version unknown/);
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
