#!/usr/bin/env python3
"""Collect merged pull requests for a sign-off window.

Queries the GitHub GraphQL API (via the `gh` CLI, which supplies auth) for every
pull request merged into the target branch since a cutoff date, along with the
PR's own labels and the labels of any issues it closed.

Outputs a single JSON document so that rendering and AI summarisation are
separate, independently testable steps.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      states: MERGED
      first: 50
      orderBy: {field: UPDATED_AT, direction: DESC}
      after: $cursor
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        url
        mergedAt
        baseRefName
        headRefOid
        isDraft
        additions
        deletions
        changedFiles
        author { login }
        labels(first: 20) { nodes { name color } }
        closingIssuesReferences(first: 10) {
          nodes {
            number
            title
            url
            labels(first: 20) { nodes { name color } }
          }
        }
      }
    }
  }
}
"""


SINGLE_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number
      title
      url
      mergedAt
      baseRefName
      headRefOid
      isDraft
      additions
      deletions
      changedFiles
      author { login }
      labels(first: 20) { nodes { name color } }
      closingIssuesReferences(first: 10) {
        nodes {
          number
          title
          url
          labels(first: 20) { nodes { name color } }
        }
      }
    }
  }
}
"""


OPEN_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      states: OPEN
      first: 50
      orderBy: {field: CREATED_AT, direction: ASC}
      after: $cursor
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        url
        mergedAt
        baseRefName
        headRefOid
        isDraft
        additions
        deletions
        changedFiles
        author { login }
        labels(first: 20) { nodes { name color } }
        closingIssuesReferences(first: 10) {
          nodes {
            number
            title
            url
            labels(first: 20) { nodes { name color } }
          }
        }
      }
    }
  }
}
"""


def run_gh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"gh {' '.join(args)} failed with {result.returncode}")
    return result.stdout


def fetch_pull_requests(owner: str, name: str) -> list[dict]:
    """Page through merged PRs, newest first."""
    nodes: list[dict] = []
    cursor: str | None = None
    while True:
        args = [
            "api", "graphql",
            "-f", f"query={QUERY}",
            "-F", f"owner={owner}",
            "-F", f"name={name}",
        ]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        page = json.loads(run_gh(args))["data"]["repository"]["pullRequests"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"] or len(nodes) >= 500:
            return nodes
        cursor = page["pageInfo"]["endCursor"]


def fetch_open_pull_requests(owner: str, name: str) -> list[dict]:
    """Every open pull request, oldest first."""
    nodes: list[dict] = []
    cursor: str | None = None
    while True:
        args = [
            "api", "graphql",
            "-f", f"query={OPEN_QUERY}",
            "-F", f"owner={owner}",
            "-F", f"name={name}",
        ]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        page = json.loads(run_gh(args))["data"]["repository"]["pullRequests"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"] or len(nodes) >= 300:
            return nodes
        cursor = page["pageInfo"]["endCursor"]


def signed_off(owner: str, name: str, sha: str, context: str) -> bool:
    """True when *sha* already carries a successful sign-off status."""
    out = run_gh(["api", f"repos/{owner}/{name}/commits/{sha}/status"])
    for status in json.loads(out).get("statuses", []):
        if status["context"] == context and status["state"] == "success":
            return True
    return False


def fetch_one_pull_request(owner: str, name: str, number: int) -> dict:
    """Fetch a single pull request, merged or not."""
    out = run_gh([
        "api", "graphql",
        "-f", f"query={SINGLE_QUERY}",
        "-F", f"owner={owner}",
        "-F", f"name={name}",
        "-F", f"number={number}",
    ])
    node = json.loads(out)["data"]["repository"]["pullRequest"]
    if node is None:
        raise SystemExit(f"no such pull request: #{number}")
    return node


def labels_of(container: dict) -> list[dict]:
    return [
        {"name": label["name"], "color": label["color"]}
        for label in container.get("labels", {}).get("nodes", [])
    ]


def normalise(node: dict) -> dict:
    issues = [
        {
            "number": issue["number"],
            "title": issue["title"],
            "url": issue["url"],
            "labels": labels_of(issue),
        }
        for issue in node.get("closingIssuesReferences", {}).get("nodes", [])
    ]
    return {
        "number": node["number"],
        "title": node["title"],
        "url": node["url"],
        "merged_at": node.get("mergedAt"),
        "head_sha": node.get("headRefOid"),
        "base": node["baseRefName"],
        "author": (node.get("author") or {}).get("login", "unknown"),
        "additions": node["additions"],
        "deletions": node["deletions"],
        "changed_files": node["changedFiles"],
        "labels": labels_of(node),
        "issues": issues,
    }


def in_window(node: dict, since: datetime, base: str) -> bool:
    if node["baseRefName"] != base:
        return False
    merged_at = datetime.fromisoformat(node["mergedAt"].replace("Z", "+00:00"))
    return merged_at >= since


def resolve_since(raw: str | None, fallback_days: int) -> datetime:
    """Interpret the --since argument, tolerating a bare date or an empty value."""
    if not raw:
        return datetime.now(timezone.utc) - timedelta(days=fallback_days)
    text = raw.strip().replace("Z", "+00:00")
    if len(text) == 10:
        text += "T00:00:00+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_prompt(payload: dict) -> str:
    """Compose the plain-text brief handed to the model."""
    heading = (
        "Pull request awaiting sign-off before it may merge:"
        if payload.get("scope") == "pull_request"
        else "Merged pull requests awaiting sign-off:"
    )
    lines = [heading, ""]
    for pr in payload["pull_requests"]:
        pr_labels = ", ".join(label["name"] for label in pr["labels"]) or "none"
        lines.append(f"- PR #{pr['number']}: {pr['title']}")
        lines.append(f"  author: {pr['author']}; labels: {pr_labels}")
        lines.append(
            f"  size: +{pr['additions']}/-{pr['deletions']} across "
            f"{pr['changed_files']} file(s)"
        )
        for issue in pr["issues"]:
            issue_labels = ", ".join(label["name"] for label in issue["labels"]) or "none"
            lines.append(
                f"  closes issue #{issue['number']}: {issue['title']} "
                f"[{issue_labels}]"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--base", default="main", help="branch PRs merged into")
    parser.add_argument(
        "--queued",
        action="store_true",
        help="report on every open PR still awaiting sign-off",
    )
    parser.add_argument(
        "--status-context",
        default="manager-signoff",
        help="commit status that marks a PR as already signed off",
    )
    parser.add_argument(
        "--pr",
        type=int,
        default=None,
        help="report on this one pull request instead of a merged window",
    )
    parser.add_argument("--since", default=None, help="ISO date or timestamp")
    parser.add_argument("--fallback-days", type=int, default=30)
    parser.add_argument("--out", default="build/prs.json")
    parser.add_argument("--prompt-out", default="build/prompt.txt")
    parser.add_argument(
        "--github-output",
        default=None,
        help="file to append pr_count and window_start to (pass $GITHUB_OUTPUT)",
    )
    args = parser.parse_args()

    owner, _, name = args.repo.partition("/")

    if args.pr is not None:
        selected = [normalise(fetch_one_pull_request(owner, name, args.pr))]
        scope = "pull_request"
        since = None
    elif args.queued:
        # A draft is not asking to merge, and a PR already signed off at its
        # current head must not be put in front of the reviewer twice.
        candidates = [
            node
            for node in fetch_open_pull_requests(owner, name)
            if not node.get("isDraft") and node["baseRefName"] == args.base
        ]
        selected = [
            normalise(node)
            for node in candidates
            if not signed_off(owner, name, node["headRefOid"], args.status_context)
        ]
        scope = "queued"
        since = None
    else:
        since = resolve_since(args.since, args.fallback_days)
        nodes = fetch_pull_requests(owner, name)
        selected = [normalise(n) for n in nodes if in_window(n, since, args.base)]
        selected.sort(key=lambda pr: pr["merged_at"] or "")
        scope = "window"

    payload = {
        "repo": args.repo,
        "base": args.base,
        "scope": scope,
        "since": since.isoformat() if since else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_requests": selected,
    }

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    prompt = pathlib.Path(args.prompt_out)
    prompt.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text(build_prompt(payload))

    if args.github_output and args.pr is None:
        lines = [f"pr_count={len(selected)}"]
        if args.queued:
            lines.append(
                "pr_numbers=" + ",".join(str(pr["number"]) for pr in selected)
            )
            # Carry the exact commit each PR was reviewed at, so the approval
            # can be refused later if the author pushed during the review.
            lines.append(
                "pr_shas="
                + ",".join(f"{pr['number']}:{pr['head_sha']}" for pr in selected)
            )
        else:
            # Report the resolved window, not the raw argument, which is empty
            # on a first run and on every scheduled run.
            lines.append(f"window_start={since.date().isoformat()}")
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    if args.pr is not None:
        print(f"collected pull request #{args.pr}")
    elif args.queued:
        print(f"{len(selected)} pull request(s) awaiting sign-off")
    else:
        print(
            f"{len(selected)} pull request(s) merged into {args.base} "
            f"since {since.date()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
