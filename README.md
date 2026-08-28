# sts2-companion

A phone-first, read-only encounter micro-HUD for **Slay the Spire 2**. The
optional Cordis plugin mounts its own page at <http://127.0.0.1:3082/sts2> on
the qq loopback web server. It shows an A10, two-player reference book for the
current fight, or the most recently completed fight between rooms. It does not
show live HP or intents and never writes game input.

The browser polls `/sts2/state`, so a new `Creating NCombatRoom` log line
replaces the card without a reload. Identity comes only from `godot*.log` and
`current_run_mp.save`; paths are injectable for tests and alternate installs.
The default probes the Steam Flatpak data root used on this host, the native
XDG data root, and the alternate Megacrit Flatpak root.

Book data is local in `data/encounters.json` and targets Steam
`public-beta` **v0.111.0**: A8 single-player HP and A9 move, block, and buff
values are normalized from wiki.gg StS2 enemy article pages. The older
`Module:Enemies/StS2 data/*` snapshots are fallback only. Runtime makes no wiki
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
