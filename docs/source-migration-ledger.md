# Source migration ledger — v0.111.0

> Historical landed-wave and audit detail moved from the repository entry point.
> Current operation and status are in [README](../README.md); current tactical
> collection semantics are authoritative in [decision-projection.md](decision-projection.md).

A phone-first, read-only encounter companion for **Slay the Spire 2**. The
optional Cordis plugin mounts its own page at <http://127.0.0.1:3082/sts2> on
the qq loopback web server. The current default consumes the checked compact
projection and shows an effect-first static reference for the current fight, the
most recently completed fight, or one exact manual selector. It does not show
live HP or intents and never writes game input.

The browser polls `/sts2/state`, so a new `Creating NCombatRoom` log line
replaces the card without a reload. Identity comes only from `godot*.log` and
`current_run_mp.save`; paths are injectable for tests and alternate installs.
The default probes the Steam Flatpak data root used on this host, the native
XDG data root, and the alternate Megacrit Flatpak root.

The current default authority is local
`data/encounter-facts-v0.111.0.json`: source-lane mechanics and A8
single-player HP values are projected through the strict adapter. For encounters
with retained records, practical presentation joins `data/encounters.json` by
exact canonical IDs: a closed checked source coordinate wins, while a symbolic
coordinate retains the exact configured A9/player-count reference value with
separate provenance. The eight current event encounters instead compile a
source-only primary from checked roster, HP/scaling, initialization, operations,
graphs, and combat lifecycle; no retained record is manufactured. Raw expressions
and all available lanes remain in Technical audit. Variable roster structure and
presence roles come only from the closed source grammar; retained flat lineups do
not override selection semantics. Runtime makes no wiki or other network requests. It
compares checked authority with local `release_info.json`; a mismatch is shown as
an exceptional warning.

The checked-in `tools/.wiki/pages.json` records full article/patch wikitext,
revision IDs and UTC harvest time. Regeneration is deliberately split into a
networked development-time snapshot and a deterministic offline build:

```sh
python3 tools/harvest-wiki.py  # refresh wiki.gg snapshots (development only)
python3 tools/generate-book.py # reads only checked-in local snapshots
```

All eight current event fights accept their exact manual selector and render a
source-only practical primary. Unknown observed/selected identities still fail
clearly rather than entering a fuzzy fallback. Missing HP, an unreadable release
file, and a version mismatch likewise remain explicit instead of producing a
blank or falsely authoritative page.

## Event coverage layers

Event coverage is not one boolean. For all eight current event fights, shipped
identity, decoded source facts, compact projection membership, strict-adapter
selection, and phone primary presentation are each covered and tested. Retained
wiki/book membership remains a distinct reconciliation lane and is not required
for a source-only card. These cards describe only combat: they do not recommend an
event option, interpret dialogue, or turn unrelated option/reward effects into
combat consequences.

## P0c exact practical roster projection

Variable initial rosters now compile directly from the adapter-validated four-kind
source grammar. The bounded deterministic analysis preserves fixed order,
uniform/dependent category choices, independent repeated draws and duplicate
outcomes, plus filtered distinct N-of-M draws without replacement. Declared
cardinality must equal analyzed outcome cardinality; unknown selection semantics,
empty branches, invalid counts, and malformed future shapes make the strict adapter
unavailable rather than reaching a flattening renderer.

The phone capsule labels actual initial cardinality and states that alternative
body cards are not a simultaneous lineup. Exact outcome count bounds drive
`always present`, `possible body`, and `possible up to N copies`, with one card per
possible source body type. Missing retained-realization alternatives use their
exact source model only, carry checked-source mechanics provenance, and leave
symbolic values runtime-set. They do not manufacture a legacy annotation or
wiki/reference merge. The exact retained flat record remains separately reachable
in Technical audit.

Possible initial, observed, and produced bodies remain separate. In particular, a
live Flyconid realization does not erase its other medium-slime possibility, the
Strangler's two small-slime nodes remain independent, and source pool catalogs for
Ruby Raiders/Bowlbugs do not become five-/four-body initial lineups. Deterministic
presentation and phone-DOM fixtures cover Flyconid, Slimes Weak, Strangler, Ruby
Raiders, and both Bowlbug selection kinds.

## Retained-wiki inventory foundation (P1a landed; semantic review deferred)

The reviewed offline audit baseline records three corrections for later P1/P2
work: Kin Follower's bad module type is in `tools/.wiki/Bosses.lua`; Fabricator's
retained book already lists all four summoned bots; and Waterfall Giant's terminal
HP is already represented. Therefore the corrected objective missing-Note count is
**79**, and the corrected grand missing/unparsed count is **103**. These are audit
classification totals, not source closure and not changes to the P0b event or P0c
roster primary implementations.

P1a materializes that baseline as the deterministic 4,433-origin offline artifact
`data/wiki-reconciliation-v0.111.0.json`; its contract is documented in
[`wiki-reconciliation.md`](wiki-reconciliation.md). Inventory completeness is
true, but the index-listed missing Events module keeps snapshot completeness
false and all unmapped mechanics remain non-final `captured-unreconciled` for
P1b. The artifact is not runtime input and cannot override source authority.

## P1b0 current membership and typed-conflict control plane

P1b0 extends the P1a census with a fail-closed reviewed final-mapping schema.
It repairs retained membership so Mysterious Knight is the current event
reconciliation/reference record and Doormaker is archive-only, records the 13
known wiki/source conflict origins with source-wins resolution, and cross-links
the existing 26 compact title conflicts without replacing them. Non-conflict
mechanical atoms stay `captured-unreconciled` (3,519 remaining). Semantic
readiness stays false. Production Doormaker mechanical stale count is 36, not
the research 42; Infested Prism Radiate conflict origins are the two Block
claims, while damage claims agree at 13.

Build order is book → compact projection → wiki reconciliation. Ordinary/event
primary counts remain 81+8. Wiki is never source authority.

## P1b1 exact identity/roster/HP/starting-state reconciliation

P1b1 adds exact generator provenance to retained bodies and a generated typed
1P/2P primary semantic surface. A reviewed policy guards every target origin and
claim; production joins use article body ordinals, module record ordinals,
canonical models, and six explicit state/model aliases, never display-name
folding or fuzzy matching.

A required atomization repair splits four comma-separated Test Subject Power
origins and Tough Egg's adjacent Minion/Hatch origin. The inventory is therefore
4,438, P1b1 maps 1,271 rather than the preliminary 1,266, total final mappings
are 1,320, and 2,253 unrelated records remain captured. P1b1 materializes 787
primary, 470 audit, eleven conflict, and three missing dispositions. The eleven new
conflicts include source-winning Eye capitalization, Strangler independent
small draws, six normal/base HP disagreements, and stale module A8 values for
Exoskeleton/Entomancer. Exact patch transitions remain missing rather than being
credited from current endpoint numbers.

P1b1 QA preserves a distinct retained/wiki `hpBelowA8` range per body/form
through book → compact legacy lane → primary semantic surface. This is audit
evidence only and does not alter source-winning A8 or player-count presentation.
The HP mapper and a family-wide invariant require exact normalized value, actor,
state, Ascension, and player scope at every value-bearing pointer. State IDs are
ownership only: Hatchling base `19–22` does not reuse Tough Egg base `14–18` or
Hatchling A8 `20–23`, and Test Subject phase bases `100/200/300` do not reuse the
source Phase 1 value or A8 `111/212/313`. Retained-only state forms and Axebot's
symbolic source base remain `knownUnknown`; only an exact same-scope source HP
coordinate and fact ref can close source authority.

All 81 ordinary and eight event primaries remain non-null. Mysterious Knight is
still source-only primary plus retained audit reference; Doormaker stays
archive-only. Fabricator's initial source roster remains Fabricator alone, with
four separately typed production possibilities. Snapshot, semantic, and overall
readiness remain false; P1b2/P1c/P2 are not claimed complete.

## Three-wave source-first model (development only)

Source-first migration is split into independently reviewable waves:

1. **Wave A — source world model:** canonical monster/state
   identities and shipped English names, initial and special HP expressions,
   exact HP multiplayer scaling, and encounter roster/pool/production ASTs.
2. **Wave B — source combat behavior (landed):** move registration/title/intent,
   operations, helpers, move and power multiplayer scaling, and selection/phase
   graphs.
3. **Wave C — checked projection and UI migration:** C0 built the compact
   projection; E1 added source placement, exact observation identities, and
   behavior inheritance; later E2 slices closed initial state, HP, production,
   event, and lifecycle families. The QA-approved default now consumes that
   fail-closed projection through the strict adapter.

The cognitive/decision-facing projection contract is documented in
[`docs/decision-projection.md`](decision-projection.md). Its phone surface uses
an evidence-gated `0..N` collection of independently qualified callouts. A collapsed view may show a ranked subset only with the total
count and an expansion path; this is a display budget, never a candidate quota.
Ordered, typed effect signatures remain primary. Practical copy is
consequence-first: structural cues replace ordinary localized move labels, while
directly tracked statuses/keywords and enemy, summon, actor, and target identities
remain visible. Opaque named Powers render as thresholds and outcomes. Exact
localized move/Power labels, canonical source IDs, retained wiki labels, full
horizon-qualified frontiers, and exact provenance stay behind expansion in
Technical audit. The current renderer preserves those E1/E2 gates while keeping
that exact support available for audit and reconciliation.

The checked raw-source authority is `data/game-v0.111.0-source.json`, generated by
`tools/extract-source.py`. It remains an offline generation input rather than a
runtime browser dependency; completion applies only to each declared source
denominator. The app reads the generated compact
`data/encounter-facts-v0.111.0.json` through its fail-closed adapter; that gate is
still mandatory. For practical presentation only, the adapter uses the retained
`data/encounters.json` record on exact encounter/body joins when a checked value
is symbolic. This fallback is visibly labeled and cannot become source authority.

### Wave A source coverage

For exact, hash-pinned, unmodded public-beta v0.111.0 inputs, the extractor
proves:

- all 81 ordinary and 8 event encounter identities and shipped English titles;
- the exact Monsters namespace census: 121 types, 120 concrete and the abstract
  `DecimillipedeSegment` base;
- 102 ordinary-reachable canonical monsters plus six event-only monsters (108
  current reachable), with all 12 excluded concrete types classified;
- shipped names for all 108 current models, including Decimillipede's shared
  title root, Tough Egg/Hatchling state identity, and Test Subject's dynamic
  localized template with the typed `kills + 8` input;
- complete initial HP getter expressions and deterministic A8 single-player
  min/max facts for all 108 reachable models, with all 120 concrete effective
  getters retained as a fail-closed census fixture;
- Tough Egg hatch, Test Subject revive phases, Axebot cumulative pre-scaling
  bonus, and Decimillipede Reattach amount/state-operation facts;
- Decimal HP multiplayer scaling, including one-player identity, player-count
  multiplication, all observed act/boss factors, and the fact that the source
  method performs no rounding or truncation; and
- exact initial roster ASTs, possible membership, and produced membership for
  all 89 encounters, including dependent/random choices, no-replacement rules,
  and Fabricator's separate aggressive and defensive spawn pools.

Every complete coverage family records a denominator and zero unresolved
facts. Title localization is classified 297/315 with 18 explicit missing/internal
keys; that family is not called complete localized coverage.

### Wave B source coverage, expanded by E2c1

For the same exact v0.111.0 inputs, the extractor proves:

- 315 current move registrations from all reachable behavior classes plus
  the abstract Decimillipede segment implementation (305 async via
  `AsyncStateMachineAttribute`, ten exact `Task.CompletedTask` no-ops);
- 297 shipped English titles joined by localization root/state, including the
  Decimillipede shared root and five second internal `_MOVE_2` aliases, with 18
  classified missing/internal titles retained as internal identities;
- 393 constructed intent sites across all 315 moves and all 316 constructor
  arguments, selected by decoded constructor signatures rather than instruction
  proximity; this includes typed boolean arguments and five source delegates
  with exact receiver/target method provenance and normalized return expressions;
- a closed census of 6,786 invocations: 6,418 direct sites in the 305 generated
  move bodies plus 368 unique recursively traversed helper sites;
  the combined 1,172-symbol census contains 514 normalized gameplay
  operations/effects, 1,101 traversed gameplay/support helpers, and 5,171
  source-proven compiler, async, collection, formula, wait, or presentation
  calls, with zero unresolved;
- 497 direct normalized sites: the prior 491 (the original 432 sinks plus 2
  self-kills, 6 Power removals, and 51 typed monster state writes) plus six Fake
  Merchant sites (3 attacks, 1 hit-count site, Frail `applyPower`, and Strength
  `applyPower`), with all 1,094 required semantic fields resolved from exact
  signature argument positions and zero fabricated defaults; helper traversal
  also audits nested command effects;
- 105 selection graphs with 315 move constructors, 317 follow-up assignments,
  24 random nodes, 17 conditional nodes, four must-once flags;
- monster Block scaling (primary/secondary enemy and powered-card-or-move
  Block only; 1P/2P use player count; higher counts multiply the act/room
  factor) distinct from HP scaling and from ordinary attacks, which do not
  scale through those paths; and
- 12 Power opt-ins and five formula overrides, with Buffer inactive because it
  overrides without opting in.

Schema 5 decodes ECMA-335 method signatures and performs bounded CFG/stack/local/
field abstract interpretation over registration methods, intent callback bodies,
and generated `MoveNext` bodies. Intent and sink arguments are selected by their
exact static/instance stack contract; arithmetic,
conversions, locals, and compiler spill fields retain typed expression evidence.
Attack targets are `allOpponentsOfSourceMonster` only because the separately
hashed `AttackCommand.FromMonster` body calls `TargetingAllOpponents`; attacker
identity alone is not treated as target evidence. Unequal required joins,
unknown signatures/opcodes/targets, unknown command APIs, unclassified framework
calls, ambiguous interface implementations, or missing helper proof abort extraction
with a stable unresolved evidence ID before atomic artifact replacement.

See
[`docs/source-world-model.md`](docs/source-world-model.md) for the normalized
schema and AST grammar.

### E1 source placement, observation identity, and behavior applicability

Schema 5 adds three independently gated source families:

- **Placement:** `ModelDb.get_Acts` owns four current act identities. Their
  `GenerateAllEncounters` arrays and exact `EncounterModel.RoomType`/`IsWeak`
  getters derive 20 weak/regular/elite/boss/event pools, 192 full registry
  memberships, and 90 current encounter memberships. All 89 current encounters
  are classified: 87 are pool members; `TUNNELER_NORMAL` is source-proven absent
  from every act encounter registry; and `THE_ARCHITECT_EVENT_ENCOUNTER` is a
  source-proven scripted final transition. Weights remain Decimal `"1.0"`, weak
  and elite draw counts remain exact, regular draw count remains a source
  expression, immediate tag exclusions/fallback remain explicit, and event
  ordering, shuffle, eligibility, and repetition structure are preserved.
- **Event linkage:** all eight event encounters join to exact event owners and
  transition/layout methods. Act-local and shared memberships remain separate.
  Fake Merchant therefore retains four act memberships plus its exact dynamic
  availability predicate; The Architect is not forced into an act pool.
- **Observation identity:** current save history obtains `MonsterModel.Id` and
  serializes exact `ModelId` strings. The complete adapter vocabulary is the 108
  unique current `MONSTER.*` model IDs, case-sensitive, with no prefix stripping
  or fuzzy fallback and no source-declared current aliases. A separate 108-row
  resource representation records the exact proved
  `res://scenes/creature_visuals/<entry-lowercase>.tscn` transformation; it is
  never a model-ID matching fallback. Decimillipede emits
  `MONSTER.DECIMILLIPEDE_SEGMENT_{FRONT,MIDDLE,BACK}`; Ruby Raider bodies use
  their five full canonical IDs. Tough Egg hatch and Test Subject phases remain
  states of one emitted model ID and are explicitly not distinguishable from
  that ID alone. Legacy IDs such as `DECIMILLIPEDE_FRONT`, `ASSASSIN_RAIDER`,
  `HATCHLING`, or `TEST_SUBJECT_PHASE_2` are not promoted into source aliases.
- **Behavior applicability:** exact `TypeDef.Extends` transitive closure joins all
  105 behavior owners/graphs and all 315 registrations to reachable concrete
  models. Five `DecimillipedeSegment` registrations apply to the three concrete
  segment models. Cycles, missing bases, duplicate identities, lookalike names,
  or owners without concrete applicability fail generation.

These are bounded encounter facts, not a complete acts/rooms/events/map model.
Source predicate methods for unrelated non-combat events remain proof references;
only conditions required for current event-encounter availability are normalized.
No observed save/log sample is checked into either artifact.

### Authority and durability boundary

The artifact is authoritative only for the exact input manifest it embeds. A
game update requires a new exact manifest, regeneration, and review. Mods and
live combat/save state are not silently treated as static source facts. The
extractor reads PCK, PE/CLI metadata, and CIL method bodies as bytes; it never
loads the assembly through reflection, executes game methods or CIL,
initializes Godot, or injects into the game. `sts2.xml` participates only in
the exact mixed-version input gate; neither saved research nor this extractor
claims or derives XML migrations.

Raw source remains the primary authority. The schema reserves explicit future
`community` and `empirical` provenance tiers (URL, revision or retrieval date,
claimed game version, confidence, and status). Such observations must never be
silently merged into raw facts, and disagreements must become visible conflicts.
Waves A and B do not ingest community data.

A checked artifact and self-contained tests are regression/integrity evidence.
Source-strength evidence requires successful fail-closed regeneration from the
exact raw files under the pinned extractor/parser trusted computing base.

### Exact regeneration

The documented installation root is:

```text
/home/qqp/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Slay the Spire 2
```

Use an isolated development environment; these packages are not runtime
requirements:

```sh
python3 -m venv .venv-source
.venv-source/bin/python -m pip install -r requirements-source.txt

GAME_ROOT="${STS2_GAME_ROOT:-/home/qqp/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Slay the Spire 2}"
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT"
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --check
```

For a second determinism check:

```sh
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --output /tmp/sts2-source-a.json
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --output /tmp/sts2-source-b.json
cmp /tmp/sts2-source-a.json /tmp/sts2-source-b.json
```

The raw game files, extracted PCK trees, virtual environments, and disposable
research evidence are never checked in. Ordinary `npm test` needs none of them
and no optional Python packages.

## Optional sibling follow-up (outside this worktree)

Do not patch `qq-core/bin/qq` here. The follow-up is exactly:

```sh
add_optional_sibling "${QQ_STS2_ROOT:-$sibling_parent/sts2-companion}" '@hypermemetic-ai/sts2-companion'
```

Missing this sibling must not affect qq-core startup.

## Test

```sh
npm test
```


### E2a initial creature state and intrinsic Power hooks

Schema 6 closes temporal setup for the exact existing 89-encounter/108-model
scope. It derives 89 `GenerateMonsters` roots, 137 construction sites, 38 RNG
calls, 25 setter sites in 13 roots, and five explicit constructor writes across
four models. Generator writes, constructor defaults, creature-addition effects,
transitive helpers, Power `AfterApplied`, and `BeforeCombatStart` remain separate
ordered stages.

Exact inheritance resolves 108 owners to 59 effective `AfterAddedToRoom`
implementations: 48 inherit the source-proven `Task.CompletedTask` base no-op,
52 owners have ordered gameplay effects after helper expansion, and eight have
source-proven non-gameplay-only overrides. The direct implementation census is
54 `PowerCmd.Apply`, one Block, one max/current-HP, and one current-HP site.
Transitive closure emits 111 ordered facts, classifies 1,092 calls, closes 41
initially reachable Power models across `BeforeApplied`, `AfterApplied`, and
`BeforeCombatStart`, and registers 47 runtime-state contracts.

Named source facts include Aeonglass's custom Withering Presence target plus
Artifact; Lagavulin Matriarch's `Sleep` helper; Cubex Construct's Block,
Artifact, HP subscription, and state; the shared three-model Decimillipede hook;
Punch Off HP reduction; Tough Egg's exact
`(CurrentSide == 2) ? Hatch 2 : Hatch 1` branch and restored hatched branch;
Mysterious Knight; and all three Battle Friends. Illusion's
secondary Minion, Plating's player-count variable, and Galvanic/Vital Spark card
afflictions are intrinsic Power-hook facts. The 19 relic `BeforeCombatStart`
listeners and other run-owned listeners remain explicit external-runtime
boundaries, never an assumed empty loadout.

A requested regression audit expected Dense Vegetation to enable Wriggler's
stunned start. Exact CIL instead calls `set_StartStunned(false)`; Wriggler's
state-machine constructor selects `SPAWNED_MOVE` only when that field is true.
The artifact preserves the false write and exact evidence rather than forcing
the expected distribution.

The projection classifies all 57 legacy `startsWithA9` rows. Exact source
agreements, source supersets, dynamic comparisons, state-not-model rows, and the
three unmatched Decimillipede shortcuts stay distinct. The shortcuts are not
aliases; Tough Egg/Hatchling and Test Subject phases remain state/timing facts.

At the E2a boundary, downstream HP Decimal-to-integer conversion/cap/storage was
still unproven. E2b closes that chain; event-turn behavior, general
summon/death/revive/phase/removal lifecycle, and companion-wide formula inlining
remain reason-coded blockers.

### E2b HP assignment, storage, and wire chain

Schema 7 keeps two numeric layers distinct. `ScaleHpForMultiplayer` converts the
integer base HP to `Decimal`, multiplies `base × playerCount × actRoomFactor`, and
returns a `Decimal` with `arithmeticRounding: none`. `SetMaxHpInternal` then rejects
negative input, explicitly converts `Decimal` to `Int32` by truncating toward zero,
and only then caps at `999999999`. For source-proven non-negative HP, truncation
toward zero equals floor; no such equivalence is claimed for negatives. Max storage
precedes `current = min(previousCurrent, newMax)`. `SetCurrentHpInternal` first
applies the Decimal upper clamp, then performs the same explicit conversion; source
shows no lower clamp there.

Normal enemy creation uses the inclusive integer `MinInitialHp..MaxInitialHp`
domain, removes teammate max-HP values when candidates remain, falls back to the
full domain when they do not, and draws from run RNG. One player bypasses the
multiplayer setter writes. Tough Egg, Test Subject, and all Decimillipede segment
paths join the same assignment contract. Creature and network current/max fields
are CLI `Int32`; network capture, `WriteInt(..., 32)`, `ReadInt(32)`, and storage
retain current-then-max order.

Source-discovered complete denominators are 4 base-selection methods, 9
wrapper/helper sites, 11 setter method/sites, 52 command/special applicability
records, 8 cap/clamp/precondition fields, 10 storage/wire joins, and 85 compact
semantic fields. The raw artifact retains 19 direct HP-target sites and all 44 HP
command callers; the projection omits that proof bulk.

The former HP rounding unknown is retired only after these gates. A resolved audit
retains all three historical statements: helper arithmetic has no rounding,
downstream assignment truncates, and the stable legacy consumer uses `Math.floor`.
Its resolution is agreement for non-negative final assigned HP, with no lane
precedence and no negative-value generalization.

### E2c1 event turn machines (script/lifecycle boundary retained)

Schema 8 expands behavior discovery from ordinary-only reachability to the exact
current reachable domain. Source enumeration yields 105 physical graph owners and
315 registrations. Five physical graphs and eight registrations are newly included:
Architect, Battle Friend V1/V2/V3, and Fake Merchant. Mysterious Knight adds exact
applicability to Flail Knight's existing graph and three registrations; it does not
create a duplicate graph. Dense Vegetation reuses Wriggler and Punch Off reuses Punch
Construct.

Every event encounter has a compact source classification:

| Event encounter(s) | Turn classification | E2c1 boundary |
|---|---|---|
| Battleworn Dummy V1/V2/V3 | `noOpTurnMachineWithLifecycle` | One `NOTHING_MOVE` self-loop and exact synchronous no-op each; timeout Power escape/result semantics remain unresolved lifecycle dependencies. |
| Dense Vegetation | `normalTurnMachine` | Reuses the ordinary Wriggler graph. |
| Fake Merchant | `normalTurnMachine` | Four localized moves, two random nodes, five intent constructors, three attacks, one hit count, Frail, and Strength are closed. |
| Mysterious Knight | `inheritedTurnMachine` | Exact Flail Knight applicability with independently proven `MYSTERIOUS_KNIGHT` title roots. |
| Punch Off | `normalTurnMachine` | Reuses the ordinary Punch Construct graph. |
| The Architect | `scriptedNonTurnCombat` | Hidden no-op self-loop is source-proven but insufficient; the external event state machine remains an E2c2 dependency. |

Battle Friend graphs use the exact source generic read-only `MoveState` collection
constructor. Collection constructor, overload, element type, order, cardinality, and
joins are closed and mutation-tested. Fake Merchant's `ShowDialogueForMove` is
recursively traversed; `System.String.Concat` is classified only in the exact
`model entry + ".moves." + move argument + ".speakLine"` localization-key context,
never as a broad ignored framework call. The event slice closes 103 invocation sites,
six direct gameplay operations, and four explicit no-op proofs with zero unresolved.

At the E2c1 boundary, `UNKNOWN.EVENT_BEHAVIOR`,
`UNKNOWN.EVENT_SCRIPTED_BEHAVIOR`, and `UNKNOWN.EVENT_LIFECYCLE` all remained. E2c2b
now closes the separately audited Architect script and retires only the scripted
unknown; Battle Friend timeout/escape/results and general lifecycle remain open.

### E2c2a linked event scripts (Architect and lifecycle retained)

Schema 9 starts from the seven exact E1 `eventLinkage` combat-transition roots and
closes five non-Architect event owners. Source discovery yields 12 option/delegate
constructions, seven transition stack contracts, seven outcome rows, 25 nodes, 20
edges, 76 owner/nested methods, 14 Foul Potion support methods, 53 common framework
roots/async bodies, and a 1,549-site invocation census with zero unresolved. These
are discovered denominators, not seeded expectations.

| Owner | Source-complete linked script contract |
|---|---|
| Battleworn Dummy | Three independently decoded options/transitions use empty added-reward arrays and resume the parent event. `Resume` reads encounter `RanOutOfTime`; timeout sets the defeat page, while V1/V2/V3 success respectively constructs a dynamic potion reward, upgrades at most two runtime-selected cards, or constructs a dynamic relic reward before joining owner-keyed combat extra rewards. |
| Dense Vegetation | Eligibility retains `event.dynamicVars.HpLoss.baseValue`; Trudge On damage uses the same runtime value, Rest refers to the rest-site heal formula, and only Rest makes Fight available. Fight has no added rewards and does not resume the event. |
| Fake Merchant | The initial option collection is empty. Foul Potion usability/targeting dispatches `FoulPotionThrown` to every player's mutable event instance and awaits `Task.WhenAll`; the transition sets `StartedFight`, adds the rug plus conditionally dynamic unstocked relic rewards, and does not resume. |
| The Lantern Key | Return and Keep are initial options; Keep makes Fight available. Fight constructs a Lantern Key `SpecialCardReward`, enters Mysterious Knight, and does not resume. |
| Punch Off | Nab and Take are initial options; Take makes Fight available. Cancellation/subscription and punch-loop calls are classified exactly, gameplay curse/reward calls remain effects, and Fight constructs relic and potion rewards without resume. |

The three Battle display calls are decoded from their individual CIL stacks. Their
monster inputs are V1/V2/V3 respectively; the exact encounter argument is the V1
encounter at all three sites. This is a source-derived result, not a presumed target
or correction policy. Presentation classification is declaration-specific; an
unrecognized command or a damage command in the presentation slice fails extraction.

Evidence grade is **raw pinned metadata/CIL** for identities, callbacks, stack
arguments, branches, rewards, state reads/writes, and framework edges. Formula and
lifecycle values remain stable dependency refs rather than copied/defaulted facts.
At the E2c2a boundary, `UNKNOWN.EVENT_SCRIPTED_BEHAVIOR` remained for Architect.
Schema 10/E2c2b retires it. `UNKNOWN.EVENT_LIFECYCLE` is narrowed to the Battle timeout producer and escape,
common event-combat terminal result, and Architect run-end. Aggregate event, global
lifecycle, formula/runtime, provenance/title, and broader-world blockers remain.
Source, encounter-companion, root, and global `runtimeReady`/readiness stay false.


### E2c2b Architect terminal script (lifecycle/formula retained)

Schema 10 closes the Architect scripted component from its exact E1 link, pinned CIL,
and the selected `localization/eng/ancients.json` entry. The distributions below were
independently source-discovered before they became regression assertions: five
character groups, 17 dialogue templates, 39 ordered line nodes, 22 continuation
edges, 17 terminal-proceed edges, two option/delegate constructors, 96 deduplicated
methods, and 715 classified invocation sites. The structural localization closure is
64 keys: 39 line keys, 22 continuation-button keys, and three source-required control
keys. Raw and compact artifacts contain key identities and per-key/value SHA-256
witnesses only—never localized dialogue or button prose.

Dialogue selection remains dynamic. It reads the source character ID, character wins
(with the source zero branch when stats are absent), global progress wins, first
prefers exact nullable visit matches, falls back to eligible repeating templates only
when exact candidates are absent, and uses event RNG `NextItem`. No concrete template,
score, VFX count, score split, or timing is manufactured.

The component proves `EventLayoutType.Combat` creates an `NCombatRoom` in
`CombatRoomMode.VisualOnly` (`notActiveCombat`). The hidden Architect no-op monster
turn graph remains a referenced turn fact and is explicitly insufficient as script
proof. Room entry refreshes stats, resolves the enemy-side Architect node, and stores
the exact `ScoreUtility.CalculateScore(event.owner.runState, true)` result as a formula
reference. The complete presentation slice contains Talk/speech-bubble, wait,
animation, TriggerAnim, hit/fire VFX, and damage-number VFX calls but no gameplay
Damage or Attack sink; score splitting remains RNG-dependent and non-deterministic.

Terminal control is ordered player end animation, Architect end animation, locally
guarded `RunManager.WinRun`, await, then an empty-option finished state. There is no
event-combat transition, resume, or reward page. `RunManager.OnEnded(true)`,
`GuaranteeKillAllPlayers`, and their run-end ordering remain E2d2 lifecycle dependency
refs; `ScoreUtility` formula values remain E2e. `UNKNOWN.EVENT_SCRIPTED_BEHAVIOR` is
retired and `AUDIT.RESOLVED.ARCHITECT_SCRIPT` preserves this boundary.
`UNKNOWN.EVENT_LIFECYCLE` and aggregate `UNKNOWN.EVENT_BEHAVIOR` remain, as do global
lifecycle, formula/runtime, provenance/title, and broader-world blockers. Source,
encounter-companion, root, and global readiness stay false.

### E2d1a random-branch repair and production discovery

Schema 11 corrects the generic random graph contract across all source-discovered
21 random graphs and 61 branches. CLI parameter metadata and all ten
`RandomBranchState.AddBranch` overload bodies prove that the old integer `weight`
field was a `MoveRepeatType`, `maxRepeats`, or cooldown argument. The eight values
previously labeled Boolean predicates are parameterless `Func<float>` weight
callbacks. Corrected branches therefore keep repeat policy, cooldown, and typed
float weight separately. The distribution is four `CanRepeatForever`, ten
`CanRepeatXTimes`, 45 `CannotRepeat`, and two `UseOnlyOnce`; 53 weights are exact
float constants and eight remain dynamic delegates. `StateWeight.GetWeight`,
`GetStateWeight`, and `GetNextState` prove callback evaluation, independent
state-log/repeat/cooldown zeroing, effective-weight summation, and
`Rng.NextFloat(total)` source-order selection. Callback values are never rendered
as fixed probabilities.

The named Rat regression is source-derived rather than copied from the earlier
research statement: Scratch and Disease Bite are `CannotRepeat` with cooldown 0,
Screech is `CannotRepeat` with cooldown 3, and `CALL_FOR_BACKUP_MOVE` is
`UseOnlyOnce` with cooldown 0. Fabricator and Fogmog preserve their float callback
weights and independently decoded repeat rules.

The same wave closes an assembly-wide census of 14 `CreatureCmd.Add` sites and 17
separate `OstyCmd.Summon` sites. Current encounter behavior discovers six producer
owners, seven move roots, three Fabricator helpers, five helper-call edges, and six
direct Add sinks. Existing behavior evidence already traversed
`SpawnDefensiveBot`, `SpawnAggroBot`, and shared `SpawnBot`, including Fabricating
Strike; E2d1a reuses and deduplicates those call-site facts instead of claiming the
helpers were previously invisible. Death-Power, player-pet, mock, core-forwarding,
and Osty sites retain explicit out-of-scope classifications.

The shared core contract proves generic and explicit-model body construction,
`CreateCreature` and unique canonical-model spawn history before insertion, live
combat checks, combat/manager/room insertion, awaited E2a initial-state dispatch,
room model-ID history, awaited `Hook.AfterCreatureAddedToCombat`, and exact created
body identity returned to producers. Different-combat and duplicate-body paths
throw; non-live combat returns without insertion; exceptions propagate without
rollback or cancellation. Core Add performs no slot validation and never invokes
`Hook.AfterSummon`, which remains on the separate Osty API. Producer pools,
availability, slots/no-slot handling, cardinality, caps/repetition, and post-add
ordering remain explicitly `pendingE2d1b`; death/revive/removal/results remain
E2d2. `UNKNOWN.LIFECYCLE_COVERAGE` is retained.

### E2d1b producer semantics

Schema 13 retains the seven source-discovered producer triggers without changing a
consumer. The six owners remain Fabricator, Fogmog, Living Fog, Ovicopter, The
Obscura, and Two-Tailed Rat; Fabricator contributes both Fabricate and
Fabricating Strike. The closed denominators are seven producer records, seven
pools with nine distinct candidate models, six slot policies, one shared
candidate-RNG selection site, four ordered post-Add effects, 12 runtime-state
contracts, and four explicit E2d2 dependency refs.

Fabricator's aggressive `[Zapbot, Stabbot]` and defensive
`[Guardbot, Noisebot]` pools are reusable. `SpawnBot` excludes only the
immediately previous canonical model **reference**, selects uniformly with the
Monster-AI RNG, stores the choice before Add, and faults after an empty
`NextItem` result rather than silently cancelling. `CanFabricate` is the exact
alive same-side count `< 4` precondition. Fabricate makes defensive then
aggressive helper attempts; Fabricating Strike attacks before its aggressive
attempt. Both await the exact returned body before applying Minion. There is no
pool depletion or lifetime cap; death/removal can change later availability and
therefore remains E2d2.

Two-Tailed Rat preserves the ordered `CanSummon` clauses: turns at or below zero,
group call count below three, a nonempty first-free slot query, and no other
teammate already planning Call for Backup. The actual Add independently chooses
the last free declared slot. It awaits one Rat body and then synchronizes every
current Rat to `Max(old + 1)`, proving a three-completed-call group bound rather
than a cap inferred from five visible slots. The graph branch remains
`UseOnlyOnce` per Rat body.

Ovicopter starts with an unconditional Lay Eggs path; later graph cycles use
`CanLay` (`alive same-side count <= 3`). Each activation performs exactly three
attempts, each independently taking the last free slot, so normally added bodies
remain `0..3`. Every successful Tough Egg Add is followed by awaited Minion.
Tough Egg Hatch is a later same-body E2d2 state transition, not another Add.
Living Fog retains dynamic `BloatAmount` (source default 1), one first-free query
per iteration, reusable Gas Bombs, no Minion, and no lifetime cap. Fogmog and The
Obscura each use fixed `"illusion"` without an occupancy check on their one graph
path; Obscura writes `HasSummoned=true` only after Add returns.

Core Add still performs no slot validation. Producer differences are explicit:
Rat, Ovicopter, and Living Fog skip when no slot is available; Fabricator passes
an empty first-free result through; the two fixed-name paths pass `"illusion"`.
Runtime collections, alive flags, next moves, counters, RNG, and internal fields
remain unavailable to the current observation adapter. Production is
source-complete, but listener effects, death/removal, death-Power Add sites,
hatch/revive/escape/results, and broader lifecycle stay E2d2 dependencies.
`UNKNOWN.PRODUCTION_SEMANTICS` is retired; `UNKNOWN.LIFECYCLE_COVERAGE` remains.

## E2d2a core lifecycle — `force`, not `playDeathEffects`

> **Correction:** both public `CreatureCmd.Kill` overloads name their Boolean
> parameter `force`; `KillWithoutCheckingWinCondition` takes
> `(creature, force, recursion)`. There is no source `playDeathEffects` field.
> `force:false` is ordinary death and does **not** skip death effects. Gas Bomb
> and Waterfall Giant both call `Kill(..., force:false)` and retain HP zeroing,
> `BeforeDeath`, `Died`, animation, `AfterDeath`, removal, Power cleanup, and
> player cleanup as applicable. The two completed entry guards apply regardless
> of `force`; after they pass, `force:true` bypasses only the out-of-combat
> multiplayer player safety heal and ordered `ShouldDie` prevention.

Schema 13 closes four command declarations/physical bodies, 21 Kill-family call
sites, three Escape call sites, six dispatch methods, three logical plus three
physical listener registries, four escape/removal methods, the four
`CheckWinCondition`/`EndCombatInternal` declarations and physical bodies plus
three support methods, 14 centralized win-check call sites, seven explicit
runtime boundaries, seven dependencies, 707 classified lifecycle-method invocations, and 59 normalized lifecycle nodes.
The singular Kill wraps an exact one-body list. The list overload returns on an
empty list, snapshots run/list state, and awaits each inner kill sequentially.
An inner fault/cancellation propagates before manager, loss, game-over, or
turn-ending stages. If all run players are dead, live combat calls `LoseCombat`
and then falls through to the same `TestMode.IsOff` gate reached by non-live
combat. Test-off synchronously stops music, calls `OnEnded(false)`, and shows
game over—even when `PendingLoss` was just set; test-on skips that sequence.
Only the player-remains branch reaches killed-player EndTurn handling. Neither
Kill overload directly invokes `CheckWinCondition`.

Immediately after capturing `CurrentCombatId`, inner Kill returns completed with
no HP or death hooks for `(CombatState == null && !IsPlayer)` and for
`(CombatState != null && !CombatState.IsLiveCombat)`. A detached player and a
body attached to live combat pass these guards. There is still no generic
already-dead short circuit: an eligible zero-HP body runs awaited `BeforeDeath`.
When HP is positive it first writes HP to zero and awaits
`AfterCurrentHpChanged`. `ShouldDie` runs early then late and the first
false listener is the exact preventer. Allowed death orders synchronous `Died`,
removal predicates, animation/node request, awaited `AfterDeath(false)`, living
teammate snapshot, manager-before-state removal (with move-time state-list
removal deferred), sequential death-Power removal/`AfterRemoved`, primary-to-
secondary cleanup with `force:false`, then player orb/Osty/hook/death handling.
Prevented death throws at recursion 10; otherwise it awaits `AfterDeath(true)`,
then `AfterPreventingDeath`, and recurses only if the body remains dead. The
out-of-combat multiplayer player safety branch also awaits `CreatureCmd.Heal`;
only success returns `SAFETY_HEALED`. Awaited fault/cancellation propagates with only
already-completed effects; later stages are never inferred.

`BeforeDeath`, `AfterDeath`, and `AfterPreventingDeath` await one current listener
at a time and call `InvokeExecutionFinished` only after a successful listener
callback—never `Task.WhenAll`. Combat listeners preserve allies then enemies;
per body Powers then Monster; active-player relics, potions, orbs, combat-pile
cards, afflictions, and enchantments; combat modifiers, badges, multiplayer
scaling; then mod subscribers. Run listeners preserve deck cards/enchantments,
relics/potions, run modifiers, badges, scaling, mod subscribers, then the child
combat registry. Current-membership filtering, source collection order, and
duplicates remain; player contents and mod registries are dynamic external
runtime boundaries, not empty or ignored.

Escape returns without mutation for dead, detached, or non-live bodies. Otherwise
it synchronously removes all Powers, optionally requests node removal and hides/
disables interaction, performs Monster `BeforeRemovedFromRoom` then state-machine
reset, tracker unsubscribe and manager event, appends the exact body to escaped
history, and removes/unattaches it from exactly one state side before the state
event. Escape fires no death hooks and creates no escape-result enum. Room exit/
reset remains separate.

Combat ending uses nullable `PendingLoss`, not an invented result enum. Victory
requires a live turn, no alive primary enemy, and no current stop-ending listener;
living secondary-only enemies do not block it, and all enemies escaping becomes
ordinary victory at the next centralized check. Victory marks the turn ended and
clears phases/actions synchronously, then awaits each player's
`ReviveBeforeCombatEnd` before `AfterCombatEnd`. A revive fault/cancellation
cannot imply history, room, victory-hook, or save stages. The successful path
clears history, ends the room, cleans players, awaits `AfterCombatVictory`,
records and saves, updates progress/achievements/scaling, fires `CombatWon`,
unpauses queues, and finally fires `CombatEnded`. Reward/parent event routing
remains E2d2c.
Action normal completion and the executor's logged-fault branch reach the
centralized check; cancellation has no success edge, and an awaited termination
failure does not imply later stages.

Implementation deliberately reuses the existing `AssemblyMetadata` method/code
reader, bounded `CilDataFlow` (including its exact trailing-Boolean slice),
normalized operation AST, proof records, denominator coverage, canonical JSON/
atomic replacement, and compact projection validator. The HP token scanner now
delegates to the shared metadata code reader. No parallel lifecycle authority,
model-name call classifier, compatibility alias, assembly execution, or
proprietary CIL dump was added.

E2d2a adds `AUDIT.RESOLVED.CORE_LIFECYCLE`, but
`UNKNOWN.LIFECYCLE_COVERAGE` remains with narrowed E2d2b listener/phase/
relationship/death-Add, E2d2c event routing, and E2d2d run-termination scope.
`UNKNOWN.EVENT_LIFECYCLE`, aggregate `UNKNOWN.EVENT_BEHAVIOR`, formula, root,
global, and companion gates remain false. Only the independent encounter
projection remains ready.

## E2 compact encounter projection (historical offline landing; no consumer change at that wave)

`data/encounter-facts-v0.111.0.json` is a deterministic schema 10 compact projection for
future encounter UI work. It is **not** a runtime input in E2d2a. The stable
`/sts2` route still reads only `data/encounters.json`; no file under `src/`
imports the projection or the source artifact. Generate or verify it
without a game installation:

```sh
python3 tools/generate-encounter-facts.py
python3 tools/generate-encounter-facts.py --check
# equivalent: npm run build:encounter-facts / npm run check:encounter-facts
```

The generator reads exactly two checked files, whose logical paths, byte sizes,
and SHA-256 digests are pinned in the output:

- `data/game-v0.111.0-source.json` (schema 13 raw source facts); and
- `data/encounters.json` (legacy/community presentation annotations).

It never reads `/home/qqp/games/STS2`, a save, a log, `src/`, or the network.
Output replacement is atomic and happens only after complete validation;
`--check` never replaces output. There are no generated timestamps.

### Authority lanes

The projection keeps five non-mergeable sections:

- `sourceFacts` contains exact source encounter/monster/state identities,
  roster ASTs and cardinalities, separate possible/produced sets and production
  pools, HP expressions/scaling/assignment/storage/wire contracts, move registrations/titles/intents/operations,
  behavior owners/applicability, selection graphs, source-derived act/room/pool
  placement, event linkage, exact observation identity contracts, corrected
  random repeat/float-weight graphs, compact production-discovery/core-Add
  contracts, seven closed producer records, and the compact E2d2a command/dispatch/
  registry/removal/combat-termination component with explicit remaining dependencies. Event encounters remain source-only.
- `legacyAnnotations` contains visibly labeled act/room labels, starts-with
  prose, roles/packs, patterns, rules/timing, move prose, and unjoined move-title
  fallback candidate sets. Its missing per-fact `confidence` and `status` are
  reported as an incomplete known-unknown; they are not manufactured.
- `laneComparisons` and `conflicts` classify comparable source/community facts.
  Every disagreement retains both fact IDs and values and is unresolved; there
  is no winner or object-spread precedence.
- `resolvedAudits` retains the three-lane HP rounding history, production-only
  closure, E2d2a core-lifecycle closure, event-turn and linked-script closures, and the Architect script closure
  with explicit formula/lifecycle boundaries. No audit selects source/consumer precedence.
- `knownUnknowns` no longer contains the resolved E1 absence reasons,
  `UNKNOWN.INITIAL_STATES`, `UNKNOWN.HP_ROUNDING_CONFLICT`, or
  `UNKNOWN.PRODUCTION_SEMANTICS`. It retains event behavior,
  lifecycle closure (including production's explicit E2d2 dependencies), and
  companion-wide formula/runtime contract closure, plus all 18 missing source move titles, incomplete
  legacy per-fact provenance, and broader world-model families.

`DOORMAKER_BOSS` exists only in `legacyAnnotations.archive`; it is never part of
current source scope. Tough Egg/Hatchling and Test Subject phases remain states
of their canonical models rather than simultaneous bodies. Fabricator
production pools and random/dependent roster ASTs remain distinct from initial
co-presence.

### Digests, evidence, and readiness

`embeddedSourceInputManifestSha256` is SHA-256 over compact canonical JSON of
the schema 13 artifact's exact four game input rows. `payloadSha256` is SHA-256
over compact canonical JSON of the top-level `payload` object only, so checksum
semantics are non-self-referential. Each projected fact points through
`factReferences` to deduplicated evidence containing an exact RFC 6901 pointer
and pointed-value digest in one of the two checked inputs. The full invocation
census and repeated CIL proof objects are intentionally excluded.

Readiness is generated from declared gates. The bounded
`runtimeScopes.encounterProjection` section is complete for its named coverage
families and joins. Root/global world-model readiness and
`runtimeScopes.encounterCompanion` remain hardcoded and validated
`incomplete`/false: the aggregate event blocker remains because referenced event
lifecycle/timeout/result and formula semantics are unresolved; broader lifecycle
closure and companion-wide formula contracts also remain blockers. E2d2a therefore does not alter the stable UI default,
security headers, no-store behavior, state selection, or route boundary.


## C1 shadow reader-representation bridge

The opt-in C1 consumer preserves the stable state-reader payload. `parseSave`
continues converting saved `MONSTER.*` wire IDs to unprefixed state model IDs;
the source adapter reuses that one pure conversion when it constructs a
collision-checked secondary index from fully validated compact-projection
observation rows. The exact checked `observedId` and canonical model remain in
the shadow output.

This bridge does not change the source identity policy. In particular,
`matchingPolicy.prefixStripping:false` still means source observation matching
is exact: no alias table, case folding, fuzzy lookup, roster inference, or
legacy-to-source promotion is permitted. The conversion exists only because the
adapter receives the state reader's already-normalized representation. Invalid
row shape/kind/policy, an unsupported wire prefix, normalization failure,
duplicate checked identity, or normalized-key collision makes the shadow
adapter unavailable while stable routes continue serving legacy data.
