# Retained-wiki inventory and reconciliation contract — v0.111.0

## Authority and scope

`data/wiki-reconciliation-v0.111.0.json` is the deterministic, offline census of
the checked retained wiki snapshot. It is **coverage and reconciliation input
only**. It is not imported by a runtime route, it does not refresh the network,
and it cannot override closed reverse-engineered facts in
`data/game-v0.111.0-source.json` or their checked compact projection.

P1a captured origins. P1b0 adds a reviewed final-mapping control plane for
membership and already-known typed conflicts only. Every mechanical origin
without a reviewed mapping still has review state `captured-unreconciled`. That
phrase means only “the structural origin cannot silently disappear.” It is not a
final audit disposition, a source-closure claim, or evidence that primary/audit
presentation contains the claim.

The artifact targets `v0.111.0` on `public-beta`. Its manifest hashes
`pages.json`, `index.json`, all six retained Lua files, the retained book, raw
source, compact projection, the reviewed policy, parser/generator tools, and
current repository documentation/contracts. Paths are repository-relative. No
generation timestamp, absolute path, file-order observation, inode, or temporary
path participates in output.

## Four different completeness statements

These terms must not be collapsed:

1. **Inventory completeness** asks whether every unit in the declared retained
   snapshot/atomization contract has a stable origin record and exactly one
   review state. P1a sets this true for 4,433 units.
2. **Snapshot completeness** asks whether all content promised by the snapshot
   index is retained and expandable. This is false: `index.json` lists
   `Module:Enemies/StS2 data/Events`, but `tools/.wiki/Events.lua` is absent.
   The exact version-scoped waiver permits CI to inventory what exists; it does
   not fabricate an empty module or make readiness true.
3. **Source extraction completeness** is independent of the wiki inventory.
   The compact artifact's declared encounter-projection scope is ready, but its
   global/root readiness remains false for its declared known unknowns. The wiki
   artifact therefore reports `sourceExtractionComplete: false` and separately
   reports the bounded encounter-projection scope as complete.
4. **Semantic reconciliation completeness** asks whether every mechanical atom
   has a reviewed final disposition and exact representation/provenance path.
   This remains false because 3,519 records are still `captured-unreconciled`
   after P1b0. Overall reconciliation readiness is consequently false.

The checked Events waiver and 69 shorthand `Power Infobox` plus two `Intents`
invocations are first-class snapshot limitations. Their template bodies are not
in the snapshot. Invocation identities and arguments are inventoried; absent
body semantics are not inferred.

## Stable origins and atomization

A record has a stable structural `id` and a content-sensitive `claimId`.
Page-origin IDs include page key, page ID, revision ID, section path with heading
ordinals, and the relevant template/row/list/sentence/field/claim ordinal.
Module-origin IDs include the relative module path, table key, record ordinal,
and field/move/claim ordinals. IDs do not derive from normalized wording, so two
moves named `Dark Strike` remain distinct. The separate claim ID changes when
an excerpt or normalized structure changes.

The inventory atomizes identity/type/debut/alias, lead and roster claims; HP and
Ascension fields; starting Powers; every `Power Infobox` invocation and retained
inline field; every article move Name, balanced comma-separated Intent token,
and Effect claim; Lua move Names and Effect claims (with the complete retained
IntentIcons/AscText structure attached); Pattern clauses/lists; Notes; tactics;
Trivia; patch facts; and explicit non-guide units. HTML comments are masked
before mechanical parsing and retained only as excluded comment fragments.
Balanced parsing never splits nested templates or links on raw pipes, equals,
commas, or `<br>` markup.

The reviewed denominators are enforced both by category and origin family. The
artifact also reports, without conflation, 89 current source encounters (81
ordinary and eight event), 108 reachable current source models, 315 compact
moves, eight compact states, 81 current retained encounters, one archived
Doormaker encounter, one current Mysterious Knight event reference, 105 current
body IDs, and one archived body ID.

## Exclusions and membership

`tools/wiki-reconciliation-policy-v0.111.0.json` is a checked, version-scoped
review input. An origin receives final disposition `intentionally-excluded` only
when a typed structural policy matches it. Policies cover visual units,
navigation, category links, update history, beta boilerplate, dialogue/source
blocks, HTML comments, out-of-scope patch bullets, Trivia, reviewed tactics, and
three exact non-combat Notes. The origin records remain in the artifact.

Doormaker page/module origins are structurally `deprecated`, never current. The
generated book stores Doormaker only under `archive.encounters`. It is not a
current adapter selector, source encounter, primary card, fallback, or current
coverage denominator. Its 36 mechanical captured origins are final-mapped
`stale/deprecated/version-ambiguous`; 31 non-guide Doormaker origins remain
P1a exclusions and are not double-dispositioned.

Mysterious Knight page/module origins are `current`. Deterministic book
generation now emits `retainedReferences.MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER` as
the current event reconciliation/reference record, including identity, HP,
setup, three moves, and weighted no-repeat Pattern. It is not a current
`encounters` selector. The P0b event card remains checked-source-only;
unresolved wiki values do not fall back into that primary.

The corrected research review is preserved as a non-applied baseline: Kin
Follower's bad `Type=Boss` origin is `tools/.wiki/Bosses.lua`; Fabricator's
retained book has Fabricator initial and Guardbot/Noisebot/Stabbot/Zapbot marked
summoned; Waterfall Giant's terminal `999999999` HP is present in retained rules,
compact lifecycle, and primary lifecycle rendering; objective Note gaps are 79;
and aggregate historical totals are 2,167 `primary-present` and 103
`missing/unparsed` over the unchanged 4,433 denominator. P1a does not copy those
historical final labels onto records.

## Offline build and strict check

From the repository root:

```sh
npm run build:wiki-reconciliation
npm run check:wiki-reconciliation
# equivalent direct commands
python3 tools/audit-retained-wiki.py
python3 tools/audit-retained-wiki.py --check
```

Both modes first run `tools/generate-book.py` in an isolated temporary tree and
require its `data/encounters.json` output to be byte-identical to the checked
book. They do not access the network, game files, or runtime routes. Write mode
uses atomic replacement. Check mode never writes and requires exact artifact
bytes.

Input, page revision, module record, parser denominator, source/compact digest,
policy, tool, or documentation changes make check mode fail. If a prior origin
ID disappears, write mode also fails unless the policy adds an explicit reviewed
`tombstone` or `approvedOriginReclassification`. Denominator decreases require a
reviewed policy update. Newly captured origins remain `captured-unreconciled`;
regeneration never promotes them based on substring matches.

## P1b0 control plane

`tools/wiki-reconciliation-policy-v0.111.0.json` now carries `finalMappings`.
Each mapped origin has an exact origin ID, a live `claimId` guard, exactly one
final disposition, a typed semantic mapping, `authorityComparison` with
closure and no-silent-merge resolution, representation JSON pointers, rationale,
owner, severity, and reviewed version. Structural rules are allowed only with
an exact expected ID set and count; the builder materializes and validates each
record. There is no substring rule or same-title inference.

P1b0 maps 49 origins: 13 known wiki/source conflict atoms and 36 Doormaker
mechanical stale atoms. Research counted 13 Infested Prism atoms as combined
move rows and 42 Doormaker stale atoms; production uses 13 conflict origins
(Radiate damage claims agree at 13 and stay unreconciled until P1b2) and 36
Doormaker mechanical origins. The compact projection's 26 title conflicts are
cross-linked table-driven from `payload.conflicts`, remain dual-lane
unresolved in compact, and keep source titles as hero-copy authority.

Closed source wins primary/presentation. Wiki/retained values stay auditable.
`sourceFlags` strings are not the sole machine-readable conflict
representation; book `typedConflicts` and reconciliation mappings are.

### Build order

Avoid digest cycles:

1. `python3 tools/generate-book.py` — current + archive + retained references;
2. `npm run build:encounter-facts` — compact projection from source + the new book;
3. `npm run build:wiki-reconciliation` — final census last.

Runtime never imports the wiki artifact. Compact typed conflicts are generated
from the retained book/source inputs.

Later slices: P1b1 identity/HP/Power atoms; P1b2 move/pattern atoms; P1c
Power/intent localization; P2 the 79 objective Note gaps; optional P3 tactics.

