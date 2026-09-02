"""Pure retained-wiki inventory parser and deterministic artifact builder.

The wiki snapshot is reconciliation input, never runtime or source authority.
This module deliberately captures structural claims without inferring whether a
substring is represented by source, compact, or primary presentation data.
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

SCHEMA_VERSION = 1
TARGET_VERSION = "v0.111.0"
TARGET_BRANCH = "public-beta"
DEFAULT_ARTIFACT = "data/wiki-reconciliation-v0.111.0.json"
DEFAULT_POLICY = "tools/wiki-reconciliation-policy-v0.111.0.json"
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
        index += 1
    if curly or square:
        raise AuditError("unbalanced starting-Power field")
    lines.append(raw[start:])
    return [line.strip() for line in lines if plain(line)]


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
                    normalized={"kind": "starting-power", "owner": owner, "value": plain(claim)},
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
                    normalized={"kind": "starting-power", "owner": owner, "stateField": key, "value": plain(claim)},
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
                    normalized={"kind": "module-starting-power", "owner": table_key,
                                "parentField": starts, "value": plain(claim)},
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
            # The first bullet is a grouping parent; reviewed facts are the nine
            # exact child/leaf coordinates in policy.
            classification = classifications.get(enemy_ordinal)
            if not classification:
                continue
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


def _validate_policy(policy: dict[str, Any]) -> None:
    required = {
        "schemaVersion", "targetVersion", "targetBranch", "review",
        "expectedCategoryCounts", "expectedFamilyCounts", "exclusionPolicies",
        "snapshotGapWaivers", "patchEnemyFactClassifications", "tombstones",
        "approvedOriginReclassifications",
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


def _manifest_paths(root: Path) -> list[str]:
    paths = [
        "tools/.wiki/pages.json", "tools/.wiki/index.json",
        *[f"tools/.wiki/{stem}.lua" for stem in MODULE_STEMS],
        "data/encounters.json", "data/game-v0.111.0-source.json",
        "data/encounter-facts-v0.111.0.json", DEFAULT_POLICY,
        "tools/generate-book.py", "tools/retained_wiki.py", "tools/audit-retained-wiki.py",
        "src/source-presentation.mjs", "package.json", "README.md",
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
    except (KeyError, TypeError) as exc:
        raise AuditError("source/compact/book denominator path is malformed") from exc
    body_ids = {
        body["monsterId"]
        for encounter in encounters.values()
        for body in encounter.get("lineup", [])
        if body.get("monsterId")
    }
    wiki_pages = book.get("meta", {}).get("wikiPages", [])
    result = {
        "currentSourceEncounters": encounter_counts["currentTotal"],
        "currentSourceOrdinaryEncounters": encounter_counts["currentOrdinary"],
        "currentSourceEventEncounters": encounter_counts["currentEvent"],
        "currentReachableSourceModels": model_counts["totalReachable"],
        "compactMoves": len(source_facts["moves"]),
        "compactStates": len(source_facts["states"]),
        "retainedGeneratedEncounters": len(encounters),
        "retainedGeneratedBodyIdsIncludingDoormaker": len(body_ids),
        "retainedGeneratedWikiPages": len(wiki_pages),
        "declaredEncounterProjectionScopeReady": bool(projection_ready),
        "globalSourceExtractionReady": bool(global_ready),
    }
    expected = {
        "currentSourceEncounters": 89,
        "currentSourceOrdinaryEncounters": 81,
        "currentSourceEventEncounters": 8,
        "currentReachableSourceModels": 108,
        "compactMoves": 315,
        "compactStates": 8,
        "retainedGeneratedEncounters": 82,
        "retainedGeneratedBodyIdsIncludingDoormaker": 106,
        "retainedGeneratedWikiPages": 73,
        "declaredEncounterProjectionScopeReady": True,
        "globalSourceExtractionReady": False,
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
            "status": "captured-for-p1b-not-semantically-disposed",
            "correction": "The erroneous retained Type=Boss field for Kin Follower originates in tools/.wiki/Bosses.lua, not Hive.lua.",
            "originId": kin[0]["id"],
        },
        {
            "id": "review-correction-fabricator-membership-v1",
            "status": "captured-for-p1b-not-semantically-disposed",
            "correction": "The retained book has Fabricator as the sole initial body and Guardbot, Noisebot, Stabbot, and Zapbot as summoned bodies; compact source production pools remain a separate lane.",
            "coordinates": ["data/encounters.json#/encounters/FABRICATOR_NORMAL/lineup"],
        },
        {
            "id": "review-correction-waterfall-terminal-hp-v1",
            "status": "captured-for-p1b-not-semantically-disposed",
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
    if len(records) != 4433:
        raise AuditError(f"overall atom denominator drift: expected 4433, derived {len(records)}")
    expected_metrics = {
        "articleIdentityRecords": 105, "articleMoveRows": 293, "articlePatternRecords": 105,
        "intentsTransclusions": 2, "moduleRecords": 105, "moduleMoveRows": 301,
        "patchEnemyFacts": 9,
    }
    if metrics != expected_metrics:
        raise AuditError(f"structural denominator drift: expected {expected_metrics}, derived {metrics}")

    review_counts = _counter(records, "reviewState")
    if review_counts != {"captured-unreconciled": 3568, "policy-reviewed-exclusion": 865}:
        raise AuditError(f"review-state denominator drift: {review_counts}")
    for record in records:
        if record["reviewState"] == "captured-unreconciled" and "disposition" in record:
            raise AuditError(f"non-final captured record has a final disposition: {record['id']}")
        if record["reviewState"] == "policy-reviewed-exclusion" and record.get("disposition") != "intentionally-excluded":
            raise AuditError(f"excluded record lacks final intentionally-excluded disposition: {record['id']}")
    doormaker = [record for record in records
                 if record["origin"].get("pageKey") == "Doormaker" or record["origin"].get("tableKey") == "Doormaker"]
    if not doormaker or any(record["membership"] != "deprecated" for record in doormaker):
        raise AuditError("Doormaker origin is absent or marked current")
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
                    "articleMembership": "current", "listedInRetainedBookWikiPages": "Mysterious Knight" in generated_page_titles,
                    "status": "current-membership-reconciliation-gap-deferred-to-p1b",
                },
                "doormaker": {
                    "articleMembership": "deprecated", "listedInRetainedBookWikiPages": "Doormaker" in generated_page_titles,
                    "status": "archived-not-current",
                },
            },
        },
        "reviewCorrections": corrections,
        "researchBaseline": {
            "status": "corrected-historical-semantic-review-reference-not-applied-as-p1a-record-dispositions",
            "researchArtifact": {
                "workflowReference": "research-b43f3e9e/answer.md",
                "sha256": "ea6b405bb2adc3bdd9bdcbf8e3f7f82336aee5eaa79f434d494d288c803adb7e"
            },
            "objectiveNoteGaps": 79,
            "aggregateDispositionTotals": {
                "primary-present": 2167,
                "audit-present": 1241,
                "source-present-not-projected": 2,
                "retained-book-only": 0,
                "conflict": 13,
                "missing/unparsed": 103,
                "intentionally-excluded": 865,
                "stale/deprecated/version-ambiguous": 42,
                "total": 4433,
            },
            "warning": "These corrected P0 research totals are a review baseline only. P1a records use captured-unreconciled until P1b assigns final semantic dispositions and representation paths.",
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
                f"{review_counts['captured-unreconciled']} retained-origin atoms remain captured-unreconciled pending P1b.",
                "Unexpanded Power Infobox and Intents template bodies are not present in the retained snapshot.",
                "Global source extraction readiness remains false even though its declared encounter-projection scope is ready.",
            ],
        },
        "summary": {
            "recordCount": len(records),
            "reviewStateCounts": review_counts,
            "membershipCounts": _counter(records, "membership"),
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
        raise AuditError("P1a cannot report overall reconciliation readiness")
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
