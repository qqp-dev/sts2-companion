import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { liveStatePlugin } from "./src/state.mjs";

export { liveStatePlugin };

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
    liveStatePlugin(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "icons/*.png", "icons/*.svg", "data/**/*.json"],
      manifest: {
        name: "Slay the Spire 2 Encounter Companion",
        short_name: "StS2 Companion",
        description: "Phone-first offline checked static encounter reference for Slay the Spire 2",
        start_url: "./",
        scope: "./",
        display: "standalone",
        orientation: "portrait-primary",
        theme_color: "#000000",
        background_color: "#000000",
        categories: ["games", "reference"],
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any"
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable"
          },
          {
            src: "icons/icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any"
          }
        ]
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,json,svg,png,webmanifest}"]
      }
    })
  ],
  build: {
    target: "esnext",
    chunkSizeWarningLimit: 2000
  }
});
