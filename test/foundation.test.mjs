import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";

import { encounterFor, encounterIds } from "../src/book.mjs";

const artifactBytes = readFileSync(new URL("../data/game-v0.111.0-foundation.json", import.meta.url));
const artifact = JSON.parse(artifactBytes);
const oldBookBytes = readFileSync(new URL("../data/encounters.json", import.meta.url));
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const compactCanonical = (value) => {
  if (Array.isArray(value)) return `[${value.map(compactCanonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${compactCanonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
};
const sortedValue = (value) => {
  if (Array.isArray(value)) return value.map(sortedValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedValue(value[key])]));
  }
  return value;
};

test("checked source foundation is canonical, pinned, partial, and metadata-only", () => {
  const canonical = `${JSON.stringify(sortedValue(artifact), null, 2)}\n`;
  assert.equal(artifactBytes.toString("utf8"), canonical, "canonical sorted JSON serialization");
  assert.equal(artifact.schemaVersion, 1);
  assert.equal(artifact.extractorVersion, "1.0.0");
  assert.equal(artifact.runtimeReady, false);
  assert.equal(artifact.status, "incomplete");
  assert.deepEqual(artifact.game, {
    branch: "v0.111.0",
    commit: "41cef1ea",
    mainAssemblyHash: 1579942752,
    version: "v0.111.0",
  });
  assert.deepEqual(artifact.inputs, [
    {
      path: "SlayTheSpire2.pck",
      sha256: "42443027622a6a82de8ab21e81ed5b68e522c0f5647fb6a26a74c4a0970a0d34",
      size: 1990363992,
    },
    {
      path: "data_sts2_linuxbsd_x86_64/sts2.dll",
      sha256: "2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f",
      size: 9756160,
    },
    {
      path: "data_sts2_linuxbsd_x86_64/sts2.xml",
      sha256: "a88331870d38cdb84d8fc371ab3d7fb619afa25c8c7249a47aaa77e1c7bf4286",
      size: 5650972,
    },
    {
      path: "release_info.json",
      sha256: "9e5dbce5bcd8ff3b7b432291200220642408e31b8bae7bba14f39aeb6914cd51",
      size: 150,
    },
  ]);
  assert.deepEqual(artifact.safety, {
    assemblyExecution: false,
    cilExecution: false,
    godotInitialization: false,
    mode: "metadataOnly",
    pckAccess: "readOnlySelective",
    reflectionLoading: false,
  });
  assert.deepEqual(artifact.encounterCensus.counts, {
    abstract: 1,
    currentEvent: 8,
    currentOrdinary: 81,
    currentTotal: 89,
    deprecatedPlaceholder: 1,
  });
  assert.deepEqual(artifact.coverage.encounterIdentities, { count: 89, status: "complete" });
  assert.deepEqual(artifact.coverage.encounterTitlesEnglish, { count: 89, status: "complete" });
  for (const family of ["hp", "monsterIdentities", "moves", "multiplayerScaling", "patterns", "powers", "rostersAndPools", "stateFormulas"]) {
    assert.deepEqual(artifact.coverage[family], { status: "notExtracted" }, family);
  }
  assert.doesNotMatch(artifactBytes.toString("utf8"), /(?:generated|extracted|created)(?:At|_at)|timestamp/i);
});

test("all 89 canonical encounter identities have exact title and fact provenance joins", () => {
  const ordinary = artifact.encounters.ordinary;
  const events = artifact.encounters.event;
  assert.equal(ordinary.length, 81);
  assert.equal(events.length, 8);
  const all = [...ordinary, ...events];
  const ids = all.map((record) => record.canonicalId);
  assert.equal(new Set(ids).size, 89);
  assert.deepEqual(ordinary.map((record) => record.canonicalId), [...ordinary.map((record) => record.canonicalId)].sort());
  assert.deepEqual(events.map((record) => record.canonicalId), [...events.map((record) => record.canonicalId)].sort());
  assert.ok(ids.includes("AEONGLASS_BOSS"));
  assert.ok(!ids.includes("DOORMAKER_BOSS"));

  const blob = artifact.provenance.localizationBlob;
  assert.equal(blob.pckPath, "localization/eng/encounters.json");
  assert.equal(blob.entryMd5, "1589dcf731c52d77c63f7cce25f86068");
  assert.equal(blob.entrySha256, "d4d8ce9e8e2ff984d6f6cfdd9575b11d7639cfa015cd0da030f040e2b722ed6a");
  assert.equal(blob.entryFlags, 0);

  for (const record of all) {
    assert.match(record.canonicalId, /^[A-Z0-9_]+$/);
    assert.equal(record.assemblyCategory, "ENCOUNTER");
    assert.equal(record.sourceType, `MegaCrit.Sts2.Core.Models.Encounters.${record.sourceType.split(".").at(-1)}`);
    assert.ok(record.title.length > 0);
    const identity = record.provenance.identity;
    assert.equal(identity.assemblySha256, artifact.inputs.find((input) => input.path.endsWith("sts2.dll")).sha256);
    assert.equal(identity.sourceType, record.sourceType);
    assert.equal(identity.modelIdRule, "modelDb.typeToId.v0.111.0");
    assert.match(identity.diagnosticMetadataToken, /^0x02[0-9a-f]{6}$/);
    assert.equal(identity.semanticWitness.entry, record.canonicalId);
    assert.equal(identity.semanticWitness.category, "ENCOUNTER");
    assert.equal(identity.semanticWitness.sourceType, record.sourceType);
    assert.equal(identity.semanticWitnessSha256, sha256(Buffer.from(compactCanonical(identity.semanticWitness))));

    const title = record.provenance.title;
    assert.equal(title.pckPath, blob.pckPath);
    assert.equal(title.pckSha256, blob.pckSha256);
    assert.equal(title.entryMd5, blob.entryMd5);
    assert.equal(title.entrySha256, blob.entrySha256);
    assert.equal(title.localizationKey, `${record.canonicalId}.title`);
    assert.equal(title.keyValueWitnessSha256, sha256(Buffer.from(compactCanonical([title.localizationKey, record.title]))));
  }
});

test("ModelDb and Slugify provenance uses symbols and body hashes, not tokens as identity", () => {
  const rule = artifact.provenance.assemblyRules["modelDb.typeToId.v0.111.0"];
  assert.equal(rule.assemblySha256, "2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f");
  assert.equal(rule.methods.length, 5);
  assert.ok(rule.normalizedSemanticWitness.includes("entry = Slugify(concreteType.Name)"));
  assert.equal(rule.semanticWitnessSha256, sha256(Buffer.from(compactCanonical(rule.normalizedSemanticWitness))));
  for (const method of rule.methods) {
    assert.match(method.symbolSignature, /MegaCrit\.Sts2\.Core\./);
    assert.match(method.metadataSignature, /^[0-9a-f]+$/);
    assert.match(method.methodBodySha256, /^[0-9a-f]{64}$/);
    assert.match(method.cilInstructionsSha256, /^[0-9a-f]{64}$/);
    assert.match(method.diagnosticMetadataToken, /^0x06[0-9a-f]{6}$/);
    assert.equal(method.assemblySha256, rule.assemblySha256);
  }
});

test("foundation is not consumed and the wiki-derived runtime book is byte-unchanged", () => {
  assert.equal(sha256(oldBookBytes), "0c01dd0b851c501acea59fb41b10a828030ad2c3e63f9fc624f98b6e403e0103");
  assert.equal(encounterIds.length, 82);
  assert.ok(encounterFor("DOORMAKER_BOSS"));
  assert.equal(encounterFor("BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER"), null);
  assert.equal(encounterFor("AEONGLASS_BOSS").name, "Aeonglass");
});
