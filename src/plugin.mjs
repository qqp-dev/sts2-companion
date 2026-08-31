// Optional sibling Cordis entry point. Core does not import this package.
import { createSts2Handler } from "./http.mjs";
import { createStateReader } from "./state.mjs";

export const name = "sts2-companion";
export const inject = ["webServer"];

export function apply(ctx, config = {}) {
  if (ctx.webServer.host !== "127.0.0.1") {
    throw new Error("sts2-companion: refusing a non-loopback web server");
  }
  const basePath = String(config.basePath ?? "/sts2").replace(/\/$/, "") || "/sts2";
  const reader = createStateReader(config);
  const handler = createSts2Handler(reader, { basePath, players: config.players ?? 2 });
  ctx.effect(() => {
    const unregister = ctx.webServer.register({ kind: "prefix", path: basePath, handler });
    return () => unregister();
  }, "sts2-companion: encounter book HTTP routes");

  const registerConsoleMenu = (menuCtx) => {
    const ui = menuCtx.get?.("qq-ui", false) ?? menuCtx["qq-ui"];
    if (!ui?.consoleMenu || typeof ui.consoleMenu.register !== "function") return;
    menuCtx.effect(
      () => ui.consoleMenu.register({
        kind: "navigation",
        id: "sts2-companion",
        label: "StS2 Companion",
        href: basePath,
        order: 100,
      }),
      "sts2-companion: qq-ui navigation",
    );
  };
  if (typeof ctx.inject === "function") ctx.inject(["qq-ui"], registerConsoleMenu);
  else registerConsoleMenu(ctx);
}
