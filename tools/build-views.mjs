#!/usr/bin/env node
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { createSourceAdapter } from "../src/source-adapter.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const PUBLIC_VIEWS_DIR = join(ROOT, "public", "data", "views");
const SRC_VIEWS_DIR = join(ROOT, "src", "data", "generated-views");
const SRC_DATA_DIR = join(ROOT, "src", "data");

mkdirSync(PUBLIC_VIEWS_DIR, { recursive: true });
mkdirSync(SRC_VIEWS_DIR, { recursive: true });

const adapter = createSourceAdapter({ players: 2 });
if (!adapter.available) {
  console.error("Adapter unavailable:", adapter.error);
  process.exit(1);
}

const idleState = {
  status: "idle",
  encounterId: null,
  monsterIds: [],
  releaseInfo: { version: "v0.111.0", branch: "public-beta" },
};

const index = [];
const loaders = [];

console.log(`Building views for ${adapter.canonicalIds.length} checked encounters...`);

for (const id of adapter.canonicalIds) {
  const view = adapter.view(idleState, id);
  if (view.status !== "selected" || !view.encounter) {
    console.error(`Failed to compile view for ${id}:`, view.error);
    process.exit(1);
  }

  const enc = view.encounter;
  const ctx = enc.presentation?.context || {};
  const primary = enc.presentation?.primary;
  const header = primary?.header;

  const stats = header?.stats || (enc.hpContract ? `${enc.hpContract.canonicalRange?.[0]}–${enc.hpContract.canonicalRange?.[1]} HP` : "");
  const placement = header?.placement || ctx.summary || (enc.placement?.memberships?.[0]?.actId?.replace("ACT.", "") || "Event");
  const act = ctx.summary || (enc.placement?.memberships?.[0]?.actId?.replace("ACT.", "") || "Event");
  const tier = ctx.kind || enc.kind;
  const bodies = primary?.bodies?.map((b) => b.name) || enc.monsters?.map((m) => m.name) || [];

  const meta = {
    id,
    title: enc.title,
    act,
    tier,
    stats,
    placement,
    bodies,
  };

  index.push(meta);

  const viewJson = JSON.stringify(view);
  writeFileSync(join(PUBLIC_VIEWS_DIR, `${id}.json`), viewJson, "utf8");
  writeFileSync(join(SRC_VIEWS_DIR, `${id}.json`), viewJson, "utf8");
  loaders.push(`  "${id}": () => import("./generated-views/${id}.json")`);
}

const indexJson = JSON.stringify(index, null, 2);
writeFileSync(join(ROOT, "public", "data", "index.json"), indexJson, "utf8");
writeFileSync(join(SRC_DATA_DIR, "index.json"), indexJson, "utf8");

const viewsModule = `// Pre-generated views loader for all 89 checked encounters
export const encounterIndex = ${indexJson};

export const viewLoaders = {
${loaders.join(",\n")}
};

export async function loadEncounterView(id) {
  if (viewLoaders[id]) {
    const mod = await viewLoaders[id]();
    return mod.default || mod;
  }
  const basePath = typeof window !== "undefined" && window.__STS2_BASE_PATH__ ? window.__STS2_BASE_PATH__ : "";
  const res = await fetch(\`\${basePath}/data/views/\${encodeURIComponent(id)}.json\`);
  if (!res.ok) throw new Error(\`Failed to load encounter: \${id}\`);
  return res.json();
}
`;

writeFileSync(join(SRC_DATA_DIR, "views.js"), viewsModule, "utf8");
console.log(`Successfully generated ${index.length} encounter views and index.`);
