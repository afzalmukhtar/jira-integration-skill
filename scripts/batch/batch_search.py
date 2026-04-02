#!/usr/bin/env python3
"""Run multiple JQL queries concurrently via MCP and aggregate results.

Usage:
    # Shortcut queries:
    uv run python scripts/batch/batch_search.py mine sprint bugs recent

    # Custom JQL:
    uv run python scripts/batch/batch_search.py "priority=High AND status!=Done"

    # JSON output:
    uv run python scripts/batch/batch_search.py --json-output mine sprint
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from mcp_client import MCPPool, run_async


def resolve_shortcut(query: str, project_key: str) -> str:
    """Convert shortcut names to JQL queries."""
    shortcuts = {
        "mine": f"project={project_key} AND assignee=currentUser() AND status!=Done ORDER BY priority DESC",
        "sprint": f"project={project_key} AND sprint in openSprints() ORDER BY rank",
        "recent": f"project={project_key} AND updated >= -7d ORDER BY updated DESC",
        "bugs": f"project={project_key} AND type=Bug AND status!=Done ORDER BY priority DESC",
        "done": f"project={project_key} AND status=Done AND resolved >= -7d ORDER BY resolved DESC",
        "blocked": f"project={project_key} AND status=Blocked ORDER BY priority DESC",
        "high": f"project={project_key} AND priority IN (Highest, High) AND status!=Done ORDER BY priority DESC",
        "unassigned": f"project={project_key} AND assignee IS EMPTY AND status!=Done ORDER BY created DESC",
    }
    return shortcuts.get(query.lower(), query)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch JQL search via MCP")
    parser.add_argument("queries", nargs="+", help="JQL queries or shortcuts")
    parser.add_argument("--max-results", type=int, default=50, help="Max results per query (default: 50)")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel sessions (default: 3)")
    parser.add_argument("--json-output", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    project_key = os.environ.get("JIRA_PROJECT_KEY", "")
    base_url = os.environ.get("JIRA_BASE_URL", "")
    resolved = [resolve_shortcut(q, project_key) for q in args.queries]
    concurrency = min(args.concurrency, len(resolved))

    print(f"Running {len(resolved)} query(ies) via MCP ({concurrency} parallel sessions)...\n")

    async with MCPPool(concurrency=concurrency) as pool:
        cid = await pool.cloud_id()

        call_args = [
            {
                "cloudId": cid,
                "jql": jql,
                "fields": ["key", "summary", "status", "issuetype", "priority", "assignee"],
                "maxResults": args.max_results,
            }
            for jql in resolved
        ]
        raw_results = await pool.map("searchJiraIssuesUsingJql", call_args)

    results = []
    for i, r in enumerate(raw_results):
        jql = resolved[i]
        if isinstance(r, Exception):
            results.append({"jql": jql, "total": 0, "issues": [], "status": "failed", "error": str(r)})
        else:
            issues = []
            for issue in (r.get("issues", []) if isinstance(r, dict) else []):
                f = issue.get("fields", {})
                issues.append({
                    "key": issue.get("key", ""),
                    "summary": f.get("summary", ""),
                    "status": f.get("status", {}).get("name", ""),
                    "type": f.get("issuetype", {}).get("name", ""),
                    "priority": f.get("priority", {}).get("name", ""),
                    "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                })
            results.append({
                "jql": jql,
                "total": r.get("total", 0) if isinstance(r, dict) else 0,
                "issues": issues,
                "status": "ok",
            })

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        for i, result in enumerate(results):
            if i > 0:
                print()
            jql_display = result["jql"][:80]
            icon = "OK" if result["status"] == "ok" else "FAILED"
            print(f"--- Query [{icon}]: {jql_display} ---")
            if result["status"] == "failed":
                print(f"  Error: {result.get('error', 'Unknown')}")
                continue
            print(f"  Total: {result['total']} issue(s)")
            for issue in result["issues"]:
                key = issue["key"]
                summary = issue["summary"][:60]
                status = issue["status"]
                assignee = issue["assignee"]
                priority = issue["priority"]
                print(f"  [{key}] {summary}")
                print(f"    Status: {status} | Priority: {priority} | Assignee: {assignee}")
                if base_url:
                    print(f"    {base_url}/browse/{key}")

    total_issues = sum(r["total"] for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n=== Summary: {total_issues} total issues across {len(results)} queries ({failed} failed) ===")


if __name__ == "__main__":
    run_async(main())
