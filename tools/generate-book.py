#!/usr/bin/env python3
"""Normalize checked-in wiki.gg Module:Enemies/StS2 data/* snapshots.

This is a development-time provenance tool. The plugin reads data/encounters.json
and never fetches the wiki at runtime.
"""
from pathlib import Path
import html, json, re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "Overgrowth": ROOT / "tools/.wiki/Overgrowth.lua",
    "Underdocks": ROOT / "tools/.wiki/Underdocks.lua",
    "Hive": ROOT / "tools/.wiki/Hive.lua",
    "Glory": ROOT / "tools/.wiki/Glory.lua",
    "Elites": ROOT / "tools/.wiki/Elites.lua",
    "Bosses": ROOT / "tools/.wiki/Bosses.lua",
}


def balanced(text, opening):
    depth, quote, escape, i = 0, None, False, opening
    while i < len(text):
        ch = text[i]
        if quote:
            if escape: escape = False
            elif ch == "\\": escape = True
            elif ch == quote: quote = None
        elif ch in "\"'": quote = ch
        elif text.startswith("--", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: return text[opening:i + 1]
        i += 1
    raise ValueError("unbalanced Lua table")


def field(block, key):
    match = re.search(rf"\b{re.escape(key)}\s*=\s*\"((?:\\.|[^\"])*)\"", block)
    return match.group(1) if match else None


def plain(raw):
    if not raw: return None
    text = raw.replace("\\\"", '"').replace("<br>", "; ").replace("<br/>", "; ")
    template = re.compile(r"\{\{([^{}]+)\}\}")
    for _ in range(8):
        def sub(match):
            parts = match.group(1).split("|")
            kind, args = parts[0], parts[1:]
            if not args: return kind
            if kind == "Asc2": return args[-1]
            if kind in {"BD2", "KW2", "M", "C2", "2"}:
                candidates = [value for value in args if value and not value.isdigit() and "<" not in value]
                return candidates[1] if kind in {"M", "C2", "2"} and len(candidates) > 1 else candidates[0]
            return args[-1]
        updated = template.sub(sub, text)
        if updated == text: break
        text = updated
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip(" ;")


def parse_hp(raw):
    if not raw: return None
    values = [int(n) for n in re.findall(r"\d+", raw)]
    return values[:2] if len(values) > 1 else values[:1]


def ascended_markup(raw):
    """Collapse `base (Asc2 threshold value)` to its ascended magnitude."""
    if not raw: return raw
    return re.sub(r"\d+(?:-\d+)?\s*\(\s*(\{\{Asc2\|[^{}]+\}\})\s*\)", r"\1", raw)


def entries(path):
    text = path.read_text()
    result = {}
    for match in re.finditer(r'^\s*\["([^"]+)"\]\s*=\s*\{', text, re.M):
        name = match.group(1)
        block = balanced(text, text.find("{", match.start()))
        # Enemy entries all carry Type; this excludes any future keyed helpers.
        if not field(block, "Type"): continue
        intents = []
        intent_match = re.search(r"\bIntents\s*=\s*\{", block)
        if intent_match:
            intent_table = balanced(block, block.find("{", intent_match.start()))
            for move_match in re.finditer(r"\{\s*Name\s*=\s*\"([^\"]+)\"", intent_table):
                move = balanced(intent_table, move_match.start())
                source_text = field(move, "Text") or ""
                asc_match = re.search(r"\bAscText\s*=\s*\{", move)
                if asc_match:
                    asc = balanced(move, move.find("{", asc_match.start()))
                    strings = re.findall(r'\"((?:\\.|[^\"])*)\"', asc)
                    if strings: source_text = strings[-1]
                intents.append({"name": move_match.group(1), "textA9": plain(source_text)})
        body = {
            "displayName": name,
            "type": field(block, "Type"),
            "hpA8": parse_hp(field(block, "AscHP")),
            "startsWithA9": plain(ascended_markup(field(block, "StartsWith"))),
            "moves": intents,
            "partyNote": plain(field(block, "InPartyWith")),
        }
        result[name] = {key: value for key, value in body.items() if value not in (None, [], "")}
    return result


# body name, count, optional monster id. Count is the A10 two-player book lineup.
def L(name, count=1, monster=None, role=None): return {"body": name, "count": count, **({"monsterId": monster} if monster else {}), **({"role": role} if role else {})}

ENCOUNTERS = {}
def add(act, kind, ids):
    for encounter_id, lineup in ids.items():
        ENCOUNTERS[encounter_id] = {"act": act, "kind": kind, "lineup": lineup}

add("Overgrowth", "hallway", {
 "FUZZY_WURM_CRAWLER_WEAK":[L("Fuzzy Wurm Crawler")], "SLIMES_WEAK":[L("Twig Slime (M)"),L("Twig Slime (S)"),L("Leaf Slime (S)")],
 "SHRINKER_BEETLE_WEAK":[L("Shrinker Beetle")], "NIBBITS_WEAK":[L("Nibbit")], "NIBBITS_NORMAL":[L("Nibbit",2)],
 "FLYCONID_NORMAL":[L("Flyconid"),L("Leaf Slime (M)")], "MAWLER_NORMAL":[L("Mawler")], "VINE_SHAMBLER_NORMAL":[L("Vine Shambler")],
 "FOGMOG_NORMAL":[L("Fogmog"),L("Eye With Teeth", role="summoned")], "INKLETS_NORMAL":[L("Inklet",3)],
 "SLIMES_NORMAL":[L("Twig Slime (M)"),L("Leaf Slime (M)"),L("Twig Slime (S)"),L("Leaf Slime (S)")],
 "SLITHERING_STRANGLER_NORMAL":[L("Slithering Strangler"),L("Leaf Slime (S)",2)], "SNAPPING_JAXFRUIT_NORMAL":[L("Snapping Jaxfruit"),L("Flyconid")],
 "RUBY_RAIDERS_NORMAL":[L("Assassin Raider"),L("Axe Raider"),L("Crossbow Raider")], "CUBEX_CONSTRUCT_NORMAL":[L("Cubex Construct")],
 "OVERGROWTH_CRAWLERS":[L("Fuzzy Wurm Crawler"),L("Shrinker Beetle")],
})
add("Underdocks", "hallway", {
 "CORPSE_SLUGS_WEAK":[L("Corpse Slug",2)], "TOADPOLES_WEAK":[L("Toadpole",2)], "SLUDGE_SPINNER_WEAK":[L("Sludge Spinner")],
 "SEAPUNK_WEAK":[L("Seapunk")], "LIVING_FOG_NORMAL":[L("Living Fog"),L("Gas Bomb", role="summoned")], "CORPSE_SLUGS_NORMAL":[L("Corpse Slug",3)],
 "PUNCH_CONSTRUCT_NORMAL":[L("Punch Construct")], "FOSSIL_STALKER_NORMAL":[L("Fossil Stalker")], "TWO_TAILED_RATS_NORMAL":[L("Two-Tailed Rat",3)],
 "HAUNTED_SHIP_NORMAL":[L("Haunted Ship")], "GREMLIN_MERC_NORMAL":[L("Gremlin Merc"),L("Fat Gremlin", role="summoned on death"),L("Sneaky Gremlin", role="summoned on death")],
 "SEAPUNK_NORMAL":[L("Seapunk"),L("Calcified Cultist")], "CULTISTS_NORMAL":[L("Calcified Cultist"),L("Damp Cultist")], "SEWER_CLAM_NORMAL":[L("Sewer Clam")],
})
add("Hive", "hallway", {
 "TUNNELER_WEAK":[L("Tunneler")], "THIEVING_HOPPER_WEAK":[L("Thieving Hopper")], "BOWLBUGS_WEAK":[L("Bowlbug (Rock)"),L("Bowlbug (Egg)")],
 "EXOSKELETONS_WEAK":[L("Exoskeleton")], "MYTES_NORMAL":[L("Myte",2)], "BOWLBUGS_NORMAL":[L("Bowlbug (Rock)"),L("Bowlbug (Silk)"),L("Bowlbug (Nectar)")],
 "LOUSE_PROGENITOR_NORMAL":[L("Louse Progenitor")], "SPINY_TOAD_NORMAL":[L("Spiny Toad")], "THE_OBSCURA_NORMAL":[L("The Obscura"),L("Parafright", role="summoned")],
 "EXOSKELETONS_NORMAL":[L("Exoskeleton",2)], "OVICOPTER_NORMAL":[L("Ovicopter"),L("Tough Egg",3, role="summoned")], "SLUMBERING_BEETLE_NORMAL":[L("Slumbering Beetle"),L("Bowlbug (Rock)"),L("Bowlbug (Silk)")],
 "HUNTER_KILLER_NORMAL":[L("Hunter Killer")], "CHOMPERS_NORMAL":[L("Chomper",2)], "TUNNELER_NORMAL":[L("Tunneler")],
})
add("Glory", "hallway", {
 "DEVOTED_SCULPTOR_WEAK":[L("Devoted Sculptor")], "SCROLLS_OF_BITING_WEAK":[L("Scroll of Biting",3)],
 "TURRET_OPERATOR_WEAK":[L("Living Shield"),L("Turret Operator")], "OWL_MAGISTRATE_NORMAL":[L("Owl Magistrate")], "GLOBE_HEAD_NORMAL":[L("Globe Head")],
 "SLIMED_BERSERKER_NORMAL":[L("Slimed Berserker")], "CONSTRUCT_MENAGERIE_NORMAL":[L("Punch Construct"),L("Cubex Construct",2)],
 "THE_LOST_AND_FORGOTTEN_NORMAL":[L("The Lost"),L("The Forgotten")], "FROG_KNIGHT_NORMAL":[L("Frog Knight")],
 "FABRICATOR_NORMAL":[L("Fabricator"),L("Guardbot", role="summoned option"),L("Zapbot", role="summoned option")], "SCROLLS_OF_BITING_NORMAL":[L("Scroll of Biting",4)], "AXEBOTS_NORMAL":[L("Axebot",2)],
})
add("Overgrowth", "elite", {"BYGONE_EFFIGY_ELITE":[L("Bygone Effigy")], "BYRDONIS_ELITE":[L("Byrdonis")], "PHROG_PARASITE_ELITE":[L("Phrog Parasite"),L("Wriggler",4, role="summoned on death")]})
add("Underdocks", "elite", {"PHANTASMAL_GARDENERS_ELITE":[L("Phantasmal Gardener",4)], "SKULKING_COLONY_ELITE":[L("Skulking Colony")], "TERROR_EEL_ELITE":[L("Terror Eel")]})
add("Hive", "elite", {"DECIMILLIPEDE_ELITE":[L("Decimillipede",1,"DECIMILLIPEDE_FRONT"),L("Decimillipede",1,"DECIMILLIPEDE_MIDDLE"),L("Decimillipede",1,"DECIMILLIPEDE_BACK")], "ENTOMANCER_ELITE":[L("Entomancer")], "INFESTED_PRISMS_ELITE":[L("Infested Prism")]})
add("Glory", "elite", {"KNIGHTS_ELITE":[L("Flail Knight"),L("Spectral Knight"),L("Magi Knight")], "MECHA_KNIGHT_ELITE":[L("Mecha Knight")], "SOUL_NEXUS_ELITE":[L("Soul Nexus")]})
add("Overgrowth", "boss", {"CEREMONIAL_BEAST_BOSS":[L("Ceremonial Beast")], "THE_KIN_BOSS":[L("Kin Priest"),L("Kin Follower",2)], "VANTOM_BOSS":[L("Vantom")]})
add("Underdocks", "boss", {"LAGAVULIN_MATRIARCH_BOSS":[L("Lagavulin Matriarch")], "SOUL_FYSH_BOSS":[L("Soul Fysh")], "WATERFALL_GIANT_BOSS":[L("Waterfall Giant")]})
add("Hive", "boss", {"THE_INSATIABLE_BOSS":[L("The Insatiable")], "KNOWLEDGE_DEMON_BOSS":[L("Knowledge Demon")], "KAISER_CRAB_BOSS":[L("Crusher"),L("Rocket")]})
add("Glory", "boss", {"QUEEN_BOSS":[L("Queen"),L("Torch Head Amalgam")], "TEST_SUBJECT_BOSS":[L("Test Subject", role="phase 1"),L("Test Subject (Phase 2)", role="phase 2"),L("Test Subject (Phase 3)", role="phase 3")], "AEONGLASS_BOSS":[L("Aeonglass")]})

OVERRIDES = {
 "DECIMILLIPEDE_ELITE": {
  "name":"Decimillipede",
  "patterns":[
   {"type":"cycle","text":"Front: Bulk → Writhe → Outgas; after Reattach, resumes at a random move."},
   {"type":"cycle","text":"Middle: Writhe → Outgas → Bulk; after Reattach, resumes at a random move."},
   {"type":"cycle","text":"Back: Outgas → Bulk → Writhe; after Reattach, resumes at a random move."},
  ],
  "rules":["Each dead segment Revives with 25 HP after 2 turns if any other segment is alive; it then resumes randomly.", "Kill all remaining segments before a Reattach resolves."],
  "timing":["Poison resolves before enemy moves.", "Doom resolves after Reattach, so the revived segment can be targeted; Doom can miss."],
 },
 "PHANTASMAL_GARDENERS_ELITE":{"patterns":[{"type":"cycle","text":"Bite → Lash → Flail → Enlarge; all 4 Gardeners start at different offsets."}]},
 "TERROR_EEL_ELITE":{"patterns":[{"type":"opener","text":"Crash opener, then alternates Crash ↔ Thrash. At the Shriek threshold: Stun → Terror, then resume."}]},
 "ENTOMANCER_ELITE":{"patterns":[{"type":"cycle","text":"Beeeees! → Spear! → Pheromone Spit → repeat."}]},
 "INFESTED_PRISMS_ELITE":{"patterns":[{"type":"cycle","text":"Jab → Radiate → Whirlwind → Pulsate → repeat."}]},
 "MECHA_KNIGHT_ELITE":{"patterns":[{"type":"opener","text":"Charge once, then Flamethrower → Windup → Heavy Cleave → repeat."}]},
 "SOUL_NEXUS_ELITE":{"patterns":[{"type":"opener","text":"Soul Burn opener; then Soul Burn / Maelstrom / Drain Life equally at random, never the same move twice."}]},
 "TEST_SUBJECT_BOSS":{
  "patterns":[
   {"type":"cycle","text":"Phase 1 alternates Bite ↔ Skull Bash."},
   {"type":"cycle","text":"Phase 2 repeats Multi-Claw every turn, starting at 3 hits and adding 1 hit each use."},
   {"type":"cycle","text":"Phase 3: Lacerate → Big Pounce → Burning Growl → repeat."}
  ],
  "rules":["These 3 bodies are sequential phases, not simultaneous enemies: Adaptable revives Phase 1 as Phase 2, then Phase 2 as Phase 3.", "Each transition removes all status effects; the body cannot be targeted until it revives."],
  "timing":["On-kill and Fatal effects trigger on each phase transition."]
 },
 "PHROG_PARASITE_ELITE":{"rules":["On death, Infested summons 4 Wrigglers."]},
 "GREMLIN_MERC_NORMAL":{"rules":["On death, summons Fat Gremlin and Sneaky Gremlin minions."]},
 "LIVING_FOG_NORMAL":{"rules":["Summons Gas Bomb minions; their intent is Death Blow."]},
 "FOGMOG_NORMAL":{"rules":["Summons an Eye With Teeth mid-fight."]},
 "OVICOPTER_NORMAL":{"rules":["Summons 3 Tough Egg minions; eggs hatch into attackers."]},
 "THE_OBSCURA_NORMAL":{"rules":["Summons a Parafright minion."]},
 "FABRICATOR_NORMAL":{"rules":["Summons defensive and aggressive bot minions."]},
 "KNIGHTS_ELITE":{"rules":["While Magi Knight is alive, Dampen Downgrades all player cards."]},
 "QUEEN_BOSS":{"rules":["Torch Head Amalgam is a Minion and fights alongside Queen."]},
}

bodies = {}
for source in SOURCES.values(): bodies.update(entries(source))

for encounter_id, encounter in ENCOUNTERS.items():
    lineup = []
    for spec in encounter["lineup"]:
        body = bodies.get(spec["body"])
        if not body: raise SystemExit(f"unknown body {spec['body']} in {encounter_id}")
        default_id = re.sub(r"[^A-Z0-9]+", "_", spec["body"].upper()).strip("_")
        lineup.append({**body, "monsterId":spec.get("monsterId", default_id), "count":spec["count"], **({"role":spec["role"]} if spec.get("role") else {}),
            "pattern":{"type":"random-with-constraint", "text":"Uses the listed moves; exact opener and repeat constraints vary."}})
    encounter["name"] = encounter_id.removesuffix("_WEAK").removesuffix("_NORMAL").removesuffix("_ELITE").removesuffix("_BOSS").replace("_", " ").title()
    encounter["lineup"] = lineup
    encounter["rules"] = []
    encounter["timing"] = []
    for body in lineup:
        note = body.get("partyNote", "")
        if re.search(r"summon|death|minion|while .*alive", note, re.I): encounter["rules"].append(note)
        for move in body.get("moves", []):
            if re.search(r"summon|revive|death blow|while .*alive|then dies", move["textA9"], re.I): encounter["rules"].append(f"{body['displayName']} — {move['textA9']}")
    override = OVERRIDES.get(encounter_id, {})
    for key in ("name", "rules", "timing"):
        if key in override: encounter[key] = override[key]
    if "patterns" in override:
        for body, pattern in zip(lineup, override["patterns"]): body["pattern"] = pattern
    encounter["rules"] = list(dict.fromkeys(encounter["rules"]))

output = {
 "meta":{"source":"Slay the Spire Wiki (wiki.gg), StS2 enemy pages and Module:Enemies/StS2 data/*", "ascension":"A8 HP; A9 move/block/buff values", "players":2},
 "encounters": dict(sorted(ENCOUNTERS.items())),
}
(ROOT / "data/encounters.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {len(ENCOUNTERS)} encounters and {len(bodies)} enemy bodies")
