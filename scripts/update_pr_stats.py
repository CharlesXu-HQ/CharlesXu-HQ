"""Refresh the selected upstream PR counts in the profile README."""

import json
import os
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


USER = "CharlesXu-HQ"
START = "<!-- open-source-prs:start -->"
END = "<!-- open-source-prs:end -->"
LIMIT = 10


def fetch_prs():
    items = []
    for page in range(1, 11):
        url = "https://api.github.com/search/issues?" + urlencode(
            {"q": f"author:{USER} type:pr", "per_page": 100, "page": page}
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


def render_table(items):
    counts = defaultdict(lambda: [0, 0])
    for item in items:
        if item["user"]["login"].casefold() != USER.casefold():
            continue
        repo = item["repository_url"].split("/repos/", 1)[1]
        if repo.split("/", 1)[0].casefold() == USER.casefold():
            continue
        counts[repo][0] += 1
        counts[repo][1] += bool(item["pull_request"]["merged_at"])

    ranked = sorted(counts.items(), key=lambda pair: (-pair[1][0], -pair[1][1], pair[0].casefold()))[:LIMIT]
    lines = [
        "| Open-source project / 开源项目 | Merged / 已合并 | All PRs / 全部 PR |",
        "| --- | ---: | ---: |",
    ]
    for repo, (total, merged) in ranked:
        base_query = f"repo:{repo} author:{USER} is:pr"
        all_url = "https://github.com/search?q=" + quote(base_query, safe="") + "&type=pullrequests"
        merged_url = "https://github.com/search?q=" + quote(base_query + " is:merged", safe="") + "&type=pullrequests"
        lines.append(
            f"| [{repo}](https://github.com/{repo}) | [{merged}]({merged_url}) | [{total}]({all_url}) |"
        )
    return "\n".join(lines)


def replace_table(readme, table):
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one PR table marker pair")
    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)
    return before + START + "\n\n" + table + "\n\n" + END + after


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "README.md"
    original = path.read_text()
    updated = replace_table(original, render_table(fetch_prs()))
    if updated != original:
        path.write_text(updated)
        print("Updated open-source PR counts")
    else:
        print("Open-source PR counts unchanged")
