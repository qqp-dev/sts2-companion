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
 * Local qq-like compatibility tokens, verified against the stable characteristics
 * in qq-ui/assets/console.css. qq-ui does not publish a shared token contract, so
 * this full-document sibling intentionally keeps a minimal independent layer.
 */
const GUIDE_CSS = `
:root{
  color-scheme:dark;
  font-family:"Geist UI",Geist,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-synthesis:none;
  --qq-bg:#000;
  --qq-surface:#0a0a0a;
  --qq-raised:#111;
  --qq-text:#e8e8e8;
  --qq-muted:#8a8a8a;
  --qq-line:#1a1a1a;
  --qq-accent:#eee;
  --qq-danger:#ffc4bf;
  --qq-focus:#e8e8e8;
  background:var(--qq-bg);
  color:var(--qq-text)
}
*{box-sizing:border-box;min-width:0}
html{max-width:100%;min-height:100%;overflow-x:hidden;-webkit-tap-highlight-color:rgba(225,235,242,.025)}
body{max-width:100%;min-height:100%;margin:0;overflow-x:hidden;background:var(--qq-bg);color:var(--qq-text);font-size:15px;line-height:1.5}
button,input,textarea,select,summary,pre,code,kbd,samp{font:inherit}
a,summary{touch-action:manipulation}
a{color:inherit}
.site-header,.guide-shell{width:min(calc(100% - 2rem),90ch);margin-inline:auto}
.site-header{display:flex;align-items:center;justify-content:space-between;min-height:3.5rem;color:var(--qq-muted);font-size:.83rem;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--qq-line)}
.site-header a{color:var(--qq-accent);font-weight:750;text-decoration:none}
.site-header a:hover{color:#fff}
.site-header a:focus-visible,summary:focus-visible{outline:2px solid var(--qq-focus);outline-offset:3px;border-radius:.15rem}
.guide-shell{padding-bottom:max(2rem,env(safe-area-inset-bottom))}
.guide-state{width:100%}
.encounter-hero{padding:1.15rem 0 1rem;border-bottom:1px solid var(--qq-line)}
.eyebrow,.static-contract,.body-role,.quiet{color:var(--qq-muted)}
.eyebrow{margin:0 0 .3rem;font-size:.75rem;font-weight:650;letter-spacing:.08em;text-transform:uppercase}
.encounter-title{margin:0;font-size:clamp(1.65rem,8vw,2.35rem);font-weight:700;letter-spacing:-.025em;line-height:1.08}
.static-contract{margin:.45rem 0 0;font-size:.87rem}
.version-warning{display:grid;gap:.15rem;margin:.8rem 0;padding:.7rem .8rem;border:1px solid #3a2222;border-radius:.5rem;background:#120808;color:var(--qq-danger);font-size:.86rem}
.guide-section{padding:1rem 0;border-bottom:1px solid var(--qq-line)}
.section-title{margin:0 0 .7rem;color:var(--qq-muted);font-size:.77rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.slot-count{margin:0;color:var(--qq-muted);font-size:.77rem;font-weight:650;text-transform:uppercase;letter-spacing:.05em}
.roster-line{margin:.25rem 0;font-size:1.14rem;font-weight:650;line-height:1.3}
.boundary-note,.condition-line,.clock-line,.unknown-line{margin:.5rem 0;padding-left:.65rem;border-left:2px solid #444;color:#c8c8c8}
.body-card,.rule-card,.effect-card,.unknown-row,.callout-card{max-width:100%;overflow:hidden;border:1px solid var(--qq-line);border-radius:.55rem;background:var(--qq-surface)}
.body-card{margin:.75rem 0;padding:.85rem}
.body-head{display:grid;gap:.55rem;align-items:start}
.body-title{margin:0;font-size:1.28rem;line-height:1.15}
.body-role{margin:.2rem 0 0;font-size:.72rem;font-weight:650;letter-spacing:.055em;text-transform:uppercase}
.hp-pill{justify-self:start;padding:.28rem .48rem;border:1px solid #444;border-radius:.4rem;color:var(--qq-accent);font-size:.79rem;line-height:1.3;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.mechanic-group{margin-top:.8rem;padding-top:.75rem;border-top:1px solid var(--qq-line)}
.minor-title{margin:0 0 .45rem;color:var(--qq-muted);font-size:.74rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase}
.fact-row+.fact-row{margin-top:.55rem}
p{overflow-wrap:anywhere}
.effect-line,.behavior-line,.form-line,.path-line,.lifecycle-line,.pool-line{margin:.38rem 0}
.path-line{padding:.42rem .55rem;border-left:2px solid #444;background:var(--qq-raised);font-size:.88rem}
.effect-card{margin:.55rem 0;padding:.65rem .7rem;background:var(--qq-raised)}
.effect-title,.rule-title,.unknown-title,.callout-title{margin:0 0 .35rem;font-size:.96rem;line-height:1.25}
.effect-list,.plain-list{margin:.25rem 0;padding-left:1.3rem}
.effect-list .effect-line,.plain-list .effect-line{padding-left:.1rem}
.chips{display:flex;flex-wrap:wrap;gap:.35rem;margin:.65rem 0}
.chip{max-width:100%;padding:.22rem .45rem;border:1px solid #2a2a2a;border-radius:.4rem;background:var(--qq-raised);font-size:.8rem;overflow-wrap:anywhere}
.rule-card{margin:.65rem 0;padding:.72rem}
.pool-line{color:var(--qq-muted);font-size:.86rem}
.lifecycle-card .effect-list{margin-bottom:.45rem}
.unknown-row{margin:.55rem 0;padding:.68rem;border-left:3px solid #444}
.unknown-title{color:#c8c8c8}
.callout-card{margin:.55rem 0;padding:.7rem;border-left:3px solid var(--qq-accent)}
.empty-state{padding:1.4rem 0}
.empty-state h1{margin:0 0 .55rem;font-size:1.5rem}
details{width:100%;max-width:100%;margin-top:.6rem;border-top:1px solid var(--qq-line)}
summary{min-height:44px;padding:.55rem .1rem;cursor:pointer;color:var(--qq-accent);font-weight:650;overflow-wrap:anywhere}
summary:hover{color:#fff}
details[open]>summary{margin-bottom:.25rem}
.technical-audit{margin:1rem 0;border:1px solid var(--qq-line);border-radius:.55rem;background:var(--qq-surface);padding:0 .75rem}
.technical-audit>summary{font-size:.9rem}
.audit-content{max-width:100%;padding:0 0 .75rem}
.audit-content .quiet{margin:.2rem 0 .6rem;font-size:.84rem}
.tree{width:100%;max-width:100%;padding:.1rem 0;overflow-wrap:anywhere;word-break:break-word;font:clamp(.7rem,3.4vw,.8rem)/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
.tree .tree{margin:.15rem 0;padding-left:.45rem;border-left:1px solid var(--qq-line)}
.tree-key{color:var(--qq-muted)}.tree-value{color:var(--qq-text)}
@media(min-width:44rem){.body-head{grid-template-columns:minmax(0,1fr) auto}.hp-pill{justify-self:end;max-width:16rem}.body-card{padding:1rem}}
@media(max-width:42rem){.site-header,.guide-shell{width:100%;padding-left:max(.8rem,env(safe-area-inset-left));padding-right:max(.8rem,env(safe-area-inset-right))}.site-header{min-height:3.2rem}.guide-section{padding-block:.9rem}}
@media(max-width:23rem){body{font-size:14px}.site-header,.guide-shell{padding-left:.6rem;padding-right:.6rem}.body-card,.rule-card{padding:.65rem}.tree .tree{padding-left:.3rem}}
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
  const sourceAdapter = options.sourceAdapter ?? createSourceAdapter(options.sourceOptions ?? {});
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
