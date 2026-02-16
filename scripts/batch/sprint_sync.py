#!/usr/bin/env python3
"""Bidirectional sync between JIRA_TODO.md and Jira via MCP.

Phase 1 - Push: Read locally completed tickets ([x]), tell agent to transition.
Phase 2 - Pull: Fetch sprint tickets from Jira and regenerate JIRA_TODO.md.

Usage:
    uv run python scripts/batch/sprint_sync.py
    uv run python scripts/batch/sprint_sync.py --pull-only
    uv run python scripts/batch/sprint_sync.py --push-only
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from mcp_client import MCPPool, mcp_session, run_async

TICKET_RE = re.compile(r"- \[([x ])\] \[([A-Z]+-\d+)\]")
HEADER_RE = re.compile(r"## \[([x ])\] \[([A-Z]+-\d+)\]")
DONE_STATUSES = {"done", "closed", "resolved"}


# ---------------------------------------------------------------------------
# Phase 1: Push local completions
# ---------------------------------------------------------------------------


def parse_completed_tickets(todo_path: Path, project_key: str) -> list[str]:
    """Extract ticket keys marked [x] from JIRA_TODO.md."""
    if not todo_path.exists():
        return []
    text = todo_path.read_text()
    completed: list[str] = []
    for pattern in (TICKET_RE, HEADER_RE):
        for match in pattern.finditer(text):
            checked, key = match.group(1), match.group(2)
            if checked == "x" and key.startswith(f"{project_key}-"):
                completed.append(key)
    return list(dict.fromkeys(completed))


async def push_completions(pool: MCPPool, cid: str, keys: list[str]) -> list[dict]:
    """Add a 'marked as done' comment to completed tickets.

    Actual status transitions should be confirmed by the AI agent, since the
    Atlassian MCP server handles transitions as part of issue updates.
    """
    results = []
    for key in keys:
        try:
            # Check current status
            issue = await pool.call("getJiraIssue", cloudId=cid, issueIdOrKey=key)
            status = "unknown"
            if isinstance(issue, dict):
                status = issue.get("fields", {}).get("status", {}).get("name", "unknown").lower()

            if status in DONE_STATUSES:
                print(f"  {key}: already {status}")
                results.append({"key": key, "status": "already_done"})
                continue

            await pool.call("addCommentToJiraIssue",
                            cloudId=cid, issueIdOrKey=key,
                            commentBody="Marked as complete in JIRA_TODO.md. Please transition to Done.")
            print(f"  {key}: completion comment added (transition via agent)")
            results.append({"key": key, "status": "commented"})
        except Exception as exc:
            print(f"  {key}: FAILED — {exc}", file=sys.stderr)
            results.append({"key": key, "status": "failed", "error": str(exc)})
    return results


# ---------------------------------------------------------------------------
# Phase 2: Pull sprint tickets and regenerate JIRA_TODO.md
# ---------------------------------------------------------------------------


async def pull_sprint_tickets(pool: MCPPool, cid: str, project_key: str) -> list[dict]:
    """Fetch current sprint tickets for the user."""
    jql = (
        f"project={project_key} "
        f"AND assignee=currentUser() "
        f"AND sprint in openSprints() "
        f"ORDER BY rank"
    )
    data = await pool.call(
        "searchJiraIssuesUsingJql",
        cloudId=cid,
        jql=jql,
        fields=["key", "summary", "status", "issuetype", "parent"],
        maxResults=200,
    )
    if isinstance(data, dict):
        return data.get("issues", [])
    return []


def generate_todo_md(issues: list[dict], base_url: str) -> str:
    """Build the JIRA_TODO.md markdown content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# JIRA Sprint TODO",
        "",
        f"Generated: {now}",
        f"Source: {base_url}",
        "",
    ]

    stories: dict[str, dict] = {}
    standalone: list[dict] = []

    for issue in issues:
        f = issue.get("fields", {})
        key = issue.get("key", "")
        summary = f.get("summary", "")
        status = f.get("status", {}).get("name", "")
        itype = f.get("issuetype", {}).get("name", "")
        parent_key = f.get("parent", {}).get("key") if f.get("parent") else None
        checkbox = "[x]" if status.lower() in DONE_STATUSES else "[ ]"
        url = f"{base_url}/browse/{key}" if base_url else key

        entry = {"key": key, "summary": summary, "checkbox": checkbox, "url": url}

        if itype in ("Story", "Epic", "Bug") and not parent_key:
            stories[key] = {**entry, "children": []}
        elif parent_key and parent_key in stories:
            stories[parent_key]["children"].append(entry)
        else:
            standalone.append(entry)

    done_count = 0
    total_count = 0

    for key, story in stories.items():
        lines.append(f"## {story['checkbox']} [{key}]({story['url']}) {story['summary']}")
        lines.append("")
        total_count += 1
        if story["checkbox"] == "[x]":
            done_count += 1
        for child in story["children"]:
            lines.append(f"- {child['checkbox']} [{child['key']}]({child['url']}) {child['summary']}")
            total_count += 1
            if child["checkbox"] == "[x]":
                done_count += 1
        lines.append("")

    if standalone:
        lines.append("## Other Tasks")
        lines.append("")
        for t in standalone:
            lines.append(f"- {t['checkbox']} [{t['key']}]({t['url']}) {t['summary']}")
            total_count += 1
            if t["checkbox"] == "[x]":
                done_count += 1
        lines.append("")

    lines.append("---")
    lines.append(f"**Progress:** {done_count}/{total_count} completed")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bidirectional Jira sync via MCP")
    parser.add_argument("--file", default="JIRA_TODO.md", help="Path to JIRA_TODO.md")
    parser.add_argument("--pull-only", action="store_true", help="Skip push, only pull")
    parser.add_argument("--push-only", action="store_true", help="Skip pull, only push")
    args = parser.parse_args()

    project_key = os.environ.get("JIRA_PROJECT_KEY", "")
    base_url = os.environ.get("JIRA_BASE_URL", "")
    if not project_key:
        print("ERROR: JIRA_PROJECT_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    todo_path = Path(args.file)

    async with MCPPool(concurrency=1) as pool:
        cid = await pool.cloud_id()

        # Phase 1: Push
        if not args.pull_only:
            completed = parse_completed_tickets(todo_path, project_key)
            if completed:
                print(f"=== Phase 1: Pushing {len(completed)} completion(s) via MCP ===")
                results = await push_completions(pool, cid, completed)
                commented = sum(1 for r in results if r["status"] == "commented")
                already = sum(1 for r in results if r["status"] == "already_done")
                failed = sum(1 for r in results if r["status"] == "failed")
                print(f"  Commented: {commented}, Already done: {already}, Failed: {failed}")
            else:
                print("=== Phase 1: No locally completed tickets to push ===")

            if args.push_only:
                return

        # Phase 2: Pull
        print(f"\n=== Phase 2: Pulling sprint tickets via MCP ===")
        issues = await pull_sprint_tickets(pool, cid, project_key)
        print(f"  Fetched {len(issues)} issue(s)")

        md = generate_todo_md(issues, base_url)
        todo_path.write_text(md)
        print(f"  Wrote {todo_path}")

        done_count = md.count("[x]")
        total_lines = md.count("[ ]") + done_count
        print(f"  Progress: {done_count}/{total_lines}")


if __name__ == "__main__":
    run_async(main())
