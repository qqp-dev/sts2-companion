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
endpoints read the checked compact projection
`data/encounter-facts-v0.111.0.json` through one strict adapter. For encounters
with a retained `data/encounters.json` record, the adapter joins that guide by
exact canonical encounter and monster IDs. All eight current event encounters
instead use a deliberate checked-source-only primary path; no retained record or
wiki fallback is fabricated. The flat default scan path is:

1. compact encounter title, configured HP/kind, practical placement, and static
   detected/manual context;
2. for variable initial rosters, an exact-cardinality capsule with fixed order,
   uniform alternatives, independent draws, or distinct N-of-M selection;
3. explicit numbered phases when the retained pattern declares phases;
4. otherwise honest `Opener`, `Cycle`, `Branch`, or `Response` sections;
5. turn/condition cues and numbered sequence steps with concise consequences,
   transitions, repeat cues, and body-adjacent encounter-distinct rules;
6. zero or more independently qualified flat `TACTIC`/`WATCH` lines; and
7. quiet lane/player-count provenance plus collapsed **Technical audit**.

For a retained-backed primary, the guide uses the best available value per
practical coordinate. A projected checked value supersedes the retained guide only
when it is actually closed. If its source expression remains symbolic, the exact
retained A9/body/move value is rendered as a consequence with configured
multiplayer scaling and quiet `wiki/reference` provenance—never as source-closed
and never as an `unresolved` placeholder when that exact fallback exists. The eight
event-fight primaries do not use this merger: closed HP/setup/operation/graph and
combat-lifecycle facts render with `checked source values` provenance, while
symbolic amounts stay concise and honest. Matching is exact only; the adapter does
not guess aliases, fold case, or fuzzy-match fallback records.

An **event fight** card is the ordinary combat reference for a fight reached from
a map event. It identifies initial bodies, HP/setup, behavior branches/cycles, and
combat-specific clocks or termination. It is not an event walkthrough and never
advises which event option to choose. Option effects, dialogue, rewards, and
post-event selection remain Technical audit unless an exact combat-transition or
lifecycle join makes a consequence part of this fight.

Primary copy is consequence-first: it answers **when does it happen, what happens,
and what must the player track or target?** Ordinary canonical move labels are not
primary row headings. Player-facing tracked keywords and statuses such as Strength,
Ringing, Vulnerable, Weak, Stunned, and Block remain visible, as do actor, target,
and summoned-enemy identities such as Zapbot. Opaque named Powers and internal
concepts are expressed through thresholds and outcomes rather than unexplained
stack nouns. Exact canonical move/Power labels, source IDs, retained wiki labels,
and per-value provenance remain unchanged as audit/reconciliation metadata inside
the collapsed **Technical audit**.

The variable-roster capsule and body presence roles are compiled recursively from
the checked roster grammar, not from the retained flat lineup. `always present`,
`possible body`, and `possible up to N copies` come from exact per-model count
bounds across every ordered outcome. Each uniform-choice node is its own draw;
repeated nested nodes therefore remain independent and can produce duplicates.
Filtered pools preserve exact N-of-M, model-count-limit, distinct, and
without-replacement semantics. One mechanics card is shown per possible body type,
with an explicit warning that alternative cards are not all co-present. A possible
model without an exact retained body join gets a labeled checked-source mechanics
card; symbolic values remain runtime-set known-unknowns rather than borrowed wiki
numbers.

Possible initial bodies, locally observed bodies, and produced/summoned bodies are
separate lanes. An observed realization never narrows or replaces the static source
grammar, and a produced body never becomes an initial body. Source expressions
(including symbolic getters), raw identifiers, behavior graphs, source authority,
exact retained records, per-value merge reasons, conflicts, callout basis refs, and
evidence pointers remain reachable inside **Technical audit**.

Schema 12 preserves 69 Power localizations (62 exact, seven missing) and 32
intent entries (14 pairs, four formats) as unresolved, encounter-closed
**Technical audit** only—never a live Power instance or intent prediction.

Editorial callouts remain a separately gated, evidence-linked `0..N`
collection; encounters without a qualifying record show no filler.

The guide states its static boundary once. It does **not** execute/read game
binaries at runtime, recreate the projection generator, predict the next move,
or observe current HP, Block, Powers, intent, target, turn, phase/counter,
realized lineup/survivors, timer, hand, or branch. It never fabricates a current
imperative from encounter identity.

The projection's `matchingPolicy.prefixStripping:false` governs exact observed
identity matching. A missing, malformed, unsupported-version or oversized
projection still fails closed; the reference book never bypasses that source
projection gate. Version mismatch remains an explicit warning rather than a
silent authority claim.

## Authority and detailed contracts

This repository targets unmodded Steam public-beta **v0.111.0** and the pinned
DLL SHA-256:

```text
2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f
```

`encounterProjection.ready` is required. The broader
`encounterCompanion.ready` intentionally remains false and is not a static-guide
gate. Unknown inputs are never converted to zero or a guessed default. The
retained A9/2P community book is a presentation fallback, not source authority:
it is selected only by exact IDs, remains separately labeled/auditable, and is
superseded coordinate-by-coordinate when the checked source value closes. Absence
from that retained book does not imply missing runtime identity, compact-adapter,
or primary coverage; the eight event-fight cards are the current source-only
example.

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

Projection and retained-wiki inventory generation are deterministic and offline
from checked inputs:

```sh
npm run build:retained-book
npm run build:encounter-facts
npm run build:primary-semantic-surface
npm run build:wiki-reconciliation
npm run check:wiki-reconciliation
```

Use book → compact → primary surface → census order. Not runtime input.
The [audit contract](docs/wiki-reconciliation.md) has 4,438 origins: 1,394
final-mapped and 2,179 captured after exact P1c Power/passive reconciliation, so
readiness remains false.

Raw-source regeneration is a development operation requiring the exact local
game files and isolated Python dependencies; it is not a runtime requirement:

```sh
python3 -m venv .venv-source
.venv-source/bin/python -m pip install -r requirements-source.txt
GAME_ROOT="${STS2_GAME_ROOT:-/home/qqp/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Slay the Spire 2}"
.venv-source/bin/python -m pip install -r requirements-source.txt
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --check
```

Run all Node and Python tests, and independently check the approved 390px
Ceremonial Beast snapshot, with:

```sh
npm test
npm run check:phone-snapshot
npm run check:consequence-naming
npm run check:retained-book
npm run check:encounter-facts
npm run check:primary-semantic-surface
npm run check:wiki-reconciliation
npm run check:event-primary-guides
npm run check:roster-guides
```

No generated data change is expected for presentation or adapter-consumer work.
To remove the optional runtime, disable or remove the sibling from the qq
profile; qq-core remains independent.
