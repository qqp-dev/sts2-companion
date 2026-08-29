# Source world model schema

`data/game-v0.111.0-source.json` is a deterministic, presentation-independent
world model for exact public-beta v0.111.0 inputs. It contains identities,
localization joins, formulas, roster selections, membership sets, and state
facts—not UI sentences or layout. Schema 4 is the Wave B boundary and remains
runtime-incomplete until the runtime cutover wave lands.

## Three-wave boundary

| Wave | Scope | Current status |
|---|---|---|
| A | Monster/state identity and names; HP/state formulas; HP multiplayer scaling; encounter roster/pool/production facts | Complete for explicit denominators |
| B | Move registration/title/intent; operations and helpers; move/Power scaling; selection and phase graphs | Complete for explicit denominators, with 18 classified missing titles |
| C | Runtime/UI rendering, encounter scope correction, fact references and proof enforcement | Not started |

The current app does not import this artifact and still displays the
wiki-derived book. Wave A changes no routes, renderer output, event display, or
`data/encounters.json` bytes.

## Identities and state

Canonical model references have the form `MONSTER.<ModelDb entry>`. Source type,
canonical model, display identity, and state identity are separate fields.
Consequently:

- `MONSTER.TOUGH_EGG#HATCHED` remains the `TOUGH_EGG` model but uses shipped
  `HATCHLING.name` and the hatch HP expression;
- Test Subject phases remain states of `MONSTER.TEST_SUBJECT`; its title is the
  localized template plus an explicit save-progress input expression;
- Front, middle, and back Decimillipede segments are separate canonical models
  whose title getter uses `DECIMILLIPEDE_SEGMENT.name`; and
- aliases from the old presentation book are never used to generate source
  facts.

Reachability classification is likewise separate: ordinary-reachable,
event-only, deprecated placeholder, helper/test, helper/obsolete, or obsolete.

## Normalized AST grammar

All objects are closed: unknown node kinds, fields, operations, numeric types,
or excessive depth fail validation. JSON numbers are used only for integers.
Decimal constants are canonical strings so serialization never introduces
binary floating-point ambiguity.

### Typed expressions

Every expression declares `valueType`.

| `kind` | Meaning |
|---|---|
| `constant` | Typed integer, Decimal string, or boolean literal |
| `stateVariable` | Named external input with an explicit bounded domain |
| `sourceField` | Exact compiler/source field symbol with a numeric type; evaluation requires an explicit supplied field context |
| `reference` | Exact source method signature, optionally carrying a separately compiled expression |
| `combatQuery` | Typed runtime query input; the pure evaluator requires it to be supplied |
| `ascensionSelect` | Select `below` or `atOrAbove` at an observed threshold |
| `arithmetic` | Reviewed `add`, `subtract`, `multiply`, or `divide` operation |
| `compare` | Typed comparison producing boolean |
| `conditional` | Typed condition with equal-typed branches |
| `actRoomFactor` | Reviewed act-index and boss-context Decimal factor table |
| `convert` | Explicit exact integer-to-Decimal conversion or named Decimal-to-integer rounding |
| `range` | Integer minimum/maximum expression pair |

Example (abridged Axebot minimum HP):

```json
{
  "kind": "arithmetic",
  "operator": "add",
  "valueType": "integer",
  "operands": [
    {
      "kind": "ascensionSelect",
      "threshold": 8,
      "below": { "kind": "constant", "valueType": "integer", "value": 70 },
      "atOrAbove": { "kind": "constant", "valueType": "integer", "value": 76 },
      "valueType": "integer"
    },
    {
      "kind": "arithmetic",
      "operator": "multiply",
      "valueType": "integer",
      "operands": [
        {
          "kind": "stateVariable",
          "name": "axebotRespawnCount",
          "valueType": "integer",
          "domain": { "minimum": 0, "maximum": 2 }
        },
        { "kind": "constant", "valueType": "integer", "value": 10 }
      ]
    }
  ]
}
```

HP multiplayer scaling accepts Decimal `baseHp`. One player returns it
unchanged. More players evaluate `baseHp × Decimal(playerCount) × factor`.
The observed factor input domain is act index 0 through 2 plus boss context;
out-of-domain acts fail. The source method returns Decimal and performs no
rounding or truncation. The pure test evaluator runs only normalized ASTs and
never game code.

### Roster selections

| `kind` | Meaning |
|---|---|
| `fixed` | One canonical model |
| `sequence` | Ordered children; order is fixed or RNG-selected as declared |
| `uniformChoice` | One uniformly selected child |
| `weightedChoice` | One child selected by explicit integer weights |
| `repeat` | Independent or without-replacement repeated draws |
| `permutation` | RNG-selected ordering of a child selection |
| `filteredChoice` | Repeated selection under a reviewed count/exclusion constraint |

Each initial roster is separate from `possibleMonsters`, `producedMonsters`,
and `productionPools`. Candidate membership is never flattened into a lineup.
For example, Flyconid is represented as a two-slot sequence: a uniform medium
slime choice followed by fixed Flyconid. Fabricator initially contains only
Fabricator; its four bots are produced membership split into aggressive and
defensive pools.

Dependent choices are represented structurally. Slimes Weak is a uniform choice
between the two complete small-slime orders, with an independent medium choice
in the middle. This proves exactly three bodies and exactly one of each small
slime without pretending the four candidates are one lineup.

Fixed rosters are compiled by a bounded stack/data-flow interpreter over a
strict opcode, call-signature, and collection-builder allowlist; model call
sites alone are not treated as bodies. Reviewed loops require an exact CFG and
a separately proven finite input. Dense Vegetation, for example, iterates its
source-defined four-entry `get_Slots` array and therefore emits an ordered
four-Wriggler sequence. An unknown or dynamic slot cardinality fails extraction
instead of being flattened to the loop body's single `ModelDb.Monster` call.

## Provenance

Raw facts use `authority: "rawSource"` (directly or through the artifact-level
default) and bind to:

- exact assembly/PCK SHA-256;
- fully qualified type/method signature;
- exact method-body and CIL instruction hashes;
- normalized instruction and semantic/expression witness hashes;
- localization PCK path, entry MD5/SHA-256, key, and key/value witness; and
- diagnostic metadata tokens only as exact-build locators, never identities.

Selection roots and possible/produced membership facts carry their own method
and semantic witnesses. Whole-method hashes do not replace normalized formula
or selection witnesses.

Future non-raw observations must use an explicit `community` or `empirical`
kind with URL, revision or retrieval date, claimed version, confidence, and
status. A raw/community disagreement is a conflict requiring review; it cannot
be silently merged or relabeled. No such fallback is ingested in Wave A.

## Failure and durability rules

Extraction hashes every manifest input before parsing facts and writes only
after the complete build succeeds. Unknown required-slice opcodes, calls,
signatures, branches, localization joins, arithmetic, state inputs, model
references, recursion, or depth fail extraction. No previous artifact facts and
no wiki values are used to fill a failed raw extraction.

Authority applies only to the embedded exact manifest for unmodded v0.111.0.
A game update needs a new manifest plus regeneration and review. Mods and live
combat/save values are outside this static artifact. Checked bytes and unit
tests provide regression/integrity evidence; exact-file regeneration under the
extractor trusted computing base provides source-strength evidence.

## Commands

```sh
GAME_ROOT="/home/qqp/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Slay the Spire 2"
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT"
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --check
npm test
```

## Regression comparison with the current book

These checks are discrepancy fixtures, never extraction inputs or source proof:

- after mapping current-book compatibility aliases and display states, all 105
  current non-Doormaker A8 body/state HP facts compare equal to the raw-derived
  values;
- the raw build has eight event encounters that the current runtime book does
  not display, while the runtime book retains the removed Doormaker entry;
- the current flat Flyconid lineup fixes Leaf Slime (M), but raw selection is
  uniform Leaf Slime (M)/Twig Slime (M);
- the current flat Slimes Weak candidates do not express the exact three-body
  rule (one of each small slime and one random medium slime);
- the current Slithering Strangler lineup does not express its three secondary
  categories or the independent draws in the two-small category; and
- current presentation names may differ from shipped encounter titles.

A mismatch in these fixtures is surfaced for review. It cannot supply, replace,
or override a missing raw fact.


## Combat operations and graphs

Wave B adds closed operation and graph grammars. Unknown operation kinds, graph
node/edge kinds, helper names, or missing provenance fail validation.

### Operations

| `kind` | Meaning |
|---|---|
| `attack` | `DamageCmd.Attack` amount/target |
| `attackHitCount` | `AttackCommand.WithHitCount` |
| `applyPower` | `PowerCmd.Apply` with canonical Power |
| `gainBlock` | `CreatureCmd.GainBlock` |
| `addStatusCard` / `addGeneratedCard` | card pile sinks |
| `summon` | `CreatureCmd.Add` |
| `heal` / `escape` / `removeCard` | remaining reviewed command sinks |
| `kill` | exact `CreatureCmd.Kill` target and play-death-effects argument |
| `removePower` | generic canonical Power removal or an exact runtime-selected Power-instance contract |
| `stateWrite` | typed monster property write with exact setter identity |
| `helperEffect` | Reattach, Fabricator spawn, ChooseCurse, Tough Egg hatch, Waterfall pressure |
| `transition` | explicit no-op or nonnumeric/state update |

Amounts are typed expressions. A `reference` node retains an exact source method
signature; a `sourceField` retains an exact typed compiler/source field without
inventing a domain. The pure evaluator only evaluates either when a compiled
expression or explicit context is supplied.

Intent constructors use the same decoded-signature stack contract. The 387
constructor sites contain 311 required arguments: numeric expressions, typed
boolean constants, or the closed `sourceDelegate` shape. A source delegate keeps
its `(object, nativeInt)` constructor signature, receiver binding, exact target
method and body/slice hashes, and a normalized `resultExpression` derived from
all reachable return stacks. Array indices and neighboring constants/getters are
not constructor arguments. Unknown signatures, delegate bindings/targets,
return stacks, or non-unique expressions fail extraction. The two complete
coverage families separately count 387 classified constructors and 311 resolved
arguments, so a site census cannot conceal an unresolved Func overload.

Intent templates from `intents.json` are localization facts; their numerals are
not effect authority.

### Closed invocation classification

Every one of the 6,332 direct `call`, `callvirt`, and `newobj` sites in the 301
current `MoveNext` bodies, plus 351 unique sites in 29 recursively reached helper
bodies, has an evidence-bearing census record and exactly one outcome:
`normalizedGameplayOperation`, `traversedGameplayHelper`, or
`provenNonGameplayPlumbing`; an unresolved fourth outcome aborts extraction and
is never serialized as complete. The combined 6,683-site census contains 1,156 exact source symbols and resolves
508 / 1,080 / 5,095 sites respectively; separate direct/helper denominators are
retained (6,332 and 351). Exact command declarations
form a closed boundary. A newly observed command method, unknown Godot/framework
member, missing signature, or unsupported local side-effecting method receives a
stable `UNRESOLVED.INVOCATION.<sha256>` identifier and fails the family.

Local monster, Power, and card helpers resolve by exact owner/member/signature.
Async helpers are followed through `AsyncStateMachineAttribute` to generated
`MoveNext` bodies; abstract helper calls traverse every concrete CLI
`InterfaceImpl`/override. Their nested calls are classified recursively, exposing
helper-contained effects such as Stun, bot spawning and Minion application,
card selection/Power application, HP reset/heal, deck-card removal, and gold
loss. SFX, animation, waits, task awaiters, collections, and presentation nodes
use narrow declaration/member recognizers and remain visible in the census; no
unknown-prefix ignore can claim completeness.

Schema 4 obtains every sink stack contract by decoding the exact ECMA-335
signature, including static versus instance receivers and generic signatures.
A bounded CFG abstract interpreter carries constants, arguments, locals,
fields, getters, arithmetic, conversions, and fluent command receivers across
branches and async resume plumbing. Equal joins collapse; unequal required
values remain unresolved and abort generation. Unknown stack effects, call
signatures, branch targets, target classes, or expression types likewise fail
before atomic replacement. No positional instruction window or “last getter”/
“last constant” fallback is used.

Operation fields are closed by kind. In particular, attack amounts come from
the sole `DamageCmd.Attack` argument, hit counts from the argument consumed by
`WithHitCount`, Block from `GainBlock.amount` rather than its trailing props
enum, and Power amount/target from the selected `Apply` overload. Summon,
escape, and card removal do not receive dummy numeric values. `CreatureCmd.Kill`
retains its exact creature and boolean arguments; the two explosion moves are
source-monster self-kills with play-death-effects false. Generic `PowerCmd.Remove`
retains canonical Power type arguments (including Soar, Adaptable, and Painful
Stabs). The sole non-generic removal is explicitly a runtime-selected iterator
Power instance rather than an invented model. Attack target
classification is backed by a separately hashed slice of
`AttackCommand.FromMonster -> TargetingAllOpponents`, producing
`allOpponentsOfSourceMonster`; `FromMonster` attacker evidence by itself is not
a target fact. Other observed targets remain distinct (`sourceMonster`,
`registeredTargets`, `iteratedCreature`, teammates, or an awaited summoned
creature), as do slot and card selections.

### Graphs

Nodes are `move`, `random`, or `conditional`. Edges are `followUp`,
`randomBranch`, or `conditionalBranch`. Weights are emitted only from AddBranch
integers. Predicate callbacks remain `reference` expressions unless a later
wave compiles them. Branched initial states (Decimillipede `StarterMoveIdx % 3`,
Axebot stock override, Chomper `_screamFirst`) are recorded as multiple proven
initials rather than a guessed single start.

Monster Block scaling and Power opt-in/override formulas are separate from
ordinary `DamageCmd.Attack` amounts. Ordinary monster attacks do not inherit
HP or Block multiplayer multipliers.

The 6,683-site combined invocation census (6,332 direct plus 351 helper),
491 direct-operation census, and each
operation-kind denominator are reported separately from 1,081/1,081 required
semantic fields. A physical site is not counted as
semantic completion unless its required arguments, target/selection, model,
expression type, and normalized slice resolve.

18 move titles are classified `missingLocalization`. That is complete
classification, not complete localized coverage, and is reserved for an
explicit, visibly cited Wave C community fallback if useful. Wave B never
imports community/wiki data into the raw artifact and makes no XML migration
claim.
