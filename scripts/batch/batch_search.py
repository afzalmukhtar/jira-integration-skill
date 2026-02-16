#!/usr/bin/env python3
"""Run multiple JQL queries concurrently and aggregate results.

Usage:
    # Multiple JQL queries:
    python batch_search.py "assignee=currentUser() AND status='In Progress'" "priority=High AND status!=Done"

    # Shortcut queries:
    python batch_search.py mine sprint bugs recent

    # Output as JSON:
    python batch_search.py --json-output mine sprint
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from jira_client import JiraClient, JiraConfig, run_async


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


async def run_query(client: JiraClient, jql: str, max_results: int = 50) -> dict:
    """Execute a single JQL search and return structured result."""
    try:
        data = await client.search(jql, max_results=max_results)
        issues = []
        for issue in data.get("issues", []):
            f = issue.get("fields", {})
            issues.append({
                "key": issue["key"],
                "summary": f.get("summary", ""),
                "status": f.get("status", {}).get("name", ""),
                "type": f.get("issuetype", {}).get("name", ""),
                "priority": f.get("priority", {}).get("name", ""),
                "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            })
        return {
            "jql": jql,
            "total": data.get("total", 0),
            "issues": issues,
            "status": "ok",
        }
    except Exception as exc:
        return {"jql": jql, "total": 0, "issues": [], "status": "failed", "error": str(exc)}


async def batch_search(client: JiraClient, queries: list[str], max_results: int = 50) -> list[dict]:
    tasks = [run_query(client, q, max_results) for q in queries]
    return await asyncio.gather(*tasks)


def print_results(results: list[dict], base_url: str) -> None:
    """Pretty-print search results to stdout."""
    for i, result in enumerate(results):
        if i > 0:
            print()
        jql_display = result["jql"][:80]
        status_icon = "OK" if result["status"] == "ok" else "FAILED"
        print(f"--- Query [{status_icon}]: {jql_display} ---")

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
            url = f"{base_url}/browse/{key}"
            print(f"  [{key}] {summary}")
            print(f"    Status: {status} | Priority: {priority} | Assignee: {assignee}")
            print(f"    {url}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch JQL search with parallel execution")
    parser.add_argument("queries", nargs="+", help="JQL queries or shortcuts (mine, sprint, bugs, recent, done, blocked, high, unassigned)")
    parser.add_argument("--max-results", type=int, default=50, help="Max results per query (default: 50)")
    parser.add_argument("--json-output", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    config = JiraConfig.from_env()
    resolved = [resolve_shortcut(q, config.project_key) for q in args.queries]

    print(f"Running {len(resolved)} query(ies) in parallel...\n")

    async with JiraClient(config=config) as client:
        results = await batch_search(client, resolved, args.max_results)

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, config.base_url)

    total_issues = sum(r["total"] for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n=== Summary: {total_issues} total issues across {len(results)} queries ({failed} failed) ===")


if __name__ == "__main__":
    run_async(main())
