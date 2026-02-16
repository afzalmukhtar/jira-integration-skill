#!/usr/bin/env python3
"""Bidirectional sync between JIRA_TODO.md and Jira (async version).

Phase 1 - Push: Read locally completed tickets ([x]) and transition to Done in Jira.
Phase 2 - Pull: Fetch sprint tickets from Jira and regenerate JIRA_TODO.md.

All API calls within each phase run concurrently.

Usage:
    python sprint_sync.py                        # default: ./JIRA_TODO.md
    python sprint_sync.py --file path/to/TODO.md
    python sprint_sync.py --pull-only            # skip push, just pull
    python sprint_sync.py --push-only            # skip pull, just push
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

from jira_client import JiraClient, JiraConfig, run_async

TICKET_RE = re.compile(r"- \[([x ])\] \[([A-Z]+-\d+)\]")
HEADER_RE = re.compile(r"## \[([x ])\] \[([A-Z]+-\d+)\]")
DONE_STATUSES = {"done", "closed", "resolved"}


# ---------------------------------------------------------------------------
# Phase 1: Push local completions to Jira
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
    return list(dict.fromkeys(completed))  # deduplicate preserving order


async def push_completion(client: JiraClient, key: str) -> dict:
    """Transition a single ticket to Done (skip if already done)."""
    try:
        issue = await client.get_issue(key)
        current = issue["fields"]["status"]["name"].lower()
        if current in DONE_STATUSES:
            print(f"  {key}: already {current}")
            return {"key": key, "status": "already_done"}

        tid = await client.find_transition_id(key, "Done")
        if not tid:
            print(f"  {key}: no 'Done' transition available", file=sys.stderr)
            return {"key": key, "status": "no_transition"}

        await client.transition_issue(key, tid)
        print(f"  {key}: transitioned to Done")
        return {"key": key, "status": "transitioned"}
    except Exception as exc:
        print(f"  {key}: FAILED — {exc}", file=sys.stderr)
        return {"key": key, "status": "failed", "error": str(exc)}


async def push_all(client: JiraClient, keys: list[str]) -> list[dict]:
    tasks = [push_completion(client, k) for k in keys]
    return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Phase 2: Pull sprint tickets and regenerate JIRA_TODO.md
# ---------------------------------------------------------------------------


async def pull_sprint_tickets(client: JiraClient, config: JiraConfig) -> list[dict]:
    """Fetch current sprint tickets for the user."""
    jql = (
        f"project={config.project_key} "
        f"AND assignee=currentUser() "
        f"AND sprint in openSprints() "
        f"ORDER BY rank"
    )
    data = await client.search(
        jql,
        fields="key,summary,status,issuetype,parent",
        max_results=200,
    )
    return data.get("issues", [])


def generate_todo_md(issues: list[dict], config: JiraConfig) -> str:
    """Build the JIRA_TODO.md markdown content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# JIRA Sprint TODO",
        "",
        f"Generated: {now}",
        f"Source: {config.base_url}",
        "",
    ]

    stories: dict[str, dict] = {}
    standalone: list[dict] = []

    for issue in issues:
        f = issue["fields"]
        key = issue["key"]
        summary = f["summary"]
        status = f["status"]["name"]
        itype = f["issuetype"]["name"]
        parent_key = f.get("parent", {}).get("key") if f.get("parent") else None
        checkbox = "[x]" if status.lower() in DONE_STATUSES else "[ ]"
        url = f"{config.base_url}/browse/{key}"

        entry = {
            "key": key,
            "summary": summary,
            "status": status,
            "checkbox": checkbox,
            "url": url,
        }

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
    parser = argparse.ArgumentParser(description="Bidirectional Jira ↔ JIRA_TODO.md sync")
    parser.add_argument("--file", default="JIRA_TODO.md", help="Path to JIRA_TODO.md")
    parser.add_argument("--pull-only", action="store_true", help="Skip push, only pull")
    parser.add_argument("--push-only", action="store_true", help="Skip pull, only push")
    args = parser.parse_args()

    config = JiraConfig.from_env()
    if not config.project_key:
        print("ERROR: JIRA_PROJECT_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    todo_path = Path(args.file)

    async with JiraClient(config=config) as client:
        # Phase 1: Push
        if not args.pull_only:
            completed = parse_completed_tickets(todo_path, config.project_key)
            if completed:
                print(f"=== Phase 1: Pushing {len(completed)} completion(s) to Jira ===")
                results = await push_all(client, completed)
                transitioned = sum(1 for r in results if r["status"] == "transitioned")
                already = sum(1 for r in results if r["status"] == "already_done")
                failed = sum(1 for r in results if r["status"] == "failed")
                print(f"  Transitioned: {transitioned}, Already done: {already}, Failed: {failed}")
            else:
                print("=== Phase 1: No locally completed tickets to push ===")

            if args.push_only:
                return

        # Phase 2: Pull
        print(f"\n=== Phase 2: Pulling sprint tickets from Jira ===")
        issues = await pull_sprint_tickets(client, config)
        print(f"  Fetched {len(issues)} issue(s)")

        md = generate_todo_md(issues, config)
        todo_path.write_text(md)
        print(f"  Wrote {todo_path}")

        done_count = md.count("[x]")
        total_lines = md.count("[ ]") + done_count
        print(f"  Progress: {done_count}/{total_lines}")


if __name__ == "__main__":
    run_async(main())
