import { readFileSync } from "node:fs";

import { bookForState, bookMeta } from "./book.mjs";
import { createSourceAdapter } from "./source-adapter.mjs";

const CLIENT = readFileSync(new URL("./client.js", import.meta.url), "utf8");
const SOURCE_CLIENT = readFileSync(new URL("./source-client.js", import.meta.url), "utf8");
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

function renderBody(body, showRawId = false) {
  const count = body.count > 1 ? `${body.count}× ` : "";
  const hp = body.hp
    ? `<div class="hp">${escapeHtml(range(body.hp))} HP</div>`
    : `<div class="hp unknown-field">HP unknown</div>`;
  const role = body.role ? `<div class="role">${escapeHtml(body.role)}</div>` : "";
  const pack = body.pack ? `<div class="pack">pack · ${escapeHtml(body.pack)}</div>` : "";
  const rawId = showRawId && body.monsterId ? `<div class="monster-id">${escapeHtml(body.monsterId)}</div>` : "";
  const flags = (body.sourceFlags ?? []).map((flag) => `<div class="source-flag">${escapeHtml(flag)}</div>`).join("");
  const starts = body.startsWith ? `<div class="starts">starts · ${escapeHtml(body.startsWith)}</div>` : "";
  const pattern = body.pattern
    ? `<div class="pattern${body.pattern.type === "unknown" ? " unknown-field" : ""}"><span class="pattern-type">${escapeHtml(body.pattern.type === "unknown" ? "known unknown · pattern" : body.pattern.type.replaceAll("-", " "))}</span> ${escapeHtml(body.pattern.text)}</div>`
    : `<div class="pattern unknown-field"><span class="pattern-type">known unknown · pattern</span> Pattern data is missing.</div>`;
  const moves = (body.moves ?? []).map((move) => `<div class="move"><strong class="move-name">${escapeHtml(move.name)}${move.intent ? `<small class="move-intent">${escapeHtml(move.intent)}</small>` : ""}</strong><span class="move-text">${escapeHtml(move.text)}</span></div>`).join("");
  return `<article class="body-card"><div class="body-heading"><h2 class="body-name">${escapeHtml(count + body.displayName)}</h2>${hp}</div>${role}${pack}${rawId}${flags}${starts}${pattern}<div class="moves">${moves}</div></article>`;
}

function listSection(title, values) {
  if (!Array.isArray(values) || values.length === 0) return "";
  return `<section class="notes"><h2 class="section-title">${escapeHtml(title)}</h2><ul>${values.map((value) => `<li class="note">${escapeHtml(value)}</li>`).join("")}</ul></section>`;
}

function renderVersion(version) {
  const book = version?.book ?? {};
  const installed = version?.installed;
  const bookLabel = `book ${book.version ?? "unknown"} · ${book.branch ?? "unknown branch"}`;
  if (!installed?.version) {
    return `<div class="version-card known-unknown"><strong>version unknown</strong><span>${escapeHtml(bookLabel)} · installed release_info.json unreadable</span></div>`;
  }
  const installedLabel = `game ${installed.version} · ${installed.branch ?? "unknown branch"}`;
  if (version.matches === false) {
    return `<div class="version-card version-mismatch"><strong>version mismatch</strong><span>${escapeHtml(bookLabel)} · ${escapeHtml(installedLabel)}</span></div>`;
  }
  if (version.matches === true) return "";
  return `<div class="version-card known-unknown"><strong>version unknown</strong><span>${escapeHtml(bookLabel)} · ${escapeHtml(installedLabel)} · comparison unavailable</span></div>`;
}

function renderState(state, basePath) {
  const version = renderVersion(state.version);
  if (state.status === "idle") {
    return `<main id="encounter" data-base-path="${escapeHtml(basePath)}" class="state state-idle">${version}<div class="idle"><p class="idle-copy">no run / no combat · waiting for the next fight</p></div></main>`;
  }
  const book = state.encounter;
  const label = state.status === "combat" ? "combat" : "last";
  const meta = [book?.act, book?.kind].filter(Boolean).join(" · ");
  const rawEncounterId = !book?.known && state.encounterId
    ? `<div class="encounter-id">${escapeHtml(state.encounterId)}</div>` : "";
  let content = `<header class="encounter-header"><div class="status-line status-${label}"><i class="status-dot" aria-hidden="true"></i>${label}</div><h1 class="encounter-name">${escapeHtml(book?.name ?? state.encounterId)}</h1>${rawEncounterId}<div class="meta">${escapeHtml(meta)}</div></header>${version}`;
  if (!book?.known) {
    content += `<div class="unknown">No local book entry for this encounter yet. Raw encounter and monster identities are shown.</div>`;
    content += (book?.lineup ?? []).map((body) => renderBody({ ...body, moves: [] }, true)).join("");
  } else {
    content += `<div class="cards">${book.lineup.map((body) => renderBody(body)).join("")}</div>`;
    content += listSection("death & extra rules", book.rules);
    content += listSection("timing", book.timing);
    content += `<footer class="source"><div class="scale-note">hp ×${book.scale.hp.toFixed(1)} · block ×${book.scale.block} · attacks &amp; combat stats unscaled · mp powers by formula</div><div>source values · wiki.gg · a8 hp · a9 moves · rendered for a9 / 2p</div></footer>`;
  }
  return `<main id="encounter" data-base-path="${escapeHtml(basePath)}" class="state state-${escapeHtml(state.status)}">${content}</main>`;
}

const CSS = `
:root{
  color-scheme:dark;
  --page:#000;
  --text:#e8e8e8;
  --line:#1a1a1a;
  --line-strong:#2a2a2a;
  --muted:#8a8a8a;
  --live:#3ddc84;
  --combat:#f7ce74;
  --danger:#ff6b63;
  --danger-soft:#ffaaa4;
  --chrome-size:1rem;
  font-family:"Geist UI",ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#000;
  color:#e8e8e8;
  font-size:16px;
}
*{box-sizing:border-box}
html,body{min-height:100%;background:#000}
body{margin:0;color:var(--text)}
.shell{width:min(100%,48rem);margin:auto;padding:env(safe-area-inset-top) .9rem calc(3rem + env(safe-area-inset-bottom))}
.topbar{display:flex;align-items:center;justify-content:space-between;min-height:3.25rem;padding:.85rem .1rem;border-bottom:1px solid var(--line);color:var(--muted);font-size:var(--chrome-size);font-weight:560;letter-spacing:.02em;text-transform:lowercase}
.live-dot,.status-dot{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;background:var(--live);margin-right:.5rem;flex:0 0 auto}
.state{padding-top:.1rem}
.encounter-header{padding:1.15rem .1rem 1rem}
.status-line{display:flex;align-items:center;color:var(--muted);font-size:var(--chrome-size);font-weight:560;letter-spacing:.02em;text-transform:lowercase}
.status-combat{color:var(--combat)}
.status-last{color:var(--muted)}
.status-last .status-dot{background:var(--muted)}
.encounter-name{font-size:clamp(1.2rem,4vw,1.65rem);font-weight:650;line-height:1.15;margin:.7rem 0 .35rem;letter-spacing:.02em;text-wrap:balance}
.meta,.role{color:var(--muted);font-size:.85rem;font-weight:560;letter-spacing:.02em;text-transform:lowercase}
.pack{color:var(--muted);font-size:.78rem;margin:.2rem 0 .45rem}
.meta{margin-top:.55rem}
.role{margin-top:.4rem}
.encounter-id,.monster-id{margin-top:.4rem;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--danger-soft);font-size:.75rem;overflow-wrap:anywhere}
.cards{display:grid;gap:.75rem}
.body-card,.notes,.unknown,.version-card{background:#000;border:1px solid var(--line);border-radius:0;padding:1rem}
.body-heading{display:flex;gap:.7rem;justify-content:space-between;align-items:baseline}
.body-name{font-size:1.15rem;font-weight:650;letter-spacing:.02em;margin:0;line-height:1.2}
.hp{white-space:nowrap;color:var(--text);font-size:1rem;font-weight:650}
.starts{margin-top:.75rem;color:var(--text);line-height:1.4}
.pattern{margin-top:.75rem;color:var(--text);line-height:1.4}
.pattern-type{display:inline;color:var(--muted);font-size:.78rem;letter-spacing:.02em;font-weight:650;text-transform:lowercase;margin-right:.2rem}
.moves{margin-top:.85rem;border-top:1px solid var(--line-strong)}
.move{display:grid;grid-template-columns:minmax(5.5rem,35%) 1fr;gap:.7rem;padding:.75rem 0;border-bottom:1px solid var(--line);line-height:1.35}
.move-name{color:var(--text);font-weight:650}
.move-intent{display:block;margin-top:.2rem;color:var(--danger-soft);font-size:.7rem;font-weight:560;letter-spacing:.02em;text-transform:lowercase}
.move-text{color:var(--text)}
.notes{margin-top:.75rem}
.section-title{margin:0 0 .65rem;font-size:var(--chrome-size);font-weight:650;letter-spacing:.02em;text-transform:lowercase}
.notes ul{margin:0;padding-left:1.25rem}
.note{margin:.55rem 0;line-height:1.4}
.source{display:grid;gap:.3rem;padding:1.15rem .1rem;color:var(--muted);font-size:.75rem;line-height:1.4}
.scale-note{position:static;background:transparent;color:var(--muted);padding:0;margin:0;font-size:inherit;font-weight:560}
.version-card{display:grid;gap:.25rem;margin:.2rem 0 .75rem;font-size:.78rem;line-height:1.4}
.version-card strong{color:var(--danger);font-size:.85rem;font-weight:650;letter-spacing:.02em;text-transform:lowercase}
.version-card span{color:var(--danger-soft);overflow-wrap:anywhere}
.known-unknown,.version-mismatch{border-color:var(--line-strong)}
.unknown-field{color:var(--danger-soft)}
.unknown-field .pattern-type{color:var(--danger)}
.hp.unknown-field{color:var(--danger-soft);font-size:.8rem}
.source-flag{margin-top:.65rem;border:1px solid var(--line-strong);border-radius:0;padding:.5rem;color:var(--danger-soft);font-size:.75rem;font-weight:560}
.unknown{margin:.2rem 0 .75rem;color:var(--danger-soft);line-height:1.4}
.idle{padding:2rem .1rem}
.idle-copy{margin:0;color:var(--muted);font-size:.95rem;line-height:1.5}
@media(min-width:42rem){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.body-card:only-child{grid-column:1/-1}}
`;

function page(state, basePath) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#000"><title>sts2 companion</title><style>${CSS}</style></head><body><div class="shell"><div class="topbar"><span><i class="live-dot" aria-hidden="true"></i>sts2 companion</span><span>a9 · 2p</span></div>${renderState(state, basePath)}</div><script src="${escapeHtml(basePath)}/client.js" defer></script></body></html>`;
}

function payload(reader, players) {
  let state;
  try { state = reader.read(); }
  catch { state = { status: "idle", encounterId: null, monsterIds: [], actId: null, roomType: null, source: null, releaseInfo: null }; }
  const installed = state.releaseInfo ?? null;
  const normalizeVersion = (value) => String(value ?? "").trim().toLowerCase();
  const version = {
    book: { version: bookMeta.targetVersion ?? null, branch: bookMeta.targetBranch ?? null },
    installed,
    matches: installed?.version ? normalizeVersion(installed.version) === normalizeVersion(bookMeta.targetVersion) : null,
  };
  return { ...state, ascension: 9, players, version, encounter: bookForState(state, { players }) };
}


const SOURCE_CSS = `
:root{color-scheme:dark;--bg:#070707;--card:#111;--line:#303030;--text:#f2eee7;--muted:#aaa39a;--source:#66e3a4;--observed:#73baff;--legacy:#d6aaff;--unknown:#ffbd70}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 ui-sans-serif,system-ui,sans-serif}.source-shell{max-width:52rem;margin:auto;padding:1rem}.shadow-top{display:flex;justify-content:space-between;color:var(--muted);font-size:.76rem;letter-spacing:.08em;text-transform:uppercase;padding:.3rem 0 1rem}.source-header,.hero,.source-section,.empty{border:1px solid var(--line);background:var(--card);padding:1rem;margin-bottom:.8rem}.badges,.chips{display:flex;gap:.4rem;flex-wrap:wrap}.badge,.chip{border:1px solid currentColor;padding:.15rem .42rem;font-size:.68rem;letter-spacing:.06em;text-transform:uppercase}.badge-source{color:var(--source)}.badge-observed{color:var(--observed)}.badge-legacy{color:var(--legacy)}.badge-unknown{color:var(--unknown)}.badge-manual{color:#f7e481}.authority-line,.canonical,.model-id,.fact-ref{color:var(--muted);font-size:.75rem;overflow-wrap:anywhere;margin-top:.6rem}.eyebrow,.section-heading{color:var(--muted);text-transform:uppercase;font-size:.72rem;letter-spacing:.07em}.hero h1{font-size:1.8rem;margin:.2rem 0}.notice{border-left:2px solid var(--unknown);padding-left:.65rem;color:var(--muted)}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:1rem}.section-heading h2{color:var(--text);font-size:1.05rem;margin:.1rem 0 .8rem}.lead{color:var(--muted)}.chip{color:var(--source);overflow-wrap:anywhere}.chip.produced{color:var(--unknown)}details{border-top:1px solid var(--line);margin-top:.7rem;padding-top:.65rem}summary{cursor:pointer;color:var(--source);font-weight:650}.tree{overflow-wrap:anywhere}.tree .tree{border-left:1px solid var(--line);padding-left:.6rem;margin:.25rem 0}.tree-key{color:var(--muted)}.tree-value{color:var(--text)}.monster-card{border-top:2px solid var(--line);padding:1rem 0}.monster-card:first-of-type{border-top:0}.monster-head{display:flex;justify-content:space-between;gap:1rem;align-items:baseline}.monster-head h3{font-size:1.15rem;margin:.1rem 0}.model-id{text-align:right}.formula{color:var(--unknown)}.mechanic-line{margin:.5rem 0}.subsection,.moves{margin-top:1rem}.subsection h4,.moves h4{font-size:.82rem;text-transform:uppercase;color:var(--muted)}.state-row,.observed-row,.placement{padding:.4rem 0;border-bottom:1px solid var(--line)}.operation{display:grid;gap:.25rem;padding:.65rem 0;border-bottom:1px solid var(--line)}.operation>span{overflow-wrap:anywhere}.intent{display:block;color:var(--unknown);font-size:.72rem;margin-top:.15rem}.unknown{color:var(--unknown)}.move-summary{display:flex;justify-content:space-between;gap:1rem}.empty{padding:2rem 1rem}@media(min-width:44rem){.source-shell{padding:1.5rem}.source-section,.hero,.source-header{padding:1.2rem 1.35rem}}
`;

function sourcePage(basePath) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#070707"><title>sts2 source shadow</title><style>${SOURCE_CSS}</style></head><body><div class="source-shell"><div class="shadow-top"><span>sts2 · source shadow</span><span>non-default · static</span></div><main id="source-encounter" data-base-path="${escapeHtml(basePath)}" class="source-state"><section class="empty"><h1>Loading source mechanics…</h1><p>No live tactical state is inferred.</p></section></main></div><script src="${escapeHtml(basePath)}/source/client.js" defer></script></body></html>`;
}
function readSourceObservation(reader) {
  try { return reader.read(); }
  catch { return { status: "idle", encounterId: null, monsterIds: [], actId: null, roomType: null, source: null, releaseInfo: null }; }
}
function manualSelector(url) {
  const selectors = url.searchParams.getAll("encounter");
  if (selectors.length > 1) return { error: "Ambiguous selector: provide one exact canonical encounter" };
  return { value: selectors.length ? selectors[0] : null };
}

export function createSts2Handler(reader, options = {}) {
  const basePath = String(options.basePath ?? "/sts2").replace(/\/$/, "") || "/sts2";
  const players = Number(options.players ?? 2);
  const sourceAdapter = options.sourceAdapter ?? createSourceAdapter(options.sourceOptions ?? {});
  return function sts2Handler(req, res) {
    const head = req.method === "HEAD";
    let url;
    try { url = new URL(req.url ?? basePath, "http://sts2.invalid"); }
    catch { text(res, 400, "Malformed request URL", head); return; }
    const pathname = url.pathname;
    const route = pathname === basePath || pathname === `${basePath}/` ? "page"
      : pathname === `${basePath}/state` ? "state"
        : pathname === `${basePath}/client.js` ? "client"
          : pathname === `${basePath}/source` || pathname === `${basePath}/source/` ? "source-page"
            : pathname === `${basePath}/source/state` ? "source-state"
              : pathname === `${basePath}/source/client.js` ? "source-client" : null;
    if (!route) { text(res, 404, "Not found", head); return; }
    if (req.method !== "GET" && !head) {
      write(res, 405, { Allow: "GET, HEAD", "Content-Type": "text/plain; charset=utf-8" }, "Method not allowed\n", head);
      return;
    }
    if (route === "client") { write(res, 200, { "Content-Type": "text/javascript; charset=utf-8" }, CLIENT, head); return; }
    if (route === "source-client") {
      if (!sourceAdapter.available) { text(res, 503, sourceAdapter.error, head); return; }
      write(res, 200, { "Content-Type": "text/javascript; charset=utf-8" }, SOURCE_CLIENT, head); return;
    }
    if (route === "source-page" || route === "source-state") {
      if (!sourceAdapter.available) { text(res, 503, sourceAdapter.error, head); return; }
      const selector = manualSelector(url);
      if (selector.error) { text(res, 400, selector.error, head); return; }
      const sourceState = sourceAdapter.view(readSourceObservation(reader), selector.value);
      if (sourceState.status === "invalid-selector") { text(res, 400, sourceState.error, head); return; }
      if (sourceState.status === "unknown-selector") { text(res, 404, sourceState.error, head); return; }
      if (route === "source-state") {
        write(res, 200, { "Content-Type": "application/json; charset=utf-8" }, `${JSON.stringify(sourceState)}\n`, head); return;
      }
      write(res, 200, { "Content-Type": "text/html; charset=utf-8" }, sourcePage(basePath), head); return;
    }
    const state = payload(reader, players);
    if (route === "state") { write(res, 200, { "Content-Type": "application/json; charset=utf-8" }, `${JSON.stringify(state)}\n`, head); return; }
    write(res, 200, { "Content-Type": "text/html; charset=utf-8" }, page(state, basePath), head);
  };
}

export const internals = Object.freeze({ SECURITY_HEADERS, escapeHtml, renderState, renderVersion, payload, sourcePage, manualSelector, readSourceObservation });
