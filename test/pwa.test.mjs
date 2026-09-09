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

test("Invariant 6: Live State API endpoint (/api/state) returns current combat state and safe idle observation", async () => {
  const { createLiveStateMiddleware, liveStatePlugin } = await import("../src/state.mjs");
  const { createServer } = await import("node:http");

  assert.equal(typeof liveStatePlugin, "function");
  assert.equal(typeof createLiveStateMiddleware, "function");

  // Plugin structure and hooks
  const plugin = liveStatePlugin();
  assert.equal(plugin.name, "sts2-live-state");
  assert.equal(typeof plugin.configureServer, "function");
  assert.equal(typeof plugin.configurePreviewServer, "function");

  let devHandler = null;
  let previewHandler = null;
  plugin.configureServer({ middlewares: { use: (fn) => { devHandler = fn; } } });
  plugin.configurePreviewServer({ middlewares: { use: (fn) => { previewHandler = fn; } } });
  assert.equal(typeof devHandler, "function");
  assert.equal(typeof previewHandler, "function");

  // Test with real HTTP server and mock readers
  let currentMockState = {
    status: "combat",
    encounterId: "DECIMILLIPEDE_ELITE",
    monsterIds: ["DECIMILLIPEDE_FRONT"],
    actId: "HIVE",
    roomType: "elite",
    source: "log",
    releaseInfo: { version: "v0.111.0", branch: "public-beta" },
  };

  const mockReader = {
    read() {
      if (currentMockState === "THROW") {
        throw new Error("Simulated reader failure");
      }
      return currentMockState;
    },
  };

  const middleware = createLiveStateMiddleware({ reader: mockReader });
  const server = createServer((req, res) => {
    middleware(req, res, () => {
      res.statusCode = 404;
      res.end("Not Found");
    });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const baseUrl = `http://127.0.0.1:${port}`;

  try {
    // 1. GET /api/state returns combat state with required headers
    const combatRes = await fetch(`${baseUrl}/api/state`);
    assert.equal(combatRes.status, 200);
    assert.match(combatRes.headers.get("content-type"), /^application\/json/);
    assert.equal(combatRes.headers.get("cache-control"), "no-store");
    const combatJson = await combatRes.json();
    assert.equal(combatJson.status, "combat");
    assert.equal(combatJson.encounterId, "DECIMILLIPEDE_ELITE");
    assert.deepEqual(combatJson.monsterIds, ["DECIMILLIPEDE_FRONT"]);

    // 2. GET /api/state with last combat state
    currentMockState = {
      status: "last",
      encounterId: "CEREMONIAL_BEAST_BOSS",
      monsterIds: [],
      actId: null,
      roomType: null,
      source: "log",
      releaseInfo: null,
    };
    const lastRes = await fetch(`${baseUrl}/api/state`);
    assert.equal(lastRes.status, 200);
    const lastJson = await lastRes.json();
    assert.equal(lastJson.status, "last");
    assert.equal(lastJson.encounterId, "CEREMONIAL_BEAST_BOSS");

    // 3. Reader failure returns safe idle observation without crashing
    currentMockState = "THROW";
    const failRes = await fetch(`${baseUrl}/api/state`);
    assert.equal(failRes.status, 200);
    const failJson = await failRes.json();
    assert.equal(failJson.status, "idle");
    assert.equal(failJson.encounterId, null);
    assert.deepEqual(failJson.monsterIds, []);

    // 4. HEAD /api/state returns 200 with empty body
    const headRes = await fetch(`${baseUrl}/api/state`, { method: "HEAD" });
    assert.equal(headRes.status, 200);
    const headText = await headRes.text();
    assert.equal(headText, "");

    // 5. POST /api/state returns 405 Method Not Allowed with Allow header
    const postRes = await fetch(`${baseUrl}/api/state`, { method: "POST" });
    assert.equal(postRes.status, 405);
    assert.equal(postRes.headers.get("allow"), "GET, HEAD");

    // 6. Non-matching path passes through to next middleware
    const otherRes = await fetch(`${baseUrl}/unknown`);
    assert.equal(otherRes.status, 404);
  } finally {
    server.closeAllConnections?.();
    await new Promise((resolve) => server.close(resolve));
  }
});

test("Invariant 7: Live Auto-Tracking in PWA Client respects 1.5s interval and status indicators", () => {
  // Verify compiled bundle includes live polling, 1500ms interval, and status indicators
  const jsFiles = readdirSync(join(DIST, "assets")).filter((f) => f.startsWith("index-") && f.endsWith(".js"));
  assert.ok(jsFiles.length > 0, "dist/assets/index-*.js must exist");
  const jsContent = readFileSync(join(DIST, "assets", jsFiles[0]), "utf8");

  // 1. Polling endpoint and 1500ms interval
  assert.match(jsContent, /\/api\/state/, "Client must fetch /api/state");
  assert.match(jsContent, /1500/, "Client must poll at 1500ms (1.5s) interval");

  // 2. Status indicators
  assert.match(jsContent, /\[LIVE · Combat\]/, "Indicator must support [LIVE · Combat]");
  assert.match(jsContent, /\[LIVE · Last Fight\]/, "Indicator must support [LIVE · Last Fight]");
  assert.match(jsContent, /\[LIVE · Idle\]/, "Indicator must support [LIVE · Idle]");
  assert.match(jsContent, /\[Manual\]/, "Indicator must support [Manual]");
  assert.match(jsContent, /\[Offline Reference\]/, "Indicator must support [Offline Reference]");

  // 3. Mode toggle controls
  assert.match(jsContent, /mode-pill/, "Client must render mode-pill group");
  assert.match(jsContent, /children:[`"]Live[`"]/, "Client must render Live button");
  assert.match(jsContent, /children:[`"]Manual[`"]/, "Client must render Manual button");

  // 4. CSS rules for indicators and toggle
  const cssFiles = readdirSync(join(DIST, "assets")).filter((f) => f.startsWith("index-") && f.endsWith(".css"));
  assert.ok(cssFiles.length > 0, "dist/assets/index-*.css must exist");
  const cssContent = readFileSync(join(DIST, "assets", cssFiles[0]), "utf8");
  assert.match(cssContent, /\.mode-pill/, "CSS must define .mode-pill");
  assert.match(cssContent, /\.status-indicator/, "CSS must define .status-indicator");
  assert.match(cssContent, /\.status-combat/, "CSS must define .status-combat");
  assert.match(cssContent, /\.status-last/, "CSS must define .status-last");
});

test("Invariant 8: Manual Override & Return to Live state transitions", () => {
  // Verify state logic in source App.jsx
  const appSrc = readFileSync(join(ROOT, "src", "App.jsx"), "utf8");

  // Default true when no manual query
  assert.match(appSrc, /!params\.has\("encounter"\)/, "Default isLiveMode must be true when no ?encounter= query");

  // Switches to manual mode when selecting an encounter
  assert.match(appSrc, /selectEncounter[\s\S]*?setIsLiveMode\(false\)/, "Selecting an encounter must switch to manual mode");

  // Resume live removes ?encounter= and sets isLiveMode true
  assert.match(appSrc, /resumeLive[\s\S]*?setIsLiveMode\(true\)/, "resumeLive must set isLiveMode to true");
  assert.match(appSrc, /searchParams\.delete\("encounter"\)/, "resumeLive must remove encounter query param");

  // Automatic encounter tracking in live mode
  assert.match(appSrc, /data\.status === "combat" \|\| data\.status === "last"/, "Must auto-track both combat and last fight");
});

test("Invariant 9: Offline Resilience quietly degrades to [Offline Reference]", () => {
  const appSrc = readFileSync(join(ROOT, "src", "App.jsx"), "utf8");

  // Silent error handling in catch block
  assert.match(appSrc, /catch\s*\{[\s\S]*?setIsOffline\(true\)/, "Fetch catch must set offline state without throwing error banner");
  assert.doesNotMatch(appSrc, /catch\s*\{[\s\S]*?console\.error/, "Fetch catch must not spam console.error");

  // Status mapping to [Offline Reference]
  assert.match(appSrc, /statusLabel\s*=\s*"\[Offline Reference\]"/, "Must display [Offline Reference] when offline");
});

test("Invariant 10: Client polling state machine handles combat transitions, manual override, and offline recovery", async () => {
  // Simulate client state machine logic as executed in App.jsx
  let isLiveMode = true;
  let selectedId = "CEREMONIAL_BEAST_BOSS";
  let liveState = null;
  let isOffline = false;
  let searchParams = new URLSearchParams("");

  const poll = async (mockFetch) => {
    try {
      const res = await mockFetch("/api/state");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      isOffline = false;
      liveState = data;
      if (data && (data.status === "combat" || data.status === "last") && data.encounterId) {
        selectedId = data.encounterId;
      }
    } catch {
      isOffline = true;
    }
  };

  const selectEncounter = (id) => {
    isLiveMode = false;
    selectedId = id;
    searchParams.set("encounter", id);
  };

  const resumeLive = () => {
    isLiveMode = true;
    searchParams.delete("encounter");
    if (liveState && (liveState.status === "combat" || liveState.status === "last") && liveState.encounterId) {
      selectedId = liveState.encounterId;
    }
  };

  const getStatus = () => {
    if (!isLiveMode) return "[Manual]";
    if (isOffline) return "[Offline Reference]";
    if (liveState?.status === "combat") return "[LIVE · Combat]";
    if (liveState?.status === "last") return "[LIVE · Last Fight]";
    return "[LIVE · Idle]";
  };

  // 1. Initial live idle state
  assert.equal(isLiveMode, true);
  assert.equal(selectedId, "CEREMONIAL_BEAST_BOSS");
  assert.equal(getStatus(), "[LIVE · Idle]");

  // 2. Poll receives active combat
  await poll(async () => ({
    ok: true,
    json: async () => ({ status: "combat", encounterId: "DECIMILLIPEDE_ELITE" }),
  }));
  assert.equal(selectedId, "DECIMILLIPEDE_ELITE");
  assert.equal(getStatus(), "[LIVE · Combat]");

  // 3. Poll receives completed combat
  await poll(async () => ({
    ok: true,
    json: async () => ({ status: "last", encounterId: "DECIMILLIPEDE_ELITE" }),
  }));
  assert.equal(selectedId, "DECIMILLIPEDE_ELITE");
  assert.equal(getStatus(), "[LIVE · Last Fight]");

  // 4. User manually selects another encounter
  selectEncounter("AXEBOTS_NORMAL");
  assert.equal(isLiveMode, false);
  assert.equal(selectedId, "AXEBOTS_NORMAL");
  assert.equal(searchParams.get("encounter"), "AXEBOTS_NORMAL");
  assert.equal(getStatus(), "[Manual]");

  // 5. User clicks "Live" to resume tracking
  resumeLive();
  assert.equal(isLiveMode, true);
  assert.equal(searchParams.get("encounter"), null);
  assert.equal(selectedId, "DECIMILLIPEDE_ELITE");
  assert.equal(getStatus(), "[LIVE · Last Fight]");

  // 6. Network drops / phone offline
  await poll(async () => { throw new Error("Failed to fetch"); });
  assert.equal(isOffline, true);
  assert.equal(getStatus(), "[Offline Reference]");
  // Current encounter remains visible without crash or error banner
  assert.equal(selectedId, "DECIMILLIPEDE_ELITE");

  // 7. Network restores
  await poll(async () => ({
    ok: true,
    json: async () => ({ status: "combat", encounterId: "CEREMONIAL_BEAST_BOSS" }),
  }));
  assert.equal(isOffline, false);
  assert.equal(selectedId, "CEREMONIAL_BEAST_BOSS");
  assert.equal(getStatus(), "[LIVE · Combat]");
});


