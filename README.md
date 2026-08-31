# sts2-companion

Phone-first, read-only **Slay the Spire 2** combat guidance for the optional qq
Cordis sibling. It reads checked local encounter facts and local
log/save/release metadata, never sends game input, and makes no runtime external
network requests.

## Open it

StS2 Companion has one user-facing document:

- local: <http://127.0.0.1:3082/sts2>
- Tailscale: <https://qq-box.tail580136.ts.net/sts2>

For static reference browsing, append one exact, case-sensitive checked
encounter selector:

<http://127.0.0.1:3082/sts2?encounter=AXEBOTS_NORMAL>

Unknown or repeated selectors fail clearly; there is no fuzzy matching. Manual
selection remains manual during polling. When qq-ui is available, the plugin
contributes one ordinary **StS2 Companion** menu item linking to its configured
`/sts2` base path.

## What the guide means

The document and its bounded `/sts2/state` and `/sts2/client.js` implementation
endpoints read only the checked compact projection
`data/encounter-facts-v0.111.0.json`, once at startup, through one strict
adapter. The narrow default guide leads with:

- encounter name and alternative/random roster possibilities without claiming
  those possibilities are all present;
- enemy/form HP parameters, compact human effect signatures, openers, cycles,
  forks, statuses, scaling and production;
- death, revive, hatch, escape, phase and clock rules; and
- decision-relevant static conditions and explicit unknowns.

Raw identifiers, move titles, expressions, graph records and evidence pointers
stay inside the native **Technical audit** disclosure. They do not occupy the
collapsed combat guide. The empty checked editorial-callout collection does not
create an empty product section; the internal collection contract remains
`0..N` and a collapsed display limit never discards passing records.

The view does **not** execute/read game binaries at runtime, recreate the
projection generator, predict the next move, or observe current HP, Block,
Powers, intent, turn, phase, hand, branch or live-body survival. Possible initial
bodies, state-reader body identities and produced bodies remain separate. It
never fabricates current tactics or imperatives from a model identity.

The projection's `matchingPolicy.prefixStripping:false` governs exact observed
identity matching. The adapter does not guess aliases, fold case, or fuzzy-match.
A missing, malformed, unsupported-version or oversized projection fails closed;
checked mechanics are never silently replaced with community/wiki values.

## Authority and detailed contracts

This repository targets unmodded Steam public-beta **v0.111.0** and the pinned
DLL SHA-256:

```text
2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f
```

`encounterProjection.ready` is required. The broader
`encounterCompanion.ready` intentionally remains false and is not a static-guide
gate. Unknown inputs stay named/conditional; they are never converted to zero or
a guessed default.

Detailed schema/readiness and implementation authority:

- [decision projection contract](docs/decision-projection.md)
- [source world model](docs/source-world-model.md)
- [v0.111.0 source migration ledger](docs/source-migration-ledger.md)

Schema numbers are not duplicated here because coordinated source closeouts may
advance them. The adapter itself is the runtime allowlist.

## Install and run

This package is an optional sibling; qq-core must still start when it is absent.
The sibling profile layer is `cordis.patch.yml`. The web server must remain bound
to `127.0.0.1`; the plugin refuses any non-loopback host. On this machine,
Tailscale Serve terminates HTTPS and proxies to that loopback service.

The browser uses exact routes, no-store responses, restrictive CSP, frame denial,
MIME-sniffing denial, referrer suppression, and DOM text rendering. The page is a
native full-document qq sibling with local qq-like design tokens and no external
runtime dependency.

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

No generated data change is expected for presentation or adapter-consumer work.
To remove the optional runtime, disable or remove the sibling from the qq
profile; qq-core remains independent.
