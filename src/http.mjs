import { readFileSync } from "node:fs";

import { bookForState } from "./book.mjs";

const CLIENT = readFileSync(new URL("./client.js", import.meta.url), "utf8");
const SECURITY_HEADERS = Object.freeze({
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function write(res, status, headers, body, head = false) {
  const content = body == null ? "" : String(body);
  res.writeHead(status, {
    ...SECURITY_HEADERS,
    ...headers,
    "Content-Length": String(Buffer.byteLength(content)),
  });
  res.end(head ? undefined : content);
}

function text(res, status, message, head) {
  write(res, status, { "Content-Type": "text/plain; charset=utf-8" }, `${message}\n`, head);
}

function range(values) {
  if (!Array.isArray(values) || values.length === 0) return "?";
  return values.length === 1 ? String(values[0]) : `${values[0]}–${values[1]}`;
}

function renderBody(body) {
  const count = body.count > 1 ? `${body.count}× ` : "";
  const hp = body.hp ? `<div class="hp">${escapeHtml(range(body.hp))} HP</div>` : "";
  const role = body.role ? `<div class="role">${escapeHtml(body.role)}</div>` : "";
  const starts = body.startsWith ? `<div class="starts">Starts · ${escapeHtml(body.startsWith)}</div>` : "";
  const pattern = body.pattern ? `<div class="pattern"><span class="pattern-type">${escapeHtml(body.pattern.type.replaceAll("-", " "))}</span> ${escapeHtml(body.pattern.text)}</div>` : "";
  const moves = (body.moves ?? []).map((move) => `<div class="move"><strong class="move-name">${escapeHtml(move.name)}</strong><span class="move-text">${escapeHtml(move.text)}</span></div>`).join("");
  return `<article class="body-card"><div class="body-heading"><h2 class="body-name">${escapeHtml(count + body.displayName)}</h2>${hp}</div>${role}<div class="monster-id">${escapeHtml(body.monsterId ?? "")}</div>${starts}${pattern}<div class="moves">${moves}</div></article>`;
}

function listSection(title, values) {
  if (!Array.isArray(values) || values.length === 0) return "";
  return `<section class="notes"><h2 class="section-title">${escapeHtml(title)}</h2><ul>${values.map((value) => `<li class="note">${escapeHtml(value)}</li>`).join("")}</ul></section>`;
}

function renderState(state, basePath) {
  if (state.status === "idle") {
    return `<main id="encounter" data-base-path="${escapeHtml(basePath)}" class="state state-idle"><div class="idle-mark">◇</div><h1 class="idle-title">No run / no combat</h1><p class="idle-copy">Start a fight in Slay the Spire 2. This page will update automatically.</p></main>`;
  }
  const book = state.encounter;
  const label = state.status === "combat" ? "IN COMBAT" : "LAST COMBAT";
  const meta = [book?.act, book?.kind, "A10 · 2 players"].filter(Boolean).join(" · ");
  let content = `<header class="encounter-header"><div class="status-badge">${label}</div><h1 class="encounter-name">${escapeHtml(book?.name ?? state.encounterId)}</h1><div class="encounter-id">${escapeHtml(state.encounterId)}</div><div class="meta">${escapeHtml(meta)}</div></header>`;
  if (!book?.known) {
    content += `<div class="unknown">No local book entry for this encounter yet. The raw encounter identity is still shown.</div>`;
    content += (book?.lineup ?? []).map((body) => renderBody({ ...body, moves: [] })).join("");
  } else {
    content += `<div class="scale-note">HP &amp; buffs ×${book.scale.hpAndBuff.toFixed(1)} · Block ×${book.scale.block} · Attacks unscaled</div>`;
    content += `<div class="cards">${book.lineup.map(renderBody).join("")}</div>`;
    content += listSection("Death & extra rules", book.rules);
    content += listSection("Timing", book.timing);
    content += `<footer class="source">Source values: wiki.gg · A8 HP · A9 moves · rendered for A10 / 2P</footer>`;
  }
  return `<main id="encounter" data-base-path="${escapeHtml(basePath)}" class="state state-${escapeHtml(state.status)}">${content}</main>`;
}

const CSS = `
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;background:#090b10;color:#f6f3ea;font-size:18px}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% -10%,#293a39 0,transparent 34rem),#090b10;min-height:100vh}.shell{width:min(100%,48rem);margin:auto;padding:env(safe-area-inset-top) .85rem calc(5rem + env(safe-area-inset-bottom))}.topbar{display:flex;align-items:center;justify-content:space-between;padding:1rem .15rem;color:#97aaa6;font-size:.78rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase}.live-dot{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;background:#6de2bd;box-shadow:0 0 1rem #6de2bd;margin-right:.45rem}.state{border-top:1px solid #25302f}.encounter-header{padding:1.35rem .15rem 1rem}.status-badge{display:inline-flex;border:1px solid #53645f;border-radius:99rem;padding:.35rem .65rem;font-weight:900;letter-spacing:.14em;font-size:.72rem;color:#c4d3ce}.state-combat .status-badge{color:#090b10;background:#6de2bd;border-color:#6de2bd}.state-last{opacity:.88}.state-last .status-badge{background:#30353b;color:#d2d5da}.encounter-name{font-size:clamp(2rem,10vw,3.7rem);line-height:.95;margin:.8rem 0 .45rem;letter-spacing:-.045em;text-wrap:balance}.role{display:inline-block;margin-top:.45rem;border:1px solid #53645f;border-radius:99rem;padding:.2rem .45rem;color:#9fc9bd;font-size:.61rem;font-weight:900;letter-spacing:.1em;text-transform:uppercase}.encounter-id,.monster-id{font-family:ui-monospace,SFMono-Regular,monospace;color:#71817d;font-size:.68rem;overflow-wrap:anywhere}.meta{color:#afbbb7;font-weight:700;margin-top:.65rem;text-transform:capitalize}.scale-note{position:sticky;top:.5rem;z-index:2;background:#d8b45b;color:#171309;border-radius:.75rem;padding:.65rem .8rem;margin:.4rem 0 1rem;font-size:.75rem;font-weight:900;box-shadow:0 .5rem 2rem #0008}.cards{display:grid;gap:.8rem}.body-card,.notes,.unknown{background:#15191f;border:1px solid #2b3139;border-radius:1rem;padding:1rem;box-shadow:0 .75rem 2.5rem #0004}.body-heading{display:flex;gap:.7rem;justify-content:space-between;align-items:baseline}.body-name{font-size:1.35rem;margin:0;line-height:1.05}.hp{white-space:nowrap;color:#ff9292;font-size:1.2rem;font-weight:950}.starts{margin-top:.8rem;padding:.55rem .7rem;border-left:.2rem solid #d8b45b;background:#211e18;color:#f0d993;font-weight:750}.pattern{margin-top:.75rem;color:#c9d2d0;line-height:1.35}.pattern-type{display:inline-block;color:#86d9c0;text-transform:uppercase;font-size:.66rem;letter-spacing:.09em;font-weight:950;margin-right:.25rem}.moves{margin-top:.8rem;border-top:1px solid #2a3037}.move{display:grid;grid-template-columns:minmax(5.5rem,35%) 1fr;gap:.7rem;padding:.7rem 0;border-bottom:1px solid #242a31;line-height:1.25}.move-name{color:#f3d990}.move-text{color:#d8dadd}.notes{margin-top:.8rem}.section-title{margin:0 0 .65rem;font-size:1.15rem}.notes ul{margin:0;padding-left:1.25rem}.note{margin:.55rem 0;line-height:1.4}.source{padding:1.25rem .2rem;color:#71817d;font-size:.7rem}.unknown{margin-top:1rem;border-color:#7b5b31;color:#f3d990}.idle{text-align:center;padding:18vh 1rem}.idle-mark{font-size:5rem;color:#52615e}.idle-title{font-size:2rem;margin:.5rem 0}.idle-copy{color:#93a09d;line-height:1.5}.state-combat{border-top-color:#6de2bd}@media(min-width:42rem){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.body-card:only-child{grid-column:1/-1}}
`;

function page(state, basePath) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#090b10"><title>STS2 Companion</title><style>${CSS}</style></head><body><div class="shell"><div class="topbar"><span><i class="live-dot"></i>STS2 Companion</span><span>A10 · 2P</span></div>${renderState(state, basePath)}</div><script src="${escapeHtml(basePath)}/client.js" defer></script></body></html>`;
}

function payload(reader, players) {
  let state;
  try { state = reader.read(); }
  catch { state = { status: "idle", encounterId: null, monsterIds: [], actId: null, roomType: null, source: null }; }
  return { ...state, ascension: 10, players, encounter: bookForState(state, { players }) };
}

export function createSts2Handler(reader, options = {}) {
  const basePath = String(options.basePath ?? "/sts2").replace(/\/$/, "") || "/sts2";
  const players = Number(options.players ?? 2);
  return function sts2Handler(req, res) {
    const head = req.method === "HEAD";
    let pathname;
    try { pathname = new URL(req.url ?? basePath, "http://sts2.invalid").pathname; }
    catch { text(res, 400, "Malformed request URL", head); return; }
    const route = pathname === basePath || pathname === `${basePath}/` ? "page"
      : pathname === `${basePath}/state` ? "state"
        : pathname === `${basePath}/client.js` ? "client" : null;
    if (!route) { text(res, 404, "Not found", head); return; }
    if (req.method !== "GET" && !head) {
      write(res, 405, { Allow: "GET, HEAD", "Content-Type": "text/plain; charset=utf-8" }, "Method not allowed\n", head);
      return;
    }
    if (route === "client") {
      write(res, 200, { "Content-Type": "text/javascript; charset=utf-8" }, CLIENT, head); return;
    }
    const state = payload(reader, players);
    if (route === "state") {
      write(res, 200, { "Content-Type": "application/json; charset=utf-8" }, `${JSON.stringify(state)}\n`, head); return;
    }
    write(res, 200, { "Content-Type": "text/html; charset=utf-8" }, page(state, basePath), head);
  };
}

export const internals = Object.freeze({ SECURITY_HEADERS, escapeHtml, renderState, payload });
