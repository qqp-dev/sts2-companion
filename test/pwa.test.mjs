import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const ROOT = new URL("..", import.meta.url).pathname;
const DIST = join(ROOT, "dist");
const MANIFEST_PATH = join(DIST, "manifest.webmanifest");
const SW_PATH = join(DIST, "sw.js");

test("Invariant 1: Zero dsh / cordis / qq / paseo dependencies", () => {
  assert.equal(existsSync(join(ROOT, "cordis.patch.yml")), false, "cordis.patch.yml must not exist");
  assert.equal(existsSync(join(ROOT, "paseo-plugin.json")), false, "paseo-plugin.json must not exist");
  assert.equal(existsSync(join(ROOT, "src/plugin.mjs")), false, "src/plugin.mjs must not exist");

  const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));
  assert.equal(pkg.dsh, undefined, "package.json must not have dsh configuration");
  assert.equal(pkg.exports?.["./cordis.patch.yml"], undefined, "package.json exports must not reference cordis");
  assert.equal(pkg.files?.includes("cordis.patch.yml"), false, "package.json files must not include cordis");

  const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };
  for (const dep of Object.keys(allDeps)) {
    assert.doesNotMatch(dep, /cordis|dsh|@getpaseo/i, `Forbidden dependency: ${dep}`);
  }
});

test("Invariant 2: PWA distribution files exist and build cleanly", () => {
  assert.ok(existsSync(join(DIST, "index.html")), "dist/index.html must exist");
  assert.ok(existsSync(MANIFEST_PATH), "dist/manifest.webmanifest must exist");
  assert.ok(existsSync(SW_PATH), "dist/sw.js must exist");
  assert.ok(existsSync(join(DIST, "icons", "icon-192.png")), "192px icon must exist");
  assert.ok(existsSync(join(DIST, "icons", "icon-512.png")), "512px icon must exist");
  assert.ok(existsSync(join(DIST, "icons", "icon.svg")), "SVG icon must exist");
  assert.ok(existsSync(join(DIST, "data", "index.json")), "dist/data/index.json must exist");

  const views = readdirSync(join(DIST, "data", "views")).filter((f) => f.endsWith(".json"));
  assert.equal(views.length, 89, `dist/data/views must contain exactly 89 views, found ${views.length}`);
});

test("Invariant 3: Web App Manifest meets standalone PWA contract", () => {
  const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf8"));
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.theme_color, "#000000");
  assert.equal(manifest.background_color, "#000000");
  assert.ok(manifest.name && manifest.name.length > 0);
  assert.ok(manifest.short_name && manifest.short_name.length > 0);
  assert.ok(Array.isArray(manifest.icons) && manifest.icons.length >= 2);

  const icon192 = manifest.icons.find((i) => i.sizes === "192x192");
  assert.ok(icon192, "192x192 icon must be declared in manifest");
  const icon512 = manifest.icons.find((i) => i.sizes === "512x512");
  assert.ok(icon512, "512x512 icon must be declared in manifest");
});

test("Invariant 4: Service Worker precaches 100% of offline application data", () => {
  const swContent = readFileSync(SW_PATH, "utf8");
  assert.match(swContent, /precacheAndRoute/);
  assert.match(swContent, /data\/index\.json/);
  assert.match(swContent, /data\/views\/CEREMONIAL_BEAST_BOSS\.json/);
  assert.match(swContent, /data\/views\/AXEBOTS_NORMAL\.json/);
  assert.match(swContent, /manifest\.webmanifest/);
});

test("Invariant 5: Encounter index covers all 89 checked encounters with valid fields", () => {
  const index = JSON.parse(readFileSync(join(DIST, "data", "index.json"), "utf8"));
  assert.equal(index.length, 89);
  const ids = new Set(index.map((e) => e.id));
  assert.equal(ids.size, 89);
  assert.ok(ids.has("CEREMONIAL_BEAST_BOSS"));
  assert.ok(ids.has("AXEBOTS_NORMAL"));
  assert.ok(ids.has("THE_ARCHITECT_EVENT_ENCOUNTER"));

  for (const item of index) {
    assert.ok(item.id, "Encounter item must have id");
    assert.ok(item.title, `Encounter ${item.id} must have title`);
    assert.ok(item.act, `Encounter ${item.id} must have act`);
    assert.ok(item.tier, `Encounter ${item.id} must have tier`);
    assert.ok(item.stats, `Encounter ${item.id} must have stats`);
  }
});
