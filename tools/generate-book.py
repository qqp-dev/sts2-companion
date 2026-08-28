#!/usr/bin/env python3
'''Build the local encounter book from checked-in wiki.gg snapshots.

Authoritative StS2 enemy article wikitext is preferred per body. The older
Module:Enemies snapshots are retained only as structured fallback. This script
is deterministic and offline; tools/harvest-wiki.py is the development-only
network step.
'''
from copy import deepcopy
from pathlib import Path
import html
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "tools/.wiki"
MODULE_SOURCES = {
    "Overgrowth": WIKI_DIR / "Overgrowth.lua",
    "Underdocks": WIKI_DIR / "Underdocks.lua",
    "Hive": WIKI_DIR / "Hive.lua",
    "Glory": WIKI_DIR / "Glory.lua",
    "Elites": WIKI_DIR / "Elites.lua",
    "Bosses": WIKI_DIR / "Bosses.lua",
}
SNAPSHOT = json.loads((WIKI_DIR / "pages.json").read_text())
TARGET_ASCENSION = 9


def lua_balanced(text, opening):
    depth, quote, escape, index = 0, None, False, opening
    while index < len(text):
        character = text[index]
        if quote:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif text.startswith("--", index):
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[opening:index + 1]
        index += 1
    raise ValueError("unbalanced Lua table")


def lua_field(block, key):
    match = re.search(rf'\b{re.escape(key)}\s*=\s*"((?:\\.|[^"])*)"', block)
    return match.group(1) if match else None


def wiki_balanced(text, opening):
    depth, index = 0, opening
    while index < len(text) - 1:
        if text.startswith("{{", index):
            depth += 1
            index += 2
            continue
        if text.startswith("}}", index):
            depth -= 1
            index += 2
            if depth == 0:
                return text[opening:index]
            continue
        index += 1
    raise ValueError(f"unbalanced wiki template at offset {opening}")


def split_top_level(text, delimiter="|"):
    result, start, index = [], 0, 0
    curly = square = 0
    while index < len(text):
        if text.startswith("{{", index):
            curly += 1
            index += 2
            continue
        if text.startswith("}}", index):
            curly = max(0, curly - 1)
            index += 2
            continue
        if text.startswith("[[", index):
            square += 1
            index += 2
            continue
        if text.startswith("]]", index):
            square = max(0, square - 1)
            index += 2
            continue
        if text[index] == delimiter and curly == 0 and square == 0:
            result.append(text[start:index])
            start = index + 1
        index += 1
    result.append(text[start:])
    return result


def parse_template(template):
    parts = split_top_level(template[2:-2])
    name = parts[0].strip()
    positional, named = [], {}
    for part in parts[1:]:
        key_value = split_top_level(part, "=")
        if len(key_value) > 1:
            key = key_value[0].strip()
            named[key] = "=".join(key_value[1:]).strip()
        else:
            positional.append(part.strip())
    return name, positional, named


def iter_templates(text, template_name):
    expression = re.compile(r"\{\{\s*" + re.escape(template_name) + r"(?=[|}\s])", re.I)
    for match in expression.finditer(text):
        try:
            template = wiki_balanced(text, match.start())
        except ValueError:
            continue
        yield match.start(), match.start() + len(template), template


def asc_value(template):
    name, positional, _ = parse_template(template)
    if name.lower() == "asc2" and len(positional) >= 2:
        try:
            threshold = int(positional[0])
        except ValueError:
            return None
        return positional[-1] if threshold <= TARGET_ASCENSION else None
    # Some pages accidentally use the StS1 template. Its last argument is the
    # game selector, so the magnitude is the second value after threshold.
    if name.lower() == "asc" and len(positional) >= 2:
        try:
            threshold = int(positional[0])
        except ValueError:
            return None
        return positional[1] if threshold <= TARGET_ASCENSION else None
    return None


def select_ascension(raw):
    '''Select <=A9 markup while collapsing base/ascended alternatives.'''
    if not raw:
        return raw
    text = str(raw)
    marker_index = 0
    markers = {}
    while True:
        matches = list(iter_templates(text, "Asc2")) + list(iter_templates(text, "Asc"))
        if not matches:
            break
        opening, end, template = min(matches, key=lambda item: item[0])
        value = asc_value(template)
        replacement = "" if value is None else f"\x00ASC{marker_index}\x00"
        if value is not None:
            markers[marker_index] = value
            marker_index += 1
        text = text[:opening] + replacement + text[end:]
    marker = r"\x00ASC\d+\x00"
    text = re.sub(rf"\([^();]*;\s*({marker})\s*\)", r"\1", text)
    text = re.sub(rf"(?:\d+(?:[-x×/]\d+)*)\s*\(\s*({marker})\s*\)", r"\1", text)
    for index, value in markers.items():
        text = text.replace(f"\x00ASC{index}\x00", value)
    return text


def plain(raw):
    if not raw:
        return None
    text = select_ascension(str(raw))
    # A break inside a template display label is visual wrapping (for example
    # `Withering<br>Presence`); top-level breaks separate distinct powers.
    nested_break = re.compile(r"(\{\{[^{}]*)<br\s*/?>([^{}]*\}\})", re.I)
    while nested_break.search(text):
        text = nested_break.sub(r"\1 \2", text)
    text = re.sub(r"(?i)<br\s*/?>", "; ", text)
    text = re.sub(r"(?m)^\s*[#*]+\s*", " • ", text)
    innermost = re.compile(r"\{\{([^{}]*)\}\}")
    for _ in range(30):
        def replace(match):
            parts = split_top_level(match.group(1))
            kind = parts[0].strip()
            args = [part.strip() for part in parts[1:]]
            lower = kind.lower()
            if lower == "int":
                if len(args) > 2 and args[2]:
                    return args[2]
                return args[1] if len(args) > 1 else (args[0] if args else "")
            if lower in {"clear", "beta content", "enemy2nav", "patchnav",
                         "sequel disambiguation", "intents table/end",
                         "update history table/start", "update history table/end"}:
                return ""
            candidates = [arg for arg in args if arg and not re.fullmatch(r"\d+", arg)]
            if not candidates:
                # Navboxes and other arg-less chrome are not prose.
                return ""
            if lower in {"bd2", "kw2", "c2", "m", "m2", "e", "r2", "p2", "2"}:
                return candidates[-1]
            return candidates[-1]
        updated = innermost.sub(replace, text)
        if updated == text:
            break
        text = updated
    text = re.sub(r"(?i)\[\[Category:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text)
    text = re.sub(r"\s*•\s*", " • ", text)
    text = re.sub(r"\s+", " ", text).strip(" ;•")
    text = re.sub(r"\bDeals?\s+(\d+)\s+damage\s+(\d+)\s+times\b", r"Deals \1×\2 damage", text, flags=re.I)
    text = re.sub(r"\bDeals?\s+(\d+)\s+damage\s*[x×]\s*(\d+)\b", r"Deals \1×\2 damage", text, flags=re.I)
    text = re.sub(r"\bDeals?\s+(\d+)\s*[x×]\s*(\d+)\s+damage\b", r"Deals \1×\2 damage", text, flags=re.I)
    return text or None


def parse_hp(raw):
    if not raw:
        return None
    values = [int(number) for number in re.findall(r"\d+", plain(raw) or "")]
    return values[:2] if len(values) > 1 else values[:1]


def hp_from_fields(fields):
    if fields.get("AscHP"):
        return parse_hp(fields["AscHP"])
    raw = fields.get("HP")
    if not raw:
        return None
    ascended = []
    for _, _, template in list(iter_templates(raw, "Asc2")) + list(iter_templates(raw, "Asc")):
        value = asc_value(template)
        if value is not None:
            ascended = parse_hp(value)
    return ascended or parse_hp(raw)


def module_entries(path):
    text = path.read_text()
    result = {}
    for match in re.finditer(r'^\s*\["([^"]+)"\]\s*=\s*\{', text, re.M):
        name = match.group(1)
        block = lua_balanced(text, text.find("{", match.start()))
        if not lua_field(block, "Type"):
            continue
        intents = []
        intent_match = re.search(r"\bIntents\s*=\s*\{", block)
        if intent_match:
            intent_table = lua_balanced(block, block.find("{", intent_match.start()))
            for move_match in re.finditer(r'\{\s*Name\s*=\s*"([^"]+)"', intent_table):
                move = lua_balanced(intent_table, move_match.start())
                source_text = lua_field(move, "Text") or ""
                asc_match = re.search(r"\bAscText\s*=\s*\{", move)
                if asc_match:
                    asc = lua_balanced(move, move.find("{", asc_match.start()))
                    strings = re.findall(r'"((?:\\.|[^"])*)"', asc)
                    if strings:
                        source_text = strings[-1]
                intents.append({"name": move_match.group(1), "textA9": plain(source_text)})
        link = lua_field(block, "Link") or name
        title, _, section = link.partition("#")
        body = {
            "displayName": name,
            "type": lua_field(block, "Type"),
            "hpA8": parse_hp(lua_field(block, "AscHP") or lua_field(block, "BaseHP")),
            "startsWithA9": plain(lua_field(block, "StartsWith")),
            "moves": intents,
            "partyNote": plain(lua_field(block, "InPartyWith")),
            "articleTitle": title.replace("_", " "),
            "articleSection": section or name,
        }
        result[name] = {key: value for key, value in body.items() if value not in (None, [], "")}
    return result


def parse_pattern(raw):
    text = plain(raw)
    if not text:
        return {"type": "unknown", "text": "Pattern prose is missing from the wiki.gg article snapshot."}
    lower = text.lower()
    first_sentence = re.split(r"(?<=[.!?])\s+", lower, maxsplit=1)[0]
    cycle_words = r"\bcycle|\bcycles|\bcyclic|\balternates?|\brepeats?|\bfixed (?:order|pattern|sequence)|every turn|follows (?:a |this |the )?(?:pattern|sequence)"
    opener_words = r"\b(?:opens?|starts with|begins with)\b|\bfirst turn\b|\buses? .+ first\b"
    if re.search(r"\brandom|cannot (?:use|repeat)|never (?:uses?|repeats?)", lower):
        kind = "random-with-constraint"
    elif re.search(opener_words, first_sentence) and not re.search(cycle_words, first_sentence):
        kind = "opener"
    elif re.search(cycle_words, lower):
        kind = "cycle"
    elif re.search(opener_words, lower):
        kind = "opener"
    else:
        kind = "unknown"
    return {"type": kind, "text": text}


def remove_templates(text, names):
    result = text
    for name in names:
        while True:
            found = list(iter_templates(result, name))
            if not found:
                break
            opening, end, _ = found[-1]
            result = result[:opening] + result[end:]
    return result


# A pattern can end at an article heading or in the middle of tabber markup.
# Stop before structural templates/tags reach plain(), which would otherwise
# turn phase labels and infobox fields into apparent pattern prose.
PATTERN_STOP = re.compile(
    r"(?im)(?:^\s*={2,5}[^=].*?={2,5}\s*$"
    r"|<tabber\b|</tabber\s*>|^\s*\|-\|"
    r"|\{\{\s*[^{}\n|]*\bInfobox\b"
    r"|^\s*\{\{\s*(?:Clear|Enemy2Nav|PatchNav|Sequel Disambiguation|Beta content)\b"
    r"|^\s*\[\[Category:)"
)


def pattern_slice(text, start):
    rest = text[start:]
    stop = PATTERN_STOP.search(rest)
    prose = rest[:stop.start()] if stop else rest
    prose = remove_templates(prose, [
        "Clear", "Enemy2Nav", "PatchNav", "Sequel Disambiguation",
        "Beta content", "Intents Table/end",
        "Update History Table/start", "Update History Table/end", "Update History Table/row",
    ])
    prose = re.sub(r"(?i)\[\[(?:Category|File|Image):[^\]]*\]\]", "", prose)
    return prose


def extract_page_notes(text):
    text = re.split(r"(?mi)^\s*==\s*Update History\s*==\s*$", text, maxsplit=1)[0]
    text = remove_templates(text, ["Enemy Infobox", "#invoke:Infobox", "Intents Table/row", "Intents Table/start", "Intents Table/end"])
    rules, timing = [], []
    allowed = True
    for raw_line in text.splitlines():
        heading = re.match(r"^\s*={2,5}\s*(.*?)\s*={2,5}\s*$", raw_line)
        if heading:
            title = plain(heading.group(1)) or ""
            allowed = bool(re.search(r"Pattern|Notes|Interaction|Trivia|In Party|^[^ ]+$", title, re.I))
            continue
        if not allowed or not raw_line.strip() or raw_line.lstrip().startswith("{{"):
            continue
        line = plain(raw_line)
        if not line or len(line) < 12:
            continue
        rule_words = re.search(r"\b(?:death|dies?|dying|killed|kill|revive|reattach|respawn|stock|minion|summon|hatch|death blow|fatal|invulnerable|while .{0,60} alive|flee|escapes?)\b", line, re.I)
        timing_words = re.search(r"\b(?:before|after|next turn|following turn|during (?:the )?enemy turn|immediately|resolves?|triggers?|transition)\b", line, re.I)
        if rule_words:
            rules.append(line)
        if timing_words and (rule_words or re.search(r"\b(?:Poison|Doom|turn to the player|fades instantly)\b", line, re.I)):
            timing.append(line)
    return list(dict.fromkeys(rules)), list(dict.fromkeys(timing))


def article_records(page):
    text = page["wikitext"]
    records = {}
    for opening, _, template in iter_templates(text, "Enemy Infobox"):
        _, _, fields = parse_template(template)
        name = plain(fields.get("Name"))
        if not name:
            continue
        records.setdefault(name, {}).update({
            "displayName": name,
            "type": plain(fields.get("Type")),
            "hpA8": hp_from_fields(fields),
            "startsWithA9": plain(fields.get("Powers")),
            "_position": opening,
        })
    for opening, _, template in iter_templates(text, "#invoke:Infobox"):
        _, positional, fields = parse_template(template)
        if not positional or positional[0].lower() != "main":
            continue
        name = plain(fields.get("title"))
        if not name:
            continue
        records.setdefault(name, {}).update({
            "displayName": name,
            "hpA8": hp_from_fields(fields),
            "startsWithA9": plain(fields.get("Powers")),
            "_position": opening,
        })
    for opening, start_end, template in iter_templates(text, "Intents Table/start"):
        _, positional, _ = parse_template(template)
        if not positional:
            continue
        name = plain(positional[0])
        end_match = re.search(r"\{\{\s*Intents Table/end\s*\}\}", text[start_end:], re.I)
        if not end_match:
            continue
        table_end = start_end + end_match.end()
        table = text[start_end:start_end + end_match.start()]
        moves = []
        for _, _, row in iter_templates(table, "Intents Table/row"):
            _, _, fields = parse_template(row)
            move_name = plain(fields.get("Name"))
            effect = plain(fields.get("Effect"))
            if move_name and effect:
                move = {"name": move_name, "textA9": effect}
                if re.search(r"Death\s*Blow", fields.get("Intent", ""), re.I):
                    move["intent"] = "Death Blow"
                moves.append(move)
        record = records.setdefault(name, {"displayName": name, "_position": opening})
        if moves:
            record["moves"] = moves
        record["pattern"] = parse_pattern(pattern_slice(text, table_end))
    for opening, template_end, template in iter_templates(text, "Intents"):
        _, positional, _ = parse_template(template)
        if not positional:
            continue
        name = plain(positional[0])
        if name in records and records[name].get("pattern"):
            continue
        record = records.setdefault(name, {"displayName": name, "_position": opening})
        record["pattern"] = parse_pattern(pattern_slice(text, template_end))
    page_rules, page_timing = extract_page_notes(text)
    for record in records.values():
        record["rules"] = page_rules
        record["timing"] = page_timing
        record["sourcePage"] = page["url"]
        for key in [key for key, value in record.items() if value in (None, [], "")]:
            del record[key]
    return records


MODULE_BODIES = {}
for module_path in MODULE_SOURCES.values():
    MODULE_BODIES.update(module_entries(module_path))

ARTICLE_BODIES = {}
ARTICLE_PAGES = {}
for title, page in SNAPSHOT["pages"].items():
    if title == SNAPSHOT["meta"]["patchPage"]:
        continue
    ARTICLE_PAGES[title] = page
    ARTICLE_BODIES.update(article_records(page))

PATCH_VALUES = {
    "Axebot": {
        "moves": {
            "Hammer Uppercut": "Deals 18 damage. Applies 2 Weak and 2 Frail.",
            "The One-Two": "Deals 11×2 damage.",
        },
        "rules": ["Stock respawns gain +10 Max HP cumulatively each time."],
    },
    "Mecha Knight": {"moves": {"Flamethrower": "Deals 12 damage. Adds 4 Burn to your hand."}},
    "Exoskeleton": {"hpA8": [26, 30]},
    "Globe Head": {"startsWithA9": "Galvanic 8"},
    "Louse Progenitor": {"moves": {"Curl and Grow": "Gains 18 Block. Gains 7 Strength."}},
    "Soul Fysh": {"moves": {"De-Gas": "Deals 18 damage."}},
    "Entomancer": {"hpA8": [165]},
}


# Fail closed if the checked-in patch snapshot is not the authoritative list
# these overrides were transcribed from. Article values may drift; patch wins.
patch_wikitext = SNAPSHOT["pages"][SNAPSHOT["meta"]["patchPage"]]["wikitext"]
patch_enemies = re.search(r"(?ms)^=== Enemies: ===\s*(.*?)(?=^=== )", patch_wikitext)
if not patch_enemies:
    raise RuntimeError("v0.111.0 patch snapshot has no Enemies section")
patch_names = {"Mecha Knight": "Mechaknight", **{name: name for name in PATCH_VALUES if name != "Mecha Knight"}}
missing_patch_targets = [name for name, label in patch_names.items() if not re.search(rf"\b{re.escape(label)}\b", patch_enemies.group(1), re.I)]
if missing_patch_targets:
    raise RuntimeError(f"v0.111.0 Enemies snapshot missing patch targets: {missing_patch_targets}")


def apply_patch_override(name, body):
    patch = PATCH_VALUES.get(name)
    if not patch:
        return body
    body["patchChecked"] = "v0.111.0 Enemies"
    conflicts = []
    if "hpA8" in patch:
        expected = patch["hpA8"]
        if body.get("hpA8") != expected:
            conflicts.append(f"hpA8 article={body.get('hpA8')} patch={expected}")
        body["hpA8"] = expected
    if "startsWithA9" in patch:
        expected = patch["startsWithA9"]
        if body.get("startsWithA9") != expected:
            conflicts.append(f"startsWithA9 article={body.get('startsWithA9')} patch={expected}")
        body["startsWithA9"] = expected
    moves = {move["name"]: move for move in body.get("moves", [])}
    for move_name, expected in patch.get("moves", {}).items():
        actual = moves.get(move_name, {}).get("textA9")
        if actual != expected:
            conflicts.append(f"{move_name} article={actual!r} patch={expected!r}")
        if move_name in moves:
            moves[move_name]["textA9"] = expected
        else:
            body.setdefault("moves", []).append({"name": move_name, "textA9": expected})
    body.setdefault("rules", []).extend(patch.get("rules", []))
    body["rules"] = list(dict.fromkeys(body.get("rules", [])))
    if conflicts:
        body["sourceFlags"] = [f"PATCH OVERRIDE: {conflict}" for conflict in conflicts]
    return body


def merged_body(name):
    fallback = MODULE_BODIES.get(name)
    if not fallback:
        raise KeyError(f"unknown module body {name}")
    page = ARTICLE_PAGES.get(fallback["articleTitle"])
    article = ARTICLE_BODIES.get(name)
    if article is None and page:
        candidates = article_records(page)
        article = candidates.get(fallback.get("articleSection")) or candidates.get(fallback["articleTitle"])
    merged = deepcopy({key: value for key, value in fallback.items() if key not in {"articleTitle", "articleSection", "partyNote"}})
    if article:
        for key in ("displayName", "type", "hpA8", "startsWithA9", "moves", "pattern", "sourcePage", "rules", "timing"):
            if key in article:
                merged[key] = deepcopy(article[key])
    # Alternate infoboxes occasionally render powers as `25 Reattach`; keep
    # the established power-first book notation used by runtime scaling.
    if re.match(r"^\d", merged.get("startsWithA9", "")) and fallback.get("startsWithA9"):
        merged["startsWithA9"] = fallback["startsWithA9"]
    if "pattern" not in merged:
        merged["pattern"] = {"type": "unknown", "text": "Pattern prose could not be parsed from the wiki.gg article snapshot."}
    if fallback.get("partyNote"):
        merged["partyNote"] = fallback["partyNote"]
    return apply_patch_override(name, merged)


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
add("Glory", "boss", {"QUEEN_BOSS":[L("Queen"),L("Torch Head Amalgam")], "TEST_SUBJECT_BOSS":[L("Test Subject", role="phase 1"),L("Test Subject (Phase 2)", role="phase 2"),L("Test Subject (Phase 3)", role="phase 3")], "AEONGLASS_BOSS":[L("Aeonglass")], "DOORMAKER_BOSS":[L("Doormaker")]})


ENCOUNTER_NOTES = {
    "DECIMILLIPEDE_ELITE": {
        "rules": [
            "Each dead segment Revives with 25 HP if any other segment is alive; after Reattach it resumes at a random move.",
            "Reducing a segment to 0 HP is not a Fatal kill unless it is the final enemy.",
        ],
        "timing": ["Poison triggers before enemy moves.", "Doom triggers after segments regenerate via Reattach."],
    },
    "TEST_SUBJECT_BOSS": {
        "rules": [
            "The three listed bodies are sequential phases, not simultaneous enemies; Adaptable revives the next phase.",
            "Each transition removes all status effects and the body cannot be targeted until it revives.",
        ],
        "timing": ["On-kill and Fatal effects trigger on each phase transition."],
    },
    "DOORMAKER_BOSS": {
        "rules": ["Door spawns first; Doormaker transforms from it on the first turn (deprecated after v0.107.1)."],
    },
}

used_titles = sorted({MODULE_BODIES[spec["body"]]["articleTitle"] for encounter in ENCOUNTERS.values() for spec in encounter["lineup"]})

for encounter_id, encounter in ENCOUNTERS.items():
    lineup = []
    for spec in encounter["lineup"]:
        source_body = merged_body(spec["body"])
        default_id = re.sub(r"[^A-Z0-9]+", "_", spec["body"].upper()).strip("_")
        lineup.append({
            **source_body,
            "monsterId": spec.get("monsterId", default_id),
            "count": spec["count"],
            **({"role": spec["role"]} if spec.get("role") else {}),
        })
    encounter["name"] = encounter_id.removesuffix("_WEAK").removesuffix("_NORMAL").removesuffix("_ELITE").removesuffix("_BOSS").replace("_", " ").title()
    encounter["lineup"] = lineup
    rules, timing = [], []
    for body in lineup:
        rules.extend(body.pop("rules", []))
        timing.extend(body.pop("timing", []))
        note = body.pop("partyNote", "")
        if re.search(r"summon|death|minion|while .*alive", note, re.I):
            rules.append(note)
        for move in body.get("moves", []):
            if move.get("intent") == "Death Blow":
                rules.append(f"{body['displayName']} — Death Blow: {move['textA9']}")
            elif re.search(r"summon|revive|death blow|while .*alive|then dies|hatches", move["textA9"], re.I):
                rules.append(f"{body['displayName']} — {move['textA9']}")
    extra = ENCOUNTER_NOTES.get(encounter_id, {})
    rules.extend(extra.get("rules", []))
    timing.extend(extra.get("timing", []))
    encounter["rules"] = list(dict.fromkeys(rules))
    encounter["timing"] = list(dict.fromkeys(timing))

page_meta = []
for title in used_titles:
    page = ARTICLE_PAGES[title]
    page_meta.append({
        "title": page["title"], "url": page["url"],
        "revisionId": page["revisionId"], "revisionTimestamp": page["revisionTimestamp"],
    })
patch_page = SNAPSHOT["pages"][SNAPSHOT["meta"]["patchPage"]]
output = {
    "meta": {
        "source": "wiki.gg StS2 enemy/elite/boss article pages; Module:Enemies snapshots only as fallback",
        "wikiPages": page_meta,
        "patchPage": {
            "title": patch_page["title"], "url": patch_page["url"],
            "revisionId": patch_page["revisionId"], "revisionTimestamp": patch_page["revisionTimestamp"],
        },
        "harvestedAt": SNAPSHOT["meta"]["harvestedAt"],
        "targetVersion": "v0.111.0", "targetBranch": "public-beta",
        "ascension": "A8 HP; A9 move/block/buff values", "players": 2,
    },
    "encounters": dict(sorted(ENCOUNTERS.items())),
}
(ROOT / "data/encounters.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
unknown_patterns = sum(body["pattern"]["type"] == "unknown" for encounter in ENCOUNTERS.values() for body in encounter["lineup"])
missing_hp = sum(not body.get("hpA8") for encounter in ENCOUNTERS.values() for body in encounter["lineup"])
print(f"wrote {len(ENCOUNTERS)} encounters from {len(used_titles)} article pages ({unknown_patterns} unknown patterns, {missing_hp} missing HP bodies)")
