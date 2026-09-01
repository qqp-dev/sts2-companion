import { readFileSync } from "node:fs";

import { createSourceAdapter } from "./source-adapter.mjs";

const CLIENT = readFileSync(new URL("./client.js", import.meta.url), "utf8");
const SECURITY_HEADERS = Object.freeze({
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
});
const MAX_STATE_BYTES = 600_000;
const MAX_CLIENT_BYTES = 100_000;

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
function text(res, status, message, head = false) {
  write(res, status, { "Content-Type": "text/plain; charset=utf-8" }, `${message}\n`, head);
}

/*
 * Local qq-like design tokens, verified against the stable characteristics
 * in qq-ui/assets/console.css. qq-ui does not publish a shared token contract, so
 * this full-document sibling intentionally keeps a minimal independent layer.
 */
const GUIDE_CSS = `
/* Local qq-like design tokens. qq-ui does not publish a shared token contract. */
:root{color-scheme:dark;--qq-bg:#000;--qq-surface:#000;--qq-raised:#090909;--qq-text:#e8e8e8;--qq-muted:#8a8a8a;--qq-line:#1a1a1a;--qq-line-strong:#303030;--qq-accent:#f0d27a;--qq-danger:#ff8a82;--qq-focus:#fff;font-family:"Geist UI",Geist,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:16px;background:var(--qq-bg);color:var(--qq-text)}
*{box-sizing:border-box}
html,body{min-height:100%;background:var(--qq-bg)}
body{margin:0;overflow-x:hidden;color:var(--qq-text);font:1rem/1.45 "Geist UI",Geist,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
p{overflow-wrap:anywhere}
.site-header{width:min(100%,44rem);min-height:3.5rem;margin:auto;padding:max(.72rem,env(safe-area-inset-top)) max(.9rem,env(safe-area-inset-right)) .72rem max(.9rem,env(safe-area-inset-left));display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--qq-line);color:var(--qq-muted);font-size:.82rem;letter-spacing:.02em}
.site-header a{color:var(--qq-text);text-decoration:none}.site-header a:focus-visible,summary:focus-visible{outline:2px solid var(--qq-focus);outline-offset:3px}
.guide-shell{width:min(100%,44rem);margin:auto;padding:0 max(.9rem,env(safe-area-inset-right)) calc(2.4rem + env(safe-area-inset-bottom)) max(.9rem,env(safe-area-inset-left))}
.guide-state{width:100%;min-width:0}
.encounter-hero{padding:1.05rem .05rem .92rem;border-bottom:1px solid var(--qq-line)}
.encounter-title{margin:0;font-size:clamp(1.36rem,6vw,1.9rem);font-weight:760;letter-spacing:.045em;line-height:1.08;text-wrap:balance}
.encounter-stats{margin:.48rem 0 0;font-size:1rem;font-weight:700;font-variant-numeric:tabular-nums}
.encounter-placement{margin:.12rem 0 0;color:var(--qq-muted);font-size:.84rem}
.selection-context{margin:.58rem 0 0;padding:0;color:var(--qq-muted);font-size:.7rem;letter-spacing:.055em;text-transform:uppercase}
.eyebrow,.static-contract,.body-role,.quiet{color:var(--qq-muted)}
.eyebrow{margin:.35rem 0 0;font-size:.78rem}.static-contract{margin:.55rem 0 0;font-size:.78rem;line-height:1.35}
.version-warning{display:grid;gap:.12rem;margin:.7rem 0;padding:.58rem .65rem;border:1px solid #4a2424;border-radius:0;background:#100606;color:var(--qq-danger);font-size:.8rem}
.primary-body-list{padding:.15rem 0}.primary-body{padding:.75rem .05rem .2rem}.primary-body+.primary-body{margin-top:.75rem;padding-top:1.15rem;border-top:1px solid var(--qq-line)}
.primary-body-head{margin-bottom:.72rem}.body-title{margin:0;font-size:1.08rem;line-height:1.2}.body-meta{margin:.2rem 0 0;color:var(--qq-muted);font-size:.76rem}
.setup-line{margin:.35rem 0 .8rem;color:#ccc;font-size:.82rem}
.phase-section{padding:1rem 0 .75rem}.phase-section+.phase-section{border-top:1px solid var(--qq-line)}
.phase-head{display:flex;gap:.68rem;align-items:baseline;margin-bottom:.58rem}.phase-number{min-width:1.75rem;color:var(--qq-accent);font-size:.72rem;font-weight:760;letter-spacing:.08em;font-variant-numeric:tabular-nums}.phase-title{margin:0;font-size:.82rem;font-weight:760;letter-spacing:.09em;text-transform:uppercase}
.phase-note{margin:.35rem 0 .65rem;color:#bdbdbd;font-size:.78rem;line-height:1.42}
.sequence-row{display:grid;grid-template-columns:6.35rem minmax(0,1fr);gap:.55rem;padding:.34rem 0;align-items:baseline;margin:0;font-size:.91rem;line-height:1.38}.sequence-row-uncued .sequence-detail{grid-column:2}.sequence-cue{color:var(--qq-muted);font-size:.72rem;line-height:1.3}.sequence-detail{color:#d0d0d0;font-variant-numeric:tabular-nums}
.threshold-line{margin:.7rem 0 .1rem;padding:.55rem 0;border-top:1px solid var(--qq-line-strong);font-size:.82rem}.threshold-label{color:var(--qq-accent);font-size:.7rem;letter-spacing:.075em}.threshold-detail{color:#c8c8c8}
.phase-transition{height:1.35rem;margin:-.12rem 0 -.55rem;color:var(--qq-muted);font-size:.92rem;line-height:1.35;text-align:center}
.repeat-line{margin:.65rem 0 0;color:var(--qq-accent);font-size:.74rem;letter-spacing:.025em}
.watch-line,.reference-note,.callout-card{margin:.75rem 0;padding:.05rem 0 .05rem .62rem;border-left:2px solid var(--qq-accent);background:transparent;font-size:.83rem}.watch-label,.reference-note-label,.callout-title{color:var(--qq-accent);font-size:.72rem;letter-spacing:.045em;text-transform:uppercase}.watch-detail{color:#d0d0d0}
.reference-notes{padding:.3rem .05rem .1rem;border-top:1px solid var(--qq-line)}.reference-note{border-left-color:var(--qq-line-strong)}
.guide-footer{margin-top:.7rem;padding:.72rem .05rem;border-top:1px solid var(--qq-line)}.provenance-line{margin:0;color:var(--qq-muted);font-size:.68rem;letter-spacing:.03em}
/* Source-only fallback rendering uses the same flat language. */
.roster-capsule{display:grid;gap:.18rem;margin:.72rem 0 .1rem;padding:.4rem 0;border-top:1px solid var(--qq-line)}.capsule-label{color:var(--qq-muted);font-size:.68rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase}.roster-line{font-size:.9rem;font-weight:650}.roster-capsule .boundary-note{padding:0;border:0}
.body-list{display:grid;padding:.25rem 0}.body-card{max-width:100%;overflow:hidden;padding:.8rem .05rem;background:transparent}.body-card+.body-card{border-top:1px solid var(--qq-line)}
.body-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.6rem;align-items:start}.body-role{margin:.16rem 0 0;font-size:.64rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase}.hp-pill{justify-self:end;max-width:13rem;padding:.13rem 0;font-size:.82rem;line-height:1.25;text-align:right;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.hp-note{margin:.48rem 0 0;color:#cfcfcf;font-size:.79rem}
.mechanic-group{margin-top:.62rem;padding-top:.58rem;border-top:1px solid var(--qq-line)}.minor-title,.section-title{margin:0 0 .4rem;color:var(--qq-muted);font-size:.68rem;font-weight:750;letter-spacing:.075em;text-transform:uppercase}.fact-row+.fact-row{margin-top:.42rem}
.effect-line,.behavior-line,.form-line,.path-line,.lifecycle-line,.pool-line{margin:.25rem 0}.unknown-line,.condition-line,.clock-line,.boundary-note{margin:.32rem 0;padding-left:.5rem;border-left:2px solid var(--qq-line-strong);color:#bdbdbd;font-size:.79rem}
.effect-row{display:grid;grid-template-columns:1.42rem minmax(0,1fr);gap:.42rem;padding:.38rem 0;border-top:1px solid var(--qq-line)}.effect-row:first-of-type{border-top:0}.sequence-marker{padding-top:.08rem;color:var(--qq-muted);font-size:.67rem;font-weight:750;font-variant-numeric:tabular-nums}.effect-list,.plain-list{margin:0;padding-left:1.15rem}.path-line{padding:.28rem 0;color:#bbb;font-size:.78rem}.behavior-line{font-size:.86rem;font-weight:620}
.rule-card,.unknown-row{max-width:100%;overflow:hidden;margin:.45rem 0;padding:.35rem 0;background:transparent}.rule-title,.unknown-title,.callout-title{margin:0 0 .3rem;line-height:1.25}.pool-line{color:var(--qq-muted);font-size:.78rem}.callout-card .effect-line{font-size:.86rem}.guide-section{padding:.8rem 0;border-top:1px solid var(--qq-line)}
.empty-state{padding:1.35rem 0}.empty-state h1{margin:0 0 .5rem;font-size:1.4rem}
details{width:100%;max-width:100%;margin-top:.55rem;border-top:1px solid var(--qq-line)}summary{min-height:44px;padding:.55rem .05rem;cursor:pointer;color:var(--qq-accent);font-weight:650;overflow-wrap:anywhere}summary:hover{color:#fff}details[open]>summary{margin-bottom:.2rem}.known-gaps{margin:.75rem 0}.technical-audit{margin:.9rem 0;padding:0;background:transparent}.technical-audit>summary{font-size:.8rem}.audit-content{max-width:100%;padding:0 0 .65rem}.audit-content .quiet{margin:.15rem 0 .55rem;font-size:.76rem}
.tree{width:100%;max-width:100%;padding:.08rem 0;overflow-wrap:anywhere;word-break:break-word;font:clamp(.68rem,3.2vw,.78rem)/1.48 ui-monospace,SFMono-Regular,Consolas,monospace}.tree .tree{margin:.12rem 0;padding-left:.4rem;border-left:1px solid var(--qq-line)}.tree-key{color:var(--qq-muted)}.tree-value{color:var(--qq-text)}
@media(min-width:44rem){.guide-shell{padding-inline:1.2rem}.encounter-hero{padding-top:1.2rem}.primary-body-list,.body-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));column-gap:1.5rem;align-items:start}.primary-body+.primary-body,.body-card+.body-card{margin-top:0;padding-top:.8rem;border-top:0}.primary-body:nth-child(even),.body-card:nth-child(even){padding-left:1rem;border-left:1px solid var(--qq-line)}.guide-section{clear:both}}
@media(max-width:21rem){:root{font-size:15px}.site-header,.guide-shell{width:100%;padding-left:max(.65rem,env(safe-area-inset-left));padding-right:max(.65rem,env(safe-area-inset-right))}.sequence-row{grid-template-columns:5.65rem minmax(0,1fr);gap:.38rem}.body-head{grid-template-columns:1fr}.hp-pill{justify-self:start;text-align:left}.tree .tree{padding-left:.28rem}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;scroll-behavior:auto!important;transition:none!important}}
`;

function guidePage(basePath) {
  const path = escapeHtml(basePath);
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#000000"><title>StS2 Companion</title><style>${GUIDE_CSS}</style></head><body><header class="site-header"><a href="/qq">qq</a><span>StS2 Companion</span></header><div class="guide-shell"><main id="guide-encounter" data-base-path="${path}" class="guide-state"><section class="empty-state"><h1>Loading combat guide…</h1><p class="quiet">No live combat state is inferred.</p></section></main></div><script src="${path}/client.js" defer></script></body></html>`;
}
function readObservation(reader) {
  try { return reader.read(); }
  catch { return { status: "idle", encounterId: null, monsterIds: [], actId: null, roomType: null, source: null, releaseInfo: null }; }
}
function manualSelector(url) {
  const selectors = url.searchParams.getAll("encounter");
  if (selectors.length > 1) return { error: "Ambiguous selector: provide one exact checked encounter" };
  return { value: selectors.length ? selectors[0] : null };
}

export function createSts2Handler(reader, options = {}) {
  const basePath = String(options.basePath ?? "/sts2").replace(/\/$/, "") || "/sts2";
  const sourceAdapter = options.sourceAdapter ?? createSourceAdapter({ ...options.sourceOptions, players: options.players ?? options.sourceOptions?.players });
  return function sts2Handler(req, res) {
    const head = req.method === "HEAD";
    let url;
    try { url = new URL(req.url ?? basePath, "http://sts2.invalid"); }
    catch { text(res, 400, "Malformed request URL", head); return; }
    const route = url.pathname === basePath ? "page"
      : url.pathname === `${basePath}/state` ? "state"
        : url.pathname === `${basePath}/client.js` ? "client" : null;
    if (!route) { text(res, 404, "Not found", head); return; }
    if (req.method !== "GET" && !head) {
      write(res, 405, { Allow: "GET, HEAD", "Content-Type": "text/plain; charset=utf-8" }, "Method not allowed\n");
      return;
    }
    if (!sourceAdapter.available) { text(res, 503, sourceAdapter.error, head); return; }
    if (route === "client") {
      if (Buffer.byteLength(CLIENT) > MAX_CLIENT_BYTES) { text(res, 503, "Guide client exceeds its bounded response", head); return; }
      write(res, 200, { "Content-Type": "text/javascript; charset=utf-8" }, CLIENT, head);
      return;
    }
    const selector = manualSelector(url);
    if (selector.error) { text(res, 400, selector.error, head); return; }
    const state = sourceAdapter.view(readObservation(reader), selector.value);
    if (state.status === "invalid-selector") { text(res, 400, state.error, head); return; }
    if (state.status === "unknown-selector") { text(res, 404, state.error, head); return; }
    if (route === "state") {
      const body = `${JSON.stringify(state)}\n`;
      if (Buffer.byteLength(body) > MAX_STATE_BYTES) { text(res, 503, "Guide state exceeds its bounded response", head); return; }
      write(res, 200, { "Content-Type": "application/json; charset=utf-8" }, body, head);
      return;
    }
    write(res, 200, { "Content-Type": "text/html; charset=utf-8" }, guidePage(basePath), head);
  };
}

export const internals = Object.freeze({
  SECURITY_HEADERS, GUIDE_CSS, MAX_CLIENT_BYTES, MAX_STATE_BYTES,
  escapeHtml, guidePage, manualSelector, readObservation,
});
