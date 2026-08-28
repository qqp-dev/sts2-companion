#!/usr/bin/env python3
"""Snapshot authoritative StS2 wiki.gg enemy articles for offline generation.

This development-only tool is the sole networked part of the book workflow.
The generator and runtime consume only checked-in files under tools/.wiki/.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "tools/.wiki"
API = "https://slaythespire.wiki.gg/api.php"
NAMESPACE = "Slay the Spire 2:"
PATCH_TITLE = "V0.111.0 - Beta Patch"
USER_AGENT = "sts2-companion/0.1 (offline encounter-book snapshot)"


def balanced(text, opening):
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
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[opening:index + 1]
        index += 1
    raise ValueError("unbalanced Lua table")


def article_titles():
    titles = set()
    for path in WIKI_DIR.glob("*.lua"):
        text = path.read_text()
        for match in re.finditer(r'^\s*\["([^"]+)"\]\s*=\s*\{', text, re.M):
            block = balanced(text, text.find("{", match.start()))
            if not re.search(r"\bType\s*=", block):
                continue
            link = re.search(r'\bLink\s*=\s*"((?:\\.|[^"])*)"', block)
            title = link.group(1).split("#", 1)[0] if link else match.group(1)
            titles.add(title.replace("_", " "))
    return sorted(titles)


def fetch(titles):
    parameters = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
        "titles": "|".join(f"{NAMESPACE}{title}" for title in titles),
    }
    request = urllib.request.Request(
        f"{API}?{urllib.parse.urlencode(parameters)}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def page_record(page):
    if page.get("missing"):
        raise RuntimeError(f"wiki article missing: {page['title']}")
    revision = page["revisions"][0]
    title = page["title"]
    short_title = title.removeprefix(NAMESPACE)
    return short_title, {
        "title": title,
        "url": f"https://slaythespire.wiki.gg/wiki/{urllib.parse.quote(title.replace(' ', '_'), safe=':_()/-')}",
        "pageId": page["pageid"],
        "revisionId": revision["revid"],
        "revisionTimestamp": revision["timestamp"],
        "wikitext": revision["slots"]["main"]["content"],
    }


def main():
    requested = article_titles()
    requested.append(PATCH_TITLE)
    pages = {}
    # Keep requests comfortably under MediaWiki's title limit.
    for offset in range(0, len(requested), 25):
        response = fetch(requested[offset:offset + 25])
        for page in response["query"]["pages"]:
            title, record = page_record(page)
            pages[title] = record
    missing = sorted(set(requested) - set(pages))
    if missing:
        raise RuntimeError(f"snapshot did not resolve requested articles: {missing}")
    snapshot = {
        "meta": {
            "api": API,
            "harvestedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "targetVersion": "v0.111.0",
            "targetBranch": "public-beta",
            "patchPage": PATCH_TITLE,
        },
        "pages": dict(sorted(pages.items())),
    }
    destination = WIKI_DIR / "pages.json"
    destination.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(pages) - 1} enemy articles and patch notes to {destination}")


if __name__ == "__main__":
    main()
