"""Pure retained-wiki inventory parser and deterministic artifact builder.

The wiki snapshot is reconciliation input, never runtime or source authority.
This module captures structural claims and, when the reviewed P1b0/P1b1 policies name
an exact origin, materializes a typed final mapping. Wiki remains coverage and
reconciliation evidence, never source authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable

SCHEMA_VERSION = 2
TARGET_VERSION = "v0.111.0"
TARGET_BRANCH = "public-beta"
DEFAULT_ARTIFACT = "data/wiki-reconciliation-v0.111.0.json"
DEFAULT_POLICY = "tools/wiki-reconciliation-policy-v0.111.0.json"
DEFAULT_P1B1_POLICY = "tools/wiki-reconciliation-p1b1-policy-v0.111.0.json"
PRIMARY_SEMANTIC_SURFACE = "data/primary-semantic-surface-v0.111.0.json"
MODULE_STEMS = ("Bosses", "Elites", "Glory", "Hive", "Overgrowth", "Underdocks")

CATEGORY_NAMES = {
    "identity-placement-roster-lead": "Identity, placement, membership, roster, and lead context",
    "hp-ascension-scaling": "HP, Ascension, player-count, and scaling",
    "starting-power-status-stack": "Starting Powers, statuses, and stacks",
    "power-passive": "Power/passive identity and description",
    "move-name-intent-effect": "Move names, intents, and effects",
    "pattern-sequence": "Pattern and sequence clauses",
    "objective-note-patch-lifecycle": "Objective Notes and patch lifecycle",
    "tactic": "Useful Cards, Synergies, and Anti-Synergies",
    "non-guide": "Images, navigation, categories, history, Trivia, dialogue, and other patch scope",
}


class AuditError(ValueError):
    """A deterministic input, atomization, or integrity failure."""


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AuditError(f"cannot read required input {path}: {exc}") from exc
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AuditError(f"cannot read required JSON {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AuditError(f"malformed JSON {path}: {exc}") from exc


def wiki_balanced(text: str, opening: int) -> str:
    """Return one balanced ``{{...}}`` template beginning at *opening*."""
    if not text.startswith("{{", opening):
        raise AuditError(f"wiki template does not start at offset {opening}")
    depth, index = 0, opening
    while index < len(text) - 1:
        if text.startswith("<!--", index):
            end = text.find("-->", index + 4)
            if end < 0:
                raise AuditError(f"unclosed HTML comment at offset {index}")
            index = end + 3
            continue
        if text.startswith("{{", index):
            depth += 1
            index += 2
            continue
        if text.startswith("}}", index):
            depth -= 1
            index += 2
            if depth == 0:
                return text[opening:index]
            if depth < 0:
                break
            continue
        index += 1
    raise AuditError(f"unbalanced wiki template at offset {opening}")


def split_top_level(text: str, delimiter: str = "|") -> list[str]:
    """Split a template field without splitting nested templates or links."""
    if len(delimiter) != 1:
        raise AuditError("split_top_level delimiter must be one character")
    result: list[str] = []
    start = index = 0
    curly = square = 0
    while index < len(text):
        if text.startswith("<!--", index):
            end = text.find("-->", index + 4)
            if end < 0:
                raise AuditError(f"unclosed HTML comment at offset {index}")
            index = end + 3
            continue
        if text.startswith("{{", index):
            curly += 1
            index += 2
            continue
        if text.startswith("}}", index):
            if curly == 0:
                raise AuditError(f"unexpected template close at offset {index}")
            curly -= 1
            index += 2
            continue
        if text.startswith("[[", index):
            square += 1
            index += 2
            continue
        if text.startswith("]]", index):
            if square == 0:
                raise AuditError(f"unexpected link close at offset {index}")
            square -= 1
            index += 2
            continue
        if text[index] == delimiter and curly == 0 and square == 0:
            result.append(text[start:index])
            start = index + 1
        index += 1
    if curly or square:
        raise AuditError("unbalanced nested template or link while splitting field")
    result.append(text[start:])
    return result


@dataclass(frozen=True)
class ParsedTemplate:
    name: str
    positional: tuple[str, ...]
    named: dict[str, str]
    named_items: tuple[tuple[str, str, int], ...]


def parse_template(template: str) -> ParsedTemplate:
    if not template.startswith("{{") or not template.endswith("}}"):
        raise AuditError("template text must include balanced outer braces")
    parts = split_top_level(template[2:-2])
    name = parts[0].strip()
    if not name:
        raise AuditError("template name is empty")
    positional: list[str] = []
    named: dict[str, str] = {}
    named_items: list[tuple[str, str, int]] = []
    for argument_ordinal, part in enumerate(parts[1:], 1):
        key_value = split_top_level(part, "=")
        if len(key_value) > 1:
            key = key_value[0].strip()
            if not key:
                raise AuditError(f"empty named field in {name} argument {argument_ordinal}")
            value = "=".join(key_value[1:]).strip()
            named[key] = value
            named_items.append((key, value, argument_ordinal))
        else:
            positional.append(part.strip())
    return ParsedTemplate(name, tuple(positional), named, tuple(named_items))


def mask_comments(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))
    masked = re.sub(r"<!--[\s\S]*?-->", replace, text)
    if "<!--" in masked or "-->" in masked:
        raise AuditError("unbalanced HTML comment")
    return masked


def iter_templates(text: str, expected_name: str) -> Iterable[tuple[int, int, str, ParsedTemplate]]:
    """Yield exact-name templates outside comments, in source order."""
    masked = mask_comments(text)
    expression = re.compile(r"\{\{\s*" + re.escape(expected_name) + r"(?=[|}\s])", re.I)
    for match in expression.finditer(masked):
        template = wiki_balanced(text, match.start())
        parsed = parse_template(template)
        if parsed.name.casefold() != expected_name.casefold():
            continue
        yield match.start(), match.start() + len(template), template, parsed


def lua_balanced(text: str, opening: int) -> str:
    if opening >= len(text) or text[opening] != "{":
        raise AuditError(f"Lua table does not start at offset {opening}")
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
            if depth < 0:
                break
        index += 1
    raise AuditError(f"unbalanced Lua table at offset {opening}")


def lua_string_field(block: str, key: str) -> str | None:
    match = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*"((?:\\.|[^"])*)"', block)
    return match.group(1) if match else None


def plain(raw: str | None) -> str | None:
    """Deterministic display normalization aligned with generate-book.py."""
    if raw is None:
        return None
    text = str(raw).replace("\\\"", '"')
    previous = None
    innermost = re.compile(r"\{\{([^{}]*)\}\}")
    while "{{" in text and text != previous:
        previous = text
        def replace(match: re.Match[str]) -> str:
            parts = split_top_level(match.group(1))
            name = parts[0].strip()
            args = [part.strip() for part in parts[1:]]
            lower = name.lower()
            if lower in {"asc2", "asc"}:
                return args[-1] if len(args) > 1 else (args[0] if args else "")
            if lower in {"clear", "beta content", "enemy2nav", "patchnav",
                         "sequel disambiguation", "intents table/end",
                         "update history table/start", "update history table/end"}:
                return ""
            candidates = [arg for arg in args if arg and not re.fullmatch(r"\d+", arg)]
            if not candidates:
                return ""
            if lower in {"bd2", "kw2", "c2", "m", "m2", "e", "r2", "p2", "2", "sts2"}:
                return candidates[-1]
            return candidates[-1]
        text = innermost.sub(replace, text)
    text = re.sub(r"(?i)\[\[Category:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text)
    text = re.sub(r"\s*•\s*", " • ", text)
    text = re.sub(r"\s+", " ", text).strip(" ;•")
    text = re.sub(r"(?<=\d)[xX](?=\d)", "×", text)
    return text or None


@dataclass(frozen=True)
class Section:
    title: str
    level: int
    heading_ordinal: int
    start: int
    body_start: int
    end: int
    direct_end: int
    path: tuple[tuple[str, int], ...]


def parse_sections(text: str) -> list[Section]:
    matches = list(re.finditer(r"(?m)^\s*(={2,5})\s*([^=].*?)\s*\1\s*$", mask_comments(text)))
    sections: list[Section] = []
    stack: list[tuple[str, int, int]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = plain(match.group(2)) or match.group(2).strip()
        while stack and stack[-1][2] >= level:
            stack.pop()
        stack.append((title, index + 1, level))
        end = next((candidate.start() for candidate in matches[index + 1:]
                    if len(candidate.group(1)) <= level), len(text))
        direct_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append(Section(
            title=title,
            level=level,
            heading_ordinal=index + 1,
            start=match.start(),
            body_start=match.end(),
            end=end,
            direct_end=direct_end,
            path=tuple((item[0], item[1]) for item in stack),
        ))
    return sections


def section_path_at(sections: list[Section], offset: int) -> list[dict[str, Any]]:
    candidates = [section for section in sections if section.start <= offset < section.end]
    if not candidates:
        return []
    section = max(candidates, key=lambda item: item.level)
    return [{"title": title, "headingOrdinal": ordinal} for title, ordinal in section.path]


def semantic_sentences(raw: str) -> list[str]:
    """Split objective effect/lead prose, preserving balanced nested markup."""
    result: list[str] = []
    for line in raw.splitlines():
        line = re.sub(r"^\s*[#*:;]+\s*", "", line).strip()
        if not line:
            continue
        chunks = re.split(r"(?<=[.!?])\s+(?=(?:\{\{|\[\[|[A-Z0-9'\"]|''))", line)
        result.extend(chunk for chunk in chunks if plain(chunk))
    return result


def pattern_clauses(raw: str) -> list[str]:
    """Normalize Pattern lines/lists and reviewed independent follow-on clauses.

    Continuation sentences beginning with The/It/They/One/Every stay attached to
    the structural line. This is a capture grammar, not semantic reconciliation.
    """
    result: list[str] = []
    boundary = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
    continuation = re.compile(r"^(?:The|It|They|One|Every)\b")
    for source_line in raw.splitlines():
        line = re.sub(r"^\s*[#*:;]+\s*", "", source_line).strip()
        if not line:
            continue
        chunks = boundary.split(line)
        merged: list[str] = []
        for chunk in chunks:
            if merged and continuation.match(chunk):
                merged[-1] += " " + chunk
            else:
                merged.append(chunk)
        result.extend(chunk for chunk in merged if plain(chunk))
    return result


PATTERN_STOP = re.compile(
    r"(?im)(?:^\s*={2,5}[^=].*?={2,5}\s*$"
    r"|<tabber\b|</tabber\s*>|^\s*\|-\|"
    r"|\{\{\s*[^{}\n|]*\bInfobox\b"
    r"|^\s*\{\{\s*(?:Clear|Enemy2Nav|PatchNav|Sequel Disambiguation|Beta content)\b"
    r"|^\s*\[\[Category:)"
)


def remove_template_spans(text: str, names: Iterable[str]) -> str:
    spans: list[tuple[int, int]] = []
    for name in names:
        spans.extend((start, end) for start, end, _, _ in iter_templates(text, name))
    result = text
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + "".join("\n" if char == "\n" else " " for char in result[start:end]) + result[end:]
    return result


def pattern_slice(text: str, start: int) -> str:
    rest = text[start:]
    stop = PATTERN_STOP.search(rest)
    prose = rest[:stop.start()] if stop else rest
    prose = remove_template_spans(prose, (
        "Clear", "Enemy2Nav", "PatchNav", "Sequel Disambiguation", "Beta content",
        "Intents Table/end", "Update History Table/start", "Update History Table/end",
        "Update History Table/row",
    ))
    prose = re.sub(r"(?i)\[\[(?:Category|File|Image):[^\]]*\]\]", "", prose)
    return prose


def split_power_claims(raw: str) -> list[str]:
    """Split top-level starting-Power assignments without raw nested delimiters."""
    lines: list[str] = []
    start = index = curly = square = 0
    while index < len(raw):
        if raw.startswith("{{", index):
            curly += 1
            index += 2
            continue
        if raw.startswith("}}", index):
            curly -= 1
            if curly < 0:
                raise AuditError("unexpected template close in starting-Power field")
            index += 2
            continue
        if raw.startswith("[[", index):
            square += 1
            index += 2
            continue
        if raw.startswith("]]", index):
            square -= 1
            if square < 0:
                raise AuditError("unexpected link close in starting-Power field")
            index += 2
            continue
        if curly == 0 and square == 0:
            match = re.match(r"(?i)<br\s*/?>", raw[index:])
            if match:
                lines.append(raw[start:index])
                index += len(match.group(0))
                start = index
                continue
            if raw[index] == ",":
                lines.append(raw[start:index])
                index += 1
                start = index
                continue
        index += 1
    if curly or square:
        raise AuditError("unbalanced starting-Power field")
    lines.append(raw[start:])
    delimited = [line.strip() for line in lines if plain(line)]
    result: list[str] = []
    for line in delimited:
        powers = list(iter_templates(line, "BD2"))
        if len(powers) <= 1:
            result.append(line)
            continue
        # A retained field may place named Powers side by side without a comma
        # (Tough Egg: Minion + Hatch 2). Preserve any prefix on the first Power
        # and any amount/Ascension suffix on the final Power.
        for power_index, (power_start, power_end, _, _) in enumerate(powers):
            piece_start = 0 if power_index == 0 else power_start
            piece_end = powers[power_index + 1][0] if power_index + 1 < len(powers) else len(line)
            piece = line[piece_start:piece_end].strip()
            if piece:
                result.append(piece)
    return result


def normalized_starting_power(raw: str, *, kind: str, owner: str, parent_field: str | None = None) -> dict[str, Any]:
    value = plain(raw)
    result: dict[str, Any] = {"kind": kind, "owner": owner, "value": value}
    if parent_field is not None:
        result["parentField"] = parent_field
    calls = list(iter_templates(raw, "BD2"))
    if len(calls) != 1:
        result["parseStatus"] = "unparsed-power-identity"
        return result
    parsed = calls[0][3]
    if not parsed.positional or not plain(parsed.positional[0]):
        result["parseStatus"] = "unparsed-power-identity"
        return result
    result["power"] = plain(parsed.positional[0])
    without_power = raw[:calls[0][0]] + " " + raw[calls[0][1]:]
    ascensions: list[dict[str, int]] = []
    for template_name in ("Asc2", "Asc"):
        for start, end, _, asc in iter_templates(without_power, template_name):
            if len(asc.positional) < 2:
                continue
            try:
                threshold = int(asc.positional[0].strip())
                selected_index = -1 if template_name == "Asc2" else 1
                amount = int(asc.positional[selected_index].strip())
            except (ValueError, IndexError):
                continue
            ascensions.append({"threshold": threshold, "amount": amount})
        without_power = remove_template_spans(without_power, [template_name])
    base_match = re.search(r"-?\d+", without_power)
    if base_match:
        result["baseAmount"] = int(base_match.group(0))
    if ascensions:
        ascensions.sort(key=lambda row: row["threshold"])
        result["ascensionAmounts"] = ascensions
    selected = result.get("baseAmount")
    for row in ascensions:
        if row["threshold"] <= 9:
            selected = row["amount"]
    if selected is not None:
        result["amountAtA9"] = selected
    result["parseStatus"] = "typed"
    return result


def _excerpt(raw: str) -> str:
    return raw.strip()


class AtomCollector:
    def __init__(self, policy: dict[str, Any]):
        self.policy = policy
        self.records: list[dict[str, Any]] = []
        self._ids: set[str] = set()
        self.policy_by_id = {item["id"]: item for item in policy["exclusionPolicies"]}

    def add(
        self,
        *,
        category: str,
        family: str,
        origin: dict[str, Any],
        excerpt: str,
        normalized: dict[str, Any],
        membership: str = "current",
        exclusion_policy_id: str | None = None,
    ) -> dict[str, Any]:
        if category not in CATEGORY_NAMES:
            raise AuditError(f"unknown category {category}")
        coordinate = {
            "schema": "retained-wiki-origin-coordinate-v1",
            "category": category,
            "family": family,
            "origin": origin,
        }
        origin_id = "wiki-origin-v1-" + sha256_bytes(canonical_json_bytes(coordinate))
        if origin_id in self._ids:
            raise AuditError(f"origin ID collision at {origin}")
        self._ids.add(origin_id)
        exact_excerpt = _excerpt(excerpt)
        if not exact_excerpt:
            raise AuditError(f"empty excerpt at {origin}")
        claim_material = {"originId": origin_id, "excerpt": exact_excerpt, "normalized": normalized}
        claim_id = "wiki-claim-v1-" + sha256_bytes(canonical_json_bytes(claim_material))
        record: dict[str, Any] = {
            "id": origin_id,
            "claimId": claim_id,
            "category": category,
            "categoryLabel": CATEGORY_NAMES[category],
            "family": family,
            "origin": origin,
            "excerpt": exact_excerpt,
            "normalized": normalized,
            "membership": membership,
        }
        if exclusion_policy_id:
            policy = self.policy_by_id.get(exclusion_policy_id)
            if not policy:
                raise AuditError(f"unknown exclusion policy {exclusion_policy_id}")
            record.update({
                "reviewState": "policy-reviewed-exclusion",
                "disposition": "intentionally-excluded",
                "exclusionPolicyId": exclusion_policy_id,
            })
            self._validate_policy_match(record, policy)
        else:
            record["reviewState"] = "captured-unreconciled"
        self.records.append(record)
        return record

    @staticmethod
    def _validate_policy_match(record: dict[str, Any], policy: dict[str, Any]) -> None:
        match = policy.get("match", {})
        if record["family"] not in match.get("families", []):
            raise AuditError(f"policy {policy['id']} does not match family {record['family']}")
        page_keys = match.get("pageKeys")
        if page_keys and record["origin"].get("pageKey") not in page_keys:
            raise AuditError(f"policy {policy['id']} does not match page {record['origin'].get('pageKey')}")
        if not policy.get("rationale") or len(policy["rationale"].strip()) < 20:
            raise AuditError(f"exclusion policy {policy['id']} lacks concrete rationale")

    def sorted_records(self) -> list[dict[str, Any]]:
        return sorted(self.records, key=lambda item: item["id"])


def _page_origin(
    page_key: str,
    page: dict[str, Any],
    sections: list[Section],
    offset: int,
    **coordinate: Any,
) -> dict[str, Any]:
    return {
        "kind": "page",
        "path": "tools/.wiki/pages.json",
        "pageKey": page_key,
        "pageId": page["pageId"],
        "revisionId": page["revisionId"],
        "sectionPath": section_path_at(sections, offset),
        **coordinate,
    }


def _field_ordinal(parsed: ParsedTemplate, key: str) -> int:
    for field, _, ordinal in parsed.named_items:
        if field == key:
            return ordinal
    raise AuditError(f"field {key} is absent from {parsed.name}")


def _membership(owner: str | None) -> str:
    return "deprecated" if owner == "Doormaker" else "current"


def _template_owner(parsed: ParsedTemplate) -> str | None:
    return plain(parsed.named.get("Name") or parsed.named.get("title"))


def _mask_spans(text: str, spans: Iterable[tuple[int, int]]) -> str:
    result = text
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + "".join("\n" if c == "\n" else " " for c in result[start:end]) + result[end:]
    return result


def _add_article_atoms(
    collector: AtomCollector,
    page_key: str,
    page: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    required = {"title", "url", "pageId", "revisionId", "revisionTimestamp", "wikitext"}
    if not required.issubset(page):
        raise AuditError(f"page {page_key} lacks required metadata: {sorted(required - set(page))}")
    text = page["wikitext"]
    if not isinstance(text, str):
        raise AuditError(f"page {page_key} wikitext is not a string")
    sections = parse_sections(text)

    enemy_templates = list(iter_templates(text, "Enemy Infobox"))
    invoke_templates = list(iter_templates(text, "#invoke:Infobox"))
    power_templates = list(iter_templates(text, "Power Infobox"))
    identity_templates: list[tuple[int, int, str, ParsedTemplate, int, str]] = []

    for ordinal, (start, end, raw, parsed) in enumerate(enemy_templates, 1):
        owner = _template_owner(parsed)
        if not owner:
            raise AuditError(f"{page_key} Enemy Infobox {ordinal} lacks Name")
        identity_templates.append((start, end, raw, parsed, ordinal, owner))
        metrics["articleIdentityRecords"] += 1
        for key in ("Name", "Type", "Debut", "EncounterAliases"):
            value = parsed.named.get(key)
            if value is None:
                continue
            collector.add(
                category="identity-placement-roster-lead",
                family="article-identity-field",
                origin=_page_origin(page_key, page, sections, start,
                    template="Enemy Infobox", templateOrdinal=ordinal,
                    field=key, fieldOrdinal=_field_ordinal(parsed, key)),
                excerpt=value,
                normalized={"kind": "infobox-field", "owner": owner, "field": key, "value": plain(value)},
                membership=_membership(owner),
            )
        for key in ("HP", "AscHP"):
            value = parsed.named.get(key)
            if value is None:
                continue
            collector.add(
                category="hp-ascension-scaling",
                family="article-hp-field",
                origin=_page_origin(page_key, page, sections, start,
                    template="Enemy Infobox", templateOrdinal=ordinal,
                    field=key, fieldOrdinal=_field_ordinal(parsed, key)),
                excerpt=value,
                normalized={"kind": "hp-field", "owner": owner, "field": key, "value": plain(value)},
                membership=_membership(owner),
            )
        powers = parsed.named.get("Powers")
        if powers is not None:
            for claim_ordinal, claim in enumerate(split_power_claims(powers), 1):
                collector.add(
                    category="starting-power-status-stack",
                    family="article-starting-power",
                    origin=_page_origin(page_key, page, sections, start,
                        template="Enemy Infobox", templateOrdinal=ordinal,
                        field="Powers", fieldOrdinal=_field_ordinal(parsed, "Powers"),
                        claimOrdinal=claim_ordinal),
                    excerpt=claim,
                    normalized=(normalized_starting_power(claim, kind="starting-power", owner=owner)
                                if _membership(owner) == "current"
                                else {"kind": "starting-power", "owner": owner, "value": plain(claim)}),
                    membership=_membership(owner),
                )
        for key in ("Image", "Icon"):
            value = parsed.named.get(key)
            if value is not None:
                collector.add(
                    category="non-guide", family="visual-unit",
                    origin=_page_origin(page_key, page, sections, start,
                        template="Enemy Infobox", templateOrdinal=ordinal,
                        field=key, fieldOrdinal=_field_ordinal(parsed, key)),
                    excerpt=value,
                    normalized={"kind": "infobox-visual-field", "owner": owner, "field": key, "value": value},
                    membership=_membership(owner), exclusion_policy_id="exclude-visual-units-v1",
                )

    valid_invoke_ordinal = 0
    for source_ordinal, (start, end, raw, parsed) in enumerate(invoke_templates, 1):
        if not parsed.positional or parsed.positional[0].casefold() != "main":
            continue
        owner = _template_owner(parsed)
        if not owner:
            raise AuditError(f"{page_key} #invoke:Infobox {source_ordinal} lacks title")
        valid_invoke_ordinal += 1
        identity_templates.append((start, end, raw, parsed, source_ordinal, owner))
        metrics["articleIdentityRecords"] += 1
        for key in ("title", "Debut"):
            value = parsed.named.get(key)
            if value is None:
                continue
            collector.add(
                category="identity-placement-roster-lead", family="article-identity-field",
                origin=_page_origin(page_key, page, sections, start,
                    template="#invoke:Infobox", templateOrdinal=source_ordinal,
                    field=key, fieldOrdinal=_field_ordinal(parsed, key)),
                excerpt=value,
                normalized={"kind": "invoke-infobox-field", "owner": owner, "field": key, "value": plain(value)},
                membership=_membership(owner),
            )
        hp = parsed.named.get("HP")
        if hp is not None:
            collector.add(
                category="hp-ascension-scaling", family="article-hp-field",
                origin=_page_origin(page_key, page, sections, start,
                    template="#invoke:Infobox", templateOrdinal=source_ordinal,
                    field="HP", fieldOrdinal=_field_ordinal(parsed, "HP")),
                excerpt=hp,
                normalized={"kind": "hp-field", "owner": owner, "field": "HP", "value": plain(hp)},
                membership=_membership(owner),
            )
        for key, value, field_ordinal in parsed.named_items:
            if key != "Powers" and not key.endswith("_Powers"):
                continue
            power_claims = split_power_claims(value)
            if not power_claims:
                power_claims = [f"{key}="]
            for claim_ordinal, claim in enumerate(power_claims, 1):
                collector.add(
                    category="starting-power-status-stack", family="article-starting-power",
                    origin=_page_origin(page_key, page, sections, start,
                        template="#invoke:Infobox", templateOrdinal=source_ordinal,
                        field=key, fieldOrdinal=field_ordinal, claimOrdinal=claim_ordinal),
                    excerpt=claim,
                    normalized=({**normalized_starting_power(claim, kind="starting-power", owner=owner), "stateField": key}
                                if _membership(owner) == "current"
                                else {"kind": "starting-power", "owner": owner, "stateField": key, "value": plain(claim)}),
                    membership=_membership(owner),
                )
        images = parsed.named.get("images")
        if images is not None:
            collector.add(
                category="non-guide", family="visual-unit",
                origin=_page_origin(page_key, page, sections, start,
                    template="#invoke:Infobox", templateOrdinal=source_ordinal,
                    field="images", fieldOrdinal=_field_ordinal(parsed, "images")),
                excerpt=images,
                normalized={"kind": "infobox-visual-field", "owner": owner, "field": "images", "value": images},
                membership=_membership(owner), exclusion_policy_id="exclude-visual-units-v1",
            )

    # Lead prose is before the first article body heading. Top-level data/chrome
    # templates are removed, while inline semantic templates remain in prose.
    first_heading = min((section.start for section in sections), default=len(text))
    lead_source = text[:first_heading]
    lead_source = remove_template_spans(lead_source, (
        "Enemy Infobox", "#invoke:Infobox", "Power Infobox", "Small Card Infobox",
        "Keyword Infobox", "Beta content", "Deprecated Content", "TOC limit",
        "Sequel Disambiguation", "Clear",
    ))
    lead_source = mask_comments(lead_source)
    lead_claims = semantic_sentences(lead_source)
    for sentence_ordinal, claim in enumerate(lead_claims, 1):
        collector.add(
            category="identity-placement-roster-lead", family="article-lead",
            origin=_page_origin(page_key, page, sections, 0, sentenceOrdinal=sentence_ordinal),
            excerpt=claim,
            normalized={"kind": "lead-claim", "value": plain(claim)},
            membership=_membership(page_key),
        )
    # The retained deprecation banner is one explicit lead-context claim and is
    # also the structural current-membership signal for Doormaker.
    for ordinal, (start, _, raw, parsed) in enumerate(iter_templates(text, "Deprecated Content"), 1):
        collector.add(
            category="identity-placement-roster-lead", family="article-lead",
            origin=_page_origin(page_key, page, sections, start,
                template="Deprecated Content", templateOrdinal=ordinal, claimOrdinal=1),
            excerpt=raw,
            normalized={"kind": "deprecation-context", "value": plain(parsed.named.get("Message") or raw)},
            membership="deprecated",
        )

    # Power invocations are captured, but shorthand template bodies are not in
    # this snapshot and are never expanded or semantically classified here.
    for ordinal, (start, _, raw, parsed) in enumerate(power_templates, 1):
        identity = parsed.named.get("Name") or (parsed.positional[0] if parsed.positional else None)
        if not identity:
            raise AuditError(f"{page_key} Power Infobox {ordinal} lacks identity")
        owner = page_key
        inline_fields = [key for key in ("Stacks", "Type", "Description") if key in parsed.named]
        collector.add(
            category="power-passive", family="article-power-invocation",
            origin=_page_origin(page_key, page, sections, start,
                template="Power Infobox", templateOrdinal=ordinal, claimOrdinal=1),
            excerpt=identity,
            normalized={
                "kind": "power-infobox-invocation", "ownerPage": owner,
                "identity": plain(identity), "positional": list(parsed.positional),
                "inlineBodyRetained": bool(inline_fields),
                "unexpandedTemplateBody": not bool(inline_fields),
            },
            membership=_membership(page_key),
        )
        for key in inline_fields:
            value = parsed.named[key]
            collector.add(
                category="power-passive", family="article-power-inline-field",
                origin=_page_origin(page_key, page, sections, start,
                    template="Power Infobox", templateOrdinal=ordinal,
                    field=key, fieldOrdinal=_field_ordinal(parsed, key)),
                excerpt=value,
                normalized={"kind": "power-inline-field", "identity": plain(identity), "field": key, "value": plain(value)},
                membership=_membership(page_key),
            )
        image = parsed.named.get("Image")
        if image is not None:
            collector.add(
                category="non-guide", family="visual-unit",
                origin=_page_origin(page_key, page, sections, start,
                    template="Power Infobox", templateOrdinal=ordinal,
                    field="Image", fieldOrdinal=_field_ordinal(parsed, "Image")),
                excerpt=image,
                normalized={"kind": "infobox-visual-field", "owner": plain(identity), "field": "Image", "value": image},
                membership=_membership(page_key), exclusion_policy_id="exclude-visual-units-v1",
            )

    # Article move rows and the Pattern record following each retained table.
    pattern_inputs: list[tuple[int, str, int, str]] = []
    for table_ordinal, (table_start, start_end, table_raw, table_parsed) in enumerate(iter_templates(text, "Intents Table/start"), 1):
        owner = plain(table_parsed.positional[0]) if table_parsed.positional else None
        if not owner:
            raise AuditError(f"{page_key} Intents Table/start {table_ordinal} lacks owner")
        end_match = re.search(r"\{\{\s*Intents Table/end\s*\}\}", text[start_end:], re.I)
        if not end_match:
            raise AuditError(f"{page_key} intent table {table_ordinal} has no end template")
        table_end = start_end + end_match.end()
        table_body = text[start_end:start_end + end_match.start()]
        rows = list(iter_templates(table_body, "Intents Table/row"))
        for row_ordinal, (relative_start, _, raw, parsed) in enumerate(rows, 1):
            row_start = start_end + relative_start
            metrics["articleMoveRows"] += 1
            name = parsed.named.get("Name")
            intent = parsed.named.get("Intent")
            effect = parsed.named.get("Effect")
            if name is None or intent is None or effect is None:
                raise AuditError(f"{page_key} table {table_ordinal} row {row_ordinal} lacks Name/Intent/Effect")
            row_structure = {
                "owner": owner, "name": plain(name),
                "intentTokens": [plain(value) for value in split_top_level(intent, ",") if plain(value)],
                "effect": plain(effect),
            }
            collector.add(
                category="move-name-intent-effect", family="article-move-name",
                origin=_page_origin(page_key, page, sections, row_start,
                    tableOrdinal=table_ordinal, rowOrdinal=row_ordinal,
                    template="Intents Table/row", field="Name", fieldOrdinal=_field_ordinal(parsed, "Name")),
                excerpt=name,
                normalized={"kind": "move-name", **row_structure}, membership=_membership(page_key),
            )
            for token_ordinal, token in enumerate(split_top_level(intent, ","), 1):
                collector.add(
                    category="move-name-intent-effect", family="article-move-intent",
                    origin=_page_origin(page_key, page, sections, row_start,
                        tableOrdinal=table_ordinal, rowOrdinal=row_ordinal,
                        template="Intents Table/row", field="Intent", fieldOrdinal=_field_ordinal(parsed, "Intent"),
                        tokenOrdinal=token_ordinal),
                    excerpt=token,
                    normalized={"kind": "intent-token", "owner": owner, "move": plain(name), "value": plain(token)},
                    membership=_membership(page_key),
                )
            for claim_ordinal, claim in enumerate(semantic_sentences(effect), 1):
                collector.add(
                    category="move-name-intent-effect", family="article-move-effect",
                    origin=_page_origin(page_key, page, sections, row_start,
                        tableOrdinal=table_ordinal, rowOrdinal=row_ordinal,
                        template="Intents Table/row", field="Effect", fieldOrdinal=_field_ordinal(parsed, "Effect"),
                        claimOrdinal=claim_ordinal),
                    excerpt=claim,
                    normalized={"kind": "move-effect-claim", "owner": owner, "move": plain(name), "value": plain(claim)},
                    membership=_membership(page_key),
                )
        pattern_inputs.append((table_end, owner, table_ordinal, "retained-table"))

    invocation_ordinal = 0
    for start, end, raw, parsed in iter_templates(text, "Intents"):
        invocation_ordinal += 1
        owner = plain(parsed.positional[0]) if parsed.positional else None
        if not owner:
            raise AuditError(f"{page_key} Intents invocation {invocation_ordinal} lacks owner")
        pattern_inputs.append((end, owner, invocation_ordinal, "unexpanded-intents-invocation"))
        metrics["intentsTransclusions"] += 1

    for record_ordinal, (start, owner, source_ordinal, source_kind) in enumerate(sorted(pattern_inputs), 1):
        metrics["articlePatternRecords"] += 1
        raw_pattern = pattern_slice(text, start)
        clauses = pattern_clauses(raw_pattern)
        if not clauses:
            raise AuditError(f"{page_key} Pattern record for {owner} has no retained clause")
        for clause_ordinal, clause in enumerate(clauses, 1):
            collector.add(
                category="pattern-sequence", family="article-pattern-clause",
                origin=_page_origin(page_key, page, sections, start,
                    patternRecordOrdinal=record_ordinal, sourceOrdinal=source_ordinal,
                    patternSource=source_kind, clauseOrdinal=clause_ordinal),
                excerpt=clause,
                normalized={"kind": "pattern-clause", "owner": owner, "source": source_kind, "value": plain(clause)},
                membership=_membership(page_key),
            )

    # Article roster sections own only their structural subheadings/list units.
    for roster_section in (section for section in sections if section.title.casefold() == "in party with"):
        descendants = [section for section in sections
                       if roster_section.body_start <= section.start < roster_section.end
                       and section.level > roster_section.level]
        for heading_ordinal, heading in enumerate(descendants, 1):
            heading_match = text[heading.start:heading.body_start]
            collector.add(
                category="identity-placement-roster-lead", family="article-roster",
                origin=_page_origin(page_key, page, sections, heading.start,
                    rosterSectionOrdinal=roster_section.heading_ordinal,
                    unitKind="act-heading", unitOrdinal=heading_ordinal),
                excerpt=heading_match,
                normalized={"kind": "roster-act-heading", "value": heading.title},
                membership=_membership(page_key),
            )
        list_ordinal = 0
        body = text[roster_section.body_start:roster_section.end]
        for line in body.splitlines():
            if not re.match(r"^\s*[*#]+\s*\S", line):
                continue
            line_claim = re.sub(r"^\s*[*#]+\s*", "", line)
            # A leading/top-level `+ body + body` roster expression owns one
            # atom per body claim; nested template plus signs remain balanced.
            claims = [line_claim]
            if line_claim.lstrip().startswith("+"):
                claims = [part.strip() for part in split_top_level(line_claim, "+") if plain(part)]
            for claim in claims:
                list_ordinal += 1
                collector.add(
                    category="identity-placement-roster-lead", family="article-roster",
                    origin=_page_origin(page_key, page, sections, roster_section.body_start,
                        rosterSectionOrdinal=roster_section.heading_ordinal,
                        unitKind="list-item", unitOrdinal=list_ordinal),
                    excerpt=claim,
                    normalized={"kind": "roster-list-item", "value": plain(claim)},
                    membership=_membership(page_key),
                )

    # Notes: list bullets and explicit numbered lines. Comments are masked and
    # inventoried separately, never interpreted as mechanics.
    for note_section in (section for section in sections if section.title.casefold() == "notes"):
        body = text[note_section.body_start:note_section.end]
        body_without_comments = re.sub(r"<!--[\s\S]*?-->", "", body)
        unit_ordinal = 0
        for line in body_without_comments.splitlines():
            if not re.match(r"^\s*(?:[*#]+|\d+\.)\s*\S", line):
                continue
            unit_ordinal += 1
            claim = re.sub(r"^\s*(?:[*#]+|\d+\.)\s*", "", line)
            exclusion = "exclude-reviewed-noncombat-notes-v1" if page_key in {"Mysterious Knight", "Two-Tailed Rat"} else None
            collector.add(
                category="objective-note-patch-lifecycle", family="article-note-claim",
                origin=_page_origin(page_key, page, sections, note_section.body_start,
                    noteSectionOrdinal=note_section.heading_ordinal, unitOrdinal=unit_ordinal),
                excerpt=claim,
                normalized={"kind": "note-claim", "value": plain(claim)},
                membership=_membership(page_key), exclusion_policy_id=exclusion,
            )

    # Direct section bodies prevent one body's nested subsection from being
    # assigned to its parent or neighboring body.
    tactic_family = {
        "useful cards": "article-tactic-useful",
        "synergies": "article-tactic-synergy",
        "anti-synergies": "article-tactic-anti-synergy",
    }
    tactic_policy = {
        "article-tactic-useful": "exclude-reviewed-tactics-useful-v1",
        "article-tactic-synergy": "exclude-reviewed-tactics-synergy-v1",
        "article-tactic-anti-synergy": "exclude-reviewed-tactics-anti-v1",
    }
    for section in sections:
        family = tactic_family.get(section.title.casefold())
        if not family:
            continue
        body = text[section.body_start:section.direct_end]
        unit_ordinal = 0
        for line in body.splitlines():
            if re.match(r"^\s*[*#]+\s*\S", line):
                claim = re.sub(r"^\s*[*#]+\s*", "", line)
            elif line.strip() and not line.lstrip().startswith(("{{", "[[", "<")):
                claim = line.strip()
            else:
                continue
            if not plain(claim):
                continue
            unit_ordinal += 1
            collector.add(
                category="tactic", family=family,
                origin=_page_origin(page_key, page, sections, section.body_start,
                    tacticSectionOrdinal=section.heading_ordinal, unitOrdinal=unit_ordinal),
                excerpt=claim,
                normalized={"kind": "reviewed-subjective-tactic", "section": section.title, "value": plain(claim)},
                membership=_membership(page_key), exclusion_policy_id=tactic_policy[family],
            )

    for section in (section for section in sections if section.title.casefold() == "trivia"):
        body = text[section.body_start:section.end]
        unit_ordinal = 0
        for line in body.splitlines():
            stripped = line.strip()
            if re.match(r"^\s*[*#]+\s*\S", line):
                claim = re.sub(r"^\s*[*#]+\s*", "", line)
            elif stripped and not re.match(r"(?i)^\{\{\s*Enemy2Nav", stripped) and not stripped.startswith("[[Category:"):
                claim = stripped
            else:
                continue
            if not plain(claim):
                continue
            unit_ordinal += 1
            collector.add(
                category="non-guide", family="trivia-unit",
                origin=_page_origin(page_key, page, sections, section.body_start,
                    triviaSectionOrdinal=section.heading_ordinal, unitOrdinal=unit_ordinal),
                excerpt=claim,
                normalized={"kind": "trivia-unit", "value": plain(claim)},
                membership=_membership(page_key), exclusion_policy_id="exclude-trivia-v1",
            )

    for section in sections:
        lower = section.title.casefold()
        if lower not in {"dialogue", "sources"}:
            continue
        block = text[section.body_start:section.end].strip()
        family = "dialogue-block" if lower == "dialogue" else "source-block"
        policy = "exclude-dialogue-blocks-v1" if lower == "dialogue" else "exclude-source-blocks-v1"
        collector.add(
            category="non-guide", family=family,
            origin=_page_origin(page_key, page, sections, section.start,
                blockSectionOrdinal=section.heading_ordinal, blockOrdinal=1),
            excerpt=block,
            normalized={"kind": family, "section": section.title, "value": plain(block) or "non-prose retained block"},
            membership=_membership(page_key), exclusion_policy_id=policy,
        )

    for ordinal, (start, _, raw, parsed) in enumerate(iter_templates(text, "Update History Table/row"), 1):
        collector.add(
            category="non-guide", family="update-history-row",
            origin=_page_origin(page_key, page, sections, start,
                template="Update History Table/row", templateOrdinal=ordinal, unitOrdinal=ordinal),
            excerpt=raw,
            normalized={"kind": "historical-update-row", "arguments": list(parsed.positional)},
            membership=_membership(page_key), exclusion_policy_id="exclude-update-history-v1",
        )

    for ordinal, (start, _, raw, parsed) in enumerate(iter_templates(text, "Enemy2Nav"), 1):
        collector.add(
            category="non-guide", family="navigation-template",
            origin=_page_origin(page_key, page, sections, start,
                template="Enemy2Nav", templateOrdinal=ordinal),
            excerpt=raw,
            normalized={"kind": "navigation-template", "template": "Enemy2Nav"},
            membership=_membership(page_key), exclusion_policy_id="exclude-navigation-v1",
        )
    for ordinal, (start, _, raw, parsed) in enumerate(iter_templates(text, "Beta content"), 1):
        collector.add(
            category="non-guide", family="beta-badge",
            origin=_page_origin(page_key, page, sections, start,
                template="Beta content", templateOrdinal=ordinal),
            excerpt=raw,
            normalized={"kind": "beta-boilerplate-badge", "template": "Beta content"},
            membership=_membership(page_key), exclusion_policy_id="exclude-beta-boilerplate-v1",
        )
    for ordinal, match in enumerate(re.finditer(r"\[\[Category:[^\]]+\]\]", mask_comments(text), re.I), 1):
        collector.add(
            category="non-guide", family="category-link",
            origin=_page_origin(page_key, page, sections, match.start(), categoryOrdinal=ordinal),
            excerpt=match.group(0),
            normalized={"kind": "category-link", "value": match.group(0)[2:-2]},
            membership=_membership(page_key), exclusion_policy_id="exclude-category-links-v1",
        )

    # Gallery lines are distinct visual units. Standalone file links are counted
    # only after infobox/gallery spans are masked, preventing duplicate hits.
    visual_spans: list[tuple[int, int]] = []
    for name in ("Enemy Infobox", "#invoke:Infobox", "Power Infobox"):
        visual_spans.extend((start, end) for start, end, _, _ in iter_templates(text, name))
    gallery_ordinal = 0
    for match in re.finditer(r"<gallery[^>]*>(.*?)</gallery>", text, re.I | re.S):
        gallery_ordinal += 1
        visual_spans.append((match.start(), match.end()))
        item_ordinal = 0
        for line in match.group(1).splitlines():
            if not re.search(r"\.(?:png|webp|jpe?g|gif)(?:\||$)", line.strip(), re.I):
                continue
            item_ordinal += 1
            collector.add(
                category="non-guide", family="visual-unit",
                origin=_page_origin(page_key, page, sections, match.start(),
                    galleryOrdinal=gallery_ordinal, itemOrdinal=item_ordinal),
                excerpt=line,
                normalized={"kind": "gallery-visual", "value": line.strip()},
                membership=_membership(page_key), exclusion_policy_id="exclude-visual-units-v1",
            )
    standalone = _mask_spans(text, visual_spans)
    for ordinal, match in enumerate(re.finditer(r"\[\[(?:File|Image):[^\]]+\]\]", standalone, re.I), 1):
        collector.add(
            category="non-guide", family="visual-unit",
            origin=_page_origin(page_key, page, sections, match.start(), standaloneVisualOrdinal=ordinal),
            excerpt=match.group(0),
            normalized={"kind": "standalone-visual-link", "value": match.group(0)},
            membership=_membership(page_key), exclusion_policy_id="exclude-visual-units-v1",
        )

    # One retained comment is intentionally represented by its three literal
    # non-empty source fragments, including delimiters. It cannot feed mechanics.
    for comment_ordinal, match in enumerate(re.finditer(r"<!--[\s\S]*?-->", text), 1):
        fragments = [line for line in match.group(0).splitlines() if line.strip()]
        for fragment_ordinal, fragment in enumerate(fragments, 1):
            collector.add(
                category="non-guide", family="html-comment-fragment",
                origin=_page_origin(page_key, page, sections, match.start(),
                    commentOrdinal=comment_ordinal, fragmentOrdinal=fragment_ordinal),
                excerpt=fragment,
                normalized={"kind": "html-comment-fragment", "value": fragment.strip()},
                membership=_membership(page_key), exclusion_policy_id="exclude-html-comments-v1",
            )


def _iter_lua_records(text: str) -> Iterable[tuple[int, str, str]]:
    for match in re.finditer(r'^\s*\["([^"]+)"\]\s*=\s*\{', text, re.M):
        opening = text.find("{", match.start())
        block = lua_balanced(text, opening)
        if lua_string_field(block, "Type") is None:
            continue
        yield match.start(), match.group(1), block


def _lua_field_position(block: str, key: str) -> tuple[int, int]:
    match = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*"((?:\\.|[^"])*)"', block)
    if not match:
        raise AuditError(f"Lua field {key} is absent")
    field_ordinal = sum(1 for candidate in re.finditer(r'(?m)^\s*[A-Za-z][A-Za-z0-9_]*\s*=', block)
                        if candidate.start() <= match.start())
    return match.start(), field_ordinal


def _module_origin(path: str, table_key: str, record_ordinal: int, **coordinate: Any) -> dict[str, Any]:
    return {
        "kind": "module",
        "path": path,
        "tableKey": table_key,
        "recordOrdinal": record_ordinal,
        **coordinate,
    }


def _lua_move_structure(move: str) -> tuple[list[str], list[str]]:
    icons: list[str] = []
    icon_match = re.search(r"\bIntentIcons\s*=\s*\{", move)
    if icon_match:
        icon_table = lua_balanced(move, move.find("{", icon_match.start()))
        icons = re.findall(r'"((?:\\.|[^"])*)"', icon_table)
    asc_values: list[str] = []
    asc_match = re.search(r"\bAscText\s*=\s*\{", move)
    if asc_match:
        asc_table = lua_balanced(move, move.find("{", asc_match.start()))
        asc_values = re.findall(r'"((?:\\.|[^"])*)"', asc_table)
    return icons, asc_values


def _add_module_atoms(
    collector: AtomCollector,
    root: Path,
    relative_path: str,
    metrics: dict[str, Any],
) -> int:
    text = (root / relative_path).read_text(encoding="utf-8")
    records = list(_iter_lua_records(text))
    for record_ordinal, (record_start, table_key, block) in enumerate(records, 1):
        metrics["moduleRecords"] += 1
        membership = _membership(table_key)
        for key in ("Type", "Debut", "Link"):
            value = lua_string_field(block, key)
            if value is None:
                continue
            _, field_ordinal = _lua_field_position(block, key)
            collector.add(
                category="identity-placement-roster-lead", family="module-identity-field",
                origin=_module_origin(relative_path, table_key, record_ordinal,
                    field=key, fieldOrdinal=field_ordinal),
                excerpt=value,
                normalized={"kind": "module-identity-field", "owner": table_key, "field": key, "value": plain(value)},
                membership=membership,
            )
        for key in ("BaseHP", "AscHP"):
            value = lua_string_field(block, key)
            if value is None:
                continue
            _, field_ordinal = _lua_field_position(block, key)
            collector.add(
                category="hp-ascension-scaling", family="module-hp-field",
                origin=_module_origin(relative_path, table_key, record_ordinal,
                    field=key, fieldOrdinal=field_ordinal),
                excerpt=value,
                normalized={"kind": "module-hp-field", "owner": table_key, "field": key, "value": plain(value)},
                membership=membership,
            )
        starts = lua_string_field(block, "StartsWith")
        if starts is not None:
            _, field_ordinal = _lua_field_position(block, "StartsWith")
            for claim_ordinal, claim in enumerate(split_power_claims(starts), 1):
                collector.add(
                    category="starting-power-status-stack", family="module-starting-power",
                    origin=_module_origin(relative_path, table_key, record_ordinal,
                        field="StartsWith", fieldOrdinal=field_ordinal, claimOrdinal=claim_ordinal),
                    excerpt=claim,
                    normalized=normalized_starting_power(
                        claim, kind="module-starting-power", owner=table_key, parent_field=starts),
                    membership=membership,
                )
        roster = lua_string_field(block, "InPartyWith")
        if roster is not None:
            _, field_ordinal = _lua_field_position(block, "InPartyWith")
            segments = [segment.strip() for segment in re.split(r"(?i)<br\s*/?>", roster)]
            segments = [segment for segment in segments if segment and "enemy-infobox-party-header" not in segment]
            for unit_ordinal, segment in enumerate(segments, 1):
                collector.add(
                    category="identity-placement-roster-lead", family="module-roster",
                    origin=_module_origin(relative_path, table_key, record_ordinal,
                        field="InPartyWith", fieldOrdinal=field_ordinal, unitOrdinal=unit_ordinal),
                    excerpt=segment,
                    normalized={"kind": "module-roster-unit", "owner": table_key, "value": plain(segment)},
                    membership=membership,
                )

        intents_match = re.search(r"\bIntents\s*=\s*\{", block)
        if not intents_match:
            continue
        intent_table = lua_balanced(block, block.find("{", intents_match.start()))
        move_matches = list(re.finditer(r'\{\s*Name\s*=\s*"([^"]+)"', intent_table))
        for move_ordinal, move_match in enumerate(move_matches, 1):
            move = lua_balanced(intent_table, move_match.start())
            name = move_match.group(1)
            source_text = lua_string_field(move, "Text")
            if source_text is None:
                raise AuditError(f"{relative_path}:{table_key} move {move_ordinal} lacks Text")
            icons, asc_values = _lua_move_structure(move)
            move_structure = {
                "kind": "module-move-name", "owner": table_key, "name": name,
                "intentIcons": icons, "text": plain(source_text),
                "ascensionTextVariants": [plain(value) for value in asc_values],
            }
            collector.add(
                category="move-name-intent-effect", family="module-move-name",
                origin=_module_origin(relative_path, table_key, record_ordinal,
                    field="Intents", moveOrdinal=move_ordinal, moveField="Name", fieldOrdinal=1),
                excerpt=name, normalized=move_structure, membership=membership,
            )
            for claim_ordinal, claim in enumerate(semantic_sentences(source_text), 1):
                collector.add(
                    category="move-name-intent-effect", family="module-move-effect",
                    origin=_module_origin(relative_path, table_key, record_ordinal,
                        field="Intents", moveOrdinal=move_ordinal, moveField="Text",
                        fieldOrdinal=3, claimOrdinal=claim_ordinal),
                    excerpt=claim,
                    normalized={
                        "kind": "module-move-effect-claim", "owner": table_key,
                        "move": name, "intentIcons": icons, "value": plain(claim),
                        "ascensionTextVariants": [plain(value) for value in asc_values],
                    },
                    membership=membership,
                )
        metrics["moduleMoveRows"] += len(move_matches)
    return len(records)


def _patch_sections_by_line(text: str) -> list[tuple[int, tuple[str, ...]]]:
    path: list[tuple[int, str]] = []
    result: list[tuple[int, tuple[str, ...]]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        heading = re.match(r"^\s*(={2,5})\s*(.*?)\s*\1\s*$", line)
        if heading:
            level = len(heading.group(1))
            path = [item for item in path if item[0] < level]
            path.append((level, plain(heading.group(2)) or heading.group(2).strip()))
        result.append((line_number, tuple(item[1] for item in path)))
    return result


def _add_patch_atoms(
    collector: AtomCollector,
    page_key: str,
    page: dict[str, Any],
    policy: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    text = page["wikitext"]
    sections = parse_sections(text)
    line_paths = dict(_patch_sections_by_line(text))
    classifications = {item["enemyBulletOrdinal"]: item for item in policy["patchEnemyFactClassifications"]}
    enemy_ordinal = global_ordinal = other_ordinal = 0
    lines = text.splitlines()
    for line_number, line in enumerate(lines, 1):
        match = re.match(r"^\s*(\*+)\s*(.*)", line)
        if not match:
            continue
        global_ordinal += 1
        section_path = line_paths[line_number]
        text_value = match.group(2).strip()
        is_enemy_balance = section_path == ("CONTENT & BALANCE", "Enemies:")
        if is_enemy_balance:
            enemy_ordinal += 1
            # The exact first bullet is the reviewed grouping parent; every
            # other bullet must have an explicit policy classification so a
            # snapshot refresh cannot silently omit a new enemy mechanic.
            classification = classifications.get(enemy_ordinal)
            if not classification:
                is_reviewed_grouping_parent = (
                    enemy_ordinal == 1
                    and match.group(1) == "*"
                    and text_value == "Buffed Axebot:"
                )
                if is_reviewed_grouping_parent:
                    continue
                raise AuditError(
                    f"patch enemy bullet {enemy_ordinal} lacks reviewed classification: {text_value}"
                )
            expected = classification["excerptSha256"]
            if sha256_bytes(text_value.encode("utf-8")) != expected:
                raise AuditError(f"patch enemy bullet {enemy_ordinal} changed without reviewed classification")
            category = classification["category"]
            family = classification["family"]
            collector.add(
                category=category, family=family,
                origin=_page_origin(page_key, page, sections, 0,
                    patchSectionPath=list(section_path), bulletOrdinal=enemy_ordinal,
                    globalBulletOrdinal=global_ordinal, fieldOrdinal=1),
                excerpt=text_value,
                normalized={"kind": family, "reviewedCoordinate": classification["id"], "value": plain(text_value)},
                membership="not-applicable",
            )
            metrics["patchEnemyFacts"] += 1
        else:
            other_ordinal += 1
            collector.add(
                category="non-guide", family="patch-other-bullet",
                origin=_page_origin(page_key, page, sections, 0,
                    patchSectionPath=list(section_path), bulletOrdinal=other_ordinal,
                    globalBulletOrdinal=global_ordinal),
                excerpt=text_value,
                normalized={"kind": "out-of-encounter-patch-scope", "sectionPath": list(section_path), "value": plain(text_value)},
                membership="not-applicable", exclusion_policy_id="exclude-other-patch-bullets-v1",
            )
    for ordinal, (start, _, raw, parsed) in enumerate(iter_templates(text, "PatchNav"), 1):
        collector.add(
            category="non-guide", family="navigation-template",
            origin=_page_origin(page_key, page, sections, start,
                template="PatchNav", templateOrdinal=ordinal),
            excerpt=raw,
            normalized={"kind": "navigation-template", "template": "PatchNav"},
            membership="not-applicable", exclusion_policy_id="exclude-navigation-v1",
        )
    # The patch's one retained file reference is an explicit visual unit.
    for ordinal, match in enumerate(re.finditer(r"\[\[(?:File|Image):[^\]]+\]\]", text, re.I), 1):
        collector.add(
            category="non-guide", family="visual-unit",
            origin=_page_origin(page_key, page, sections, match.start(), standaloneVisualOrdinal=ordinal),
            excerpt=match.group(0),
            normalized={"kind": "standalone-visual-link", "value": match.group(0)},
            membership="not-applicable", exclusion_policy_id="exclude-visual-units-v1",
        )



FINAL_DISPOSITIONS = {
    "primary-present", "audit-present", "source-present-not-projected", "retained-book-only",
    "conflict", "missing/unparsed", "intentionally-excluded", "stale/deprecated/version-ambiguous",
}
FINAL_REVIEW_STATE = "final-mapped"
ALLOWED_MAPPING_LAYERS = {
    "raw-source", "compact-projection", "retained-book", "retained-archive", "retained-reference",
    "primary-presentation", "technical-audit", "wiki-origin",
}
ALLOWED_CLOSURES = {"closed", "knownUnknown", "unjoined", "notApplicable"}
DOCUMENTS = {
    "raw-source": "data/game-v0.111.0-source.json",
    "compact-projection": "data/encounter-facts-v0.111.0.json",
    "retained-book": "data/encounters.json",
    "retained-archive": "data/encounters.json",
    "retained-reference": "data/encounters.json",
    "technical-audit": "data/encounter-facts-v0.111.0.json",
    "primary-presentation": PRIMARY_SEMANTIC_SURFACE,
}


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise AuditError(f"unresolved JSON pointer: {pointer!r}")
    current: Any = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit():
                raise AuditError(f"unresolved JSON pointer {pointer}")
            index = int(token)
            if index >= len(current):
                raise AuditError(f"unresolved JSON pointer {pointer}")
            current = current[index]
        elif isinstance(current, dict):
            if token not in current:
                raise AuditError(f"unresolved JSON pointer {pointer}")
            current = current[token]
        else:
            raise AuditError(f"unresolved JSON pointer {pointer}")
    return current


def values_equivalent(left: Any, right: Any) -> bool:
    if left == right:
        return True

    def hp_pair(value: Any) -> tuple[int, int] | None:
        if isinstance(value, list) and value and all(type(item) is int for item in value):
            return (value[0], value[-1])
        if isinstance(value, dict) and type(value.get("minimum")) is int and type(value.get("maximum")) is int:
            return (value["minimum"], value["maximum"])
        return None

    left_hp, right_hp = hp_pair(left), hp_pair(right)
    return left_hp is not None and left_hp == right_hp


def _mapping_documents(book: dict[str, Any], compact: dict[str, Any], raw_source: dict[str, Any],
                       primary_surface: dict[str, Any] | None = None) -> dict[str, Any]:
    documents = {
        "data/game-v0.111.0-source.json": raw_source,
        "data/encounter-facts-v0.111.0.json": compact,
        "data/encounters.json": book,
    }
    if primary_surface is not None:
        documents[PRIMARY_SEMANTIC_SURFACE] = primary_surface
    return documents


def _validate_representation(mapping: dict[str, Any], documents: dict[str, Any], *, require_conflict_lanes: bool) -> None:
    layers_ok = False
    seen_source = False
    seen_retained = False
    representations = mapping.get("representation") or []
    if not representations:
        raise AuditError(f"mapping {mapping.get('id')} lacks representation coordinates")
    for index, row in enumerate(representations):
        path = f"{mapping.get('id')}.representation[{index}]"
        if not isinstance(row, dict):
            raise AuditError(f"{path} is not an object")
        layer = row.get("layer")
        if layer not in ALLOWED_MAPPING_LAYERS:
            raise AuditError(f"{path} has unsupported layer {layer!r}")
        document_path = row.get("path")
        pointer = row.get("jsonPointer")
        if layer == "wiki-origin":
            continue
        if document_path not in documents:
            raise AuditError(f"{path} path {document_path} is not a checked mapping document")
        try:
            value = resolve_json_pointer(documents[document_path], pointer)
        except AuditError as exc:
            raise AuditError(f"{path} {exc}") from exc
        expected = row.get("expectedValue")
        if "expectedValue" in row and not values_equivalent(expected, value):
            raise AuditError(f"{path} expectedValue mismatch")
        lane = row.get("comparedLane")
        semantic = mapping["semanticMapping"]
        if lane == "source":
            seen_source = True
            if not values_equivalent(semantic["sourceValue"], value):
                raise AuditError(f"{path} source value mismatch")
        elif lane == "retained":
            seen_retained = True
            if not values_equivalent(semantic["retainedValue"], value):
                raise AuditError(f"{path} retained value mismatch")
        elif lane not in {None, "source", "retained"}:
            raise AuditError(f"{path} has unsupported comparedLane {lane!r}")
        layers_ok = True
    if not layers_ok:
        raise AuditError(f"mapping {mapping.get('id')} has no resolvable representation")
    authority = mapping["authorityComparison"]
    if authority.get("silentMerge") is not False:
        raise AuditError(f"mapping {mapping.get('id')} must set silentMerge false")
    if authority.get("closure") not in ALLOWED_CLOSURES:
        raise AuditError(f"mapping {mapping.get('id')} has unsupported closure")
    if require_conflict_lanes:
        if mapping["disposition"] != "conflict":
            raise AuditError(f"mapping {mapping.get('id')} is not a conflict")
        if not seen_source or not seen_retained:
            raise AuditError(f"conflict {mapping.get('id')} lacks both lanes")
        if authority.get("resolution") != "source-wins":
            raise AuditError(f"conflict {mapping.get('id')} lacks source-wins resolution")
        if not authority.get("sourceFactRefs") or not authority.get("compactFactRefs"):
            raise AuditError(f"conflict {mapping.get('id')} lacks source/compact fact refs")


_RETAINED_NORMAL_POINTER = re.compile(r"^/encounters/(\d+)/retainedBodies/(\d+)/hpBelowA8$")
_RETAINED_A8_POINTER = re.compile(r"^/encounters/(\d+)/retainedBodies/(\d+)/hpA8SinglePlayer$")
_SOURCE_NORMAL_POINTER = re.compile(r"^/encounters/(\d+)/sourceModels/(\d+)/hp/belowA8$")
_SOURCE_A8_POINTER = re.compile(r"^/encounters/(\d+)/sourceModels/(\d+)/hp/a8SinglePlayer$")
_PRIMARY_A8_POINTER = re.compile(r"^/encounters/(\d+)/primaryByPlayers/(\d+)/bodies/(\d+)/hp/a8SinglePlayer$")


def _surface_value(row: dict[str, Any], documents: dict[str, Any]) -> Any:
    if row.get("path") != PRIMARY_SEMANTIC_SURFACE:
        raise AuditError(f"HP value evidence must use the typed primary semantic surface: {row.get('jsonPointer')}")
    return resolve_json_pointer(documents[PRIMARY_SEMANTIC_SURFACE], row["jsonPointer"])


def _hp_body_scope(mapping: dict[str, Any], documents: dict[str, Any], row: dict[str, Any],
                   matcher: re.Pattern[str]) -> tuple[int, int, dict[str, Any]]:
    match = matcher.fullmatch(row.get("jsonPointer", ""))
    if not match:
        raise AuditError(f"P1b1 HP value evidence has wrong semantic coordinate: {row.get('jsonPointer')}")
    encounter_index, body_index = map(int, match.groups())
    surface = documents[PRIMARY_SEMANTIC_SURFACE]
    try:
        body = surface["encounters"][encounter_index]["retainedBodies"][body_index]
    except (IndexError, KeyError, TypeError) as exc:
        raise AuditError("P1b1 HP retained body coordinate is unresolved") from exc
    semantic = mapping["semanticMapping"]
    actor_models = set(semantic.get("actorModels") or [])
    if not actor_models or not actor_models.intersection(body.get("sourceModels") or []):
        raise AuditError(f"P1b1 HP value evidence belongs to another actor/form: {row['jsonPointer']}")
    expected_states = set(semantic.get("stateIds") or [])
    body_state = body.get("stateId")
    if expected_states:
        if body_state not in expected_states:
            raise AuditError(f"P1b1 HP value evidence belongs to another state: {row['jsonPointer']}")
    elif body_state is not None:
        raise AuditError(f"P1b1 base HP evidence substituted a state/form: {row['jsonPointer']}")
    return encounter_index, body_index, body


def _hp_source_scope(mapping: dict[str, Any], documents: dict[str, Any], row: dict[str, Any],
                     matcher: re.Pattern[str]) -> tuple[dict[str, Any], Any]:
    match = matcher.fullmatch(row.get("jsonPointer", ""))
    if not match:
        raise AuditError(f"P1b1 HP source evidence has wrong semantic coordinate: {row.get('jsonPointer')}")
    encounter_index, model_index = map(int, match.groups())
    surface = documents[PRIMARY_SEMANTIC_SURFACE]
    try:
        model = surface["encounters"][encounter_index]["sourceModels"][model_index]
    except (IndexError, KeyError, TypeError) as exc:
        raise AuditError("P1b1 HP source coordinate is unresolved") from exc
    if model.get("canonicalModel") not in set(mapping["semanticMapping"].get("actorModels") or []):
        raise AuditError(f"P1b1 HP source evidence belongs to another actor: {row['jsonPointer']}")
    return model, _surface_value(row, documents)


def _validate_hp_value_evidence(mapping: dict[str, Any], documents: dict[str, Any]) -> None:
    """Enforce exact typed value, body/state, Ascension, player, and source-closure evidence."""
    semantic = mapping["semanticMapping"]
    kind = semantic.get("kind")
    if kind == "patch-hp-transition":
        authority = mapping["authorityComparison"]
        if mapping["disposition"] != "missing/unparsed" or authority["closure"] != "unjoined" or authority["sourceFactRefs"]:
            raise AuditError("P1b1 historical HP transition was optimistically represented")
        return
    if kind not in {"normal-hp-range", "a8-hp-range", "normal-and-a8-hp-ranges"}:
        return
    authority = mapping["authorityComparison"]
    representations = mapping["representation"]
    non_wiki = [row for row in representations if row.get("layer") != "wiki-origin"]

    if kind == "normal-hp-range":
        retained = semantic.get("retainedValue")
        if not _is_typed_hp_range(retained):
            raise AuditError("P1b1 normal HP lacks a typed retained range")
        retained_rows = [row for row in non_wiki if row.get("evidenceRole") == "retained-normal-value"]
        if not retained_rows:
            raise AuditError("P1b1 normal HP has no exact retained value evidence")
        represented_states = set()
        for row in retained_rows:
            _, _, body = _hp_body_scope(mapping, documents, row, _RETAINED_NORMAL_POINTER)
            value = _surface_value(row, documents)
            if value != retained or row.get("expectedValue") != retained:
                raise AuditError("P1b1 normal HP exact retained value evidence mismatch")
            if body.get("hpBelowA8Authority") != "retained-wiki-reference":
                raise AuditError("P1b1 normal HP lost retained-wiki authority")
            if body.get("stateId"):
                represented_states.add(body["stateId"])
        if represented_states != set(semantic.get("stateIds") or []):
            raise AuditError("P1b1 normal HP state ownership/value coordinates disagree")
        if any(row.get("evidenceRole") == "retained-normal-value" and "hpA8SinglePlayer" in row.get("jsonPointer", "")
               for row in non_wiki):
            raise AuditError("P1b1 normal HP substituted an A8 value")

        source_rows = [row for row in non_wiki if row.get("evidenceRole") == "same-scope-source-value"
                       and _SOURCE_NORMAL_POINTER.fullmatch(row.get("jsonPointer", ""))]
        source_models = []
        for row in source_rows:
            model, value = _hp_source_scope(mapping, documents, row, _SOURCE_NORMAL_POINTER)
            if not _is_typed_hp_range(value) or value != semantic.get("sourceValue"):
                raise AuditError("P1b1 normal HP exact source value evidence mismatch")
            source_models.append(model)
        if semantic.get("stateIds") and source_rows:
            raise AuditError("P1b1 normal HP used another state's model value as source evidence")
        closure = authority["closure"]
        if closure == "closed":
            source_value = semantic.get("sourceValue")
            if not _is_typed_hp_range(source_value) or not source_rows:
                raise AuditError("P1b1 normal HP source closure lacks exact value evidence")
            exact_fact_ids = sorted({row["factId"] for row in source_models})
            if authority["sourceFactRefs"] != exact_fact_ids or authority["compactFactRefs"] != exact_fact_ids:
                raise AuditError("P1b1 normal HP source closure uses ownership/non-value fact refs")
            if mapping["disposition"] == "conflict":
                if source_value == retained:
                    raise AuditError("P1b1 normal HP conflict values do not conflict")
            elif source_value != retained:
                raise AuditError("P1b1 normal HP silently merged different exact values")
        elif closure == "knownUnknown":
            if semantic.get("sourceValue") is not None or source_rows or authority["sourceFactRefs"] or authority["compactFactRefs"]:
                raise AuditError("P1b1 retained-only normal HP was incorrectly source-closed")
            if semantic.get("authorityStatus") != "retained-reference-only":
                raise AuditError("P1b1 retained-only normal HP authority status drifted")
        else:
            raise AuditError("P1b1 represented normal HP has invalid authority closure")
        return

    if kind == "a8-hp-range":
        retained = semantic.get("retainedValue")
        represented = semantic.get("sourceOrFallbackValue")
        if not _is_typed_hp_range(retained) or not _is_typed_hp_range(represented):
            raise AuditError("P1b1 A8 HP lacks a typed exact range")
        body_rows = [row for row in non_wiki if _RETAINED_A8_POINTER.fullmatch(row.get("jsonPointer", ""))]
        primary_rows = [row for row in non_wiki if _PRIMARY_A8_POINTER.fullmatch(row.get("jsonPointer", ""))]
        if mapping["disposition"] == "primary-present" and (not body_rows or not primary_rows):
            raise AuditError("P1b1 primary A8 HP lacks typed body/primary value evidence")
        body_bindings: dict[int, list[dict[str, Any]]] = {}
        represented_states = set()
        for row in body_rows:
            encounter_index, _, body = _hp_body_scope(mapping, documents, row, _RETAINED_A8_POINTER)
            if _surface_value(row, documents) != represented or row.get("expectedValue") != represented:
                raise AuditError("P1b1 A8 exact body value evidence mismatch")
            body_bindings.setdefault(encounter_index, []).append(body)
            if body.get("stateId"):
                represented_states.add(body["stateId"])
        if represented_states != set(semantic.get("stateIds") or []):
            raise AuditError("P1b1 A8 state ownership/value coordinates disagree")
        players_seen = set()
        for row in primary_rows:
            match = _PRIMARY_A8_POINTER.fullmatch(row["jsonPointer"])
            encounter_index, player_index, body_ordinal = map(int, match.groups())
            encounter = documents[PRIMARY_SEMANTIC_SURFACE]["encounters"][encounter_index]
            try:
                primary = encounter["primaryByPlayers"][player_index]
            except (IndexError, KeyError, TypeError) as exc:
                raise AuditError("P1b1 A8 primary player coordinate is unresolved") from exc
            if row.get("players") != primary["players"] or _surface_value(row, documents) != represented:
                raise AuditError("P1b1 A8 player scope/value evidence mismatch")
            if not any(body_ordinal in body["primaryBodyOrdinals"] for body in body_bindings.get(encounter_index, [])):
                raise AuditError("P1b1 A8 primary value belongs to another body/state")
            players_seen.add(primary["players"])
        if mapping["disposition"] == "primary-present" and players_seen != {1, 2}:
            raise AuditError("P1b1 A8 HP lacks exact 1P/2P scope evidence")
        if any(_RETAINED_NORMAL_POINTER.fullmatch(row.get("jsonPointer", "")) for row in primary_rows):
            raise AuditError("P1b1 A8 HP substituted a base value")

        source_rows = [row for row in non_wiki if row.get("evidenceRole") == "same-scope-source-value"
                       and _SOURCE_A8_POINTER.fullmatch(row.get("jsonPointer", ""))]
        source_models = []
        source_values = []
        for row in source_rows:
            model, value = _hp_source_scope(mapping, documents, row, _SOURCE_A8_POINTER)
            if not _is_typed_hp_range(value):
                raise AuditError("P1b1 A8 exact source value is not typed")
            source_models.append(model)
            source_values.append(value)
        if semantic.get("stateIds") and source_rows:
            raise AuditError("P1b1 A8 HP used another state's model value as source evidence")
        if authority["closure"] == "closed":
            if not source_rows or len({canonical_json_bytes(value) for value in source_values}) != 1:
                raise AuditError("P1b1 A8 source closure lacks one exact source value")
            exact_fact_ids = sorted({row["factId"] for row in source_models})
            if authority["sourceFactRefs"] != exact_fact_ids or authority["compactFactRefs"] != exact_fact_ids:
                raise AuditError("P1b1 A8 source closure uses ownership/non-value fact refs")
            source_value = source_values[0]
            if mapping["disposition"] == "conflict":
                if source_value != semantic.get("sourceValue") or source_value == retained or represented != source_value:
                    raise AuditError("P1b1 A8 source-winning conflict values drifted")
            elif source_value != retained or represented != retained:
                raise AuditError("P1b1 A8 closed value does not exactly match the claim")
        elif authority["closure"] == "knownUnknown":
            if source_rows or authority["sourceFactRefs"] or authority["compactFactRefs"] or represented != retained:
                raise AuditError("P1b1 retained-fallback A8 HP was incorrectly source-closed")
        else:
            raise AuditError("P1b1 represented A8 HP has invalid authority closure")
        return

    normal = semantic.get("normalValue")
    ascended = semantic.get("a8Value")
    if not _is_typed_hp_range(normal) or not _is_typed_hp_range(ascended):
        raise AuditError("P1b1 dual HP mapping lacks typed normal/A8 ranges")
    normal_rows = [row for row in non_wiki if _SOURCE_NORMAL_POINTER.fullmatch(row.get("jsonPointer", ""))]
    a8_source_rows = [row for row in non_wiki if _SOURCE_A8_POINTER.fullmatch(row.get("jsonPointer", ""))]
    primary_rows = [row for row in non_wiki if _PRIMARY_A8_POINTER.fullmatch(row.get("jsonPointer", ""))]
    if not normal_rows or not a8_source_rows or not primary_rows:
        raise AuditError("P1b1 dual HP mapping lacks exact source/primary coordinates")
    source_models = []
    for row in normal_rows:
        model, value = _hp_source_scope(mapping, documents, row, _SOURCE_NORMAL_POINTER)
        if value != normal:
            raise AuditError("P1b1 dual HP normal range mismatch")
        source_models.append(model)
    for row in a8_source_rows:
        model, value = _hp_source_scope(mapping, documents, row, _SOURCE_A8_POINTER)
        if value != ascended:
            raise AuditError("P1b1 dual HP A8 range mismatch")
        source_models.append(model)
    if any(_surface_value(row, documents) != ascended for row in primary_rows):
        raise AuditError("P1b1 dual HP primary A8 range mismatch")
    if {row.get("players") for row in primary_rows} != {1, 2}:
        raise AuditError("P1b1 dual HP lacks exact 1P/2P coordinates")
    exact_fact_ids = sorted({row["factId"] for row in source_models})
    if authority["closure"] != "closed" or authority["sourceFactRefs"] != exact_fact_ids:
        raise AuditError("P1b1 dual HP source closure/fact refs drifted")


def _attach_mapping(record: dict[str, Any], mapping: dict[str, Any]) -> None:
    if record.get("reviewState") == "policy-reviewed-exclusion":
        raise AuditError(f"cannot double-disposition excluded origin {record['id']}")
    if record.get("reviewState") == FINAL_REVIEW_STATE:
        raise AuditError(f"duplicate final mapping for {record['id']}")
    if record["id"] != mapping["originId"]:
        raise AuditError(f"mapping {mapping.get('id')} origin mismatch")
    if record["claimId"] != mapping["claimId"]:
        raise AuditError(f"stale claim guard for {record['id']}")
    if mapping["disposition"] not in FINAL_DISPOSITIONS:
        raise AuditError(f"unsupported disposition {mapping['disposition']}")
    if mapping["disposition"] == "intentionally-excluded":
        raise AuditError(f"final mapping {mapping.get('id')} must not reuse exclusion disposition")
    if not mapping.get("rationale") or len(str(mapping["rationale"]).strip()) < 20:
        raise AuditError(f"mapping {mapping.get('id')} lacks concrete rationale")
    if mapping.get("reviewedForVersion") != TARGET_VERSION:
        raise AuditError(f"mapping {mapping.get('id')} has wrong reviewed version")
    if not mapping.get("semanticMapping") or not mapping["semanticMapping"].get("kind"):
        raise AuditError(f"mapping {mapping.get('id')} lacks typed semantic mapping")
    record.update({
        "reviewState": FINAL_REVIEW_STATE,
        "disposition": mapping["disposition"],
        "finalMappingId": mapping["id"],
        "semanticMapping": mapping["semanticMapping"],
        "authorityComparison": mapping["authorityComparison"],
        "representation": mapping["representation"],
        "rationale": mapping["rationale"],
        "owner": mapping["owner"],
        "severity": mapping["severity"],
        "reviewedForVersion": mapping["reviewedForVersion"],
    })


def _materialize_structural_mapping(record: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"{rule['id']}::{record['id']}",
        "originId": record["id"],
        "claimId": record["claimId"],
        "disposition": rule["disposition"],
        "semanticMapping": {**rule["semanticMapping"], "originFamily": record["family"]},
        "authorityComparison": rule["authorityComparison"],
        "representation": rule["representation"],
        "rationale": rule["rationale"],
        "owner": rule["owner"],
        "severity": rule["severity"],
        "reviewedForVersion": rule["reviewedForVersion"],
    }


def _match_structural_rule(record: dict[str, Any], match: dict[str, Any]) -> bool:
    if match.get("membership") and record.get("membership") != match["membership"]:
        return False
    if match.get("reviewState") and record.get("reviewState") != match["reviewState"]:
        return False
    if match.get("families") and record.get("family") not in match["families"]:
        return False
    return True


def apply_final_mappings(
    records: list[dict[str, Any]],
    policy: dict[str, Any],
    *,
    book: dict[str, Any],
    compact: dict[str, Any],
    raw_source: dict[str, Any],
) -> dict[str, Any]:
    mappings_policy = policy["finalMappings"]
    documents = _mapping_documents(book, compact, raw_source)
    by_id = {record["id"]: record for record in records}
    used: set[str] = set()

    expected_kinds = set(mappings_policy["allowedSemanticKinds"])
    expected_layers = set(mappings_policy["allowedLayers"])
    if expected_kinds != {
        "a8-hp-range", "move-effect-block", "move-title", "identity-type", "stale-deprecated-mechanic",
    }:
        raise AuditError("final-mapping allowed kinds drifted")
    if expected_layers != ALLOWED_MAPPING_LAYERS:
        raise AuditError("final-mapping allowed layers drifted")

    explicit_ids = [item["originId"] for item in mappings_policy["records"]]
    if len(explicit_ids) != len(set(explicit_ids)):
        raise AuditError("duplicate explicit final-mapping origin IDs")
    if len(mappings_policy["records"]) != mappings_policy["expectedConflictOriginCount"]:
        raise AuditError("explicit conflict mapping count drifted")

    for mapping in mappings_policy["records"]:
        if mapping["originId"] not in by_id:
            raise AuditError(f"unknown final-mapping origin {mapping['originId']}")
        if mapping["semanticMapping"]["kind"] not in expected_kinds:
            raise AuditError(f"unsupported semantic kind {mapping['semanticMapping']['kind']}")
        require_conflict = mapping["disposition"] == "conflict"
        _validate_representation(mapping, documents, require_conflict_lanes=require_conflict)
        _attach_mapping(by_id[mapping["originId"]], mapping)
        used.add(mapping["originId"])

    stale_ids: list[str] = []
    for rule in mappings_policy["structuralRules"]:
        if "expectedOriginIds" not in rule or "expectedCount" not in rule:
            raise AuditError(f"structural rule {rule.get('id')} lacks exact expected ID set/count")
        matched = [record for record in records if _match_structural_rule(record, rule.get("match") or {})]
        matched_ids = [record["id"] for record in matched]
        if matched_ids != rule["expectedOriginIds"] or len(matched) != rule["expectedCount"]:
            raise AuditError(
                f"structural rule {rule['id']} matched-ID set/count drifted: "
                f"expected {rule['expectedCount']}, derived {len(matched)}"
            )
        claim_ids = [record["claimId"] for record in matched]
        if rule.get("expectedClaimIds") != claim_ids:
            raise AuditError(f"structural rule {rule['id']} claim guards are stale")
        if mapping_overlap := set(matched_ids) & used:
            raise AuditError(f"structural rule {rule['id']} duplicates mapped origins: {sorted(mapping_overlap)[:3]}")
        for record in matched:
            materialized = _materialize_structural_mapping(record, rule)
            if materialized["semanticMapping"]["kind"] not in expected_kinds:
                raise AuditError(f"unsupported semantic kind {materialized['semanticMapping']['kind']}")
            _validate_representation(
                materialized, documents,
                require_conflict_lanes=materialized["disposition"] == "conflict",
            )
            _attach_mapping(record, materialized)
            used.add(record["id"])
            if rule["disposition"] == "stale/deprecated/version-ambiguous":
                stale_ids.append(record["id"])

    if len(used) != mappings_policy["expectedFinalMappedCount"]:
        raise AuditError(
            f"final-mapped count drifted: expected {mappings_policy['expectedFinalMappedCount']}, derived {len(used)}"
        )
    if len(stale_ids) != mappings_policy["expectedStaleOriginCount"]:
        raise AuditError("stale origin count drifted")

    title_spec = mappings_policy["compactTitleConflictCrossLinks"]
    compact_conflicts = resolve_json_pointer(compact, title_spec["sourcePointer"])
    if not isinstance(compact_conflicts, list):
        raise AuditError("compact title conflict source pointer did not resolve to a list")
    conflict_ids = [row.get("conflictId") for row in compact_conflicts]
    if conflict_ids != title_spec["expectedConflictIds"] or len(conflict_ids) != title_spec["expectedCount"]:
        raise AuditError("compact title conflict cross-link set/count drifted")
    if title_spec["expectedCount"] != mappings_policy["expectedCompactTitleConflictCount"]:
        raise AuditError("compact title conflict expected count mismatch")
    if any(row.get("family") not in {"encounterTitle", "monsterTitle"} for row in compact_conflicts):
        raise AuditError("compact title conflict family drifted")
    if any(row.get("resolution") != title_spec["compactLaneResolution"] for row in compact_conflicts):
        raise AuditError("compact title conflicts lost unresolved dual-lane representation")
    cross_links = []
    for index, row in enumerate(compact_conflicts):
        pointer = f"{title_spec['sourcePointer']}/{index}"
        resolved = resolve_json_pointer(compact, pointer)
        if resolved["conflictId"] != row["conflictId"]:
            raise AuditError(f"compact title conflict pointer {pointer} mismatch")
        if row["left"]["lane"] != "source" or row["right"]["lane"] != "legacy":
            raise AuditError(f"{row['conflictId']} lane assignment drifted")
        cross_links.append({
            "conflictId": row["conflictId"],
            "family": row["family"],
            "sourceValue": row["left"]["value"],
            "retainedValue": row["right"]["value"],
            "sourceFactId": row["left"]["factId"],
            "retainedFactId": row["right"]["factId"],
            "compactPointer": pointer,
            "compactLaneResolution": title_spec["compactLaneResolution"],
            "presentationResolution": title_spec["presentationResolution"],
            "heroCopyAuthority": title_spec["heroCopyAuthority"],
        })

    disposition_counts: dict[str, int] = {}
    for record in records:
        if "disposition" in record:
            disposition_counts[record["disposition"]] = disposition_counts.get(record["disposition"], 0) + 1
    return {
        "mappedOriginIds": sorted(used),
        "dispositionCounts": dict(sorted(disposition_counts.items())),
        "compactTitleConflicts": cross_links,
        "researchCountCorrections": mappings_policy["researchCountCorrections"],
    }



P1B1_TARGET_CATEGORIES = {
    "identity-placement-roster-lead", "hp-ascension-scaling", "starting-power-status-stack",
}


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _range_claim(value: str) -> dict[str, int]:
    numbers = [int(item.replace(",", "")) for item in re.findall(r"\d[\d,]*", value)]
    if len(numbers) not in {1, 2}:
        raise AuditError(f"P1b1 HP claim is not a fixed/range value: {value!r}")
    return {"minimum": numbers[0], "maximum": numbers[-1]}


def _is_typed_hp_range(value: Any) -> bool:
    return (isinstance(value, dict) and set(value) == {"minimum", "maximum"}
            and type(value["minimum"]) is int and type(value["maximum"]) is int
            and 0 < value["minimum"] <= value["maximum"])


def _expression_integer(expression: dict[str, Any], ascension: int) -> int | None:
    kind = expression.get("kind")
    if kind == "constant" and type(expression.get("value")) is int:
        return expression["value"]
    if kind == "convert":
        return _expression_integer(expression.get("expression") or {}, ascension)
    if kind == "ascensionSelect":
        branch = expression.get("atOrAbove") if ascension >= expression.get("threshold", 999) else expression.get("below")
        return _expression_integer(branch or {}, ascension)
    return None


def _below_a8_range(hp: dict[str, Any]) -> dict[str, int] | None:
    expression = hp.get("expression") or {}
    if expression.get("kind") != "range":
        return None
    minimum = _expression_integer(expression.get("minimum") or {}, 0)
    maximum = _expression_integer(expression.get("maximum") or {}, 0)
    if minimum is None or maximum is None:
        return None
    return {"minimum": minimum, "maximum": maximum}


def _surface_indexes(surface: dict[str, Any]) -> dict[str, Any]:
    if surface.get("schemaVersion") != 1 or surface.get("summary", {}).get("encounterCount") != 89:
        raise AuditError("P1b1 primary semantic surface schema/census drifted")
    if surface["summary"].get("nonNullOnePlayerPrimaries") != 89 or surface["summary"].get("nonNullTwoPlayerPrimaries") != 89:
        raise AuditError("P1b1 primary semantic surface lost a compiled primary")
    article: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    module: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    encounters: dict[str, dict[str, Any]] = {}
    for encounter_index, encounter in enumerate(surface["encounters"]):
        encounter_id = encounter["canonicalId"]
        if encounter_id in encounters:
            raise AuditError(f"duplicate semantic-surface encounter {encounter_id}")
        encounters[encounter_id] = {"index": encounter_index, "row": encounter}
        for body_index, body in enumerate(encounter["retainedBodies"]):
            ref = {"encounterIndex": encounter_index, "bodyIndex": body_index,
                   "encounter": encounter, "body": body}
            provenance = body["provenance"]
            a = provenance["article"]
            article.setdefault((a["pageKey"], a["revisionId"], a["template"], a["templateOrdinal"]), []).append(ref)
            m = provenance["module"]
            if not m.get("synthetic"):
                module.setdefault((m["path"], m["tableKey"], m["recordOrdinal"]), []).append(ref)
    return {"article": article, "module": module, "encounters": encounters}


def _body_refs(record: dict[str, Any], indexes: dict[str, Any], aliases: dict[tuple[Any, ...], str]) -> list[dict[str, Any]]:
    origin = record["origin"]
    if origin["kind"] == "page" and "template" in origin:
        key = (origin["pageKey"], origin["revisionId"], origin["template"], origin["templateOrdinal"])
        return indexes["article"].get(key, [])
    if origin["kind"] == "module":
        key = (origin["path"], origin["tableKey"], origin["recordOrdinal"])
        refs = indexes["module"].get(key, [])
        if refs:
            return refs
        encounter_id = aliases.get(key)
        if encounter_id:
            encounter_ref = indexes["encounters"][encounter_id]
            return [{"encounterIndex": encounter_ref["index"], "bodyIndex": None,
                     "encounter": encounter_ref["row"], "body": None}]
    return []


def _surface_pointer(ref: dict[str, Any], suffix: str = "") -> str:
    base = f"/encounters/{ref['encounterIndex']}"
    if ref.get("bodyIndex") is not None:
        base += f"/retainedBodies/{ref['bodyIndex']}"
    return base + suffix


def _source_model_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for ref in refs:
        if not ref.get("body"):
            continue
        for model in ref["body"]["sourceModels"]:
            for model_index, row in enumerate(ref["encounter"]["sourceModels"]):
                if row["canonicalModel"] != model:
                    continue
                key = (ref["encounterIndex"], model_index)
                if key not in seen:
                    seen.add(key)
                    result.append({**ref, "modelIndex": model_index, "model": row})
                break
    return result


def _state_coordinates(refs: list[dict[str, Any]], model_refs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    representations: list[dict[str, Any]] = []
    fact_ids: list[str] = []
    seen: set[tuple[int, str]] = set()
    for ref in refs:
        state_id = ref.get("body", {}).get("stateId") if ref.get("body") else None
        if not state_id:
            continue
        for model_ref in model_refs:
            if model_ref["encounterIndex"] != ref["encounterIndex"]:
                continue
            for state_index, state in enumerate(model_ref["model"]["states"]):
                if state.get("stateId") != state_id:
                    continue
                key = (model_ref["encounterIndex"], state_id)
                if key in seen:
                    continue
                seen.add(key)
                representations.append({
                    "layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                    "jsonPointer": (f"/encounters/{model_ref['encounterIndex']}/sourceModels/"
                                    f"{model_ref['modelIndex']}/states/{state_index}/stateId"),
                    "expectedValue": state_id,
                })
                fact_ids.append(state["factId"])
    return representations, fact_ids


def _primary_coordinates(refs: list[dict[str, Any]], suffix: str, *, expected: Any | None = None) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for ref in refs:
        body = ref.get("body")
        if not body:
            continue
        for player_index, player_row in enumerate(ref["encounter"]["primaryByPlayers"]):
            for body_ordinal in body["primaryBodyOrdinals"]:
                pointer = f"/encounters/{ref['encounterIndex']}/primaryByPlayers/{player_index}/bodies/{body_ordinal}{suffix}"
                if pointer in seen:
                    continue
                seen.add(pointer)
                row = {"layer": "primary-presentation", "path": PRIMARY_SEMANTIC_SURFACE,
                       "jsonPointer": pointer, "players": player_row["players"]}
                if expected is not None:
                    row["expectedValue"] = expected
                result.append(row)
    return result


def _wiki_coordinate(record: dict[str, Any], *, compared_lane: str | None = None) -> dict[str, Any]:
    row = {"layer": "wiki-origin", "originId": record["id"], "claimId": record["claimId"],
           "origin": record["origin"]}
    if compared_lane:
        row["comparedLane"] = compared_lane
    return row


def _p1b1_common(record: dict[str, Any], *, disposition: str, kind: str,
                  semantic: dict[str, Any], representations: list[dict[str, Any]],
                  closure: str, source_fact_refs: list[str], rationale: str,
                  severity: str = "low") -> dict[str, Any]:
    return {
        "id": "final-map-p1b1-" + record["id"].removeprefix("wiki-origin-v1-"),
        "originId": record["id"], "claimId": record["claimId"], "disposition": disposition,
        "semanticMapping": {"kind": kind, "originFamily": record["family"], **semantic},
        "authorityComparison": {
            "closure": closure, "sourceFactRefs": sorted(set(source_fact_refs)),
            "compactFactRefs": sorted(set(source_fact_refs)),
            "resolution": "source-wins" if disposition == "conflict" else "represented-as-scoped",
            "silentMerge": False,
        },
        "representation": representations,
        "rationale": rationale,
        "owner": "StS2 Companion P1b1 completeness review", "severity": severity,
        "reviewedForVersion": TARGET_VERSION,
    }


def _validate_wiki_coordinates(mapping: dict[str, Any], record: dict[str, Any]) -> None:
    for row in mapping["representation"]:
        if row.get("layer") != "wiki-origin":
            continue
        if row.get("originId") != record["id"] or row.get("claimId") != record["claimId"] or row.get("origin") != record["origin"]:
            raise AuditError(f"P1b1 mapping {mapping['id']} has stale wiki-origin coordinate")


def _mapping_for_identity(record: dict[str, Any], refs: list[dict[str, Any]], indexes: dict[str, Any],
                          p1_policy: dict[str, Any]) -> dict[str, Any]:
    normalized = record["normalized"]
    field, retained_value = normalized["field"], normalized["value"]
    if not refs:
        raise AuditError(f"P1b1 identity origin lacks exact provenance join: {record['id']}")
    source_refs = _source_model_refs(refs)
    source_fact_ids = [item["model"]["factId"] for item in source_refs]
    state_representations, state_fact_ids = _state_coordinates(refs, source_refs)
    source_fact_ids.extend(state_fact_ids)
    retained_coord = _surface_pointer(refs[0], f"/{'displayName' if field in {'Name', 'title'} else 'type'}") if refs[0].get("body") else None
    representations = [_wiki_coordinate(record), *state_representations]
    if field in {"Name", "title"}:
        if not source_refs or retained_coord is None:
            raise AuditError(f"P1b1 name origin lacks source body: {record['id']}")
        source_names = sorted(set(item["model"]["displayName"] for item in source_refs))
        source_name = source_names[0] if len(source_names) == 1 else source_names
        source_pointer = (f"/encounters/{source_refs[0]['encounterIndex']}/sourceModels/"
                          f"{source_refs[0]['modelIndex']}/displayName")
        if record["id"] in p1_policy["exceptions"]["eyeWithTeethConflictOriginIds"]:
            representations = [
                {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                 "jsonPointer": source_pointer, "comparedLane": "source"},
                {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                 "jsonPointer": retained_coord, "comparedLane": "retained"},
            ]
            return _p1b1_common(
                record, disposition="conflict", kind="actor-identity",
                semantic={"actorModels": sorted(set(x["model"]["canonicalModel"] for x in source_refs)),
                          "retainedValue": retained_value, "sourceValue": source_name,
                          "identityScope": "exact retained body title"},
                representations=representations, closure="closed", source_fact_refs=source_fact_ids,
                rationale="The exact retained body title capitalizes With while shipped source localizes it as lower-case with; source hero copy wins and both lanes remain Technical.",
                severity="medium")
        representations.append({"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                                "jsonPointer": retained_coord, "expectedValue": retained_value})
        representations.extend(_primary_coordinates(refs, "/displayName", expected=retained_value))
        return _p1b1_common(
            record, disposition="primary-present", kind="actor-state-identity",
            semantic={"actorModels": sorted(set(x["model"]["canonicalModel"] for x in source_refs)),
                      "stateIds": sorted(set(x["body"]["stateId"] for x in refs if x.get("body") and x["body"].get("stateId"))),
                      "retainedValue": retained_value, "sourceDisplay": source_name,
                      "identityScope": "exact retained body/state"},
            representations=representations, closure="closed", source_fact_refs=source_fact_ids,
            rationale="Exact generator provenance joins this body/state identity to checked source and to the compiled 1P/2P primary card; runtime-numbered state titles remain explicit.")
    if field == "Type":
        if retained_coord is None:
            # The only body-less Type is reviewed aggregate Knight Gang.
            retained_coord = _surface_pointer(refs[0], "/kind")
        representations.append({"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                                "jsonPointer": retained_coord})
        return _p1b1_common(
            record, disposition="audit-present", kind="actor-classification",
            semantic={"actorModels": sorted(set(x["model"]["canonicalModel"] for x in source_refs)),
                      "retainedValue": retained_value, "scope": "retained actor class, not encounter room class"},
            representations=representations, closure="unjoined", source_fact_refs=source_fact_ids,
            rationale="The retained actor class is reachable in Technical audit through exact body/aggregate provenance; practical encounter kind is not silently treated as every actor's class.")
    if field == "Debut":
        encounter_refs = sorted({ref["encounterIndex"] for ref in refs})
        representations.extend({"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                                "jsonPointer": f"/encounters/{index}/placement"} for index in encounter_refs)
        if retained_value == "The Lantern Key":
            disposition = "audit-present"
            rationale = "The exact event provenance closes The Lantern Key linkage; primary identifies a Hive event fight but does not render the event navigation title."
        else:
            disposition = "primary-present"
            for index in encounter_refs:
                representations.extend([
                    {"layer": "primary-presentation", "path": PRIMARY_SEMANTIC_SURFACE,
                     "jsonPointer": f"/encounters/{index}/primaryByPlayers/{players}/header/placement"}
                    for players in (0, 1)
                ])
            rationale = "Checked placement membership and exact generator ownership preserve the retained debut act on both compiled player-count primary surfaces."
        return _p1b1_common(
            record, disposition=disposition, kind="placement-membership",
            semantic={"retainedValue": retained_value,
                      "encounterIds": sorted(set(ref["encounter"]["canonicalId"] for ref in refs)),
                      "placements": [indexes["encounters"][ref["encounter"]["canonicalId"]]["row"]["placement"] for ref in refs]},
            representations=representations, closure="closed",
            source_fact_refs=[ref["encounter"]["placement"]["factId"] for ref in refs], rationale=rationale)
    if field in {"EncounterAliases", "Link"}:
        if retained_coord:
            representations.append({"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                                    "jsonPointer": _surface_pointer(refs[0], "/provenance")})
        else:
            representations.append({"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                                    "jsonPointer": _surface_pointer(refs[0])})
        return _p1b1_common(
            record, disposition="audit-present", kind="retained-navigation-alias",
            semantic={"retainedValue": retained_value,
                      "actorModels": sorted(set(x["model"]["canonicalModel"] for x in source_refs)),
                      "scope": "retained navigation or encounter alias only"},
            representations=representations, closure="notApplicable", source_fact_refs=source_fact_ids,
            rationale="This exact retained link/alias is useful reconciliation metadata and resolves through generator provenance, but URL/navigation copy is not promoted as practical mechanics.")
    raise AuditError(f"unsupported P1b1 identity field {field}")


def _mapping_for_hp(record: dict[str, Any], refs: list[dict[str, Any]], compact: dict[str, Any]) -> dict[str, Any]:
    if record["family"] == "patch-hp-fact":
        return _p1b1_common(
            record, disposition="missing/unparsed", kind="patch-hp-transition",
            semantic={"retainedValue": record["normalized"]["value"],
                      "scope": "historical before-to-after patch transition"},
            representations=[_wiki_coordinate(record)], closure="unjoined", source_fact_refs=[],
            rationale="The current endpoint is source-closed, but this atom asserts a historical before-to-after transition; a repeated current number is not proof and patch lifecycle projection remains P2.")
    if not refs:
        raise AuditError(f"P1b1 HP origin lacks exact provenance join: {record['id']}")
    field = record["normalized"]["field"]
    models = _source_model_refs(refs)
    source_fact_ids = [row["model"]["factId"] for row in models]
    state_representations, state_fact_ids = _state_coordinates(refs, models)
    source_fact_ids.extend(state_fact_ids)
    hp_numbers = [int(item.replace(",", "")) for item in re.findall(r"\d[\d,]*", record["normalized"]["value"])]
    if field == "HP" and len(hp_numbers) == 4:
        if record["normalized"].get("owner") != "Decimillipede":
            raise AuditError(f"unreviewed dual-range P1b1 HP atom: {record['id']}")
        normal = {"minimum": hp_numbers[0], "maximum": hp_numbers[1]}
        ascended = {"minimum": hp_numbers[2], "maximum": hp_numbers[3]}
        if not models or any(_below_a8_range(row["model"]["hp"]) != normal for row in models):
            raise AuditError("Decimillipede normal HP does not match all exact segment models")
        if any(ref["body"]["hpA8SinglePlayer"] != ascended for ref in refs):
            raise AuditError("Decimillipede A8 HP does not match all exact segment bodies")
        representations = [_wiki_coordinate(record), *state_representations]
        for row in models:
            representations.extend([
                {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                 "jsonPointer": f"/encounters/{row['encounterIndex']}/sourceModels/{row['modelIndex']}/hp/belowA8",
                 "expectedValue": normal},
                {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                 "jsonPointer": f"/encounters/{row['encounterIndex']}/sourceModels/{row['modelIndex']}/hp/a8SinglePlayer",
                 "expectedValue": ascended},
            ])
        representations.extend(_primary_coordinates(refs, "/hp/a8SinglePlayer", expected=ascended))
        return _p1b1_common(
            record, disposition="primary-present", kind="normal-and-a8-hp-ranges",
            semantic={"actorModels": sorted(set(row["model"]["canonicalModel"] for row in models)),
                      "normalValue": normal, "a8Value": ascended,
                      "scope": "shared starting HP for the three exact Decimillipede segment models"},
            representations=representations, closure="closed", source_fact_refs=source_fact_ids,
            rationale="The invoke field structurally carries normal and A8 ranges; both values match all three exact source segment models and A8 reaches each corresponding primary card.")
    retained = _range_claim(record["normalized"]["value"])
    if field in {"AscHP"}:
        state_ids = sorted(set(ref["body"]["stateId"] for ref in refs if ref["body"].get("stateId")))
        ownership_fact_ids = sorted(set(source_fact_ids))
        body_values = [ref["body"].get("hpA8SinglePlayer") for ref in refs]
        if not body_values or any(value != body_values[0] for value in body_values):
            raise AuditError(f"P1b1 A8 exact body values disagree for {record['id']}")
        surface_value = body_values[0]
        source_candidates = [{"ref": row, "value": row["model"]["hp"].get("a8SinglePlayer")} for row in models]
        same_scope_source = [] if state_ids else [row for row in source_candidates if _is_typed_hp_range(row["value"])]
        same_scope_values = {canonical_json_bytes(row["value"]) for row in same_scope_source}
        if len(same_scope_values) > 1:
            raise AuditError(f"P1b1 A8 exact source candidates disagree for {record['id']}")
        source_value = same_scope_source[0]["value"] if same_scope_source else None
        is_conflict = source_value is not None and source_value != retained
        if surface_value != (source_value if is_conflict else retained):
            raise AuditError(f"P1b1 A8 body/source value scope mismatch for {record['id']}")

        representations = [_wiki_coordinate(record, compared_lane="retained" if is_conflict else None),
                           *state_representations]
        for ref in refs:
            representations.append({
                "layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                "jsonPointer": _surface_pointer(ref, "/hpA8SinglePlayer"),
                "expectedValue": surface_value,
                "evidenceRole": "same-scope-source-value" if is_conflict else "typed-a8-body-value",
                **({"comparedLane": "source"} if is_conflict else {}),
            })
        primary_coordinates = _primary_coordinates(refs, "/hp/a8SinglePlayer", expected=surface_value)
        for row in primary_coordinates:
            row["evidenceRole"] = "primary-a8-single-player-value"
            if is_conflict:
                row["comparedLane"] = "source"
        representations.extend(primary_coordinates)
        for row in source_candidates:
            ref, value = row["ref"], row["value"]
            representations.append({
                "layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                "jsonPointer": (f"/encounters/{ref['encounterIndex']}/sourceModels/"
                                f"{ref['modelIndex']}/hp/a8SinglePlayer"),
                "expectedValue": value,
                "evidenceRole": "ownership-model-only" if state_ids else "same-scope-source-value",
                **({"comparedLane": "source"} if is_conflict else {}),
            })
        authorities = sorted(set(
            resolve_json_pointer({"row": ref["encounter"]},
                f"/row/primaryByPlayers/0/bodies/{ordinal}/hp/authority")
            for ref in refs for ordinal in ref["body"]["primaryBodyOrdinals"]
        ))
        value_source_fact_ids = [row["ref"]["model"]["factId"] for row in same_scope_source]
        source_candidate_values = [
            {"actorModel": row["ref"]["model"]["canonicalModel"], "a8SinglePlayer": row["value"],
             "scopeRelation": "different-state-ownership-model" if state_ids else "same-a8-scope"}
            for row in source_candidates
        ]
        authority_status = "source-conflict" if is_conflict else "source-closed" if source_value is not None else "retained-reference-only"
        return _p1b1_common(
            record, disposition="conflict" if is_conflict else "primary-present", kind="a8-hp-range",
            semantic={"actorModels": sorted(set(row["model"]["canonicalModel"] for row in models)),
                      "stateIds": state_ids, "retainedValue": retained,
                      **({"sourceValue": source_value} if is_conflict else {}),
                      "sourceOrFallbackValue": surface_value,
                      "sourceCandidateValues": source_candidate_values,
                      "ownershipFactRefs": ownership_fact_ids,
                      "authorityStatus": authority_status,
                      "primaryAuthority": authorities,
                      "scope": "A8 single-player HP for the exact body/state before configured player scaling; another state is ownership-only"},
            representations=representations, closure="closed" if source_value is not None else "knownUnknown",
            source_fact_refs=value_source_fact_ids,
            rationale=("The retained A8 value is stale against the exact same-body source/current value; source wins and the source model, compiled primary, and retained inventory lanes remain explicit."
                       if is_conflict else
                       "The exact A8 body/form value is typed on the primary semantic surface for both 1P/2P; source closure requires the same body scope, while state/form fallbacks remain labeled retained rather than source-closed."),
            severity="medium" if is_conflict else "low")
    # Normal/Base HP is intentionally Technical: primary is configured from A8.
    # A retained body/state ID establishes ownership only.  The exact retained
    # hpBelowA8 coordinate below is the value evidence; model HP is comparable
    # only for an unscoped/base body, never for a different lifecycle state.
    state_ids = sorted(set(ref["body"]["stateId"] for ref in refs if ref["body"].get("stateId")))
    ownership_fact_ids = sorted(set(source_fact_ids))
    retained_coordinates = []
    for ref in refs:
        body_value = ref["body"].get("hpBelowA8")
        if body_value != retained:
            raise AuditError(
                f"P1b1 HP exact retained value evidence mismatch for {record['id']}: "
                f"expected {retained}, found {body_value!r}"
            )
        if ref["body"].get("hpBelowA8Authority") != "retained-wiki-reference":
            raise AuditError(f"P1b1 HP retained authority is missing for {record['id']}")
        retained_coordinates.append({
            "layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
            "jsonPointer": _surface_pointer(ref, "/hpBelowA8"),
            "expectedValue": retained, "evidenceRole": "retained-normal-value",
        })

    source_candidates = []
    for row in models:
        value = _below_a8_range(row["model"]["hp"])
        source_candidates.append({"ref": row, "value": value})
    same_scope_source = [] if state_ids else [row for row in source_candidates if row["value"] is not None]
    same_scope_values = {canonical_json_bytes(row["value"]) for row in same_scope_source}
    if len(same_scope_values) > 1:
        raise AuditError(f"P1b1 HP exact source candidates disagree for {record['id']}")
    source_value = same_scope_source[0]["value"] if same_scope_source else None
    is_conflict = source_value is not None and source_value != retained

    representations = [_wiki_coordinate(record), *state_representations, *retained_coordinates]
    for row in source_candidates:
        ref, value = row["ref"], row["value"]
        source_representation = {
            "layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
            "jsonPointer": (f"/encounters/{ref['encounterIndex']}/sourceModels/"
                            f"{ref['modelIndex']}/hp/belowA8"),
            "expectedValue": value,
            "evidenceRole": ("ownership-model-only" if state_ids else
                             "same-scope-source-value" if value is not None else "same-scope-source-unknown"),
        }
        if is_conflict:
            source_representation["comparedLane"] = "source"
        representations.append(source_representation)
    if is_conflict:
        for row in retained_coordinates:
            row["comparedLane"] = "retained"
        # Wiki inventory remains provenance, not the retained value-bearing lane.
        representations[0] = _wiki_coordinate(record)

    runtime_starting_hp_effects = []
    if record["normalized"].get("owner") == "Punch Construct":
        for row in models:
            for initial_index, fact in enumerate(row["model"]["initialState"]):
                if fact["effect"].get("kind") in {"setState", "setCurrentHp"}:
                    runtime_starting_hp_effects.append(fact)
                    representations.append({
                        "layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                        "jsonPointer": (f"/encounters/{row['encounterIndex']}/sourceModels/"
                                        f"{row['modelIndex']}/initialState/{initial_index}"),
                        "evidenceRole": "runtime-starting-adjustment-not-base-hp",
                    })
                    ownership_fact_ids.append(fact["factId"])
    value_source_fact_ids = [row["ref"]["model"]["factId"] for row in same_scope_source]
    source_candidate_values = [
        {"actorModel": row["ref"]["model"]["canonicalModel"], "belowA8": row["value"],
         "scopeRelation": "different-state-ownership-model" if state_ids else "same-base-scope"}
        for row in source_candidates
    ]
    authority_status = "source-conflict" if is_conflict else "source-closed" if source_value is not None else "retained-reference-only"
    return _p1b1_common(
        record, disposition="conflict" if is_conflict else "audit-present", kind="normal-hp-range",
        semantic={"actorModels": sorted(set(row["model"]["canonicalModel"] for row in models)),
                  "stateIds": state_ids, "retainedValue": retained,
                  "sourceValue": source_value,
                  "sourceCandidateValues": source_candidate_values,
                  "ownershipFactRefs": sorted(set(ownership_fact_ids)),
                  "authorityStatus": authority_status,
                  "retainedFallbackSuppliesAuditValue": source_value is None,
                  "runtimeStartingHpEffects": runtime_starting_hp_effects,
                  "scope": "normal/below-A8 HP for the exact retained body/state; distinct from A8, another state, maximum HP, runtime starting reduction, and configured player scaling"},
        representations=representations, closure="closed" if source_value is not None else "knownUnknown",
        source_fact_refs=value_source_fact_ids,
        rationale=("Closed same-body source gives a different normal/base HP range; exact source and retained value coordinates remain separate and source wins."
                   if is_conflict else
                   "The exact retained normal/base HP value is typed in Technical audit; source closure is claimed only when the same unscoped body model has the identical below-A8 value, while state IDs and other-state model HP remain ownership evidence only."),
        severity="medium" if is_conflict else "low")



def _mapping_for_starting(record: dict[str, Any], refs: list[dict[str, Any]], compact: dict[str, Any],
                          conflict_review: dict[str, Any] | None) -> dict[str, Any]:
    if record["family"] == "patch-starting-power":
        return _p1b1_common(
            record, disposition="missing/unparsed", kind="patch-starting-power-transition",
            semantic={"retainedValue": record["normalized"]["value"],
                      "scope": "historical Galvanic A9 before-to-after transition"},
            representations=[_wiki_coordinate(record)], closure="unjoined", source_fact_refs=[],
            rationale="The current Galvanic endpoint is projected, but this exact historical 6-to-8 patch transition is not; patch lifecycle projection remains P2.")
    if not refs:
        raise AuditError(f"P1b1 starting-Power origin lacks exact provenance join: {record['id']}")
    normalized = record["normalized"]
    if normalized.get("parseStatus") != "typed" or not normalized.get("power"):
        raise AuditError(f"P1b1 starting-Power atom is not typed: {record['id']}")
    powers = compact["payload"]["sourceFacts"]["models"]["powers"]
    power_matches = [(index, row) for index, row in enumerate(powers) if row["englishTitle"] == normalized["power"]]
    if not power_matches:
        raise AuditError(f"P1b1 Power identity is absent from canonical title inventory: {record['id']}")
    model_refs = _source_model_refs(refs)
    candidate_ids = {row["canonicalId"] for _, row in power_matches}
    direct = []
    for model_ref in model_refs:
        for initial_index, fact in enumerate(model_ref["model"]["initialState"]):
            if fact["effect"].get("model") in candidate_ids:
                direct.append((model_ref, initial_index, fact))
    selected_ids = sorted(set(fact[2]["effect"]["model"] for fact in direct))
    selected_matches = [(index, row) for index, row in power_matches if row["canonicalId"] in selected_ids]
    if len(power_matches) > 1 and not selected_matches:
        raise AuditError(f"P1b1 duplicate Power title lacks exact owner disambiguation: {record['id']}")
    represented_matches = selected_matches or power_matches
    state_ids = sorted(set(ref["body"]["stateId"] for ref in refs if ref.get("body") and ref["body"].get("stateId")))
    state_representations, state_fact_ids = _state_coordinates(refs, model_refs)
    representations = [_wiki_coordinate(record), *state_representations]
    for power_index, power in represented_matches:
        representations.append({"layer": "technical-audit", "path": "data/encounter-facts-v0.111.0.json",
                                "jsonPointer": f"/payload/sourceFacts/models/powers/{power_index}/canonicalId",
                                "expectedValue": power["canonicalId"]})
    source_fact_ids = [power["factId"] for _, power in represented_matches] + state_fact_ids
    source_expressions = []
    for model_ref, initial_index, fact in direct:
        pointer = (f"/encounters/{model_ref['encounterIndex']}/sourceModels/{model_ref['modelIndex']}"
                   f"/initialState/{initial_index}")
        representations.append({"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                                "jsonPointer": pointer})
        source_fact_ids.append(fact["factId"])
        source_expressions.append(fact["baseValue"])

    # Join the exact normalized title and optional A9 amount to typed body tokens.
    # A title-only origin is a weaker compatible identity claim; an explicit amount
    # must equal the current joined A9 token before practical presence is credited.
    at_a9_matches = []
    body_refs = [ref for ref in refs if ref.get("body")]
    if not body_refs:
        raise AuditError(f"P1b1 starting-Power origin lacks an exact retained body: {record['id']}")
    for ref in body_refs:
        tokens = ref["body"].get("startingPowerTokens", {}).get("atA9")
        if not isinstance(tokens, list):
            raise AuditError(f"P1b1 starting-Power A9 token surface is malformed: {record['id']}")
        title_matches = [(index, token) for index, token in enumerate(tokens)
                         if token.get("title") == normalized["power"]]
        if len(title_matches) != 1:
            raise AuditError(f"P1b1 starting-Power title has no unique exact body token: {record['id']}")
        token_index, token = title_matches[0]
        at_a9_matches.append((ref, token_index, token))
    current_token_values = {json.dumps(token, sort_keys=True, separators=(",", ":"))
                            for _, _, token in at_a9_matches}
    if len(current_token_values) != 1:
        raise AuditError(f"P1b1 starting-Power joined bodies disagree on the current token: {record['id']}")
    current_token = at_a9_matches[0][2]
    retained_token = {"title": normalized["power"]}
    retained_amount = normalized.get("amountAtA9")
    if retained_amount is not None:
        retained_token["amount"] = retained_amount
    is_conflict = retained_amount is not None and current_token.get("amount") != retained_amount
    if is_conflict != (conflict_review is not None):
        raise AuditError(f"P1b1 starting-Power conflict review drifted: {record['id']}")
    configured_matches = []
    for ref in body_refs:
        configured_rows = ref["body"].get("startingPowerTokens", {}).get("configuredByPlayers")
        if not isinstance(configured_rows, list) or len(configured_rows) != len(ref["encounter"]["primaryByPlayers"]):
            raise AuditError(f"P1b1 starting-Power configured token surface is malformed: {record['id']}")
        for player_index, configured in enumerate(configured_rows):
            player_row = ref["encounter"]["primaryByPlayers"][player_index]
            if configured.get("players") != player_row.get("players") or not isinstance(configured.get("tokens"), list):
                raise AuditError(f"P1b1 starting-Power player token scope drifted: {record['id']}")
            title_matches = [(index, token) for index, token in enumerate(configured["tokens"])
                             if token.get("title") == normalized["power"]]
            if len(title_matches) > 1:
                raise AuditError(f"P1b1 starting-Power title has duplicate configured tokens: {record['id']}")
            if not title_matches:
                raise AuditError(f"P1b1 starting-Power title has no exact configured token: {record['id']}")
            token_index, token = title_matches[0]
            configured_matches.append((ref, player_index, token_index, token))

    shown = []
    shown_complete = True
    for ref in body_refs:
        for player_index, player in enumerate(ref["encounter"]["primaryByPlayers"]):
            for body_ordinal in ref["body"]["primaryBodyOrdinals"]:
                is_shown = player["bodies"][body_ordinal]["startingStateShown"] is True
                shown_complete = shown_complete and is_shown
                if is_shown:
                    shown.append((ref, player_index, body_ordinal))
    practical_present = bool(configured_matches) and shown_complete and bool(shown)

    current_reference_fallback = bool(normalized.get("amountAtA9") is not None and direct and
                                      any(_expression_integer(fact[2]["baseValue"].get("expression") or {}, 9) is None
                                          for fact in direct))
    closure = "knownUnknown" if current_reference_fallback else "closed" if direct or state_ids else "knownUnknown"
    fallback = current_reference_fallback and not is_conflict
    configured_tokens = []
    configured_seen = set()
    for ref, player_index, _, token in configured_matches:
        players = ref["encounter"]["primaryByPlayers"][player_index]["players"]
        key = (players, json.dumps(token, sort_keys=True, separators=(",", ":")))
        if key not in configured_seen:
            configured_seen.add(key)
            configured_tokens.append({"players": players, "token": token})
    if conflict_review is not None:
        required_review = {"originId", "claimId", "retainedAtA9Token", "currentAtA9Token",
                           "currentConfiguredTokensByPlayers", "rationale"}
        if (set(conflict_review) != required_review or conflict_review["originId"] != record["id"] or
                conflict_review["claimId"] != record["claimId"] or len(conflict_review["rationale"]) < 20 or
                conflict_review["retainedAtA9Token"] != retained_token or
                conflict_review["currentAtA9Token"] != current_token or
                conflict_review["currentConfiguredTokensByPlayers"] != configured_tokens):
            raise AuditError(f"P1b1 starting-Power conflict value guard drifted: {record['id']}")

    semantic = {"actorModels": sorted(set(row["model"]["canonicalModel"] for row in model_refs)),
                "stateIds": state_ids, "powerIds": [power["canonicalId"] for _, power in represented_matches],
                "powerTitle": normalized["power"],
                "baseAmount": normalized.get("baseAmount"), "amountAtA9": normalized.get("amountAtA9"),
                "ascensionAmounts": normalized.get("ascensionAmounts", []),
                "currentAtA9Token": current_token, "configuredTokensByPlayers": configured_tokens,
                "sourceValueExpressions": source_expressions,
                "currentReferenceFallbackSuppliesPrimaryAmount": current_reference_fallback,
                "retainedFallbackSuppliesPrimaryAmount": fallback,
                "scope": "one exact starting Power identity/stack on its retained body or state"}
    if is_conflict:
        semantic.update({"retainedValue": retained_token, "sourceValue": current_token,
                         "sourceOrFallbackValue": current_token})
        source_ref, token_index, _ = at_a9_matches[0]
        representations = [
            {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
             "jsonPointer": _surface_pointer(source_ref, f"/startingPowerTokens/atA9/{token_index}"),
             "expectedValue": current_token, "comparedLane": "source"},
        ]
        for ref, player_index, configured_index, token in configured_matches:
            representations.append({
                "layer": "primary-presentation", "path": PRIMARY_SEMANTIC_SURFACE,
                "jsonPointer": _surface_pointer(
                    ref, f"/startingPowerTokens/configuredByPlayers/{player_index}/tokens/{configured_index}"),
                "expectedValue": token, "comparedLane": "source",
                "players": ref["encounter"]["primaryByPlayers"][player_index]["players"],
            })
        representations.append(_wiki_coordinate(record, compared_lane="retained"))
        disposition = "conflict"
        rationale = ("The exact retained starting-Power amount conflicts with the current typed A9 body token; "
                     "the current source/reference lane wins and both values remain explicit without crediting stale practical copy.")
    else:
        for ref, token_index, token in at_a9_matches:
            representations.extend([
                {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                 "jsonPointer": _surface_pointer(ref, "/startsWithA9"),
                 "expectedValue": ref["body"]["startsWithA9"]},
                {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                 "jsonPointer": _surface_pointer(ref, f"/startingPowerTokens/atA9/{token_index}"),
                 "expectedValue": token},
            ])
        for ref, player_index, token_index, token in configured_matches:
            representations.append({
                "layer": "primary-presentation", "path": PRIMARY_SEMANTIC_SURFACE,
                "jsonPointer": _surface_pointer(
                    ref, f"/startingPowerTokens/configuredByPlayers/{player_index}/tokens/{token_index}"),
                "expectedValue": token,
                "players": ref["encounter"]["primaryByPlayers"][player_index]["players"],
            })
        for ref, player_index, body_ordinal in shown:
            representations.append({"layer": "primary-presentation", "path": PRIMARY_SEMANTIC_SURFACE,
                                    "jsonPointer": (f"/encounters/{ref['encounterIndex']}/primaryByPlayers/"
                                                    f"{player_index}/bodies/{body_ordinal}/startingStateShown"),
                                    "expectedValue": True,
                                    "players": ref["encounter"]["primaryByPlayers"][player_index]["players"]})
        disposition = "primary-present" if practical_present else "audit-present"
        rationale = ("The exact normalized Power title and optional A9 amount match typed body and 1P/2P tokens; generator provenance binds the body/state and compiled-card coordinates prove practical starting-state reachability without claiming full Power-description semantics."
                     if practical_present else
                     "The exact starting identity/amount and direct source fact remain Technical; the specialized primary lacks a complete typed starting-state coordinate, so this is not optimistically called primary-present.")
    return _p1b1_common(
        record, disposition=disposition, kind="starting-power-stack", semantic=semantic,
        representations=representations, closure=closure, source_fact_refs=source_fact_ids,
        rationale=rationale, severity="medium" if is_conflict else "low")


def _mapping_for_prose(record: dict[str, Any], review: dict[str, Any], indexes: dict[str, Any]) -> dict[str, Any]:
    encounter_refs = [indexes["encounters"].get(encounter_id) for encounter_id in review["encounterIds"]]
    if any(row is None for row in encounter_refs):
        raise AuditError(f"P1b1 prose review has unresolved encounter: {record['id']}")
    source_rows = []
    representations = [_wiki_coordinate(record)]
    source_fact_ids = []
    for item in encounter_refs:
        index, encounter = item["index"], item["row"]
        typed = {"encounterId": encounter["canonicalId"], "roster": encounter["roster"],
                 "production": encounter["production"], "placement": encounter["placement"]}
        source_rows.append(typed)
        source_fact_ids.extend([encounter["factId"], encounter["placement"]["factId"]])
        representations.append({"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
                                "jsonPointer": f"/encounters/{index}/roster"})
        if review["claimKind"] != "placement-context":
            representations.extend([
                {"layer": "primary-presentation", "path": PRIMARY_SEMANTIC_SURFACE,
                 "jsonPointer": f"/encounters/{index}/primaryByPlayers/{players}"}
                for players in (0, 1)
            ])
    semantic = {
        "retainedClaim": record["normalized"]["value"], "claimKind": review["claimKind"],
        "relation": review["relation"], "scope": review["scope"], "sourceSemantics": source_rows,
    }
    if review["disposition"] == "conflict":
        if len(source_rows) != 1:
            raise AuditError(f"P1b1 roster conflict is not exactly scoped: {record['id']}")
        semantic["retainedValue"] = {
            "smallBranch": {"draws": "fixed distinct Leaf plus Twig", "duplicatesPossible": False},
        }
        semantic["sourceValue"] = source_rows[0]["roster"]["grammar"]
        representations = [
            {"layer": "technical-audit", "path": PRIMARY_SEMANTIC_SURFACE,
             "jsonPointer": f"/encounters/{encounter_refs[0]['index']}/roster/grammar", "comparedLane": "source"},
            _wiki_coordinate(record, compared_lane="retained"),
        ]
        rationale = "The retained Strangler small branch forces one Leaf plus one Twig, while closed source performs two independent uniform small-slime draws and permits duplicates; both lanes remain explicit."
    elif review["claimKind"] == "produced-roster":
        rationale = "This exact claim is mapped to typed production facts and produced primary roles, never to the initial roster; actor/count scope remains explicit."
    else:
        rationale = "This exact reviewed prose atom maps to the scoped source roster/placement semantics it actually asserts; omitted order, independence, or replacement constraints are not credited to the retained claim."
    return _p1b1_common(
        record, disposition=review["disposition"], kind="roster-or-lead-claim",
        semantic=semantic, representations=representations,
        closure="closed", source_fact_refs=source_fact_ids, rationale=rationale,
        severity="high" if review["disposition"] == "conflict" else "low")


def apply_p1b1_mappings(records: list[dict[str, Any]], p1_policy: dict[str, Any], *,
                         compact: dict[str, Any], primary_surface: dict[str, Any]) -> dict[str, Any]:
    required = {"schemaVersion", "phase", "reviewedForVersion", "reviewer", "targetCategories",
                "expectedTargetCount", "expectedFamilyCounts", "expectedOrigins",
                "aggregateOwnerAliases", "proseReviews", "exceptions", "reviewNotes"}
    if set(p1_policy) != required or p1_policy["schemaVersion"] != 1 or p1_policy["phase"] != "P1b1":
        raise AuditError("P1b1 reviewed policy schema drifted")
    if p1_policy["reviewedForVersion"] != TARGET_VERSION or set(p1_policy["targetCategories"]) != P1B1_TARGET_CATEGORIES:
        raise AuditError("P1b1 reviewed policy target/version drifted")
    targets = [record for record in records
               if record["category"] in P1B1_TARGET_CATEGORIES and record["reviewState"] == "captured-unreconciled"]
    actual_guards = [{"originId": row["id"], "claimId": row["claimId"], "family": row["family"]}
                     for row in sorted(targets, key=lambda item: item["id"])]
    if actual_guards != p1_policy["expectedOrigins"]:
        raise AuditError("P1b1 target origin/claim guards are stale or a future target origin is unreviewed")
    if len(targets) != p1_policy["expectedTargetCount"]:
        raise AuditError("P1b1 target family count drifted")
    family_counts = _counter(targets, "family")
    if family_counts != p1_policy["expectedFamilyCounts"]:
        raise AuditError(f"P1b1 exact family counts drifted: {family_counts}")
    indexes = _surface_indexes(primary_surface)
    aliases: dict[tuple[Any, ...], str] = {}
    for alias in p1_policy["aggregateOwnerAliases"]:
        key = (alias["path"], alias["tableKey"], alias["recordOrdinal"])
        if key in aliases or alias["encounterId"] not in indexes["encounters"] or len(alias["rationale"]) < 20:
            raise AuditError("P1b1 aggregate owner alias is duplicate/unresolved/unreviewed")
        aliases[key] = alias["encounterId"]
    prose = {row["originId"]: row for row in p1_policy["proseReviews"]}
    if len(prose) != len(p1_policy["proseReviews"]):
        raise AuditError("duplicate P1b1 prose review")
    for row in prose.values():
        conflict_relation = str(row.get("relation", "")).startswith("conflict")
        if conflict_relation != (row.get("disposition") == "conflict"):
            raise AuditError("P1b1 prose conflict relation/disposition mismatch")
    conflict_review_rows = p1_policy["exceptions"].get("startingPowerConflictReviews")
    if not isinstance(conflict_review_rows, list):
        raise AuditError("P1b1 starting-Power conflict reviews are missing")
    starting_conflicts = {row.get("originId"): row for row in conflict_review_rows if isinstance(row, dict)}
    if len(starting_conflicts) != len(conflict_review_rows) or None in starting_conflicts:
        raise AuditError("P1b1 starting-Power conflict reviews are duplicate or malformed")
    target_ids = {record["id"] for record in targets if record["category"] == "starting-power-status-stack"}
    if not set(starting_conflicts).issubset(target_ids):
        raise AuditError("P1b1 starting-Power conflict review has an unknown origin")
    documents = _mapping_documents({}, compact, {}, primary_surface)
    # Only compact/surface paths are used by P1b1 validation; empty placeholders
    # ensure accidental raw/book pointers fail resolution rather than read stale data.
    disposition_counts: dict[str, int] = {}
    mapped_ids = []
    for record in targets:
        refs = _body_refs(record, indexes, aliases)
        if record["family"] in {"article-identity-field", "module-identity-field"}:
            mapping = _mapping_for_identity(record, refs, indexes, p1_policy)
        elif record["category"] == "hp-ascension-scaling":
            mapping = _mapping_for_hp(record, refs, compact)
        elif record["category"] == "starting-power-status-stack":
            mapping = _mapping_for_starting(record, refs, compact, starting_conflicts.get(record["id"]))
        elif record["family"] in {"article-lead", "article-roster", "module-roster"}:
            review = prose.get(record["id"])
            if not review or review["claimId"] != record["claimId"]:
                raise AuditError(f"missing/stale P1b1 prose review: {record['id']}")
            mapping = _mapping_for_prose(record, review, indexes)
        else:
            raise AuditError(f"unsupported P1b1 target family {record['family']}")
        _validate_wiki_coordinates(mapping, record)
        # Validate resolvable non-wiki coordinates with existing strict pointer/value/lane checks.
        non_wiki = [row for row in mapping["representation"] if row["layer"] != "wiki-origin"]
        if non_wiki:
            candidate = {**mapping, "representation": non_wiki}
            _validate_representation(candidate, documents,
                                     require_conflict_lanes=False)
        if record["category"] == "hp-ascension-scaling":
            _validate_hp_value_evidence(mapping, documents)
        if mapping["disposition"] == "conflict":
            lanes = {row["comparedLane"] for row in mapping["representation"] if "comparedLane" in row}
            if lanes != {"source", "retained"}:
                raise AuditError(f"P1b1 conflict {mapping['id']} lacks exact both-lane representation")
        _attach_mapping(record, mapping)
        mapped_ids.append(record["id"])
        disposition_counts[mapping["disposition"]] = disposition_counts.get(mapping["disposition"], 0) + 1
    if set(prose) != {row["id"] for row in targets if row["family"] in {"article-lead", "article-roster", "module-roster"}}:
        raise AuditError("P1b1 prose policy has unused or missing exact origins")
    return {"mappedOriginIds": sorted(mapped_ids), "dispositionCounts": dict(sorted(disposition_counts.items())),
            "familyCounts": family_counts, "atomizationCorrection": {
                "priorSnapshotOriginCount": 4433, "correctedOriginCount": 4438,
                "addedStartingPowerOrigins": 5,
                "reason": "Four comma-separated Test Subject Power atoms and Tough Egg Minion/Hatch were split into exact per-Power origins.",
            }}

def _validate_policy(policy: dict[str, Any]) -> None:
    required = {
        "schemaVersion", "targetVersion", "targetBranch", "review",
        "expectedCategoryCounts", "expectedFamilyCounts", "exclusionPolicies",
        "snapshotGapWaivers", "patchEnemyFactClassifications", "tombstones",
        "approvedOriginReclassifications", "finalMappings",
    }
    if not required.issubset(policy):
        raise AuditError(f"policy lacks keys: {sorted(required - set(policy))}")
    if policy["targetVersion"] != TARGET_VERSION or policy["targetBranch"] != TARGET_BRANCH:
        raise AuditError("policy target version/branch mismatch")
    ids = [item.get("id") for item in policy["exclusionPolicies"]]
    if None in ids or len(ids) != len(set(ids)):
        raise AuditError("exclusion policy IDs are missing or duplicate")
    for item in policy["exclusionPolicies"]:
        if not item.get("reviewer") or not item.get("reviewedForVersion") or not item.get("scope"):
            raise AuditError(f"exclusion policy {item.get('id')} lacks review metadata/scope")
        if item["reviewedForVersion"] != TARGET_VERSION:
            raise AuditError(f"exclusion policy {item['id']} has wrong reviewed version")
        if len(item.get("rationale", "").strip()) < 20:
            raise AuditError(f"exclusion policy {item['id']} lacks concrete rationale")
    for ledger_name, origin_key in (("tombstones", "originId"),
                                    ("approvedOriginReclassifications", "fromOriginId")):
        ledger_ids: set[str] = set()
        for item in policy[ledger_name]:
            required_ledger = {"id", origin_key, "rationale", "reviewer", "reviewedForVersion"}
            if not required_ledger.issubset(item):
                raise AuditError(f"{ledger_name} entry lacks {sorted(required_ledger - set(item))}")
            if item["id"] in ledger_ids:
                raise AuditError(f"duplicate {ledger_name} ID {item['id']}")
            ledger_ids.add(item["id"])
            if item["reviewedForVersion"] != TARGET_VERSION or len(item["rationale"].strip()) < 20:
                raise AuditError(f"{ledger_name} entry {item['id']} lacks version-scoped concrete review")
    mappings = policy["finalMappings"]
    mapping_required = {
        "schemaVersion", "allowedDispositions", "allowedSemanticKinds", "allowedLayers",
        "allowedClosures", "expectedFinalMappedCount", "expectedConflictOriginCount",
        "expectedStaleOriginCount", "expectedCompactTitleConflictCount",
        "researchCountCorrections", "records", "structuralRules", "compactTitleConflictCrossLinks",
    }
    if not mapping_required.issubset(mappings):
        raise AuditError(f"finalMappings lacks keys: {sorted(mapping_required - set(mappings))}")
    if set(mappings["allowedDispositions"]) != FINAL_DISPOSITIONS:
        raise AuditError("finalMappings allowed dispositions drifted")
    mapping_ids = []
    origin_ids = []
    for item in mappings["records"]:
        item_required = {
            "id", "originId", "claimId", "disposition", "semanticMapping", "authorityComparison",
            "representation", "rationale", "owner", "severity", "reviewedForVersion",
        }
        if not item_required.issubset(item):
            raise AuditError(f"final mapping {item.get('id')} lacks {sorted(item_required - set(item))}")
        mapping_ids.append(item["id"])
        origin_ids.append(item["originId"])
        if item["reviewedForVersion"] != TARGET_VERSION or len(item["rationale"].strip()) < 20:
            raise AuditError(f"final mapping {item['id']} lacks version-scoped concrete review")
        if item["disposition"] not in FINAL_DISPOSITIONS:
            raise AuditError(f"final mapping {item['id']} has unsupported disposition")
        if item["semanticMapping"].get("kind") not in mappings["allowedSemanticKinds"]:
            raise AuditError(f"final mapping {item['id']} has unsupported kind")
        for coord in item["representation"]:
            if coord.get("layer") not in mappings["allowedLayers"]:
                raise AuditError(f"final mapping {item['id']} has unsupported layer")
    for rule in mappings["structuralRules"]:
        rule_required = {
            "id", "disposition", "match", "expectedCount", "expectedOriginIds", "semanticMapping",
            "authorityComparison", "representation", "rationale", "owner", "severity", "reviewedForVersion",
        }
        if not rule_required.issubset(rule):
            raise AuditError(f"structural rule {rule.get('id')} lacks {sorted(rule_required - set(rule))}")
        mapping_ids.append(rule["id"])
        if len(rule["expectedOriginIds"]) != rule["expectedCount"]:
            raise AuditError(f"structural rule {rule['id']} expected count does not match ID set")
        if rule["expectedOriginIds"] != sorted(rule["expectedOriginIds"]):
            raise AuditError(f"structural rule {rule['id']} expectedOriginIds must be sorted")
        if len(set(rule["expectedOriginIds"])) != len(rule["expectedOriginIds"]):
            raise AuditError(f"structural rule {rule['id']} has duplicate expected IDs")
        origin_ids.extend(rule["expectedOriginIds"])
    if len(mapping_ids) != len(set(mapping_ids)):
        raise AuditError("duplicate final-mapping IDs")
    if len(origin_ids) != len(set(origin_ids)):
        raise AuditError("duplicate final-mapping origin IDs")
    title_spec = mappings["compactTitleConflictCrossLinks"]
    if title_spec.get("expectedCount") != mappings["expectedCompactTitleConflictCount"]:
        raise AuditError("compact title conflict expected count mismatch")
    if len(title_spec.get("expectedConflictIds") or []) != title_spec["expectedCount"]:
        raise AuditError("compact title conflict ID set/count mismatch")


def _manifest_paths(root: Path) -> list[str]:
    paths = [
        "tools/.wiki/pages.json", "tools/.wiki/index.json",
        *[f"tools/.wiki/{stem}.lua" for stem in MODULE_STEMS],
        "data/encounters.json", "data/game-v0.111.0-source.json",
        "data/encounter-facts-v0.111.0.json", PRIMARY_SEMANTIC_SURFACE,
        DEFAULT_POLICY, DEFAULT_P1B1_POLICY, "tools/primary-semantic-aliases-v0.111.0.json",
        "tools/generate-book.py", "tools/generate-primary-semantic-surface.mjs",
        "tools/retained_wiki.py", "tools/audit-retained-wiki.py", "tools/run-python-tests.py",
        "src/book.mjs", "src/source-presentation.mjs", "package.json", "README.md",
    ]
    paths.extend(str(path.relative_to(root)) for path in sorted((root / "docs").glob("*.md")))
    return paths


def _build_input_manifest(root: Path) -> dict[str, dict[str, Any]]:
    return {path: digest_file(root / path) for path in _manifest_paths(root)}


def _module_manifest(root: Path, index: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    try:
        entries = index["query"]["allpages"]
    except (KeyError, TypeError) as exc:
        raise AuditError("index.json lacks query.allpages") from exc
    if not isinstance(entries, list):
        raise AuditError("index.json query.allpages is not a list")
    listed: list[dict[str, Any]] = []
    present: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    indexed_paths: set[str] = set()
    waivers = {item["expectedPath"]: item for item in policy["snapshotGapWaivers"]}
    for entry in sorted(entries, key=lambda item: item["title"]):
        title = entry.get("title")
        if not isinstance(title, str) or "/" not in title:
            raise AuditError(f"malformed module index entry {entry!r}")
        stem = title.rsplit("/", 1)[-1]
        path = f"tools/.wiki/{stem}.lua"
        indexed_paths.add(path)
        item = {"pageId": entry.get("pageid"), "namespace": entry.get("ns"), "title": title, "expectedPath": path}
        listed.append(item)
        absolute = root / path
        if absolute.exists():
            text = absolute.read_text(encoding="utf-8")
            item = {**item, **digest_file(absolute), "recordCount": len(list(_iter_lua_records(text)))}
            present.append(item)
        else:
            waiver = waivers.get(path)
            if not waiver:
                raise AuditError(f"index-listed module {path} is absent without exact approved snapshot gap")
            if waiver.get("moduleTitle") != title or waiver.get("pageId") != entry.get("pageid"):
                raise AuditError(f"snapshot gap waiver does not exactly match {title}")
            missing.append({
                **item,
                "snapshotGap": {
                    "id": waiver["id"],
                    "status": "approved-version-scoped-waiver",
                    "reviewedForVersion": waiver["reviewedForVersion"],
                    "reviewer": waiver["reviewer"],
                    "rationale": waiver["rationale"],
                    "fabricatedEmptyModule": False,
                },
            })
    actual_paths = {str(path.relative_to(root)) for path in (root / "tools/.wiki").glob("*.lua")}
    unindexed = sorted(actual_paths - indexed_paths)
    if unindexed:
        raise AuditError(f"retained Lua files absent from index manifest: {unindexed}")
    return {
        "listedCount": len(listed), "presentCount": len(present), "missingCount": len(missing),
        "listed": listed, "present": present, "missing": missing, "unindexedPresent": unindexed,
    }


def _counter(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for record in records:
        value = record[key]
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _validate_expected_counts(policy: dict[str, Any], category_counts: dict[str, int], family_counts: dict[str, int]) -> None:
    expected_categories = dict(sorted(policy["expectedCategoryCounts"].items()))
    expected_families = dict(sorted(policy["expectedFamilyCounts"].items()))
    if category_counts != expected_categories:
        raise AuditError(f"category denominator drift: expected {expected_categories}, derived {category_counts}")
    if family_counts != expected_families:
        missing = {key: (expected_families.get(key), family_counts.get(key))
                   for key in sorted(set(expected_families) | set(family_counts))
                   if expected_families.get(key) != family_counts.get(key)}
        raise AuditError(f"family denominator drift: {missing}")


def _source_layer_denominators(raw: dict[str, Any], compact: dict[str, Any], book: dict[str, Any]) -> dict[str, Any]:
    try:
        encounter_counts = raw["encounterCensus"]["counts"]
        model_counts = raw["monsterCensus"]["counts"]
        source_facts = compact["payload"]["sourceFacts"]
        projection_ready = compact["payload"]["readiness"]["runtimeScopes"]["encounterProjection"]["ready"]
        global_ready = compact["payload"]["readiness"]["global"]["ready"]
        encounters = book["encounters"]
        archive_encounters = book["archive"]["encounters"]
        references = book["retainedReferences"]
        membership = book["meta"]["membership"]
        wiki_pages = book["meta"]["wikiPages"]
        archived_pages = book["meta"]["archivedWikiPages"]
    except (KeyError, TypeError) as exc:
        raise AuditError("source/compact/book denominator path is malformed") from exc
    if "DOORMAKER_BOSS" in encounters or "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER" in encounters:
        raise AuditError("archive/reference records leaked into current retained encounters")
    if set(archive_encounters) != {"DOORMAKER_BOSS"}:
        raise AuditError("retained archive must contain exactly DOORMAKER_BOSS")
    if set(references) != {"MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER"}:
        raise AuditError("retained references must contain exactly Mysterious Knight")
    if references["MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER"].get("notACurrentSelector") is not True:
        raise AuditError("Mysterious Knight retained reference must not be a current selector")
    current_body_ids = {
        body["monsterId"]
        for encounter in encounters.values()
        for body in encounter.get("lineup", [])
        if body.get("monsterId")
    }
    archive_body_ids = {
        body["monsterId"]
        for encounter in archive_encounters.values()
        for body in encounter.get("lineup", [])
        if body.get("monsterId")
    }
    current_page_titles = {item["title"].removeprefix("Slay the Spire 2:") for item in wiki_pages}
    archive_page_titles = {item["title"].removeprefix("Slay the Spire 2:") for item in archived_pages}
    if "Mysterious Knight" not in current_page_titles or "Doormaker" in current_page_titles:
        raise AuditError("current retained wiki pages still invert Mysterious Knight/Doormaker membership")
    if archive_page_titles != {"Doormaker"}:
        raise AuditError("archived retained wiki pages are not exclusively Doormaker")
    result = {
        "currentSourceEncounters": encounter_counts["currentTotal"],
        "currentSourceOrdinaryEncounters": encounter_counts["currentOrdinary"],
        "currentSourceEventEncounters": encounter_counts["currentEvent"],
        "currentReachableSourceModels": model_counts["totalReachable"],
        "compactMoves": len(source_facts["moves"]),
        "compactStates": len(source_facts["states"]),
        "retainedCurrentEncounters": len(encounters),
        "retainedArchivedEncounters": len(archive_encounters),
        "retainedCurrentReferences": len(references),
        "retainedCurrentBodyIds": len(current_body_ids),
        "retainedArchivedBodyIds": len(archive_body_ids),
        "retainedCurrentWikiPages": len(wiki_pages),
        "retainedArchivedWikiPages": len(archived_pages),
        "declaredEncounterProjectionScopeReady": bool(projection_ready),
        "globalSourceExtractionReady": bool(global_ready),
        "bookMembership": membership,
    }
    expected = {
        "currentSourceEncounters": 89,
        "currentSourceOrdinaryEncounters": 81,
        "currentSourceEventEncounters": 8,
        "currentReachableSourceModels": 108,
        "compactMoves": 315,
        "compactStates": 8,
        "retainedCurrentEncounters": 81,
        "retainedArchivedEncounters": 1,
        "retainedCurrentReferences": 1,
        "retainedCurrentBodyIds": 105,
        "retainedArchivedBodyIds": 1,
        "retainedCurrentWikiPages": 73,
        "retainedArchivedWikiPages": 1,
        "declaredEncounterProjectionScopeReady": True,
        "globalSourceExtractionReady": False,
        "bookMembership": {
            "currentEncounters": 81,
            "archivedEncounters": 1,
            "currentRetainedReferences": 1,
            "currentWikiPages": 73,
            "archivedWikiPages": 1,
            "currentBodyIds": 105,
            "archivedBodyIds": 1,
            "currentReferenceBodyIds": 1,
        },
    }
    if result != expected:
        raise AuditError(f"source-layer denominator drift: expected {expected}, derived {result}")
    return result


def _validate_review_corrections(root: Path, records: list[dict[str, Any]], book: dict[str, Any]) -> list[dict[str, Any]]:
    kin = [record for record in records
           if record["family"] == "module-identity-field"
           and record["origin"].get("tableKey") == "Kin Follower"
           and record["origin"].get("field") == "Type"]
    if len(kin) != 1 or kin[0]["origin"]["path"] != "tools/.wiki/Bosses.lua" or kin[0]["excerpt"] != "Boss":
        raise AuditError("Kin Follower bad Type=Boss origin correction no longer resolves exactly to Bosses.lua")
    fabricator = book.get("encounters", {}).get("FABRICATOR_NORMAL")
    if not fabricator:
        raise AuditError("retained book lacks FABRICATOR_NORMAL")
    lineup = fabricator.get("lineup", [])
    initial = [body.get("displayName") for body in lineup if body.get("role") != "summoned"]
    summoned = sorted(body.get("displayName") for body in lineup if body.get("role") == "summoned")
    if initial != ["Fabricator"] or summoned != ["Guardbot", "Noisebot", "Stabbot", "Zapbot"]:
        raise AuditError("Fabricator retained-book initial/summoned structure drifted")
    book_bytes = (root / "data/encounters.json").read_bytes()
    compact_bytes = (root / "data/encounter-facts-v0.111.0.json").read_bytes()
    primary_bytes = (root / "src/source-presentation.mjs").read_bytes()
    if b"999,999,999" not in book_bytes or b"999999999" not in compact_bytes or b"999999999" not in primary_bytes:
        raise AuditError("Waterfall Giant terminal finite-HP correction is absent from retained/compact/primary coordinates")
    return [
        {
            "id": "review-correction-kin-follower-type-origin-v1",
            "status": "p1b0-conflict-mapped-bosses-lua",
            "correction": "The erroneous retained Type=Boss field for Kin Follower originates in tools/.wiki/Bosses.lua, not Hive.lua.",
            "originId": kin[0]["id"],
        },
        {
            "id": "review-correction-fabricator-membership-v1",
            "status": "p1b0-conflict-mapped-bosses-lua",
            "correction": "The retained book has Fabricator as the sole initial body and Guardbot, Noisebot, Stabbot, and Zapbot as summoned bodies; compact source production pools remain a separate lane.",
            "coordinates": ["data/encounters.json#/encounters/FABRICATOR_NORMAL/lineup"],
        },
        {
            "id": "review-correction-waterfall-terminal-hp-v1",
            "status": "p1b0-conflict-mapped-bosses-lua",
            "correction": "Waterfall Giant terminal 999999999 HP is retained in book rules, compact lifecycle, and primary lifecycle rendering.",
            "coordinates": [
                "data/encounters.json#/encounters/WATERFALL_GIANT_BOSS/rules",
                "data/encounter-facts-v0.111.0.json#/payload/sourceFacts/lifecycle",
                "src/source-presentation.mjs#operationSummary:setMaxAndCurrentHp",
            ],
        },
    ]


def build_artifact(root: Path) -> dict[str, Any]:
    root = root.resolve()
    policy = load_json(root / DEFAULT_POLICY)
    _validate_policy(policy)
    p1b1_policy = load_json(root / DEFAULT_P1B1_POLICY)
    primary_surface = load_json(root / PRIMARY_SEMANTIC_SURFACE)
    pages_document = load_json(root / "tools/.wiki/pages.json")
    index = load_json(root / "tools/.wiki/index.json")
    book = load_json(root / "data/encounters.json")
    raw_source = load_json(root / "data/game-v0.111.0-source.json")
    compact = load_json(root / "data/encounter-facts-v0.111.0.json")
    try:
        meta = pages_document["meta"]
        pages = pages_document["pages"]
    except (KeyError, TypeError) as exc:
        raise AuditError("pages.json lacks meta/pages") from exc
    if meta.get("targetVersion") != TARGET_VERSION or meta.get("targetBranch") != TARGET_BRANCH:
        raise AuditError("pages.json target version/branch mismatch")
    if not isinstance(pages, dict) or len(pages) != 75:
        raise AuditError(f"retained page denominator drift: expected 75, derived {len(pages) if isinstance(pages, dict) else 'malformed'}")
    patch_key = meta.get("patchPage")
    if patch_key not in pages:
        raise AuditError("pages.json patchPage is absent")

    metrics: dict[str, Any] = {
        "articleIdentityRecords": 0, "articleMoveRows": 0, "articlePatternRecords": 0,
        "intentsTransclusions": 0, "moduleRecords": 0, "moduleMoveRows": 0,
        "patchEnemyFacts": 0,
    }
    collector = AtomCollector(policy)
    for page_key in sorted(pages):
        if page_key == patch_key:
            continue
        _add_article_atoms(collector, page_key, pages[page_key], metrics)
    _add_patch_atoms(collector, patch_key, pages[patch_key], policy, metrics)
    module_record_counts: dict[str, int] = {}
    for stem in MODULE_STEMS:
        relative = f"tools/.wiki/{stem}.lua"
        module_record_counts[relative] = _add_module_atoms(collector, root, relative, metrics)

    records = collector.sorted_records()
    category_counts = _counter(records, "category")
    family_counts = _counter(records, "family")
    _validate_expected_counts(policy, category_counts, family_counts)
    if len(records) != 4438:
        raise AuditError(f"overall atom denominator drift: expected 4438, derived {len(records)}")
    expected_metrics = {
        "articleIdentityRecords": 105, "articleMoveRows": 293, "articlePatternRecords": 105,
        "intentsTransclusions": 2, "moduleRecords": 105, "moduleMoveRows": 301,
        "patchEnemyFacts": 9,
    }
    if metrics != expected_metrics:
        raise AuditError(f"structural denominator drift: expected {expected_metrics}, derived {metrics}")

    pre_mapping_counts = _counter(records, "reviewState")
    if pre_mapping_counts != {"captured-unreconciled": 3573, "policy-reviewed-exclusion": 865}:
        raise AuditError(f"pre-mapping review-state denominator drift: {pre_mapping_counts}")
    p1b0_mapping_summary = apply_final_mappings(
        records, policy, book=book, compact=compact, raw_source=raw_source,
    )
    p1b1_mapping_summary = apply_p1b1_mappings(
        records, p1b1_policy, compact=compact, primary_surface=primary_surface,
    )
    review_counts = _counter(records, "reviewState")
    if review_counts != {
        "captured-unreconciled": 2253,
        "policy-reviewed-exclusion": 865,
        FINAL_REVIEW_STATE: 1320,
    }:
        raise AuditError(f"review-state denominator drift: {review_counts}")
    for record in records:
        if record["reviewState"] == "captured-unreconciled" and "disposition" in record:
            raise AuditError(f"non-final captured record has a final disposition: {record['id']}")
        if record["reviewState"] == "policy-reviewed-exclusion" and record.get("disposition") != "intentionally-excluded":
            raise AuditError(f"excluded record lacks final intentionally-excluded disposition: {record['id']}")
        if record["reviewState"] == FINAL_REVIEW_STATE:
            if record.get("disposition") not in FINAL_DISPOSITIONS - {"intentionally-excluded"}:
                raise AuditError(f"final-mapped record has invalid disposition: {record['id']}")
            if not record.get("semanticMapping") or not record.get("rationale") or not record.get("representation"):
                raise AuditError(f"final disposition lacks typed mapping/rationale: {record['id']}")
    doormaker = [record for record in records
                 if record["origin"].get("pageKey") == "Doormaker" or record["origin"].get("tableKey") == "Doormaker"]
    if not doormaker or any(record["membership"] != "deprecated" for record in doormaker):
        raise AuditError("Doormaker origin is absent or marked current")
    door_mechanical = [record for record in doormaker if record["reviewState"] != "policy-reviewed-exclusion"]
    if len(door_mechanical) != 36 or any(record.get("disposition") != "stale/deprecated/version-ambiguous" for record in door_mechanical):
        raise AuditError("Doormaker mechanical origins were not mapped archive-only stale")
    mysterious = [record for record in records
                  if record["origin"].get("pageKey") == "Mysterious Knight" or record["origin"].get("tableKey") == "Mysterious Knight"]
    if not mysterious or any(record["membership"] != "current" for record in mysterious):
        raise AuditError("Mysterious Knight origin is absent or marked deprecated")

    module_manifest = _module_manifest(root, index, policy)
    if module_manifest["listedCount"] != 7 or module_manifest["presentCount"] != 6 or module_manifest["missingCount"] != 1:
        raise AuditError("index-vs-file module denominator drift")
    if sum(module_record_counts.values()) != 105:
        raise AuditError("module record denominator drift")
    source_denominators = _source_layer_denominators(raw_source, compact, book)
    corrections = _validate_review_corrections(root, records, book)

    page_record_membership = {"current": 0, "deprecated": 0}
    for record in records:
        if record["family"] == "article-identity-field" and record["normalized"].get("field") in {"Name", "title"}:
            page_record_membership[record["membership"]] += 1
    if page_record_membership != {"current": 104, "deprecated": 1}:
        raise AuditError(f"article identity membership drift: {page_record_membership}")

    final_disposition_counts = _counter([record for record in records if "disposition" in record], "disposition")
    if sum(final_disposition_counts.values()) + review_counts.get("captured-unreconciled", 0) != len(records):
        raise AuditError("P1b1 final disposition and captured counts do not reconcile to all origins")

    origin_lines = "".join(record["id"] + "\n" for record in records).encode("utf-8")
    claim_origin_lines = "".join(record["id"] + "\0" + record["claimId"] + "\n" for record in records).encode("utf-8")
    input_manifest = _build_input_manifest(root)
    manifest_digest = sha256_bytes(canonical_json_bytes(input_manifest))

    generated_page_titles = {item["title"].removeprefix("Slay the Spire 2:") for item in book["meta"]["wikiPages"]}
    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        "target": {
            "version": TARGET_VERSION,
            "gameBranch": TARGET_BRANCH,
            "repositoryBranch": "main",
            "repositoryScope": "current checked offline checkout",
        },
        "authority": {
            "status": "offline-coverage-and-reconciliation-input-only",
            "runtimeDependency": False,
            "sourceOverrideAllowed": False,
            "statement": "This artifact inventories retained wiki origins. It does not override closed reverse-engineered source data and is not imported by runtime routes.",
        },
        "snapshotManifest": {
            "inputs": input_manifest,
            "inputsDigestSha256": manifest_digest,
            "pagesMetadata": meta,
            "modules": module_manifest,
        },
        "denominators": {
            "retainedPages": 75,
            "enemyArticlePages": 74,
            "currentEnemyPages": 73,
            "deprecatedEnemyPages": 1,
            "articleIdentityRecords": metrics["articleIdentityRecords"],
            "currentArticleIdentityRecords": page_record_membership["current"],
            "deprecatedArticleIdentityRecords": page_record_membership["deprecated"],
            "indexListedModules": module_manifest["listedCount"],
            "retainedLuaFiles": module_manifest["presentCount"],
            "moduleRecords": metrics["moduleRecords"],
            "syntheticGeneratorRecordsNotRetainedOrigins": 1,
            "articleMoveRows": metrics["articleMoveRows"],
            "moduleMoveRows": metrics["moduleMoveRows"],
            "retainedMoveRowOrigins": metrics["articleMoveRows"] + metrics["moduleMoveRows"],
            "articlePatternRecords": metrics["articlePatternRecords"],
            "normalizedPatternClauses": family_counts["article-pattern-clause"],
            "powerInfoboxCalls": family_counts["article-power-invocation"],
            "powerPassiveAtoms": family_counts["article-power-invocation"] + family_counts["article-power-inline-field"],
            "startingPowerAtoms": family_counts["article-starting-power"] + family_counts["module-starting-power"] + family_counts["patch-starting-power"],
            "noteUnitsIncludingCommentFragments": family_counts["article-note-claim"] + family_counts["html-comment-fragment"],
            "humanNoteClaims": family_counts["article-note-claim"],
            "commentFragments": family_counts["html-comment-fragment"],
            "tactics": family_counts["article-tactic-useful"] + family_counts["article-tactic-synergy"] + family_counts["article-tactic-anti-synergy"],
            "trivia": family_counts["trivia-unit"],
            "patchEnemyMechanicFacts": metrics["patchEnemyFacts"],
            "overallRetainedOriginAtoms": len(records),
            "byCategory": category_counts,
            "byOriginFamily": family_counts,
            "sourceLayerSeparateNotRetainedAtoms": source_denominators,
        },
        "snapshotLimitations": {
            "snapshotGaps": module_manifest["missing"],
            "unexpandedTemplateBodies": {
                "powerInfoboxShorthandInvocations": sum(
                    record["family"] == "article-power-invocation" and record["normalized"]["unexpandedTemplateBody"]
                    for record in records
                ),
                "intentsInvocations": metrics["intentsTransclusions"],
                "statement": "Template bodies are absent from the retained snapshot; invocations and arguments are inventoried without claiming template semantics were classified.",
            },
            "retainedBookMembership": {
                "mysteriousKnight": {
                    "articleMembership": "current",
                    "listedInCurrentRetainedBookWikiPages": "Mysterious Knight" in generated_page_titles,
                    "listedInCurrentEncounters": "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER" in book["encounters"],
                    "listedInRetainedReferences": "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER" in book.get("retainedReferences", {}),
                    "status": "current-event-reconciliation-reference",
                },
                "doormaker": {
                    "articleMembership": "deprecated",
                    "listedInCurrentRetainedBookWikiPages": "Doormaker" in generated_page_titles,
                    "listedInCurrentEncounters": "DOORMAKER_BOSS" in book["encounters"],
                    "listedInArchive": "DOORMAKER_BOSS" in book.get("archive", {}).get("encounters", {}),
                    "status": "archive-only-not-current",
                },
            },
        },
        "reviewCorrections": corrections,
        "finalMappings": {
            "phase": "P1b1",
            "mappedOriginCount": review_counts[FINAL_REVIEW_STATE],
            "p1b0": {
                "mappedOriginCount": len(p1b0_mapping_summary["mappedOriginIds"]),
                "researchCountCorrections": p1b0_mapping_summary["researchCountCorrections"],
                "compactTitleConflicts": p1b0_mapping_summary["compactTitleConflicts"],
            },
            "p1b1": {
                "mappedOriginCount": len(p1b1_mapping_summary["mappedOriginIds"]),
                "targetFamilyCounts": p1b1_mapping_summary["familyCounts"],
                "dispositionCounts": p1b1_mapping_summary["dispositionCounts"],
                "atomizationCorrection": p1b1_mapping_summary["atomizationCorrection"],
            },
        },
        "researchBaseline": {
            "status": "corrected-historical-semantic-review-reference-not-applied-as-p1a-record-dispositions",
            "researchArtifact": {
                "workflowReference": "research-b43f3e9e/answer.md",
                "sha256": "ea6b405bb2adc3bdd9bdcbf8e3f7f82336aee5eaa79f434d494d288c803adb7e"
            },
            "objectiveNoteGaps": 79,
            "aggregateDispositionTotals": {
                "primary-present": 2172,
                "audit-present": 1241,
                "source-present-not-projected": 2,
                "retained-book-only": 0,
                "conflict": 13,
                "missing/unparsed": 103,
                "intentionally-excluded": 865,
                "stale/deprecated/version-ambiguous": 42,
                "total": 4438,
            },
            "warning": "These corrected historical totals include the five-origin atomization adjustment only. Materialized P1b0/P1b1 records, not this baseline estimate, are authoritative for completed families.",
        },
        "exclusionPolicies": policy["exclusionPolicies"],
        "readiness": {
            "inventoryComplete": True,
            "snapshotComplete": False,
            "sourceExtractionComplete": False,
            "sourceExtractionDeclaredEncounterProjectionScopeComplete": source_denominators["declaredEncounterProjectionScopeReady"],
            "semanticReconciliationComplete": False,
            "overallReconciliationReady": False,
            "reasons": [
                "Events.lua is index-listed but absent under an approved version-scoped snapshot-gap waiver.",
                f"{review_counts['captured-unreconciled']} retained-origin atoms remain captured-unreconciled pending later P1b semantic review.",
                "Unexpanded Power Infobox and Intents template bodies are not present in the retained snapshot.",
                "Global source extraction readiness remains false even though its declared encounter-projection scope is ready.",
                "P1b1 maps identity, roster, HP, and starting-state atoms; move, Pattern, Power-description, and objective Note families remain non-final.",
            ],
        },
        "summary": {
            "recordCount": len(records),
            "reviewStateCounts": review_counts,
            "membershipCounts": _counter(records, "membership"),
            "finalDispositionCounts": final_disposition_counts,
            "remainingCapturedUnreconciled": review_counts.get("captured-unreconciled", 0),
            "compactTitleConflictCount": len(p1b0_mapping_summary["compactTitleConflicts"]),
            "sortedOriginIdsSha256": sha256_bytes(origin_lines),
            "sortedClaimOriginIdsSha256": sha256_bytes(claim_origin_lines),
            "ordering": "records sorted by stable origin ID; no timestamp, filesystem order, inode, temporary path, or absolute path participates",
        },
        "records": records,
    }
    if artifact["readiness"]["snapshotComplete"] and module_manifest["missingCount"]:
        raise AuditError("snapshot readiness true while module snapshot gap remains")
    if artifact["readiness"]["semanticReconciliationComplete"] and review_counts.get("captured-unreconciled", 0):
        raise AuditError("semantic readiness true while captured-unreconciled atoms remain")
    if artifact["readiness"]["overallReconciliationReady"]:
        raise AuditError("P1b1 cannot report overall reconciliation readiness")
    return artifact


def artifact_bytes(root: Path) -> bytes:
    return canonical_json_bytes(build_artifact(root))


def verify_clean_book_regeneration(root: Path) -> None:
    """Generate in an isolated clean tree and compare retained-book bytes."""
    with tempfile.TemporaryDirectory(prefix="sts2-wiki-book-check-") as directory:
        temporary = Path(directory)
        (temporary / "tools").mkdir()
        (temporary / "data").mkdir()
        shutil.copy2(root / "tools/generate-book.py", temporary / "tools/generate-book.py")
        shutil.copytree(root / "tools/.wiki", temporary / "tools/.wiki")
        result = subprocess.run(
            [sys.executable, str(temporary / "tools/generate-book.py")],
            cwd=temporary, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, text=True,
        )
        if result.returncode:
            raise AuditError(
                "clean retained-book regeneration failed: "
                + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}")
            )
        generated = (temporary / "data/encounters.json").read_bytes()
        checked = (root / "data/encounters.json").read_bytes()
        if generated != checked:
            raise AuditError("data/encounters.json differs byte-for-byte from clean deterministic regeneration")


def _validate_disappearances(existing: dict[str, Any], generated: dict[str, Any], policy: dict[str, Any]) -> None:
    old_ids = {record["id"] for record in existing.get("records", [])}
    new_ids = {record["id"] for record in generated.get("records", [])}
    disappeared = old_ids - new_ids
    if not disappeared:
        return
    tombstones = {item["originId"] for item in policy["tombstones"]}
    reclassified = {item["fromOriginId"] for item in policy["approvedOriginReclassifications"]}
    unexplained = sorted(disappeared - tombstones - reclassified)
    if unexplained:
        preview = ", ".join(unexplained[:5])
        raise AuditError(
            f"{len(unexplained)} prior origins disappeared without explicit tombstone/reclassification; first: {preview}"
        )


def write_or_check(root: Path, output: Path, *, check: bool) -> tuple[int, bytes]:
    root = root.resolve()
    output = output if output.is_absolute() else root / output
    verify_clean_book_regeneration(root)
    generated_object = build_artifact(root)
    generated = canonical_json_bytes(generated_object)
    if check:
        try:
            checked = output.read_bytes()
        except OSError as exc:
            raise AuditError(f"checked reconciliation artifact is absent: {output}: {exc}") from exc
        if checked != generated:
            raise AuditError(
                f"{output.relative_to(root) if output.is_relative_to(root) else output} is stale; "
                "run npm run build:wiki-reconciliation and review captured-unreconciled origins"
            )
        return len(generated_object["records"]), generated
    policy = load_json(root / DEFAULT_POLICY)
    if output.exists():
        existing = load_json(output)
        _validate_disappearances(existing, generated_object, policy)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.name + ".", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(generated)
        handle.flush()
    temporary.replace(output)
    return len(generated_object["records"]), generated
