# sts2-companion

A phone-first, read-only encounter micro-HUD for **Slay the Spire 2**. The
optional Cordis plugin mounts its own page at <http://127.0.0.1:3082/sts2> on
the qq loopback web server. It shows an A9 / 2P reference book for the
current fight, or the most recently completed fight between rooms. It does not
show live HP or intents and never writes game input.

The browser polls `/sts2/state`, so a new `Creating NCombatRoom` log line
replaces the card without a reload. Identity comes only from `godot*.log` and
`current_run_mp.save`; paths are injectable for tests and alternate installs.
The default probes the Steam Flatpak data root used on this host, the native
XDG data root, and the alternate Megacrit Flatpak root.

Book data is local in `data/encounters.json` and targets Steam
`public-beta` **v0.111.0**: A8 single-player HP and A9 move, block, and buff
values are normalized from wiki.gg StS2 enemy article pages. Named disagreements
are overridden and visibly flagged from the audited v0.111.0 game CIL. The
older `Module:Enemies/StS2 data/*` snapshots are fallback only. Runtime makes no wiki
or other network requests. It also compares the book target with the local
game's `release_info.json` when that file is readable; a mismatch is shown on
the page rather than silently serving the wrong book.

The checked-in `tools/.wiki/pages.json` records full article/patch wikitext,
revision IDs and UTC harvest time. Regeneration is deliberately split into a
networked development-time snapshot and a deterministic offline build:

```sh
python3 tools/harvest-wiki.py  # refresh wiki.gg snapshots (development only)
python3 tools/generate-book.py # reads only checked-in local snapshots
```

Unknown event fights keep their raw encounter ID visible. Missing HP, an
unclassified article pattern, an unreadable release file, and a version
mismatch are likewise rendered as explicit known-unknowns instead of a blank
page.

## Staged source-first foundation (development only)

Source-first extraction is being introduced in independent stages. The checked
`data/game-v0.111.0-foundation.json` is the first, deliberately incomplete
stage. It proves only these facts for the exact pinned game files:

- the 81 current ordinary and 8 current event encounter model identities; and
- their exact shipped English titles from
  `localization/eng/encounters.json`.

The artifact has `runtimeReady: false`. The app does **not** import it and still
uses the wiki-derived `data/encounters.json`; displayed event fights and the
legacy displayed Doormaker row are therefore unchanged. The foundation does
not yet prove HP, monster/body identities, rosters or pools, moves, powers,
multiplayer scaling, patterns, or state formulas. `sts2.xml` is part of the
exact mixed-version input gate only; this stage extracts no XML facts and makes
no save-migration claims.

The extractor reads PCK, PE/CLI metadata, and CIL method bodies as bytes. It
does not load the assembly through .NET reflection, execute game methods or
CIL, initialize Godot, inject into the game, or unpack the full PCK. Its Python
packages are development-only and exactly pinned in
`requirements-source-foundation.txt`.

For this pinned build, the census considers top-level TypeDefs in the exact
encounter namespace that inherit `EncounterModel`. Metadata abstract flags
exclude the abstract battleworn event base, and the explicitly named
`DeprecatedEncounter` placeholder is excluded. Concrete descendants of that
event base are events, as are direct `EncounterModel` descendants ending in
`EventEncounter`; remaining concrete direct descendants are ordinary. Every
concrete record must expose the expected encounter methods. Unknown
inheritance, names, slug behavior, types, or count drift aborts extraction.

The documented installation root is:

```text
/home/qqp/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/Slay the Spire 2
```

Pass the game root explicitly. To create an isolated development environment,
regenerate atomically, and then verify byte-for-byte equality:

```sh
python3 -m venv .venv-source
.venv-source/bin/python -m pip install -r requirements-source-foundation.txt

GAME_ROOT="${STS2_GAME_ROOT:-/home/qqp/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/Slay the Spire 2}"
.venv-source/bin/python tools/extract-source-foundation.py \
  --game-root "$GAME_ROOT"
.venv-source/bin/python tools/extract-source-foundation.py \
  --game-root "$GAME_ROOT" --check
```

For an additional determinism check, generate twice to temporary destinations
and compare them:

```sh
.venv-source/bin/python tools/extract-source-foundation.py --game-root "$GAME_ROOT" --output /tmp/sts2-foundation-a.json
.venv-source/bin/python tools/extract-source-foundation.py --game-root "$GAME_ROOT" --output /tmp/sts2-foundation-b.json
cmp /tmp/sts2-foundation-a.json /tmp/sts2-foundation-b.json
```

The four raw game files are proprietary inputs and are never checked in.
Ordinary `npm test` needs neither those files nor the optional Python packages
and performs regression/integrity validation of the checked artifact. That is
not independent source proof: proof-strength evidence comes from successful,
fail-closed regeneration using the exact hashed raw files and pinned parser
versions.

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
