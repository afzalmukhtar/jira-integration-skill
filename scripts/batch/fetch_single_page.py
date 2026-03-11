#!/usr/bin/env python3
"""Fetch one page of all-status Jira tickets and output clean JSON to stdout."""

from __future__ import annotations

import json
import sys

from mcp_client import MCPPool, run_async


async def main() -> None:
    async with MCPPool(concurrency=1) as pool:
        cid = await pool.cloud_id()
        result = await pool.call(
            "searchJiraIssuesUsingJql",
            cloudId=cid,
            jql="assignee = currentUser() ORDER BY created ASC",
            fields=["key", "summary", "status", "issuetype", "priority",
                    "assignee", "resolutiondate", "created"],
            maxResults=100,
        )

    issues = []
    for issue in (result.get("issues", []) if isinstance(result, dict) else []):
        f = issue.get("fields", {})
        issues.append({
            "key": issue.get("key", ""),
            "summary": f.get("summary", ""),
            "status": f.get("status", {}).get("name", ""),
            "type": f.get("issuetype", {}).get("name", ""),
            "priority": (f.get("priority") or {}).get("name", ""),
            "resolutiondate": (f.get("resolutiondate") or "")[:10],
            "created": (f.get("created") or "")[:10],
        })

    print(json.dumps(issues, indent=2), file=sys.stdout)
    print(f"Fetched {len(issues)} tickets", file=sys.stderr)


if __name__ == "__main__":
    run_async(main())
