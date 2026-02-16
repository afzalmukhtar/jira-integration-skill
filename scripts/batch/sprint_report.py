#!/usr/bin/env python3
"""Async sprint report generation.

Queries Jira for sprint data and produces a formatted progress report with:
  - Progress bar
  - Status breakdown (Done / In Progress / To Do)
  - In-progress and to-do ticket details with assignees
  - Stale ticket warnings (no update in 3+ days)

Usage:
    python sprint_report.py
    python sprint_report.py --stale-days 5
    python sprint_report.py --json-output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

from jira_client import JiraClient, JiraConfig, run_async

DONE_STATUSES = {"done", "closed", "resolved"}
IN_PROGRESS_STATUSES = {"in progress", "in review", "in development"}


def parse_jira_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def days_since(date_str: str | None) -> int | None:
    dt = parse_jira_date(date_str)
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    return (now - dt).days


def progress_bar(done: int, total: int, width: int = 30) -> str:
    if total == 0:
        return "[" + " " * width + "] 0%"
    pct = done / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:.0%}"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Jira sprint progress report")
    parser.add_argument("--stale-days", type=int, default=3, help="Days without update to flag as stale (default: 3)")
    parser.add_argument("--json-output", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    config = JiraConfig.from_env()
    if not config.project_key:
        print("ERROR: JIRA_PROJECT_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    jql = (
        f"project={config.project_key} "
        f"AND sprint in openSprints() "
        f"ORDER BY rank"
    )

    async with JiraClient(config=config) as client:
        data = await client.search(
            jql,
            fields="key,summary,status,issuetype,assignee,priority,updated",
            max_results=200,
        )

    issues = data.get("issues", [])
    if not issues:
        print("No issues found in the current sprint.")
        return

    done_list: list[dict] = []
    in_progress_list: list[dict] = []
    todo_list: list[dict] = []
    stale_list: list[dict] = []

    for issue in issues:
        f = issue["fields"]
        key = issue["key"]
        summary = f.get("summary", "")
        status = f.get("status", {}).get("name", "Unknown")
        assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
        priority = f.get("priority", {}).get("name", "")
        updated = f.get("updated", "")
        stale_days_val = days_since(updated)

        entry = {
            "key": key,
            "summary": summary,
            "status": status,
            "assignee": assignee,
            "priority": priority,
            "updated": updated,
            "stale_days": stale_days_val,
            "url": f"{config.base_url}/browse/{key}",
        }

        status_lower = status.lower()
        if status_lower in DONE_STATUSES:
            done_list.append(entry)
        elif status_lower in IN_PROGRESS_STATUSES:
            in_progress_list.append(entry)
            if stale_days_val is not None and stale_days_val >= args.stale_days:
                stale_list.append(entry)
        else:
            todo_list.append(entry)
            if stale_days_val is not None and stale_days_val >= args.stale_days:
                stale_list.append(entry)

    total = len(issues)
    done_count = len(done_list)
    ip_count = len(in_progress_list)
    todo_count = len(todo_list)

    if args.json_output:
        report = {
            "total": total,
            "done": done_count,
            "in_progress": ip_count,
            "todo": todo_count,
            "stale": len(stale_list),
            "progress_pct": round(done_count / total * 100, 1) if total else 0,
            "done_issues": done_list,
            "in_progress_issues": in_progress_list,
            "todo_issues": todo_list,
            "stale_issues": stale_list,
        }
        print(json.dumps(report, indent=2))
        return

    # Pretty print
    print(f"=== Sprint Report: {config.project_key} ===")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    print(f"Progress: {progress_bar(done_count, total)}")
    print(f"  Done:        {done_count}")
    print(f"  In Progress: {ip_count}")
    print(f"  To Do:       {todo_count}")
    print(f"  Total:       {total}")

    if in_progress_list:
        print(f"\n--- In Progress ({ip_count}) ---")
        for e in in_progress_list:
            stale_flag = f" [STALE {e['stale_days']}d]" if (e["stale_days"] or 0) >= args.stale_days else ""
            print(f"  [{e['key']}] {e['summary'][:60]}")
            print(f"    Assignee: {e['assignee']} | Priority: {e['priority']}{stale_flag}")

    if todo_list:
        print(f"\n--- To Do ({todo_count}) ---")
        for e in todo_list:
            stale_flag = f" [STALE {e['stale_days']}d]" if (e["stale_days"] or 0) >= args.stale_days else ""
            print(f"  [{e['key']}] {e['summary'][:60]}")
            print(f"    Assignee: {e['assignee']} | Priority: {e['priority']}{stale_flag}")

    if stale_list:
        print(f"\n--- Stale Tickets ({len(stale_list)}) --- (no update in {args.stale_days}+ days)")
        for e in stale_list:
            print(f"  [{e['key']}] {e['summary'][:50]} — {e['stale_days']}d stale ({e['assignee']})")

    if done_list:
        print(f"\n--- Completed ({done_count}) ---")
        for e in done_list:
            print(f"  [{e['key']}] {e['summary'][:60]}")

    print()


if __name__ == "__main__":
    run_async(main())
