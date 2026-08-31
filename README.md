# sts2-companion

Phone-first, read-only **Slay the Spire 2** encounter mechanics for the optional
qq Cordis sibling. It reads local log/save/release metadata, never sends game
input, and makes no runtime network requests.

## Open it

The designed source-first view is the canonical product:

- local: <http://127.0.0.1:3082/sts2>
- Tailscale: <https://qq-box.tail580136.ts.net/sts2>

For static reference browsing, append one exact, case-sensitive canonical ID:

<http://127.0.0.1:3082/sts2?encounter=AXEBOTS_NORMAL>

Unknown or repeated selectors fail clearly; there is no fuzzy matching. Manual
selection remains manual during polling. `/sts2/source` is a compatibility alias
to the same source-first surface, not a separate or primary product.

A clearly labeled temporary rollback remains at `/sts2/legacy`. It serves the old
legacy book and is not linked or presented as the default product.

When qq-ui is available, this plugin contributes its own ordinary navigation
item, **StS2 Companion**, linking to the configured canonical base path. qq-ui
owns only the generic menu registration/rendering seam; this repository owns the
item and its lifecycle.

## What the canonical surface means

`/sts2`, `/sts2/state`, and `/sts2/client.js` read only the checked compact
projection `data/encounter-facts-v0.111.0.json`, once at startup, through one
strict adapter. The phone-first static mechanics capsule leads with encounter
context, parameterized roster grammar, HP/form state, ordered human effect
signatures, behavior cycles/forks, production and lifecycle rules, and explicit
unknowns. Exact formulas, move IDs/titles, raw graphs, lane records, and evidence
remain reachable through native detail expansions instead of occupying the main
thinking window.

The projection's `matchingPolicy.prefixStripping:false` governs exact source
observation identities; it is not relaxed. Saves have already been converted to
the stable state-reader model-ID representation, so the adapter builds a
collision-checked bridge by applying that same reader conversion to each
validated projection row. It does not guess aliases, fold case, or fuzzy-match.

The view does **not** read the raw source artifact, execute/read game binaries,
recreate the projection generator, predict the next move, or observe current HP,
Block, Powers, intent, turn, phase, hand, or live body survival. Possible initial
bodies, state-reader body IDs, and produced bodies remain separate. SOURCE,
OBSERVED, LEGACY, and UNKNOWN lanes never silently merge.

No editorial source-qualified tactical callouts are currently checked in, so the
surface truthfully exposes an empty `callouts: []`. That means zero qualifying
records are available, not a one-card quota. The collection contract is `0..N`;
collapsed display limits never discard passing records.

## Authority, readiness, and failure boundary

This repository targets unmodded Steam public-beta **v0.111.0**. Runtime source
consumption accepts only explicitly supported compact projection schemas and the
corresponding generator major, exact game authority, complete required
joins/components, and pinned DLL SHA-256:

```text
2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f
```

`encounterProjection.ready` is required. The broader
`encounterCompanion.ready` intentionally remains false and is not a static
capsule gate. Unknown inputs stay named/conditional; they are never converted to
zero or a legacy default. A malformed or unsupported compact projection returns
503 on canonical source-first routes and compatibility aliases. The temporary
`/sts2/legacy` rollback can remain available for diagnosis, but never replaces a
failed source capsule with silently merged legacy data.

Detailed schema/readiness, implementation authority, and landed-wave history:

- [decision projection contract](docs/decision-projection.md)
- [source world model](docs/source-world-model.md)
- [v0.111.0 source migration ledger](docs/source-migration-ledger.md)

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
The browser routes use exact matching, no-store responses, restrictive CSP,
frame denial, MIME sniffing denial, referrer suppression, and escaped/DOM-text
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

No generated data change is expected for UI or adapter-consumer work.

## Rollback or removal

Use `/sts2/legacy` only as the temporary rollback while diagnosing the canonical
source-first view. To remove the runtime entirely, disable/remove the optional
`@hypermemetic-ai/sts2-companion` sibling from the qq profile; qq-core remains
independent. A code rollback can remove the compatibility `/sts2/source*` aliases
and temporary `/sts2/legacy*` routes without changing checked source data or the
state reader.
