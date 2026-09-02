# Retained-wiki inventory and reconciliation contract — v0.111.0

## Authority and scope

`data/wiki-reconciliation-v0.111.0.json` is the deterministic, offline census of
the checked retained wiki snapshot. It is **coverage and reconciliation input
only**. It is not imported by a runtime route, it does not refresh the network,
and it cannot override closed reverse-engineered facts in
`data/game-v0.111.0-source.json` or their checked compact projection.

P1a captured origins and P1b0 added the membership/typed-conflict control
plane. P1b1 final-maps identity/placement/lead/roster, HP/scaling, and exact
starting-Power identity/stack origins. P1c now final-maps the exact 74 pending
Power/passive origins through guarded canonical ownership and localization
coordinates. Move/intent/effect, Pattern, and corrected objective Note records
remain outside this slice unless P1b0 already mapped them. An unmapped record's
`captured-unreconciled` state means only that its structural origin cannot
silently disappear; it is not a final disposition or a presentation claim.

The artifact targets `v0.111.0` on `public-beta`. Its manifest hashes
`pages.json`, `index.json`, all six retained Lua files, the retained book, raw
source, compact projection, all three reviewed policies, the explicit state/model
alias ledger, the generated primary semantic surface, parser/generator tools,
and current repository documentation/contracts. Paths are repository-relative. No
generation timestamp, absolute path, file-order observation, inode, or temporary
path participates in output.

## Four different completeness statements

These terms must not be collapsed:

1. **Inventory completeness** asks whether every unit in the declared retained
   snapshot/atomization contract has a stable origin record and exactly one
   review state. This is true for 4,438 units after the reviewed P1b1
   atomization correction described below.
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
   This remains false because 2,179 out-of-slice records are still
   `captured-unreconciled` after P1c. Overall reconciliation readiness is
   consequently false.

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
and aggregate historical totals were 2,167 `primary-present` and 103
`missing/unparsed` over the prior 4,433 denominator. P1b1 found a real
atomization defect: four comma-separated Test Subject article/module Power
claims and Tough Egg's adjacent Minion/Hatch claim needed five additional exact
Power origins. The corrected inventory denominator is therefore 4,438 (the
historical primary estimate becomes 2,172 solely for denominator accounting).
The artifact's materialized P1b1 dispositions, not that historical estimate,
are authoritative for completed families.

## Offline build and strict check

From the repository root:

```sh
npm run build:wiki-reconciliation
npm run check:wiki-reconciliation
# individual stages
npm run check:retained-book
npm run check:encounter-facts
npm run check:primary-semantic-surface
python3 tools/audit-retained-wiki.py --check
```

The reconciliation builder first runs `tools/generate-book.py` in an isolated
temporary tree and requires its `data/encounters.json` output to be
byte-identical to the checked book. The npm build/check chains also enforce the
acyclic book → compact → primary semantic surface → reconciliation order. They do not access the network, game files, or runtime routes. Write mode
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

## P1b1 identity, roster, HP, and starting-state mappings

`tools/wiki-reconciliation-p1b1-policy-v0.111.0.json` guards every one of the
**1,271** P1b1 origins by exact origin ID, claim ID, and family. This is five
higher than the work-order's 1,266 because per-Power atomization is now correct:
article and module Test Subject phases 1/2 split comma-separated Powers (+4), and
Tough Egg splits adjacent `Minion` and `Hatch 2` (+1). The post-P1b1 unrelated remainder was **2,253**; P1c maps 74 of those,
leaving exactly **2,179**.

Canonical ownership comes from generated `retainedProvenance` on each book body:
article page/revision/template/body ordinal and module path/table key/record
ordinal are retained independently. The only model/state aliases live in
`tools/primary-semantic-aliases-v0.111.0.json`: three Decimillipede segment
shortcuts, Hatchling as `TOUGH_EGG#HATCHED`, and Test Subject phases 2/3 as
states of `MONSTER.TEST_SUBJECT`. `Knight Gang` is one explicit aggregate
encounter owner. New origins and aliases never auto-promote.

`data/primary-semantic-surface-v0.111.0.json` is generated by the checked adapter
and actual primary compiler at both 1P and 2P. It exposes typed roster grammar,
initial/possible/produced roles, source/body/state identities, normal/A8 and
configured HP, starting-Power tokens, and exact primary card ordinals. Mapping
classification never searches rendered copy. `primary-present` requires a
resolving typed surface coordinate; `audit-present` points to retained/compact
Technical data. Symbolic source expressions retain an explicitly labeled
fallback lane.

Normal/base HP is now preserved separately as `hpBelowA8` on every retained book
body, in the compact legacy/wiki lane, and on each semantic-surface
`retainedBody`. Its explicit authority is `retained-wiki-reference`; it never
feeds primary HP or overwrites the source model. A mapping may be
`audit-present` from this exact typed retained coordinate, but source closure is
`closed` only when the same unscoped body model has the identical normalized
below-A8 range and its exact source fact ref. State/form IDs prove ownership
only. Thus Hatchling `19–22` remains distinct from Tough Egg `14–18` and A8
`20–23`, while Test Subject phases retain base `100/200/300` separately from A8
`111/212/313`; phases 2/3 are retained-reference-only with `knownUnknown` source
closure.

The reconciliation builder enforces this as a programmatic HP-family invariant:
every value-bearing pointer is dereferenced, typed ranges must match exactly,
retained body/model/state and base-vs-A8 scope must agree, A8 primary evidence
must cover both 1P and 2P, and source fact refs are accepted only for the exact
same-scope source coordinate. Ownership-only model candidates remain visible but
cannot close authority. Mutation tests remove/change values while preserving
state IDs and reject cross-state and base/A8 substitution.

P1b1 dispositions are 787 `primary-present`, 470 `audit-present`, eleven
`conflict`, and three `missing/unparsed`. The missing records are the two exact
HP patch transitions and Galvanic's exact starting-Power patch transition;
current endpoints alone do not prove historical before→after claims. New
source-winning conflicts are Eye With Teeth capitalization, Strangler's forced
Leaf+Twig small branch versus two independent draws, six article/module base-HP
disagreements for Scroll of Biting, Owl Magistrate, and Slimed Berserker, and
stale module A8 values for Exoskeleton and Entomancer, and Globe Head's stale
module Galvanic 6 versus the current typed A9/1P/2P value 8. These augment—not
replace—P1b0's 13 conflict origins and 26 compact title cross-links.

Roster mappings preserve fixed order, uniform alternatives, independent draws,
without-replacement constraints, and initial-versus-produced roles. In
particular, Fabricator alone is initial while four bots remain production
possibilities; a possible alternative card is never credited as always present.
Starting-state mappings uniquely segment exact canonical Power titles before assigning a
trailing amount, so Tough Egg is typed as `Minion` plus `Hatch 2` rather than a
synthetic `Minion Hatch 2` identity. They preserve one Power per atom, owner/state, base/A9
amount, 1P/2P scaling, and canonical Power IDs.

## P1c Power/passive and localization mappings

`tools/wiki-reconciliation-p1c-policy-v0.111.0.json` guards exactly 74 origins:
68 `article-power-invocation` and six `article-power-inline-field` records. The
policy pins origin ID, claim ID, page and section owner, canonical Power ID,
compact Power index, and a typed initial-state, move-operation, or lifecycle
actor/Power coordinate. Runtime reconciliation never chooses by title,
substring, or same-name inference. The two `Back Attack` invocations are
explicitly disambiguated as Crusher/left and Rocket/right; mutation of the
owner alias, canonical ID, fact, or either pointer fails closed.

The compact schema-12 authority is 69 reachable Powers: 62 exact localized smart
description templates and seven explicit missing records
(`POWER.BACK_ATTACK_LEFT_POWER`, `POWER.BACK_ATTACK_RIGHT_POWER`,
`POWER.DAMPEN_POWER`, `POWER.HEX_POWER`, `POWER.STOCK_POWER`,
`POWER.SURROUNDED_POWER`, and `POWER.SWIPE_POWER`). It also contains 32 exact
checked intent entries: 14 independent title/description key pairs and four format entries.
Equal display values such as `Strategic` do not merge keys. Templates preserve
Godot markup and unresolved owner, amount, damage, repeat, card-count,
multiplayer, plural, and conditional tokens. Wiki prose never fills a missing
source localization.

P1c materializes 69 `audit-present` and five `missing/unparsed` mappings. The
four inline `Type`/`Stacks` values remain missing because the checked source
catalog does not project those fields; Fossil Stalker's `Strength` invocation
remains unjoined because no typed compact actor/Power row proves ownership. The
two inline `Description` origins point independently to exact retained values
and source templates. An unexpanded `Power Infobox` invocation proves only its
identity/arguments; absent template-body semantics remain a snapshot
limitation. Including a raw source template does not claim a current owner,
amount, target, status, or trigger.

Together with the three preserved P1b0 archive Power mappings, all 77
Power/passive origins are final-mapped. Totals are now 1,394 final-mapped, 865
policy-excluded, and 2,179 captured-unreconciled. Semantic/overall readiness
remain false because move/Pattern and objective Note work is not part of P1c;
snapshot completeness remains false because `Events.lua` and both shorthand
`Intents` transclusion bodies are absent.

### Build order

Avoid digest cycles:

1. `npm run build:retained-book` — current + archive + retained references and exact provenance;
2. `npm run build:encounter-facts` — compact projection from source + book;
3. `npm run build:primary-semantic-surface` — actual 1P/2P compiler semantics;
4. `python3 tools/audit-retained-wiki.py` — reconciliation census last.

`npm run build:wiki-reconciliation` runs those stages in that order; the check
command verifies each stage without rewriting. Runtime never imports either
reconciliation artifact. P1c is complete in this build; the mandated later
slices are P2 for the corrected 79 objective Note gaps, then P1b2 move/Pattern
semantics, with P3 tactics optional. Semantic and overall readiness remain
false.

