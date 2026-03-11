#!/usr/bin/env python3
"""Fetch ALL Jira tickets assigned to currentUser() with full pagination.

Outputs a JSON array of all issues to stdout.

Usage:
    uv run python scripts/batch/fetch_all_history.py > /tmp/jira_all.json
    uv run python scripts/batch/fetch_all_history.py --status-filter  # resolved only
"""

from __future__ import annotations

import argparse
import json

from mcp_client import MCPPool, run_async

PAGE_SIZE = 100


async def main() -> None:
    parser = argparse.ArgumentParser(description="Paginated full Jira history fetch")
    parser.add_argument("--status-filter", action="store_true",
                        help="Only fetch Done/Closed/Resolved tickets")
    args = parser.parse_args()

    if args.status_filter:
        jql = "assignee = currentUser() AND status in (Done, Closed, Resolved) ORDER BY created ASC"
    else:
        jql = "assignee = currentUser() ORDER BY created ASC"

    all_issues: list[dict] = []
    start_at = 0
    total = None

    async with MCPPool(concurrency=1) as pool:
        cid = await pool.cloud_id()

        while True:
            print(f"  Fetching page startAt={start_at}...", flush=True)
            result = await pool.call(
                "searchJiraIssuesUsingJql",
                cloudId=cid,
                jql=jql,
                fields=["key", "summary", "status", "issuetype", "priority",
                        "assignee", "resolutiondate", "created", "parent"],
                maxResults=PAGE_SIZE,
                startAt=start_at,
            )

            if not isinstance(result, dict):
                print(f"  Unexpected result type: {type(result)}")
                break

            if total is None:
                reported = result.get("total", 0)
                print(f"  Total tickets reported by Jira API: {reported} (may be 0 if unsupported)", flush=True)

            issues = result.get("issues", [])
            if not issues:
                print("  Empty page — pagination complete.", flush=True)
                break

            for issue in issues:
                f = issue.get("fields", {})
                parent = f.get("parent") or {}
                all_issues.append({
                    "key": issue.get("key", ""),
                    "summary": f.get("summary", ""),
                    "status": f.get("status", {}).get("name", ""),
                    "type": f.get("issuetype", {}).get("name", ""),
                    "priority": (f.get("priority") or {}).get("name", ""),
                    "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                    "resolutiondate": (f.get("resolutiondate") or "")[:10],
                    "created": (f.get("created") or "")[:10],
                    "parent_key": parent.get("key", ""),
                })

            start_at += len(issues)
            print(f"  Fetched {len(all_issues)} so far (page returned {len(issues)} issues)", flush=True)

            if len(issues) < PAGE_SIZE:
                print("  Last page (fewer results than PAGE_SIZE) — done.", flush=True)
                break

    print(f"\nFetch complete: {len(all_issues)} tickets total", flush=True)
    print(json.dumps(all_issues, indent=2))


if __name__ == "__main__":
    run_async(main())
