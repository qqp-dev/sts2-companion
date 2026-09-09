#!/usr/bin/env node
import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ICONS_DIR = join(ROOT, "public", "icons");
mkdirSync(ICONS_DIR, { recursive: true });

// 1. Generate SVG icon
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect width="512" height="512" fill="#000000"/>
  <!-- Outer accent ring -->
  <circle cx="256" cy="256" r="236" fill="none" stroke="#1a1a1a" stroke-width="8"/>
  <circle cx="256" cy="256" r="216" fill="none" stroke="#f0d27a" stroke-width="4" opacity="0.4"/>
  
  <!-- Spire Monolith -->
  <polygon points="256,60 320,380 256,430 192,380" fill="#121212" stroke="#f0d27a" stroke-width="6"/>
  
  <!-- Spire Core Gem (Danger Red) -->
  <polygon points="256,180 285,250 256,320 227,250" fill="#ff8a82" stroke="#f0d27a" stroke-width="4"/>
  
  <!-- Lateral blades -->
  <polygon points="192,380 140,330 180,270" fill="#0a0a0a" stroke="#f0d27a" stroke-width="4"/>
  <polygon points="320,380 372,330 332,270" fill="#0a0a0a" stroke="#f0d27a" stroke-width="4"/>
  
  <!-- Central line -->
  <line x1="256" y1="60" x2="256" y2="430" stroke="#f0d27a" stroke-width="3" opacity="0.7"/>
  
  <!-- Label -->
  <text x="256" y="475" text-anchor="middle" font-family="'Geist UI', system-ui, sans-serif" font-size="34" font-weight="800" fill="#f0d27a" letter-spacing="4">STS2</text>
</svg>`;

writeFileSync(join(ICONS_DIR, "icon.svg"), svg, "utf8");

// 2. Pure Node PNG generator
function createPng(width, height, drawPixel) {
  const rowBytes = width * 4 + 1;
  const raw = Buffer.alloc(rowBytes * height);
  for (let y = 0; y < height; y++) {
    const offset = y * rowBytes;
    raw[offset] = 0; // Filter: None
    for (let x = 0; x < width; x++) {
      const [r, g, b, a] = drawPixel(x, y, width, height);
      const p = offset + 1 + x * 4;
      raw[p] = r; raw[p + 1] = g; raw[p + 2] = b; raw[p + 3] = a;
    }
  }
  const compressed = deflateSync(raw);
  const crcTable = [];
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = ((c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1));
    crcTable[n] = c;
  }
  function crc32(buf) {
    let crc = 0xffffffff;
    for (let i = 0; i < buf.length; i++) crc = crcTable[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }
  function chunk(type, data) {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const t = Buffer.from(type, "ascii");
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data])));
    return Buffer.concat([len, t, data, crc]);
  }
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([sig, chunk("IHDR", ihdr), chunk("IDAT", compressed), chunk("IEND", Buffer.alloc(0))]);
}

function renderSpireIcon(x, y, size) {
  const cx = size / 2;
  const cy = size / 2;
  const dx = x - cx;
  const dy = y - cy;
  const dist = Math.sqrt(dx * dx + dy * dy);

  // Background: black
  let r = 0, g = 0, b = 0, a = 255;

  // Thin outer gold ring
  if (Math.abs(dist - size * 0.44) < size * 0.015) {
    return [240, 210, 122, 255];
  }

  // Inner Spire shape
  // Normalize coords to [-1, 1]
  const nx = dx / (size * 0.5);
  const ny = dy / (size * 0.5);

  // Spire spire tip: ny around -0.7, base around +0.6
  if (ny > -0.75 && ny < 0.65) {
    const halfWidth = 0.25 * ((ny + 0.75) / 1.4);
    if (Math.abs(nx) < halfWidth) {
      // Core gem in red
      const gemDy = Math.abs(ny - 0.0);
      const gemDx = Math.abs(nx);
      if (gemDx * 2 + gemDy < 0.25) {
        return [255, 138, 130, 255]; // Red core
      }
      // Spire body
      return [24, 24, 24, 255];
    }
    // Border of spire
    if (Math.abs(Math.abs(nx) - halfWidth) < 0.02) {
      return [240, 210, 122, 255];
    }
  }

  // Center vertical line
  if (Math.abs(nx) < 0.008 && ny > -0.75 && ny < 0.65) {
    return [240, 210, 122, 200];
  }

  return [r, g, b, a];
}

writeFileSync(join(ICONS_DIR, "icon-192.png"), createPng(192, 192, (x, y, s) => renderSpireIcon(x, y, s)));
writeFileSync(join(ICONS_DIR, "icon-512.png"), createPng(512, 512, (x, y, s) => renderSpireIcon(x, y, s)));

// 3. Manifest
const manifest = {
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
};

writeFileSync(join(ROOT, "public", "manifest.webmanifest"), JSON.stringify(manifest, null, 2), "utf8");
console.log("Icons and manifest generated successfully.");
