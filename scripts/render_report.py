#!/usr/bin/env python3
"""Render the sign-off report as Markdown (job summary) and HTML (Pages).

Both renderings are driven by the same JSON produced by collect_prs.py, so the
page the reviewer reads and the summary beside the Approve button cannot drift
apart.
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
from collections import Counter
from datetime import datetime

# Labels that should stand out to a reviewer skimming the table.
NOTABLE = {"security", "compliance", "breaking-change", "data-loss-risk"}

# Label -> how to describe it to someone who does not read code. Order matters:
# the first match wins, so the most consequential categories come first.
CATEGORIES = [
    ("security", "security"),
    ("compliance", "audit and compliance"),
    ("breaking-change", "behaviour changes"),
    ("bug", "defect fixes"),
    ("enhancement", "new capability"),
    ("performance", "performance"),
    ("documentation", "documentation"),
    ("tech-debt", "internal cleanup"),
]


def read_json(path: str) -> dict:
    return json.loads(pathlib.Path(path).read_text())


def read_optional(path: str | None) -> str:
    if not path:
        return ""
    candidate = pathlib.Path(path)
    if not candidate.exists():
        return ""
    return candidate.read_text().strip()


def pretty_date(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y")


def all_labels(pr: dict) -> list[dict]:
    """PR labels plus the labels of every issue the PR closed, de-duplicated."""
    seen: dict[str, dict] = {}
    for label in pr["labels"]:
        seen.setdefault(label["name"], label)
    for issue in pr["issues"]:
        for label in issue["labels"]:
            seen.setdefault(label["name"], label)
    return [seen[name] for name in sorted(seen)]


def is_pull_request(payload: dict) -> bool:
    """True when the report covers one open pull request rather than a window."""
    return payload.get("scope") == "pull_request"


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    return singular if count == 1 else (plural_form or singular + "s")


def categorise(pr: dict) -> str | None:
    """Assign *pr* to the most consequential category its labels imply."""
    names = {label["name"] for label in all_labels(pr)}
    for label, description in CATEGORIES:
        if label in names:
            return description
    return None


def auto_narrative(payload: dict) -> str:
    """Describe the batch in prose derived entirely from the data.

    This runs with no model and no network, so the report always carries a
    readable overview. An AI summary, when one is configured, replaces it.
    """
    prs = payload["pull_requests"]
    if not prs:
        return ""

    issues = [issue for pr in prs for issue in pr["issues"]]
    authors = sorted({pr["author"] for pr in prs})

    if is_pull_request(payload):
        pr = prs[0]
        bullets = [
            f"- {pr['author']} proposes {pr['title'].rstrip('.')}, changing "
            f"{pr['changed_files']} {plural(pr['changed_files'], 'file')} "
            f"(+{pr['additions']}/-{pr['deletions']})."
        ]
    else:
        bullets = [
            f"- {len(prs)} {plural(len(prs), 'pull request')} merged in this window, "
            f"closing {len(issues)} tracked {plural(len(issues), 'work item')}, "
            f"from {len(authors)} {plural(len(authors), 'contributor')} "
            f"({', '.join(authors)})."
        ]

    flagged = [pr for pr in prs if NOTABLE & {l["name"] for l in all_labels(pr)}]
    if flagged and is_pull_request(payload):
        tags = ", ".join(sorted(NOTABLE & {l["name"] for l in all_labels(prs[0])}))
        bullets.append(f"- Tagged {tags}, so it warrants a closer look.")
    elif flagged:
        listed = "; ".join(
            f"#{pr['number']} {pr['title']}"
            + f" ({', '.join(sorted(NOTABLE & {l['name'] for l in all_labels(pr)}))})"
            for pr in flagged
        )
        bullets.append(
            f"- Needs a closer look: {listed}."
        )

    if is_pull_request(payload):
        described = categorise(prs[0])
        if described:
            bullets.append(f"- Categorised as {described}.")
        pr = prs[0]
        if pr["issues"]:
            listed = "; ".join(f"#{i['number']} {i['title']}" for i in pr["issues"])
            bullets.append(f"- Closes {listed}.")
        else:
            bullets.append(
                "- Closes no tracked work item, so there is no issue history "
                "behind this change."
            )
        return "\n".join(bullets)

    grouped: dict[str, list[int]] = {}
    for pr in prs:
        description = categorise(pr)
        if description:
            grouped.setdefault(description, []).append(pr["number"])
    if grouped:
        listed = "; ".join(
            f"{description} ({', '.join(f'#{n}' for n in numbers)})"
            for description, numbers in grouped.items()
        )
        bullets.append(f"- What the batch consists of: {listed}.")

    untracked = [pr for pr in prs if not pr["issues"]]
    if untracked:
        listed = ", ".join(f"#{pr['number']}" for pr in untracked)
        bullets.append(
            f"- {len(untracked)} {plural(len(untracked), 'pull request')} "
            f"closed no tracked work item ({listed}), leaving no issue history "
            "behind those changes."
        )

    return "\n".join(bullets)


def label_counts(payload: dict) -> Counter:
    counter: Counter = Counter()
    for pr in payload["pull_requests"]:
        for label in all_labels(pr):
            counter[label["name"]] += 1
    return counter


# --------------------------------------------------------------------------- #
# Markdown (GitHub Actions job summary)
# --------------------------------------------------------------------------- #

def render_markdown(
    payload: dict, narrative: str, page_url: str | None, ai: bool
) -> str:
    prs = payload["pull_requests"]
    if is_pull_request(payload):
        pr = prs[0]
        lines = [
            f"# Sign-off request: PR #{pr['number']}",
            "",
            f"**[{pr['title']}]({pr['url']})** &nbsp;·&nbsp; "
            f"by @{pr['author']} &nbsp;·&nbsp; into `{payload['base']}`",
            "",
            "This pull request **cannot merge** until the sign-off below is "
            "approved.",
            "",
        ]
    else:
        lines = [
            "# Change sign-off request",
            "",
            f"**Repository:** `{payload['repo']}` &nbsp;·&nbsp; "
            f"**Branch:** `{payload['base']}` &nbsp;·&nbsp; "
            f"**Window:** {pretty_date(payload['since'])} → "
            f"{pretty_date(payload['generated_at'])}",
            "",
            f"**{len(prs)} pull request(s)** merged in this window and are awaiting "
            "your approval.",
            "",
        ]

    if page_url:
        lines += [f"📄 **[Open the full report page]({page_url})**", ""]

    if narrative:
        origin = (
            "Written by GitHub Copilot from the changes below."
            if ai
            else "Derived from the tables below."
        )
        lines += ["## Summary", "", narrative, "", f"<sub>{origin}</sub>", ""]

    if not prs:
        lines += [
            "> Nothing merged in this window. Approving records a no-change "
            "sign-off for the period.",
            "",
        ]
        return "\n".join(lines)

    lines += [
        "## The change" if is_pull_request(payload) else "## Changes in this batch",
        "",
        "| PR | Title | Author | Tags |",
        "| --- | --- | --- | --- |",
    ]
    for pr in prs:
        tags = " ".join(
            f"`{label['name']}`" for label in all_labels(pr)
        ) or "—"
        title = pr["title"].replace("|", "\\|")
        lines.append(
            f"| [#{pr['number']}]({pr['url']}) | {title} | @{pr['author']} | {tags} |"
        )

    linked = [(pr, issue) for pr in prs for issue in pr["issues"]]
    if linked:
        lines += [
            "",
            "## Work items this closes"
            if is_pull_request(payload)
            else "## Work items closed",
            "",
            "| Issue | Title | Tags | Delivered by |",
            "| --- | --- | --- | --- |",
        ]
        for pr, issue in linked:
            tags = " ".join(f"`{l['name']}`" for l in issue["labels"]) or "—"
            title = issue["title"].replace("|", "\\|")
            lines.append(
                f"| [#{issue['number']}]({issue['url']}) | {title} | {tags} | "
                f"[#{pr['number']}]({pr['url']}) |"
            )

    counts = label_counts(payload)
    if counts and not is_pull_request(payload):
        lines += ["", "## Tag totals", ""]
        lines += [
            "| Tag | Pull requests |",
            "| --- | --- |",
        ]
        for name, count in counts.most_common():
            flag = " ⚠️" if name in NOTABLE else ""
            lines.append(f"| `{name}`{flag} | {count} |")

    lines += [
        "",
        "---",
        "",
        "Approving the **external-signoff** deployment below releases this "
        "pull request to merge, with your GitHub identity and a timestamp."
        if is_pull_request(payload)
        else "Approving the **external-signoff** deployment below records your "
        "acceptance of this batch, with your GitHub identity and a timestamp.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTML (GitHub Pages)
# --------------------------------------------------------------------------- #

CSS = """
:root {
  color-scheme: light dark;
  --bg: #f6f8fa; --panel: #ffffff; --ink: #1f2328; --muted: #59636e;
  --line: #d1d9e0; --accent: #0969da; --warn: #9a6700; --warn-bg: #fff8c5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --panel: #151b23; --ink: #e6edf3; --muted: #9198a1;
    --line: #3d444d; --accent: #4493f8; --warn: #d29922; --warn-bg: #282215;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 32px 16px 64px; }
header.masthead { border-bottom: 1px solid var(--line); padding-bottom: 20px; margin-bottom: 28px; }
h1 { font-size: 26px; margin: 0 0 8px; letter-spacing: -0.01em; }
h2 { font-size: 18px; margin: 36px 0 12px; }
.meta { color: var(--muted); font-size: 13px; }
.meta code { background: var(--panel); border: 1px solid var(--line); border-radius: 5px; padding: 1px 5px; }
.stats { display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0 4px; }
.stat {
  flex: 1 1 150px; background: var(--panel); border: 1px solid var(--line);
  border-radius: 8px; padding: 14px 16px;
}
.stat .n { font-size: 24px; font-weight: 600; display: block; }
.stat .k { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.summary {
  background: var(--panel); border: 1px solid var(--line); border-left: 4px solid var(--accent);
  border-radius: 8px; padding: 4px 20px; margin: 20px 0;
}
.table-scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; background: var(--panel); font-size: 14px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
tr:last-child td { border-bottom: none; }
table { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.tag {
  display: inline-block; font-size: 11px; line-height: 18px; padding: 0 8px;
  border-radius: 999px; border: 1px solid transparent; margin: 1px 2px 1px 0; white-space: nowrap;
}
.notice {
  background: var(--warn-bg); border: 1px solid var(--line); border-left: 4px solid var(--warn);
  border-radius: 8px; padding: 14px 18px; margin: 24px 0; font-size: 14px;
}
footer { margin-top: 48px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--line); padding-top: 16px; }
.empty { background: var(--panel); border: 1px dashed var(--line); border-radius: 8px; padding: 28px; text-align: center; color: var(--muted); }
"""


def readable_ink(hex_colour: str) -> str:
    """Pick black or white text for a GitHub label colour."""
    try:
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return "#1f2328"
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1f2328" if luminance > 0.6 else "#ffffff"


def tag_html(label: dict) -> str:
    colour = label.get("color") or "d1d9e0"
    return (
        f'<span class="tag" style="background:#{colour};color:{readable_ink(colour)}">'
        f"{html.escape(label['name'])}</span>"
    )


def markdown_lite(text: str) -> str:
    """Render the model's bullet list without pulling in a Markdown dependency."""
    out, in_list = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(line[2:].strip())}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def render_html(
    payload: dict, narrative: str, run_url: str | None, ai: bool
) -> str:
    prs = payload["pull_requests"]
    counts = label_counts(payload)
    issue_count = sum(len(pr["issues"]) for pr in prs)
    authors = {pr["author"] for pr in prs}

    single = is_pull_request(payload) and prs
    if single:
        pr = prs[0]
        title = f"Sign-off — PR #{pr['number']}"
        heading = f"Sign-off request: PR #{pr['number']}"
        meta = (
            f"<a href='{pr['url']}'>{html.escape(pr['title'])}</a> · by "
            f"{html.escape(pr['author'])} · into "
            f"<code>{html.escape(payload['base'])}</code>"
        )
        stats = [
            (pr["changed_files"], "Files changed"),
            (f"+{pr['additions']}", "Lines added"),
            (f"-{pr['deletions']}", "Lines removed"),
        ]
    else:
        title = f"Change sign-off — {payload['repo']}"
        heading = "Change sign-off request"
        meta = (
            f"<code>{html.escape(payload['repo'])}</code> · branch "
            f"<code>{html.escape(payload['base'])}</code> · "
            f"{pretty_date(payload['since'])} → "
            f"{pretty_date(payload['generated_at'])}"
        )
        stats = [
            (len(prs), "Pull requests"),
            (issue_count, "Work items closed"),
            (len(authors), "Contributors"),
        ]

    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title>",
        f"<style>{CSS}</style></head><body><div class='wrap'>",
        "<header class='masthead'>",
        f"<h1>{html.escape(heading)}</h1>",
        f"<p class='meta'>{meta}</p>",
        "</header>",
        "<div class='stats'>",
    ]
    parts += [
        f"<div class='stat'><span class='n'>{value}</span>"
        f"<span class='k'>{label}</span></div>"
        for value, label in stats
    ]
    parts.append("</div>")

    if narrative:
        origin = (
            "Written by GitHub Copilot from the changes below."
            if ai
            else "Derived from the tables below."
        )
        parts += [
            "<h2>Summary</h2>",
            f"<div class='summary'>{markdown_lite(narrative)}"
            f"<p class='meta'>{origin}</p></div>",
        ]

    if not prs:
        parts.append(
            "<div class='empty'>No changes merged in this window. "
            "Approving records a no-change sign-off for the period.</div>"
        )
    else:
        parts += [
            "<h2>The change</h2>" if single else "<h2>Changes in this batch</h2>",
            "<div class='table-scroll'><table><thead><tr>"
            "<th>PR</th><th>Title</th><th>Author</th><th>Tags</th>"
            "</tr></thead><tbody>",
        ]
        for pr in prs:
            tags = "".join(tag_html(l) for l in all_labels(pr)) or "—"
            parts.append(
                f"<tr><td class='num'><a href='{pr['url']}'>#{pr['number']}</a></td>"
                f"<td>{html.escape(pr['title'])}</td>"
                f"<td class='num'>{html.escape(pr['author'])}</td>"
                f"<td>{tags}</td></tr>"
            )
        parts.append("</tbody></table></div>")

        linked = [(pr, issue) for pr in prs for issue in pr["issues"]]
        if linked:
            parts += [
                "<h2>Work items this closes</h2>"
                if single
                else "<h2>Work items closed</h2>",
                "<div class='table-scroll'><table><thead><tr>"
                "<th>Issue</th><th>Title</th><th>Tags</th><th>Delivered by</th>"
                "</tr></thead><tbody>",
            ]
            for pr, issue in linked:
                tags = "".join(tag_html(l) for l in issue["labels"]) or "—"
                parts.append(
                    f"<tr><td class='num'><a href='{issue['url']}'>#{issue['number']}</a></td>"
                    f"<td>{html.escape(issue['title'])}</td><td>{tags}</td>"
                    f"<td class='num'><a href='{pr['url']}'>#{pr['number']}</a></td></tr>"
                )
            parts.append("</tbody></table></div>")

        flagged = sorted(NOTABLE & set(counts))
        if flagged:
            listed = ", ".join(f"<strong>{html.escape(n)}</strong>" for n in flagged)
            parts.append(
                f"<div class='notice'>This batch carries {listed} tagged work. "
                "Those rows are worth a closer look before you approve.</div>"
            )

        if counts and not single:
            parts += [
                "<h2>Tag totals</h2>",
                "<div class='table-scroll'><table><thead><tr><th>Tag</th>"
                "<th>Pull requests</th></tr></thead><tbody>",
            ]
            for name, count in counts.most_common():
                colour = next(
                    (l["color"] for pr in prs for l in all_labels(pr)
                     if l["name"] == name),
                    "d1d9e0",
                )
                parts.append(
                    f"<tr><td>{tag_html({'name': name, 'color': colour})}</td>"
                    f"<td class='num'>{count}</td></tr>"
                )
            parts.append("</tbody></table></div>")

    approve = (
        f" Return to <a href='{run_url}'>the workflow run</a> to approve or reject."
        if run_url else ""
    )
    parts += [
        "<div class='notice'>This page is a read-only report. Your approval is "
        f"recorded in GitHub Actions, not here.{approve}</div>",
        f"<footer>Generated {html.escape(payload['generated_at'])} · "
        "Aurora Telemetry Gateway sign-off workflow</footer>",
        "</div></body></html>",
    ]
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="build/prs.json")
    parser.add_argument("--narrative", default=None, help="optional AI summary file")
    parser.add_argument("--markdown-out", default="build/summary.md")
    parser.add_argument("--html-out", default="site/index.html")
    parser.add_argument("--page-url", default=None)
    parser.add_argument("--run-url", default=None)
    args = parser.parse_args()

    payload = read_json(args.data)
    narrative = read_optional(args.narrative)
    from_ai = bool(narrative)
    if not narrative:
        narrative = auto_narrative(payload)

    md_path = pathlib.Path(args.markdown_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(payload, narrative, args.page_url, from_ai))

    html_path = pathlib.Path(args.html_out)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(payload, narrative, args.run_url, from_ai))

    print(f"wrote {md_path} and {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
