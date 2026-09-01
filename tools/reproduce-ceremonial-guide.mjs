#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { fileURLToPath } from "node:url";

import { createSourceAdapter } from "../src/source-adapter.mjs";

const CLIENT = readFileSync(new URL("../src/client.js", import.meta.url), "utf8");
const SNAPSHOT = new URL("../test/fixtures/ceremonial-beast-phone.snap", import.meta.url);

export function collapsedDomText(node) {
  if (!node || typeof node !== "object") return String(node ?? "");
  if (node.tagName === "details") {
    const summary = node.children.find((child) => child?.tagName === "summary");
    return summary ? collapsedDomText(summary) : "";
  }
  return node._text + (node.children ?? []).map(collapsedDomText).join(" ");
}

export function semanticSnapshot(node, depth = 0) {
  if (!node || typeof node !== "object") return "";
  const indent = "  ".repeat(depth);
  const classes = String(node.className ?? "").trim().split(/\s+/).filter(Boolean).join(".");
  const label = `${node.tagName}${classes ? `.${classes}` : ""}${node._text ? ` ${JSON.stringify(node._text)}` : ""}`;
  if (node.tagName === "details") {
    const summary = node.children.find((child) => child?.tagName === "summary");
    return `${indent}${label}\n${summary ? semanticSnapshot(summary, depth + 1) : ""}\n${indent}  [collapsed]`;
  }
  return [`${indent}${label}`, ...(node.children ?? []).map((child) => semanticSnapshot(child, depth + 1)).filter(Boolean)].join("\n");
}

export async function renderCeremonialPhone() {
  class SnapshotNode {
    constructor(tagName) { this.tagName = tagName; this.children = []; this.dataset = {}; this.className = ""; this._text = ""; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this._text = ""; this.children = children; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get textContent() { return this._text + this.children.map((child) => child?.textContent ?? String(child)).join(""); }
  }
  const root = new SnapshotNode("main"); root.dataset.basePath = "/sts2";
  const adapter = createSourceAdapter({ players: 2 });
  assert.equal(adapter.available, true, adapter.error);
  const payload = adapter.view({ status: "idle", encounterId: null, monsterIds: [], releaseInfo: { version: "v0.111.0", branch: "public-beta" } }, "CEREMONIAL_BEAST_BOSS");
  const document = {
    getElementById: (id) => id === "guide-encounter" ? root : null,
    createElement: (tagName) => new SnapshotNode(tagName),
  };
  const window = {
    innerWidth: 390,
    location: { search: "?encounter=CEREMONIAL_BEAST_BOSS" },
    setInterval: () => 1,
  };
  const fetch = async () => ({ ok: true, json: async () => structuredClone(payload) });
  runInNewContext(CLIENT, { document, window, fetch, Node: SnapshotNode, URLSearchParams, encodeURIComponent });
  await new Promise((resolve) => setImmediate(resolve));
  return { root, payload, snapshot: `# StS2 Companion phone snapshot · 390px\n${semanticSnapshot(root)}\n` };
}

async function main() {
  const { root, payload, snapshot } = await renderCeremonialPhone();
  const collapsed = collapsedDomText(root);
  const approved = ["576 HP · BOSS", "01", "Break the Plow", "Plow 352", "20 damage", "+2 Strength", "STUNNED", "02", "Three-turn loop", "1 Ringing", "17 damage", "19 damage", "+4 Strength", "Watch:", "wiki/reference values · A9 / 2P presentation"];
  let cursor = -1;
  for (const value of approved) { const next = collapsed.indexOf(value, cursor + 1); assert.ok(next > cursor, `${value} is missing or out of order`); cursor = next; }
  assert.doesNotMatch(collapsed, /unresolved|Death removal|Fight completion|all enemies escape|Ordinary|Boss · Boss/i);
  assert.match(JSON.stringify(payload.encounter), /get_PlowAmount/);
  assert.match(JSON.stringify(payload.encounter.sourceAuthority), /rawSource/);
  if (process.argv.includes("--write")) writeFileSync(SNAPSHOT, snapshot);
  else if (process.argv.includes("--check")) assert.equal(snapshot, readFileSync(SNAPSHOT, "utf8"), "phone snapshot drifted");
  else process.stdout.write(snapshot);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
