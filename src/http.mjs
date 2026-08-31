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
body{max-width:100%;min-height:100%;margin:0;overflow-x:hidden;background:var(--qq-bg);color:var(--qq-text);font-size:15px;line-height:1.45}
button,input,textarea,select,summary,pre,code,kbd,samp{font:inherit}
a,summary{touch-action:manipulation}
a{color:inherit}
p{overflow-wrap:anywhere}
.site-header,.guide-shell{width:min(calc(100% - 2rem),72ch);margin-inline:auto}
.site-header{display:flex;align-items:center;justify-content:space-between;min-height:3.5rem;color:var(--qq-muted);font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--qq-line)}
.site-header a{color:var(--qq-accent);font-weight:750;text-decoration:none}
.site-header a:hover,summary:hover{color:#fff}
.site-header a:focus-visible,summary:focus-visible{outline:2px solid var(--qq-focus);outline-offset:3px;border-radius:.15rem}
.guide-shell{padding-bottom:max(2rem,env(safe-area-inset-bottom))}
.guide-state{width:100%}
.encounter-capsule{padding:.9rem 0 .8rem;border-bottom:1px solid var(--qq-line)}
.eyebrow,.static-contract,.body-role,.quiet{color:var(--qq-muted)}
.eyebrow{margin:0 0 .24rem;font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.encounter-title{margin:0;font-size:clamp(1.55rem,7.5vw,2.1rem);font-weight:720;letter-spacing:-.025em;line-height:1.08}
.static-contract{margin:.38rem 0 0;font-size:.8rem}
.version-warning{display:grid;gap:.12rem;margin:.7rem 0;padding:.65rem .75rem;border:1px solid #3a2222;border-radius:.45rem;background:#120808;color:var(--qq-danger);font-size:.82rem}
.guide-section{padding:.9rem 0;border-bottom:1px solid var(--qq-line)}
.section-title{margin:0 0 .55rem;color:var(--qq-muted);font-size:.7rem;font-weight:750;letter-spacing:.085em;text-transform:uppercase}
.fight-shape{margin:0;font-size:1.05rem;font-weight:680;line-height:1.32}
.briefing-highlights{margin-top:.62rem;border-left:2px solid #3b3b3b}
.briefing-row{padding:.15rem 0 .52rem .68rem}
.briefing-row+.briefing-row{padding-top:.5rem;border-top:1px solid var(--qq-line)}
.briefing-title{margin:0 0 .16rem;font-size:.93rem;line-height:1.25}
.briefing-effect{margin:0;color:#d0d0d0;font-size:.88rem;line-height:1.38}
.boundary-note,.condition-line,.clock-line,.unknown-line{margin:.38rem 0;padding-left:.55rem;border-left:2px solid #444;color:#bdbdbd;font-size:.84rem}
.lineup-condition{margin-top:.5rem}
.enemy-summary-card{padding:.64rem 0;border-top:1px solid var(--qq-line)}
.enemy-summary-card:first-of-type{border-top:0;padding-top:.05rem}
.body-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.55rem;align-items:start}
.body-title{margin:0;font-size:1.05rem;line-height:1.2}
.body-role{margin:.16rem 0 0;font-size:.65rem;font-weight:700;letter-spacing:.055em;text-transform:uppercase}
.hp-pill{justify-self:end;max-width:15rem;padding:.22rem .4rem;border:1px solid #3a3a3a;border-radius:.35rem;color:var(--qq-accent);font-size:.73rem;line-height:1.3;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.compact-forms{margin-top:.45rem;padding:.35rem .5rem;background:var(--qq-surface)}
.compact-forms .form-line{margin:.15rem 0;font-size:.78rem;color:#c7c7c7}
.key-mechanics{display:grid;gap:.38rem;margin-top:.5rem}
.key-mechanic{padding-left:.55rem;border-left:2px solid #303030}
.key-title{margin:0 0 .1rem;color:#cfcfcf;font-size:.74rem;font-weight:720;letter-spacing:.035em;text-transform:uppercase}
.key-mechanic .effect-line{margin:0;font-size:.83rem;color:#bdbdbd;line-height:1.35}
.callouts-section{padding-top:.85rem}
.callout-card{margin:.5rem 0;padding:.68rem .72rem;border:1px solid #363636;border-left:3px solid var(--qq-accent);border-radius:.45rem;background:var(--qq-surface)}
.callout-title{margin:0 0 .25rem;font-size:.96rem;line-height:1.25}
details{width:100%;max-width:100%}
summary{min-height:44px;padding:.58rem .1rem;cursor:pointer;color:var(--qq-accent);font-weight:680;overflow-wrap:anywhere}
details[open]>summary{margin-bottom:.2rem}
.fight-details{margin:1rem 0 .65rem;border:1px solid #292929;border-radius:.5rem;background:var(--qq-surface);padding:0 .72rem}
.fight-details>summary{min-height:52px;padding:.78rem .05rem;font-size:.96rem}
.fight-detail-content{padding-bottom:.3rem}
.detail-section{padding:.82rem 0;border-top:1px solid var(--qq-line);scroll-margin-top:1rem}
.detail-section:first-child{border-top:0}
.detail-section>.section-title{margin-bottom:.62rem}
.slot-count{margin:0;color:var(--qq-muted);font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.roster-line{margin:.2rem 0;font-size:1rem;font-weight:650;line-height:1.3}
.body-card,.rule-card,.effect-card,.unknown-row{max-width:100%;overflow:hidden;border:1px solid var(--qq-line);border-radius:.48rem;background:#070707}
.body-card{margin:.65rem 0;padding:.72rem;scroll-margin-top:1rem}
.mechanic-group{margin-top:.7rem;padding-top:.62rem;border-top:1px solid var(--qq-line)}
.minor-title{margin:0 0 .38rem;color:var(--qq-muted);font-size:.69rem;font-weight:750;letter-spacing:.07em;text-transform:uppercase}
.fact-row+.fact-row{margin-top:.5rem}
.effect-line,.behavior-line,.form-line,.path-line,.lifecycle-line,.pool-line{margin:.32rem 0}
.path-line{padding:.36rem .48rem;border-left:2px solid #444;background:var(--qq-raised);font-size:.82rem}
.effect-card{margin:.5rem 0;padding:.58rem .62rem;background:var(--qq-raised);scroll-margin-top:1rem}
.effect-title,.rule-title,.unknown-title{margin:0 0 .3rem;font-size:.9rem;line-height:1.25}
.effect-list,.plain-list{margin:.22rem 0;padding-left:1.22rem}
.effect-list .effect-line,.plain-list .effect-line{padding-left:.08rem}
.chips{display:flex;flex-wrap:wrap;gap:.32rem;margin:.58rem 0}
.chip{max-width:100%;padding:.18rem .4rem;border:1px solid #2a2a2a;border-radius:.35rem;background:var(--qq-raised);font-size:.75rem;overflow-wrap:anywhere}
.rule-card{margin:.58rem 0;padding:.65rem;scroll-margin-top:1rem}
.pool-line{color:var(--qq-muted);font-size:.8rem}
.lifecycle-card .effect-list{margin-bottom:.4rem}
.unknown-row{margin:.5rem 0;padding:.62rem;border-left:3px solid #444}
.unknown-title{color:#c8c8c8}
.empty-state{padding:1.4rem 0}
.empty-state h1{margin:0 0 .55rem;font-size:1.5rem}
.technical-audit{margin:.65rem 0 1rem;border-top:1px solid var(--qq-line)}
.technical-audit>summary{color:var(--qq-muted);font-size:.82rem}
.audit-content{max-width:100%;padding:0 0 .75rem}
.audit-content .quiet{margin:.2rem 0 .6rem;font-size:.8rem}
.detail{margin-top:.35rem;border-top:1px solid var(--qq-line)}
.tree{width:100%;max-width:100%;padding:.1rem 0;overflow-wrap:anywhere;word-break:break-word;font:clamp(.7rem,3.4vw,.8rem)/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
.tree .tree{margin:.15rem 0;padding-left:.45rem;border-left:1px solid var(--qq-line)}
.tree-key{color:var(--qq-muted)}.tree-value{color:var(--qq-text)}
[id]{scroll-margin-top:1rem}
@media(max-width:42rem){.site-header,.guide-shell{width:100%;padding-left:max(.8rem,env(safe-area-inset-left));padding-right:max(.8rem,env(safe-area-inset-right))}.site-header{min-height:3.2rem}.guide-section{padding-block:.82rem}}
@media(max-width:23rem){body{font-size:14px}.site-header,.guide-shell{padding-left:.6rem;padding-right:.6rem}.body-head{grid-template-columns:1fr}.hp-pill{justify-self:start}.body-card,.rule-card{padding:.6rem}.tree .tree{padding-left:.3rem}}
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
