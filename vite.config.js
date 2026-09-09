import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
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
  ],
  build: {
    target: "esnext",
    chunkSizeWarningLimit: 2000
  }
});
