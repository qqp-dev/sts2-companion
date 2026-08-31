import assert from "node:assert/strict";
import { createServer, request as httpRequest } from "node:http";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { bookMeta, encounterFor, encounterIds, scaleMechanicsText, scaleRange, scaledEncounter, scalingCategories } from "../src/book.mjs";
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

test("two-player Act 1 HP is scaled from the stored A8 range", () => {
  const deci = encounterFor("DECIMILLIPEDE_ELITE");
  assert.deepEqual(deci.lineup[0].hpA8, [46, 52]);
  assert.deepEqual(scaleRange([46, 52], { players: 2, act: 1, kind: "elite" }), [101, 114]);
});

test("v0.111.0 Axebot game override and Stock cycle are authoritative", () => {
  const axebot = encounterFor("AXEBOTS_NORMAL");
  const moves = Object.fromEntries(axebot.lineup[0].moves.map((move) => [move.name, move.textA9]));
  assert.equal(moves["Hammer Uppercut"], "Deals 18 damage. Applies 2 Weak and 2 Frail.");
  assert.equal(moves["The One-Two"], "Deals 11×2 damage.");
  assert.equal(moves["Boot Up"], "Gains 15 Block and 4/8 Strength.");
  assert.deepEqual(axebot.lineup[0].hpA8, [76, 86]);
  assert.match(axebot.lineup[0].sourceFlags.join(" "), /GAME OVERRIDE: hpA8 article=\[78, 86\] game=\[76, 86\]/);
  assert.equal(axebot.lineup[0].pattern.type, "cycle");
  assert.match(axebot.lineup[0].pattern.text, /Hammer Uppercut.*The One-Two/i);
  assert.ok(axebot.rules.some((rule) => /\+10 Max HP/i.test(rule)));
});

test("Axebot Boot Up scales block but keeps A9 combat stats", () => {
  const axebot = scaledEncounter(encounterFor("AXEBOTS_NORMAL"));
  const boot = axebot.lineup[0].moves.find((move) => move.name === "Boot Up");
  assert.deepEqual(axebot.lineup[0].hp, [182, 206]);
  assert.equal(boot.sourceA9, "Gains 15 Block and 4/8 Strength.");
  assert.equal(boot.text, "Gains 30 Block and 4/8 Strength.");
  assert.ok(axebot.rules.some((rule) => /\+24 Max HP/i.test(rule)));
  assert.ok(axebot.timing.some((line) => /\+24 Max HP/i.test(line)));
  assert.equal(
    scaleMechanicsText("Gains 15 Block and 4/8 Strength.", { players: 2, act: 3, kind: "hallway" }),
    "Gains 30 Block and 4/8 Strength.",
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
    assert.match(body.pattern.text, /revive with 60 HP/i);
    assert.doesNotMatch(body.pattern.text, /revive with 25 HP/i);
  }

  const subject = scaledEncounter(encounterFor("TEST_SUBJECT_BOSS"));
  assert.match(subject.lineup[0].pattern.text, /Enrage 3/i);
  assert.doesNotMatch(subject.lineup[0].pattern.text, /Enrage 7/i);
  for (const body of subject.lineup.slice(1)) {
    assert.match(body.pattern.text, new RegExp(`Revives with ${body.hp[0]} HP`, "i"));
    assert.doesNotMatch(body.pattern.text, /Revives with (?:212|313) HP/i);
  }

  const effigy = scaledEncounter(encounterFor("BYGONE_EFFIGY_ELITE"));
  const body = effigy.lineup[0];
  const wake = body.moves.find((move) => move.name === "Wake");
  assert.match(body.pattern.text, /gains 10 Strength/i);
  assert.match(wake.text, /Gains 10 Strength/i);
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

test("scaling buckets name exactly the v0.111.0 multiplayer formula classes", () => {
  assert.deepEqual(scalingCategories, {
    combatStats: ["Strength", "Dexterity", "Vigor"],
    block: ["Block"],
    defaultPowers: ["Curl Up", "Flutter", "Hardened Shell", "Plow", "Rampart", "Reattach", "Regen", "Shriek"],
    artifact: ["Artifact"],
    plating: ["Plating"],
    skittish: ["Skittish"],
    slippery: ["Slippery"],
  });
  assert.deepEqual(scaledEncounter(encounterFor("FROG_KNIGHT_NORMAL")).scale, {
    players: 2, hp: 2.4, block: 2, plating: 3, artifactDelta: 1,
    skittish: 1.5, slippery: 2, defaultPowers: 2.4, attacks: 1, combatStats: 1,
  });
});

test("attacks and combat stats stay A9 while Block and opt-in powers scale", () => {
  assert.equal(
    scaleMechanicsText("Deals 7 damage. Gains 2 Strength, 3 Dexterity, and 4 Vigor. Gains 18 Block.", { players: 2, act: 2, kind: "elite" }),
    "Deals 7 damage. Gains 2 Strength, 3 Dexterity, and 4 Vigor. Gains 36 Block.",
  );
  assert.equal(
    scaleMechanicsText("Deal 10 damage. Gains 22 Block and Vital Spark 3.", { players: 2, act: 2, kind: "elite" }),
    "Deal 10 damage. Gains 44 Block and Vital Spark 3.",
  );
  assert.equal(
    scaleMechanicsText("Removes 2 Strength from the player. Gains 2 Strength.", { players: 2, act: 2, kind: "elite" }),
    "Removes 2 Strength from the player. Gains 2 Strength.",
  );
  const louse = scaledEncounter(encounterFor("LOUSE_PROGENITOR_NORMAL"));
  assert.equal(louse.lineup[0].startsWithA9, "Curl Up 18");
  assert.equal(louse.lineup[0].startsWith, "Curl Up 43");
  const synthetic = scaledEncounter({
    name: "Synthetic", act: "Overgrowth", kind: "hallway", rules: [], timing: [],
    lineup: [{ displayName: "Synthetic", monsterId: "SYNTHETIC", count: 1, hpA8: [1], startsWithA9: "Block 5; Strength 2; Dexterity 3; Vigor 4; Plating 6", moves: [], pattern: { type: "cycle", text: "Cycle: wait." } }],
  });
  assert.equal(synthetic.lineup[0].startsWith, "Block 10; Strength 2; Dexterity 3; Vigor 4; Plating 18");
  assert.ok(encounterIds.length >= 80);
});

test("opener and added buff prose uses special formulas and leaves unscaled powers true", () => {
  assert.equal(
    scaleMechanicsText(
      "Starts with Enrage 3. Starts Asleep with 12 Plating. Adds 3 Steam Eruption. Has gained 2 Strength. Removes 2 Strength.",
      { players: 2, act: 3, kind: "boss" },
    ),
    "Starts with Enrage 3. Starts Asleep with 36 Plating. Adds 3 Steam Eruption. Has gained 2 Strength. Removes 2 Strength.",
  );
  assert.equal(
    scaleMechanicsText(
      "Gains Vital Spark 3 and Personal Hive 1. Gains Steam Eruption 20. Gains Enrage 3, Ritual 2/6/9, Intangible 2, and Thorns 5/2.",
      { players: 2, act: 3, kind: "boss" },
    ),
    "Gains Vital Spark 3 and Personal Hive 1. Gains Steam Eruption 20. Gains Enrage 3, Ritual 2/6/9, Intangible 2, and Thorns 5/2.",
  );
  assert.equal(
    scaleMechanicsText("Loses 2 Plating. Removes 2 Artifact. Gains 2 Plating and 1 Artifact.", { players: 2, act: 2, kind: "hallway" }),
    "Loses 2 Plating. Removes 2 Artifact. Gains 6 Plating and 2 Artifact.",
  );
});

test("v0.111.0 special multiplayer powers render their own 2P formulas", () => {
  const starts = (encounterId, displayName) => {
    const lineup = scaledEncounter(encounterFor(encounterId)).lineup;
    return lineup.find((body) => !displayName || body.displayName === displayName).startsWith;
  };
  assert.equal(starts("AEONGLASS_BOSS"), "Withering Presence; Artifact 4");
  assert.equal(starts("CHOMPERS_NORMAL"), "Artifact 3");
  assert.equal(starts("PUNCH_CONSTRUCT_NORMAL"), "Artifact 2");
  assert.equal(starts("CUBEX_CONSTRUCT_NORMAL"), "Artifact 2");
  assert.equal(starts("MECHA_KNIGHT_ELITE"), "Artifact 4");
  assert.equal(starts("TURRET_OPERATOR_WEAK", "Living Shield"), "Rampart 60");
  assert.equal(starts("PHANTASMAL_GARDENERS_ELITE"), "Skittish 10");
  assert.equal(starts("INKLETS_NORMAL"), "Slippery 2");
  assert.equal(starts("VANTOM_BOSS"), "Slippery 18");

  const flutter = scaledEncounter(encounterFor("THIEVING_HOPPER_WEAK")).lineup[0].moves.find((move) => move.name === "Flutter");
  assert.match(flutter.sourceA9, /must be hit 5 times/i);
  assert.match(flutter.text, /must be hit 12 times/i);
});

test("Plating is triple at 2P while default powers retain their HP factor", () => {
  const starts = (encounterId) => scaledEncounter(encounterFor(encounterId)).lineup[0].startsWith;
  assert.equal(starts("FROG_KNIGHT_NORMAL"), "Plating 57");
  assert.equal(starts("LAGAVULIN_MATRIARCH_BOSS"), "Plating 36; Asleep 3");
  assert.equal(starts("SEWER_CLAM_NORMAL"), "Plating 27");
  assert.equal(starts("SLUMBERING_BEETLE_NORMAL"), "Plating 54; Slumber 3");
  assert.equal(starts("LOUSE_PROGENITOR_NORMAL"), "Curl Up 43");
  assert.equal(starts("DECIMILLIPEDE_ELITE"), "Reattach 60");

  const beast = scaledEncounter(encounterFor("CEREMONIAL_BEAST_BOSS"));
  assert.equal(beast.lineup[0].moves.find((move) => move.name === "Stamp").text,
    "Gains Plow 352. When its HP drops to that amount, it becomes Stunned and loses all Strength.");
});

test("v0.111.0 CIL audit overrides source HP and Infested Prism Radiate", () => {
  const fixtures = [
    ["AXEBOTS_NORMAL", [76, 86], [182, 206]],
    ["OWL_MAGISTRATE_NORMAL", [247], [592]],
    ["SCROLLS_OF_BITING_NORMAL", [33, 39], [79, 93]],
    ["SLIMED_BERSERKER_NORMAL", [281], [674]],
  ];
  for (const [encounterId, sourceHp, renderedHp] of fixtures) {
    const source = encounterFor(encounterId).lineup[0];
    assert.deepEqual(source.hpA8, sourceHp, `${encounterId} source HP`);
    assert.deepEqual(scaledEncounter(encounterFor(encounterId)).lineup[0].hp, renderedHp, `${encounterId} rendered HP`);
    assert.ok(source.sourceFlags.some((flag) => flag.startsWith("GAME OVERRIDE: hpA8 article=")), `${encounterId} provenance`);
  }
  const prism = scaledEncounter(encounterFor("INFESTED_PRISMS_ELITE")).lineup[0];
  const radiate = prism.moves.find((move) => move.name === "Radiate");
  const pulsate = prism.moves.find((move) => move.name === "Pulsate");
  assert.equal(radiate.sourceA9, "Deals 13 damage. Gains 13 Block.");
  assert.equal(radiate.text, "Deals 13 damage. Gains 26 Block.");
  assert.equal(pulsate.text, "Deal 10 damage. Gains 44 Block and Vital Spark 3.");
  assert.match(prism.sourceFlags.join(" "), /GAME OVERRIDE: Radiate/);
});

test("A9 pattern selection drops A8/A9 prose pairs", () => {
  const beast = encounterFor("CEREMONIAL_BEAST_BOSS").lineup[0].pattern.text;
  const eel = encounterFor("TERROR_EEL_ELITE").lineup[0].pattern.text;
  const queen = encounterFor("QUEEN_BOSS").lineup[0].pattern.text;
  assert.match(beast, /threshold \(160\)/);
  assert.doesNotMatch(beast, /150, or 160/);
  assert.match(eel, /threshold \(75\)/);
  assert.doesNotMatch(eel, /70, or 75/);
  assert.match(queen, /Off with Your Head: 9×5/);
  assert.match(queen, /Execution: 30/);
  assert.doesNotMatch(queen, /7×5 \/ 9×5|25 \/ 30/);
});

test("Fabricator and Ovicopter include every summoned or hatched body", () => {
  const fabricator = scaledEncounter(encounterFor("FABRICATOR_NORMAL"));
  assert.deepEqual(fabricator.lineup.map((body) => body.displayName),
    ["Fabricator", "Guardbot", "Zapbot", "Stabbot", "Noisebot"]);
  const stabbot = fabricator.lineup.find((body) => body.displayName === "Stabbot");
  const noisebot = fabricator.lineup.find((body) => body.displayName === "Noisebot");
  assert.deepEqual(stabbot.hp, [45, 57]);
  assert.equal(stabbot.moves[0].text, "Deals 12 damage. Applies 1 Frail.");
  assert.deepEqual(noisebot.hp, [45, 57]);
  assert.match(noisebot.moves[0].text, /2 Dazed/);

  const ovicopter = scaledEncounter(encounterFor("OVICOPTER_NORMAL"));
  assert.deepEqual(ovicopter.lineup.map((body) => body.displayName), ["Ovicopter", "Tough Egg", "Hatchling"]);
  const egg = ovicopter.lineup.find((body) => body.displayName === "Tough Egg");
  const hatchling = ovicopter.lineup.find((body) => body.displayName === "Hatchling");
  assert.equal(egg.moves.find((move) => move.name === "Hatch").text,
    "Hatches into a Hatchling with 48–55 HP. Removes all powers except Minion.");
  assert.deepEqual(hatchling.hp, [48, 55]);
  assert.equal(hatchling.moves.find((move) => move.name === "Nibble").text, "Deals 5 damage.");
});

test("Ruby Raiders and Bowlbugs expose random body pools instead of one sample", () => {
  const ruby = encounterFor("RUBY_RAIDERS_NORMAL");
  assert.deepEqual(ruby.lineup.map((body) => body.displayName),
    ["Assassin Raider", "Axe Raider", "Brute Raider", "Crossbow Raider", "Tracker Raider"]);
  assert.match(ruby.lineup[0].pack, /3 of 5.*without duplicates/i);
  assert.deepEqual(ruby.lineup.find((body) => body.displayName === "Brute Raider").hpA8, [31, 34]);
  assert.deepEqual(ruby.lineup.find((body) => body.displayName === "Tracker Raider").hpA8, [22, 26]);

  const weak = encounterFor("BOWLBUGS_WEAK");
  assert.deepEqual(weak.lineup.map((body) => body.displayName),
    ["Bowlbug (Rock)", "Bowlbug (Egg)", "Bowlbug (Nectar)"]);
  assert.match(weak.lineup[0].pack, /1 Rock \+ 1 worker from Egg\/Nectar/);
  const normal = encounterFor("BOWLBUGS_NORMAL");
  assert.deepEqual(normal.lineup.map((body) => body.displayName),
    ["Bowlbug (Rock)", "Bowlbug (Egg)", "Bowlbug (Silk)", "Bowlbug (Nectar)"]);
  assert.match(normal.lineup[0].pack, /1 Rock \+ 2 workers from Egg\/Silk\/Nectar/);
});

function combatStatMagnitudes(text) {
  const values = [];
  const expression = /\b(?:Strength|Dexterity|Vigor)\s+(\d+(?:[-/]\d+)*)\b|\b(\d+(?:[-/]\d+)*)\s+(?:Strength|Dexterity|Vigor)\b/gi;
  for (const match of String(text ?? "").matchAll(expression)) values.push(match[1] ?? match[2]);
  return values;
}

function assertCombatStatsUnscaled(source, rendered, location) {
  assert.deepEqual(combatStatMagnitudes(rendered), combatStatMagnitudes(source), location);
}

test("every combat-stat magnitude in the whole scaled book equals its A9 source", () => {
  for (const encounterId of encounterIds) {
    const source = encounterFor(encounterId);
    const rendered = scaledEncounter(source);
    for (let index = 0; index < source.lineup.length; index += 1) {
      const sourceBody = source.lineup[index];
      const renderedBody = rendered.lineup[index];
      const bodyLocation = `${encounterId} ${sourceBody.displayName} #${index + 1}`;
      assertCombatStatsUnscaled(sourceBody.startsWithA9, renderedBody.startsWith, `${bodyLocation} startsWith`);
      assertCombatStatsUnscaled(sourceBody.pattern?.text, renderedBody.pattern?.text, `${bodyLocation} pattern`);
      for (let moveIndex = 0; moveIndex < (sourceBody.moves ?? []).length; moveIndex += 1) {
        assertCombatStatsUnscaled(
          sourceBody.moves[moveIndex].textA9,
          renderedBody.moves[moveIndex].text,
          `${bodyLocation} move ${sourceBody.moves[moveIndex].name}`,
        );
      }
    }
    source.rules.forEach((rule, index) => assertCombatStatsUnscaled(rule, rendered.rules[index], `${encounterId} rule #${index + 1}`));
    source.timing.forEach((line, index) => assertCombatStatsUnscaled(line, rendered.timing[index], `${encounterId} timing #${index + 1}`));
  }
});

test("Nibbit cards use encounter-local turn-one openers and A9 Hiss", () => {
  const weak = encounterFor("NIBBITS_WEAK");
  assert.equal(weak.lineup.length, 1);
  assert.equal(weak.lineup[0].count, 1);
  assert.match(weak.lineup[0].pattern.text, /opener \(turn 1\): Butt/i);
  assert.doesNotMatch(weak.lineup[0].pattern.text, /paired|front|Hiss|Normal/i);

  const normal = encounterFor("NIBBITS_NORMAL");
  assert.equal(normal.lineup.length, 2);
  assert.ok(normal.lineup.every((body) => body.count === 1));
  const front = normal.lineup.find((body) => /front/i.test(body.role));
  const back = normal.lineup.find((body) => /back/i.test(body.role));
  assert.match(front.pattern.text, /opener \(turn 1\): Hesitant Slice/i);
  assert.match(back.pattern.text, /opener \(turn 1\): Hiss/i);
  assert.ok(normal.lineup.every((body) => !/Weak|alone|paired/i.test(body.pattern.text)));

  const hiss = scaledEncounter(normal).lineup[0].moves.find((move) => move.name === "Hiss");
  assert.equal(hiss.text, "Gains 3 Strength.");
});

test("fixed identical rosters have one immutable card per opener slot", () => {
  const expected = [
    ["CHOMPERS_NORMAL", "Chomper", ["Clamp", "Screech"]],
    ["MYTES_NORMAL", "Myte", ["Toxic Cornucopia", "Suck"]],
    ["THE_KIN_BOSS", "Kin Follower", ["Quick Slash", "Power Dance"]],
    ["TOADPOLES_WEAK", "Toadpole", ["Spiken", "Whirl"]],
  ];
  for (const [encounterId, name, openers] of expected) {
    const slots = encounterFor(encounterId).lineup.filter((body) => body.displayName === name);
    assert.equal(slots.length, openers.length, `${encounterId} slot count`);
    assert.ok(slots.every((body) => body.count === 1), `${encounterId} has no N× card`);
    for (const opener of openers) {
      assert.ok(slots.some((body) => body.pattern.text.includes(`Opener (turn 1): ${opener}`)), `${encounterId} ${opener} opener`);
    }
  }
});

test("Exoskeleton counts and position openers are bound to each encounter", () => {
  const weak = encounterFor("EXOSKELETONS_WEAK");
  const normal = encounterFor("EXOSKELETONS_NORMAL");
  assert.equal(weak.lineup.length, 1);
  assert.equal(normal.lineup.length, 1);
  assert.equal(weak.lineup[0].count, 3);
  assert.equal(normal.lineup[0].count, 4);
  assert.match(weak.lineup[0].pattern.text, /Openers by position \(turn 1\).*first.*Skitter.*second.*Mandibles.*third.*Enrage/i);
  assert.doesNotMatch(weak.lineup[0].pattern.text, /fourth|groups? of 3 or 4|Normal/i);
  assert.match(normal.lineup[0].pattern.text, /fourth.*randomly.*Skitter.*Mandibles/i);
  assert.doesNotMatch(normal.lineup[0].pattern.text, /Weak|groups? of 3 or 4/i);
});

test("mutable summon and death rosters render live-body templates, not frozen N× cards", () => {
  const rats = encounterFor("TWO_TAILED_RATS_NORMAL");
  assert.equal(rats.lineup.length, 1);
  assert.equal(rats.lineup[0].count, 1);
  assert.match(rats.lineup[0].pack, /3 initially/i);
  assert.match(rats.lineup[0].pattern.text, /Openers? \(turn 1/i);
  assert.ok(rats.rules.some((rule) => /summon a new (?:Two-Tailed )?Rat/i.test(rule)));

  const axebot = encounterFor("AXEBOTS_NORMAL");
  assert.equal(axebot.lineup.length, 1);
  assert.equal(axebot.lineup[0].count, 1);
  assert.match(axebot.lineup[0].pack, /1 initially|Stock/i);
  assert.ok(axebot.rules.some((rule) => /respawn|spawned mid-fight|Stock/i.test(rule)));

  const wriggler = encounterFor("PHROG_PARASITE_ELITE").lineup.find((body) => body.displayName === "Wriggler");
  assert.equal(wriggler.count, 1);
  assert.equal(wriggler.role, "summoned");
  assert.match(wriggler.pack, /4.*death/i);

  const egg = encounterFor("OVICOPTER_NORMAL").lineup.find((body) => body.displayName === "Tough Egg");
  assert.equal(egg.count, 1);
  assert.equal(egg.role, "summoned");
  assert.match(egg.pack, /3.*Lay Eggs|Lay Eggs.*3/i);
});

test("Decimillipede descriptions preserve offsets without claiming lasting sync", () => {
  const encounter = encounterFor("DECIMILLIPEDE_ELITE");
  for (const segment of encounter.lineup) {
    assert.match(segment.pattern.text, /start offset/i);
    assert.match(segment.pattern.text, /cycle.*Bulk.*Writhe.*Outgas/i);
    assert.match(segment.pattern.text, /after Reattach.*random.*sync/i);
  }
});

test("article Death Blow intent is retained as an extra rule", () => {
  const fog = encounterFor("LIVING_FOG_NORMAL");
  const gasBomb = fog.lineup.find((body) => body.displayName === "Gas Bomb");
  assert.equal(gasBomb.moves[0].intent, "Death Blow");
  assert.ok(fog.rules.some((rule) => /Death Blow:.*Dies/i.test(rule)));
});

test("startsWith uses named-power formulas but not durations or counts", () => {
  const lag = scaledEncounter(encounterFor("LAGAVULIN_MATRIARCH_BOSS"));
  assert.equal(lag.lineup[0].startsWithA9, "Plating 12; Asleep 3");
  assert.equal(lag.lineup[0].startsWith, "Plating 36; Asleep 3");

  const beetle = scaledEncounter(encounterFor("SLUMBERING_BEETLE_NORMAL"));
  assert.equal(beetle.lineup[0].startsWithA9, "Plating 18; Slumber 3");
  assert.equal(beetle.lineup[0].startsWith, "Plating 54; Slumber 3");

  const gremlin = scaledEncounter(encounterFor("GREMLIN_MERC_NORMAL"));
  assert.equal(gremlin.lineup[0].startsWithA9, "Surprise 1; Thievery 20");
  assert.equal(gremlin.lineup[0].startsWith, "Surprise 1; Thievery 20");

  const aeon = scaledEncounter(encounterFor("AEONGLASS_BOSS"));
  assert.equal(aeon.lineup[0].startsWithA9, "Withering Presence; Artifact 3");
  assert.equal(aeon.lineup[0].startsWith, "Withering Presence; Artifact 4");

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

test("Gains PowerName N default powers scale by the HP factor", () => {
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

test("deprecated Glory Doormaker remains a known book encounter", () => {
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
    assert.match(page.body, /<footer class="source"><div class="scale-note">hp ×2\.4 · block ×2 · attacks &amp; combat stats unscaled · mp powers by formula<\/div>/);
    assert.match(page.body, /rendered for a9 \/ 2p/);
    assert.doesNotMatch(page.body, /hp &amp; stored buffs/);
    assert.match(page.body, /<div class="starts">starts ·/);
    assert.doesNotMatch(page.body, /IN COMBAT|LAST COMBAT|status-badge/);
    assert.doesNotMatch(page.body, /border-radius:99rem|gradient|box-shadow/);
    assert.doesNotMatch(page.body, /<div class="version-card|version-match/i);
    assert.doesNotMatch(page.body, /DECIMILLIPEDE_ELITE|DECIMILLIPEDE_FRONT/);
    assert.equal(page.body.match(/a9 · 2p/g)?.length, 1);

    const client = await request(server, "/sts2/client.js");
    assert.equal(client.status, 200);
    assert.match(client.body, /version\.matches === true\) return null/);
    assert.match(client.body, /showRawId && body\.monsterId/);
    assert.match(client.body, /hp ×.*attacks & combat stats unscaled.*mp powers by formula/);
    assert.doesNotMatch(client.body, /hp & stored buffs/);
    const state = JSON.parse((await request(server, "/sts2/state")).body);
    assert.equal(state.ascension, 9);
    assert.equal(state.players, 2);
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


test("plugin contributes its canonical navigation item when optional qq-ui becomes available", () => {
  let injectedDependencies, attachMenu;
  let route;
  const ctx = {
    webServer: { host: "127.0.0.1", register(value) { route = value; return () => {}; } },
    effect(fn) { return fn(); },
    inject(dependencies, callback) { injectedDependencies = dependencies; attachMenu = callback; },
  };
  apply(ctx, { basePath: "/reference/sts2", logPath: "/missing/godot.log", savePath: "/missing/current_run_mp.save" });
  assert.deepEqual(injectedDependencies, ["qq-ui"]);
  assert.equal(route.path, "/reference/sts2");

  const registrations = []; let disposed = 0; let effectLabel;
  const ui = { consoleMenu: { register(item) {
    registrations.push(item);
    let active = true;
    return () => { if (active) { active = false; disposed += 1; } };
  } } };
  let cleanup;
  const menuCtx = {
    get(service, required) { assert.equal(service, "qq-ui"); assert.equal(required, false); return ui; },
    effect(fn, label) { effectLabel = label; cleanup = fn(); },
  };
  attachMenu(menuCtx);
  assert.deepEqual(registrations, [{ kind: "navigation", id: "sts2-companion", label: "StS2 Companion", href: "/reference/sts2", order: 100 }]);
  assert.match(effectLabel, /qq-ui navigation/);
  cleanup(); cleanup();
  assert.equal(disposed, 1, "qq-ui's idempotent disposer remains bound to the injected context lifecycle");
});

test("optional qq-ui contribution supports property lookup and service re-attachment", () => {
  let attachMenu;
  const ctx = {
    webServer: { host: "127.0.0.1", register() { return () => {}; } },
    effect(fn) { return fn(); },
    inject(dependencies, callback) { assert.deepEqual(dependencies, ["qq-ui"]); attachMenu = callback; },
  };
  apply(ctx, { logPath: "/missing/godot.log", savePath: "/missing/current_run_mp.save" });

  let registered = 0, disposed = 0;
  const ui = { consoleMenu: { register(item) { assert.equal(item.href, "/sts2"); registered += 1; return () => { disposed += 1; }; } } };
  const attach = () => {
    let cleanup;
    attachMenu({ "qq-ui": ui, get: () => undefined, effect(fn) { cleanup = fn(); } });
    return cleanup;
  };
  const first = attach(); first();
  const second = attach(); second();
  assert.equal(registered, 2);
  assert.equal(disposed, 2);
});
