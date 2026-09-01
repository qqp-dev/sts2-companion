# sts2-companion

Phone-first, read-only **Slay the Spire 2** encounter reference for the optional
qq Cordis sibling. It reads checked local encounter facts and local
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
selection remains manual during polling. Without a selector, the page polls every
1.5 seconds and visibly labels the detected encounter as `combat` or `last`.
When qq-ui is available, the plugin contributes one ordinary **StS2 Companion**
menu item linking to its configured `/sts2` base path.

## What the guide means

The document and its bounded `/sts2/state` and `/sts2/client.js` implementation
endpoints read only the checked compact projection
`data/encounter-facts-v0.111.0.json`, once at startup, through one strict
adapter. The flat default scan path is:

1. detected `combat`/`last` context, or the exact manual selector;
2. encounter and possible initial-roster context;
3. each possible enemy/body with checked A8 single-player HP where closed;
4. starting state, compact ordered effect signatures, then sequence/fork context;
5. body-adjacent production, death, revive, hatch, phase, escape, and clock rules;
6. zero or more independently qualified static `TACTIC`/`WATCH` callouts.

Effects are primary. Closed constants retain their values and operation order,
including hit count, Block, Powers/status quantities, cards, summons, and
lifecycle consequences. Numeric sequence markers connect effects to the pattern
without displaying move names. When a source expression or required runtime
modifier does not close, the guide names the affected coordinate/input (for
example, `damage amount unresolved for this behavior` or `runtime Power
modifiers`) rather than substituting a legacy value or generic `checked amount`.

Possible initial bodies and produced bodies remain visibly distinct. Random and
alternative roster branches are possibilities, not a claim that every listed
body is present. Raw identifiers, move titles, expressions, graphs, callout
basis refs, conflicts, and evidence pointers stay inside **Technical audit**.

The editorial registry is deliberately separate from source extraction. It
currently contains one source-backed conditional callout for Axebot Stock
replacement and one for the Decimillipede shared finish window. Every candidate
passes the existing seven gates and cites fact, condition, and causal refs.
Encounters without a qualifying record show no filler. The collection contract
remains `0..N`; all passing records remain reachable when a collapsed display
uses an expansion path.

The guide states its static boundary once. It does **not** execute/read game
binaries at runtime, recreate the projection generator, predict the next move,
or observe current HP, Block, Powers, intent, target, turn, phase/counter,
realized lineup/survivors, timer, hand, or branch. It never fabricates a current
imperative from encounter identity.

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
a guessed default. The older A9/2P community book remains an exported,
offline-tested artifact; the default renderer does not use it as authority or
fallback.

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
.venv-source/bin/python -m pip install -r requirements-source.txt
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --check
```

Run all Node and Python tests with:

```sh
npm test
```

No generated data change is expected for presentation or adapter-consumer work.
To remove the optional runtime, disable or remove the sibling from the qq
profile; qq-core remains independent.
