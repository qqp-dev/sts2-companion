# Source world model schema

`data/game-v0.111.0-source.json` is a deterministic, presentation-independent
world model for exact public-beta v0.111.0 inputs. It contains identities,
localization joins, formulas, roster selections, membership sets, and state
facts—not UI sentences or layout. Schema 2 is the Wave A boundary and remains
runtime-incomplete until the behavior and cutover waves land.

## Three-wave boundary

| Wave | Scope | Current status |
|---|---|---|
| A | Monster/state identity and names; HP/state formulas; HP multiplayer scaling; encounter roster/pool/production facts | Complete for explicit denominators |
| B | Move registration/title/intent; operations and helpers; move/Power scaling; selection and phase graphs | `notExtracted` |
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
