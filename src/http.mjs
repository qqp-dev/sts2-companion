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
p,li,summary{overflow-wrap:anywhere}
.site-header,.guide-shell{width:min(calc(100% - 2rem),40rem);margin-inline:auto}
.site-header{display:flex;align-items:center;justify-content:space-between;min-height:3.5rem;border-bottom:1px solid var(--qq-line);color:var(--qq-muted);font-size:.78rem;letter-spacing:.08em;text-transform:uppercase}
.site-header a{color:var(--qq-accent);font-weight:750;text-decoration:none}
.site-header a:hover,summary:hover{color:#fff}
.site-header a:focus-visible,summary:focus-visible{outline:2px solid var(--qq-focus);outline-offset:3px}
.guide-shell{padding-bottom:max(2rem,env(safe-area-inset-bottom))}
.guide-state{width:100%}
.encounter-capsule{padding:1.05rem 0 .95rem;border-bottom:1px solid var(--qq-line)}
.eyebrow,.static-contract,.body-role,.quiet{color:var(--qq-muted)}
.eyebrow{margin:0 0 .28rem;font-size:.76rem;font-weight:560}
.encounter-title{margin:0;font-size:clamp(1.55rem,7.5vw,2.1rem);font-weight:720;letter-spacing:-.025em;line-height:1.08}
.static-contract{margin:.42rem 0 0;font-size:.8rem}
.version-warning{display:grid;gap:.12rem;margin:.8rem 0;padding:.7rem .8rem;border:1px solid #3a2222;border-radius:.4rem;background:#120808;color:var(--qq-danger);font-size:.82rem}
.guide-section{padding:1rem 0;border-bottom:1px solid var(--qq-line)}
.section-title{margin:0 0 .62rem;color:#b8b8b8;font-size:.84rem;font-weight:650;line-height:1.25}
.briefing-section .section-title{color:var(--qq-text);font-size:.94rem}
.fight-shape{margin:0;font-size:1.05rem;font-weight:680;line-height:1.34}
.briefing-highlights{margin-top:.72rem}
.briefing-row{padding:.52rem 0}
.briefing-row+.briefing-row{border-top:1px solid var(--qq-line)}
.briefing-title{margin:0 0 .16rem;font-size:.93rem;line-height:1.25}
.briefing-effect{margin:0;color:#d0d0d0;font-size:.88rem;line-height:1.4}
.boundary-note,.condition-line,.clock-line,.unknown-line{margin:.34rem 0;color:#a8a8a8;font-size:.82rem;line-height:1.4}
.lineup-condition{margin-top:.52rem}
.enemy-summary-card{padding:.72rem 0}
.enemy-summary-card+.enemy-summary-card{border-top:1px solid var(--qq-line)}
.enemy-summary-card:first-of-type{padding-top:.08rem}
.body-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.75rem;align-items:baseline}
.body-title{margin:0;font-size:1.02rem;line-height:1.25}
.body-role{margin:.14rem 0 0;font-size:.74rem;line-height:1.35}
.hp-meta{justify-self:end;max-width:16rem;color:#a8a8a8;font-size:.76rem;font-weight:560;line-height:1.35;text-align:right;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.compact-forms{margin-top:.48rem}
.compact-forms .form-line{margin:.18rem 0;color:#b8b8b8;font-size:.8rem}
.key-mechanics{display:grid;gap:.55rem;margin-top:.58rem}
.key-title{margin:0 0 .12rem;color:#cfcfcf;font-size:.8rem;font-weight:650;line-height:1.3}
.key-mechanic .effect-line{margin:0;color:#b8b8b8;font-size:.83rem;line-height:1.4}
.callouts-section{padding-top:1rem}
.callout-card{margin:0;padding:.25rem 0 .72rem;border:0;border-radius:0;background:transparent}
.callout-card+.callout-card{padding-top:.72rem;border-top:1px solid var(--qq-line)}
.callout-title{margin:0 0 .24rem;font-size:.96rem;line-height:1.3}
details{width:100%;max-width:100%}
summary{position:relative;display:flex;align-items:center;min-height:44px;padding:.62rem 1.35rem .62rem 0;list-style:none;cursor:pointer;color:var(--qq-accent);font-weight:650;line-height:1.3}
summary::-webkit-details-marker{display:none}
summary::after{content:"";position:absolute;right:.2rem;top:50%;width:.38rem;height:.38rem;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:translateY(-65%) rotate(45deg);transform-origin:center}
details[open]>summary::after{transform:translateY(-35%) rotate(225deg)}
.fight-details{margin:0;border-bottom:1px solid var(--qq-line);background:transparent}
.fight-details>summary{min-height:52px;font-size:.95rem}
.fight-detail-content{padding-bottom:.35rem}
.detail-section{padding:.92rem 0;border-top:1px solid var(--qq-line);scroll-margin-top:1rem}
.detail-section:first-child{border-top:0}
.detail-section>.section-title{margin-bottom:.62rem}
.slot-count{margin:0;color:var(--qq-muted);font-size:.76rem;font-weight:560}
.roster-line{margin:.22rem 0;font-size:1rem;font-weight:650;line-height:1.35}
.body-card,.rule-card,.effect-card,.unknown-row{max-width:100%;overflow:visible;border:0;border-radius:0;background:transparent}
.body-card{margin:.72rem 0;padding:0;scroll-margin-top:1rem}
.body-card+.body-card{margin-top:1rem;padding-top:1rem;border-top:1px solid var(--qq-line)}
.mechanic-group{margin-top:.78rem;padding-top:.7rem;border-top:1px solid var(--qq-line)}
.minor-title{margin:0 0 .38rem;color:#a8a8a8;font-size:.81rem;font-weight:650;line-height:1.3}
.fact-row+.fact-row{margin-top:.52rem}
.effect-line,.behavior-line,.form-line,.path-line,.lifecycle-line,.pool-line{margin:.34rem 0}
.path-line{color:#c0c0c0;font-size:.84rem}
.effect-card{margin:.62rem 0;padding:0;scroll-margin-top:1rem}
.effect-title,.rule-title,.unknown-title{margin:0 0 .3rem;font-size:.9rem;line-height:1.3}
.effect-list,.plain-list{margin:.24rem 0;padding-left:1.25rem}
.effect-list .effect-line,.plain-list .effect-line{padding-left:.08rem}
.chips{display:block;margin:.52rem 0;color:#b8b8b8;font-size:.82rem}
.chip{display:inline;padding:0;border:0;border-radius:0;background:transparent;overflow-wrap:anywhere}
.chip+.chip::before{content:" · ";color:var(--qq-muted)}
.rule-card{margin:.68rem 0;padding:0;scroll-margin-top:1rem}
.rule-card+.rule-card{padding-top:.68rem;border-top:1px solid var(--qq-line)}
.pool-line{color:var(--qq-muted);font-size:.8rem}
.lifecycle-card .effect-list{margin-bottom:.42rem}
.unknown-row{margin:.62rem 0;padding:0}
.unknown-row+.unknown-row{padding-top:.62rem;border-top:1px solid var(--qq-line)}
.unknown-title{color:#c8c8c8}
.empty-state{padding:1.4rem 0}
.empty-state h1{margin:0 0 .55rem;font-size:1.5rem}
.technical-audit{margin:0 0 1rem;border-bottom:1px solid var(--qq-line);background:transparent}
.technical-audit>summary{color:var(--qq-muted);font-size:.82rem}
.audit-content{max-width:100%;padding:0 0 .85rem}
.audit-content .quiet{margin:.2rem 0 .62rem;font-size:.8rem}
.detail{margin-top:.35rem;border-top:1px solid var(--qq-line)}
.tree{width:100%;max-width:100%;padding:.1rem 0;overflow-wrap:anywhere;word-break:break-word;font:clamp(.7rem,3.4vw,.8rem)/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
.tree .tree{margin:.15rem 0;padding-left:.6rem}
.tree-key{color:var(--qq-muted)}.tree-value{color:var(--qq-text)}
[id]{scroll-margin-top:1rem}
@media(max-width:42rem){.site-header,.guide-shell{width:100%;padding-left:max(.85rem,env(safe-area-inset-left));padding-right:max(.85rem,env(safe-area-inset-right))}.site-header{min-height:3.2rem}.encounter-capsule{padding-top:.9rem}.guide-section{padding-block:.9rem}}
@media(max-width:23rem){body{font-size:14px}.site-header,.guide-shell{padding-left:max(.65rem,env(safe-area-inset-left));padding-right:max(.65rem,env(safe-area-inset-right))}.body-head{grid-template-columns:minmax(0,1fr);gap:.22rem}.hp-meta{justify-self:start;text-align:left}.tree .tree{padding-left:.35rem}}
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
