#!/usr/bin/env python3
"""Fetches all public repos from GitHub API, picks today's, and updates index.html."""

import json
import os
import re
import urllib.request
from datetime import date
from pathlib import Path

GITHUB_USER = "chartmann1590"
INDEX_FILE = Path(__file__).resolve().parent.parent / "index.html"
MARKER_RE = re.compile(r"<!-- FEATURED_START -->.*?<!-- FEATURED_END -->", re.DOTALL)

LANG_ICONS = {
    "Kotlin": "📱", "Java": "☕", "Python": "🐍",
    "JavaScript": "⚡", "TypeScript": "⚡", "Dart": "🎯",
    "Swift": "🍎", "C++": "⚙️", "Rust": "🦀", "Go": "🐹", "C#": "🔷",
}


def fetch_all_repos() -> list:
    """Pages through the GitHub API to get every public non-fork repo."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repos = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{GITHUB_USER}/repos"
            f"?per_page=100&type=owner&sort=updated&page={page}"
        )
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req) as resp:
            batch = json.loads(resp.read())
        if not batch:
            break
        repos.extend(batch)
        page += 1
    # exclude forks and the github.io site repo itself
    return [r for r in repos if not r["fork"] and r["name"] != f"{GITHUB_USER}.github.io"]


def build_card(repo: dict) -> str:
    icon = LANG_ICONS.get(repo.get("language") or "", "💻")
    name = repo["name"].replace("-", " ").replace("_", " ").title()
    desc = repo.get("description") or "An open-source project by Charles Hartmann."
    language = repo.get("language") or ""
    topics = repo.get("topics") or []
    homepage = (repo.get("homepage") or "").strip()

    tags: list[dict] = []
    if language:
        tags.append({"label": language, "gold": True})
    for topic in topics[:4]:
        tags.append({"label": topic, "gold": False})

    tags_html = "".join(
        f'\n              <span class="tag{"  gold" if t["gold"] else ""}">{t["label"]}</span>'
        for t in tags
    )
    links_html = ""
    if homepage:
        links_html += f'\n              <a href="{homepage}">Website</a>'
    links_html += f'\n              <a href="{repo["html_url"]}">Source</a>'

    return (
        f'        <div class="project-card">\n'
        f'          <div class="project-icon">{icon}</div>\n'
        f'          <div class="project-body">\n'
        f'            <div class="project-name">{name}</div>\n'
        f'            <div class="project-desc">{desc}</div>\n'
        f'            <div class="project-tags">{tags_html}\n'
        f'            </div>\n'
        f'            <div class="project-links">{links_html}\n'
        f'            </div>\n'
        f'          </div>\n'
        f'        </div>'
    )


def main() -> None:
    repos = fetch_all_repos()
    if not repos:
        raise SystemExit("No repos found via GitHub API")

    # stable daily rotation: use day-of-year ordinal so new repos join naturally
    idx = date.today().toordinal() % len(repos)
    chosen = repos[idx]

    card_html = build_card(chosen)
    replacement = f"<!-- FEATURED_START -->\n{card_html}\n        <!-- FEATURED_END -->"

    html = INDEX_FILE.read_text(encoding="utf-8")
    if not MARKER_RE.search(html):
        raise SystemExit("FEATURED_START/END markers not found in index.html")

    INDEX_FILE.write_text(MARKER_RE.sub(replacement, html), encoding="utf-8")
    print(f"Featured: {chosen['name']}  (slot {idx} of {len(repos)})")


if __name__ == "__main__":
    main()
