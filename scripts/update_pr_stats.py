"""Refresh the merged upstream PR chart for the profile README."""

import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


USER = "CharlesXu-HQ"
LIMIT = 10


def fetch_prs():
    items = []
    for page in range(1, 11):
        url = "https://api.github.com/search/issues?" + urlencode(
            {"q": f"author:{USER} type:pr is:merged", "per_page": 100, "page": page}
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-pr-stats",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token := os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            result = json.load(response)
        if result["incomplete_results"] or result["total_count"] > 1000:
            raise RuntimeError("GitHub Search did not return a complete PR set")
        items.extend(result["items"])
        if len(items) >= result["total_count"]:
            if not items:
                raise RuntimeError("GitHub Search returned no authored PRs")
            return items
    raise RuntimeError("GitHub Search pagination ended before all PRs were fetched")


def rank_projects(items):
    counts = Counter()
    for item in items:
        if item["user"]["login"].casefold() != USER.casefold() or not item["pull_request"]["merged_at"]:
            continue
        repo = item["repository_url"].split("/repos/", 1)[1]
        if repo.split("/", 1)[0].casefold() == USER.casefold():
            continue
        counts[repo] += 1

    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))[:LIMIT]
    if not ranked:
        raise RuntimeError("No external merged PRs found")
    return ranked


def render_chart(projects, dark=False):
    colors = (
        {"background": "#0d1117", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e", "bar": "#58a6ff"}
        if dark else
        {"background": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#59636e", "bar": "#0969da"}
    )
    width, height = 1000, 130 + 44 * len(projects)
    max_count = max(count for _, count in projects)
    details = "; ".join(f"{repo}: {count} merged PRs" for repo, count in projects)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<title>Merged open-source pull requests by project</title><desc>{escape(details)}</desc>',
        f'<rect x="0.5" y="0.5" width="999" height="{height - 1}" rx="14" fill="{colors["background"]}" stroke="{colors["border"]}"/>',
        '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif">',
        f'<text x="28" y="40" font-size="25" font-weight="700" fill="{colors["text"]}">Merged open-source PRs / 已合并的开源 PR</text>',
        f'<text x="28" y="68" font-size="15" fill="{colors["muted"]}">External projects ranked by merged PRs / 按已合并 PR 数排序</text>',
    ]
    for index, (repo, count) in enumerate(projects):
        y = 105 + 44 * index
        bar_width = round(560 * count / max_count)
        lines.extend([
            f'<text x="28" y="{y + 21}" font-size="16" fill="{colors["text"]}">{escape(repo)}</text>',
            f'<rect x="292" y="{y + 3}" width="{bar_width}" height="24" rx="5" fill="{colors["bar"]}"/>',
            f'<text x="971" y="{y + 21}" text-anchor="end" font-size="16" font-weight="600" fill="{colors["text"]}">{count}</text>',
        ])
    lines.extend(["</g>", "</svg>"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    assets = Path(__file__).resolve().parents[1] / "assets"
    assets.mkdir(exist_ok=True)
    projects = rank_projects(fetch_prs())
    for dark, theme in ((False, "light"), (True, "dark")):
        path = assets / f"open-source-prs-{theme}.svg"
        svg = render_chart(projects, dark=dark)
        if not path.exists() or path.read_text() != svg:
            path.write_text(svg)
            print(f"Updated {path.name}")
