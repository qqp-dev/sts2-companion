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
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#000"><title>sts2 legacy rollback</title><style>${CSS}</style></head><body><div class="shell"><div class="topbar"><span><i class="live-dot" aria-hidden="true"></i>sts2 · legacy rollback</span><span>temporary · a9 · 2p</span></div>${renderState(state, basePath)}</div><script src="${escapeHtml(basePath)}/client.js" defer></script></body></html>`;
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
:root{color-scheme:dark;--bg:#080a0b;--surface:#111517;--raised:#171d20;--line:#344047;--text:#f4f1e9;--muted:#b7b2a8;--source:#76e7ae;--observed:#8cc9ff;--manual:#f4df82;--unknown:#ffc77d;--danger:#ff9a92;--focus:#fff2a8}
*{box-sizing:border-box;min-width:0}
html,body{width:100%;max-width:100%;overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.48 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-text-size-adjust:100%}
.source-shell{width:100%;max-width:48rem;margin:0 auto;padding:max(.75rem,env(safe-area-inset-top)) max(.75rem,env(safe-area-inset-right)) max(1.25rem,env(safe-area-inset-bottom)) max(.75rem,env(safe-area-inset-left))}
.source-state,.source-state>*{max-width:100%}
.shadow-top{display:flex;flex-wrap:wrap;justify-content:space-between;gap:.25rem 1rem;padding:.15rem .15rem .75rem;color:var(--muted);font-size:.7rem;font-weight:750;letter-spacing:.1em;text-transform:uppercase}
.encounter-hero{padding:1.1rem 1rem 1rem;border:1px solid var(--line);border-bottom:3px solid var(--source);background:linear-gradient(145deg,#151b1e,#0e1214)}
.eyebrow{margin:0 0 .35rem;color:var(--muted);font-size:.72rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase;overflow-wrap:anywhere}
.encounter-title{margin:0;font-size:clamp(1.7rem,9vw,2.45rem);line-height:1.04;letter-spacing:-.025em;overflow-wrap:anywhere}
.static-contract{margin:.75rem 0 0;color:var(--source);font-size:.86rem;font-weight:700}
.boundary-strip{margin:0 0 .8rem;padding:.75rem 1rem;border:1px solid var(--line);border-top:0;background:#0d1113}
.badges,.chips{display:flex;flex-wrap:wrap;gap:.4rem}
.badge,.chip{max-width:100%;border:1px solid currentColor;padding:.2rem .45rem;font-size:.67rem;font-weight:800;letter-spacing:.055em;text-transform:uppercase;overflow-wrap:anywhere}
.badge-source,.chip{color:var(--source)}.badge-observed{color:var(--observed)}.badge-manual{color:var(--manual)}.badge-unknown{color:var(--unknown)}.badge-danger{color:var(--danger)}
.boundary-copy,.boundary-warning{margin:.65rem 0 0;font-size:.82rem}.boundary-copy{color:var(--muted)}.boundary-warning{padding-left:.6rem;border-left:3px solid var(--danger);color:var(--text)}
.capsule-section,.empty-state{margin:0 0 .8rem;padding:1rem;border:1px solid var(--line);background:var(--surface);overflow-wrap:anywhere}
.section-title{margin:0 0 .85rem;font-size:.78rem;line-height:1.2;color:var(--muted);font-weight:850;letter-spacing:.1em;text-transform:uppercase}
.roster-count{margin:0;color:var(--source);font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.065em}
.roster-grammar{margin:.35rem 0;font-size:1.22rem;line-height:1.28;font-weight:760}
.possibility-note,.condition-line,.clock-line,.unknown-line{margin:.55rem 0;padding-left:.65rem;border-left:3px solid var(--unknown)}
.possibility-note,.condition-line,.clock-line{color:#e7d9c3}.quiet,.body-role{color:var(--muted)}.quiet{margin:.5rem 0;font-size:.88rem}
.observed-identities,.mechanic-group,.forms{margin-top:1rem;padding-top:.9rem;border-top:1px solid var(--line)}
.identity-row,.form-line,.path-line,.lifecycle-line,.pool-line{margin:.45rem 0}
.body-card{margin:.9rem -0.25rem 0;padding:1rem .25rem 0;border-top:3px solid var(--line)}.body-card:first-of-type{margin-top:0;border-top:0;padding-top:0}
.body-head{display:grid;gap:.55rem}.body-title{margin:0;font-size:1.35rem;line-height:1.15}.body-role{margin:.2rem 0 0;font-size:.76rem;font-weight:750;letter-spacing:.06em;text-transform:uppercase}
.hp-pill{justify-self:start;padding:.35rem .55rem;border:1px solid var(--source);color:var(--source);font-size:.8rem;line-height:1.25;overflow-wrap:anywhere}
.minor-title{margin:0 0 .55rem;font-size:.79rem;color:var(--muted);font-weight:850;letter-spacing:.07em;text-transform:uppercase}
.initial-effect,.effect-card,.rule-card,.unknown-card,.callout-card{margin:.65rem 0;padding:.75rem;border:1px solid var(--line);background:var(--raised)}
.timing-label{display:inline-block;margin-bottom:.35rem;color:var(--observed);font-size:.69rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.effect-title,.rule-title,.unknown-title,.callout-headline{margin:0 0 .5rem;font-size:1rem;line-height:1.25}
.effect-list{margin:.25rem 0;padding-left:1.35rem}.effect-line{margin:.34rem 0}.effect-list .effect-line{padding-left:.15rem}
.behavior-headline{margin:.2rem 0;font-weight:750}.path-line{padding:.45rem .55rem;border-left:2px solid var(--observed);background:#10171b;font-size:.9rem}
.rule-card .condition-line,.rule-card .clock-line{font-size:.9rem}.pool-line{font-size:.88rem;color:var(--muted)}
.unknown-card{border-left:4px solid var(--unknown)}.unknown-title{color:var(--unknown)}
.callouts{background:#0d1113}.callouts-empty{padding-top:.75rem;padding-bottom:.75rem}.callouts-available{border-color:#50745f}.collection-count{margin:0 0 .65rem;color:var(--source);font-size:.83rem;font-weight:800}.callout-card{border-left:4px solid var(--source)}.callout-cause,.callout-condition{margin:.35rem 0}.callout-condition{color:#e7d9c3}
.audit-capsule{background:#0c0f11}
details{width:100%;max-width:100%;margin-top:.65rem;border-top:1px solid var(--line)}
summary{display:flex;align-items:center;min-height:44px;padding:.4rem 0;cursor:pointer;color:var(--source);font-weight:750;overflow-wrap:anywhere}
summary:hover{text-decoration:underline}summary:focus-visible{outline:3px solid var(--focus);outline-offset:3px;border-radius:2px}
details[open]>summary{margin-bottom:.35rem}.callout-expander>summary{font-size:1rem}
.tree{width:100%;max-width:100%;padding:.12rem 0;overflow-wrap:anywhere;word-break:break-word;font:clamp(.72rem,3.5vw,.82rem)/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
.tree .tree{margin:.18rem 0;padding-left:.5rem;border-left:1px solid var(--line)}.tree-key{color:var(--muted)}.tree-value{color:var(--text)}
.empty-state{padding:1.4rem 1rem}.empty-state h1{margin:0 0 .6rem;font-size:1.55rem}
@media (max-width:23rem){.source-shell{padding-left:.55rem;padding-right:.55rem}.encounter-hero,.capsule-section,.empty-state{padding-left:.8rem;padding-right:.8rem}.initial-effect,.effect-card,.rule-card,.unknown-card,.callout-card{padding:.65rem}.tree .tree{padding-left:.35rem}}
@media (min-width:44rem){.source-shell{padding:1.5rem}.encounter-hero,.capsule-section,.empty-state{padding:1.25rem 1.35rem}.body-head{grid-template-columns:minmax(0,1fr) auto;align-items:start}.hp-pill{justify-self:end;max-width:15rem}}
`;

function sourcePage(basePath) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#070707"><title>StS2 Companion</title><style>${SOURCE_CSS}</style></head><body><div class="source-shell"><div class="shadow-top"><span>StS2 Companion</span><span>static source mechanics</span></div><main id="source-encounter" data-base-path="${escapeHtml(basePath)}" class="source-state"><section class="empty-state"><h1>Loading source mechanics…</h1><p>No live tactical state is inferred.</p></section></main></div><script src="${escapeHtml(basePath)}/client.js" defer></script></body></html>`;
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
  const legacyPath = `${basePath}/legacy`;
  const players = Number(options.players ?? 2);
  const sourceAdapter = options.sourceAdapter ?? createSourceAdapter(options.sourceOptions ?? {});
  return function sts2Handler(req, res) {
    const head = req.method === "HEAD";
    let url;
    try { url = new URL(req.url ?? basePath, "http://sts2.invalid"); }
    catch { text(res, 400, "Malformed request URL", head); return; }
    const pathname = url.pathname;
    const route = pathname === basePath || pathname === `${basePath}/` ? "source-page"
      : pathname === `${basePath}/state` ? "source-state"
        : pathname === `${basePath}/client.js` ? "source-client"
          : pathname === `${basePath}/source` || pathname === `${basePath}/source/` ? "source-page"
            : pathname === `${basePath}/source/state` ? "source-state"
              : pathname === `${basePath}/source/client.js` ? "source-client"
                : pathname === legacyPath || pathname === `${legacyPath}/` ? "legacy-page"
                  : pathname === `${legacyPath}/state` ? "legacy-state"
                    : pathname === `${legacyPath}/client.js` ? "legacy-client" : null;
    if (!route) { text(res, 404, "Not found", head); return; }
    if (req.method !== "GET" && !head) {
      write(res, 405, { Allow: "GET, HEAD", "Content-Type": "text/plain; charset=utf-8" }, "Method not allowed\n", head);
      return;
    }
    if (route === "legacy-client") { write(res, 200, { "Content-Type": "text/javascript; charset=utf-8" }, CLIENT, head); return; }
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
    if (route === "legacy-state") { write(res, 200, { "Content-Type": "application/json; charset=utf-8" }, `${JSON.stringify(state)}\n`, head); return; }
    write(res, 200, { "Content-Type": "text/html; charset=utf-8" }, page(state, legacyPath), head);
  };
}

export const internals = Object.freeze({ SECURITY_HEADERS, escapeHtml, renderState, renderVersion, payload, sourcePage, manualSelector, readSourceObservation });
