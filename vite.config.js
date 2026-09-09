import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { liveStatePlugin } from "./src/state.mjs";

export { liveStatePlugin };

export function entryCacheControlPlugin() {
  const applyHeaders = (req, res, next) => {
    const url = (req.url || "").split("?")[0];
    const isEntryFile =
      url === "" ||
      url === "/" ||
      url.endsWith("/") ||
      url === "/index.html" ||
      url.endsWith("/index.html") ||
      url === "/sw.js" ||
      url.endsWith("/sw.js");

    if (isEntryFile) {
      const noStoreValue = "no-store, no-cache, must-revalidate, max-age=0";
      const origSetHeader = res.setHeader.bind(res);
      const origWriteHead = res.writeHead.bind(res);

      res.setHeader = function (key, val) {
        if (typeof key === "string" && key.toLowerCase() === "cache-control") {
          return origSetHeader(key, noStoreValue);
        }
        return origSetHeader(key, val);
      };

      res.writeHead = function (statusCode, ...args) {
        for (let i = 0; i < args.length; i++) {
          if (args[i] && typeof args[i] === "object" && !Array.isArray(args[i])) {
            for (const k of Object.keys(args[i])) {
              if (k.toLowerCase() === "cache-control") {
                args[i][k] = noStoreValue;
              }
            }
          }
        }
        origSetHeader("Cache-Control", noStoreValue);
        origSetHeader("Pragma", "no-cache");
        return origWriteHead(statusCode, ...args);
      };

      origSetHeader("Cache-Control", noStoreValue);
      origSetHeader("Pragma", "no-cache");
    }
    next();
  };

  return {
    name: "sts2-entry-cache-control",
    configureServer(server) {
      server.middlewares.use(applyHeaders);
    },
    configurePreviewServer(server) {
      server.middlewares.use(applyHeaders);
    },
  };
}

export default defineConfig({
  base: "./",
  server: {
    allowedHosts: true,
  },
  preview: {
    port: 35809,
    host: "127.0.0.1",
    allowedHosts: true,
  },
  plugins: [
    react(),
    entryCacheControlPlugin(),
    liveStatePlugin(),
  ],
  build: {
    target: "esnext",
    chunkSizeWarningLimit: 2000
  }
});
