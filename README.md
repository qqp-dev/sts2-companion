# sts2-companion

Phone-first, read-only **Slay the Spire 2** encounter reference for the optional
qq Cordis sibling. It reads local log/save/release metadata, never sends game
input, and makes no runtime network requests.

## Open it

The existing stable page remains the default and is behaviorally unchanged:

- local: <http://127.0.0.1:3082/sts2>
- Tailscale: <https://qq-box.tail580136.ts.net/sts2>

The additive source-first shadow is opt-in by URL and is **not the default**:

- local: <http://127.0.0.1:3082/sts2/source>
- Tailscale: <https://qq-box.tail580136.ts.net/sts2/source>

For static reference browsing, append one exact, case-sensitive canonical ID,
for example:

<http://127.0.0.1:3082/sts2/source?encounter=AXEBOTS_NORMAL>

Unknown or repeated selectors fail clearly; there is no fuzzy matching. The
shadow polls encounter identity only. A manual selection stays manual and is not
replaced by polling.

## What each surface means

### Stable `/sts2`

The production/default page continues to use `data/encounters.json` through the
existing `book.mjs` and state reader. It shows A9 / 2P legacy reference material
for a current combat or most recently completed room. This route, its JSON at
`/sts2/state`, and `/sts2/client.js` are unchanged by the shadow.

### Shadow `/sts2/source`

The shadow reads only the checked compact projection
`data/encounter-facts-v0.111.0.json`, once at startup, through a strict adapter.
The projection's `matchingPolicy.prefixStripping:false` governs exact source
observation identities; it is not relaxed. Saves have already been converted to
the stable state-reader model-ID representation, so the adapter builds a
collision-checked bridge by applying that same reader conversion to each
validated projection row. It does not guess aliases, fold case, or fuzzy-match.
It renders rich **static mechanics**: placement, initial roster grammar, HP
expressions, states, initial effects, move intents/ordered operations/graphs,
production, event scripts, lifecycle boundaries, affected unknowns/conflicts,
and expandable evidence.

It does **not** read the raw source artifact, execute/read game binaries, recreate
the projection generator, predict the next move, or observe current HP, Block,
Powers, intent, turn, phase, hand, or live body survival. Possible initial
bodies, state-reader body IDs, and produced bodies remain separate. SOURCE,
OBSERVED, LEGACY, and UNKNOWN lanes never silently merge.

No editorial source-qualified tactical callouts are currently checked in, so the
shadow truthfully exposes an empty `callouts: []`. That means zero qualifying
records are available, not a one-card quota. The future collection contract is
`0..N`; collapsed display limits never discard passing records.

## Authority, readiness, and version boundary

This repository targets unmodded Steam public-beta **v0.111.0**. Runtime source
consumption is accepted only for explicitly supported compact projection schemas
and the corresponding generator major, exact game authority, complete required
joins/components, and pinned DLL SHA-256:

```text
2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f
```

`encounterProjection.ready` is required. The broader
`encounterCompanion.ready` intentionally remains false and is not a shadow gate.
Unknown inputs stay named/conditional; they are never converted to zero or a
legacy default. A malformed or unsupported compact projection returns 503 only
on shadow routes; stable routes continue serving the legacy book.

Detailed current schema/readiness and landed-wave history live in:

- [source world model](docs/source-world-model.md)
- [v0.111.0 source migration ledger](docs/source-migration-ledger.md)
- [decision projection and callout contract](docs/decision-projection.md)

Schema numbers are intentionally not duplicated here because coordinated source
closeouts may advance them. The adapter itself is the runtime allowlist.

## Install and run

This package is an optional sibling; qq-core must still start when it is absent.
The sibling profile layer is `cordis.patch.yml`. The web server must remain bound
to `127.0.0.1`; the plugin refuses any non-loopback host. On this machine,
Tailscale Serve terminates HTTPS and proxies to that loopback service. Do not
weaken the loopback restriction to expose the plugin.

The state reader probes the supported Steam Flatpak/native XDG data roots. Paths,
base path, and player count remain injectable for tests and alternate installs.
The browser routes use exact matching, no-store responses, a restrictive CSP,
frame denial, MIME sniffing denial, referrer suppression, and escaped/DOM text
rendering.

## Generate and check

Projection generation is deterministic and offline from checked inputs:

```sh
npm run build:encounter-facts
npm run check:encounter-facts
```

Raw-source regeneration is a development operation requiring the exact local
game files and isolated Python dependencies; it is not a runtime requirement:

```sh
python3 -m venv .venv-source
.venv-source/bin/python -m pip install -r requirements-source.txt
GAME_ROOT="${STS2_GAME_ROOT:-/home/qqp/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Slay the Spire 2}"
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --check
```

Run all Node and Python tests with:

```sh
npm test
```

No generated data change is expected for shadow-only UI work.

## Rollback or removal

The shadow is additive: keep using `/sts2` to opt out immediately. To remove the
runtime entirely, disable/remove the optional `@hypermemetic-ai/sts2-companion`
sibling from the qq profile; qq-core remains independent. A code rollback can
remove the `/sts2/source*` routes and `source-*`/callout modules without changing
`data/encounters.json`, the state reader, stable assets, or the default link.
Never switch `/sts2` to source-first without a separately reviewed migration and
QA gate.
