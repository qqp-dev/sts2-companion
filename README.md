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

Book data is local in `data/encounters.json`: A8 single-player HP and A9 move,
block, and buff values normalized from the wiki.gg `Module:Enemies/StS2 data/*`
modules. Runtime makes no wiki or other network requests. The checked-in
`tools/.wiki` snapshots and `tools/generate-book.py` document regeneration.
Event fights may be unknown; their raw encounter ID remains visible.

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
