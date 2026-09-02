import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { createSourceAdapter, internals as adapterInternals } from "../src/source-adapter.mjs";
import { eventPrimaryFixture, EVENT_PRIMARY_IDS } from "../tools/reproduce-event-primary-guides.mjs";

const artifact = JSON.parse(readFileSync(new URL("../data/encounter-facts-v0.111.0.json", import.meta.url), "utf8"));
const expected = JSON.parse(readFileSync(new URL("./fixtures/event-primary-guides.json", import.meta.url), "utf8"));

test("all eight event fights have deterministic source-only primary and collapsed DOM cards at 1P and 2P", async () => {
  const actual = await eventPrimaryFixture();
  assert.deepEqual(actual, expected);
  assert.deepEqual(Object.keys(actual["1P"]), EVENT_PRIMARY_IDS);
  assert.deepEqual(Object.keys(actual["2P"]), EVENT_PRIMARY_IDS);
});


test("event primary fails closed when a typed scaling signature drifts", () => {
  const changed = structuredClone(artifact);
  changed.payload.sourceFacts.scaling.power.rule.summary.optIns = 11;
  changed.metadata.payloadSha256 = adapterInternals.payloadDigest(changed.payload);
  const adapter = createSourceAdapter({ projection: changed, players: 2 });
  assert.equal(adapter.available, true, adapter.error);
  const selected = adapter.view({ status: "idle" }, "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER");
  assert.equal(selected.encounter.presentation.primary, null);
});
