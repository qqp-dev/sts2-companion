import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const START = /Creating NCombatRoom with mode=ActiveCombat encounter=([A-Z0-9_]+)/;
const WIN = /has won against encounter (?:ENCOUNTER\.)?([A-Z0-9_]+)/;
const TERMINAL = /Combat state becomes NotInCombat|\bNotInCombat\b/;
const COMBAT_ROOM_TYPES = new Set(["monster", "elite", "boss"]);

function unprefix(value, prefix) {
  const text = typeof value === "string" ? value : "";
  return text.startsWith(prefix) ? text.slice(prefix.length) : text;
}

/** Parse combat lifecycle only. Move logs are deliberately ignored. */
export function parseLog(text) {
  let encounterId = null;
  let status = "idle";
  for (const line of String(text ?? "").split(/\r?\n/)) {
    const start = line.match(START);
    if (start) {
      encounterId = start[1];
      status = "combat";
      continue;
    }
    if (!encounterId) continue;
    const win = line.match(WIN);
    if (win && win[1] === encounterId) {
      status = "last";
      continue;
    }
    if (TERMINAL.test(line)) status = "last";
  }
  return encounterId ? { status, encounterId } : { status: "idle", encounterId: null };
}

function roomCandidates(point) {
  if (!point || typeof point !== "object") return [];
  if (Array.isArray(point.rooms)) return point.rooms;
  // Be permissive with single-room fixtures and future schema revisions.
  return point.room && typeof point.room === "object" ? [point.room] : [];
}

/** Parse the final completed combat room from the multiplayer run save. */
export function parseSave(input) {
  const save = typeof input === "string" || Buffer.isBuffer(input)
    ? JSON.parse(String(input))
    : input;
  if (!save || typeof save !== "object") return null;

  const groups = Array.isArray(save.map_point_history) ? save.map_point_history : [];
  let found = null;
  for (let actIndex = 0; actIndex < groups.length; actIndex += 1) {
    const points = Array.isArray(groups[actIndex]) ? groups[actIndex] : [groups[actIndex]];
    for (const point of points) {
      for (const room of roomCandidates(point)) {
        const roomType = String(room?.room_type ?? point?.map_point_type ?? "").toLowerCase();
        if (!COMBAT_ROOM_TYPES.has(roomType)) continue;
        const encounterId = unprefix(room?.model_id, "ENCOUNTER.");
        if (!encounterId) continue;
        const act = Array.isArray(save.acts) ? save.acts[actIndex] : null;
        found = {
          status: "last",
          encounterId,
          monsterIds: Array.isArray(room.monster_ids)
            ? room.monster_ids.map((id) => unprefix(id, "MONSTER.")).filter(Boolean)
            : [],
          actId: unprefix(act?.id, "ACT.") || null,
          roomType,
        };
      }
    }
  }
  return found;
}

/** Parse only the release fields needed for local book compatibility. */
export function parseReleaseInfo(input) {
  const value = typeof input === "string" || Buffer.isBuffer(input)
    ? JSON.parse(String(input))
    : input;
  if (!value || typeof value !== "object") return null;
  const version = typeof value.version === "string" ? value.version : null;
  const branch = typeof value.branch === "string" ? value.branch : null;
  return version || branch ? { version, branch } : null;
}

function regularFiles(paths) {
  return [...new Set(paths.filter(Boolean))].filter((path) => {
    try { return statSync(path).isFile(); } catch { return false; }
  });
}

function newest(paths) {
  return regularFiles(paths).sort((a, b) => {
    try { return statSync(b).mtimeMs - statSync(a).mtimeMs; } catch { return 0; }
  })[0] ?? null;
}

function defaultRoots(env, home) {
  const xdgData = env.XDG_DATA_HOME ?? join(home, ".local", "share");
  return [
    join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "SlayTheSpire2"),
    join(home, ".var", "app", "com.megacrit.cardcrawl2", "data", "SlayTheSpire2"),
    join(xdgData, "SlayTheSpire2"),
  ];
}

function logFiles(root) {
  const dir = join(root, "logs");
  try {
    return readdirSync(dir)
      .filter((name) => /^godot(?:.*)\.log$/i.test(name))
      .map((name) => join(dir, name));
  } catch {
    return [];
  }
}

function saveFiles(root) {
  const steam = join(root, "steam");
  try {
    return readdirSync(steam, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => join(steam, entry.name, "profile1", "saves", "current_run_mp.save"));
  } catch {
    return [];
  }
}

function defaultReleaseInfoPaths(env, home) {
  const xdgData = env.XDG_DATA_HOME ?? join(home, ".local", "share");
  return [
    join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam", "steamapps", "common", "Slay the Spire 2", "release_info.json"),
    join(home, ".steam", "steam", "steamapps", "common", "Slay the Spire 2", "release_info.json"),
    join(xdgData, "Steam", "steamapps", "common", "Slay the Spire 2", "release_info.json"),
  ];
}

export function resolvePaths(options = {}) {
  const env = options.env ?? process.env;
  const home = options.home ?? env.HOME ?? homedir();
  const roots = options.rootPaths ?? (options.root ? [options.root] : defaultRoots(env, home));
  const logs = options.logPaths ?? (options.logPath ? [options.logPath] : roots.flatMap(logFiles));
  const saves = options.savePaths ?? (options.savePath ? [options.savePath] : roots.flatMap(saveFiles));
  const explicitRelease = options.releaseInfoPath
    ? [options.releaseInfoPath]
    : options.gamePath ? [join(options.gamePath, "release_info.json")] : null;
  const releases = options.releaseInfoPaths ?? explicitRelease ?? defaultReleaseInfoPaths(env, home);
  return { logPath: newest(logs), savePath: newest(saves), releaseInfoPath: newest(releases) };
}

function safeRead(path) {
  try { return path && existsSync(path) ? readFileSync(path, "utf8") : null; }
  catch { return null; }
}

/** A read-through reader: every HTTP poll sees newly appended/rotated files. */
export function createStateReader(options = {}) {
  return {
    read() {
      const paths = resolvePaths(options);
      const logText = safeRead(paths.logPath);
      const saveText = safeRead(paths.savePath);
      const releaseText = safeRead(paths.releaseInfoPath);
      let log = { status: "idle", encounterId: null };
      let saved = null;
      let releaseInfo = null;
      try { if (logText != null) log = parseLog(logText); } catch { /* idle */ }
      try { if (saveText != null) saved = parseSave(saveText); } catch { /* mid-write */ }
      try { if (releaseText != null) releaseInfo = parseReleaseInfo(releaseText); } catch { /* unreadable/mid-update */ }

      if (log.status !== "idle") {
        const matching = saved?.encounterId === log.encounterId ? saved : null;
        return {
          ...log,
          monsterIds: matching?.monsterIds ?? [],
          actId: matching?.actId ?? null,
          roomType: matching?.roomType ?? null,
          source: "log",
          releaseInfo,
        };
      }
      if (saved) return { ...saved, source: "save", releaseInfo };
      return {
        status: "idle",
        encounterId: null,
        monsterIds: [],
        actId: null,
        roomType: null,
        source: null,
        releaseInfo,
      };
    },
  };
}

export const internals = Object.freeze({ defaultRoots, defaultReleaseInfoPaths, logFiles, saveFiles, newest, unprefix });
