#!/usr/bin/env python3
"""Batch-create Jira issues in parallel via MCP.

Usage:
    # From CLI arguments:
    uv run python scripts/batch/batch_create.py --type story "Implement auth" "Add logging"

    # Sub-tasks under a parent:
    uv run python scripts/batch/batch_create.py --type subtask --parent PROJ-100 "Unit tests" "Docs"

    # From JSON stdin:
    echo '[{"summary":"Task A","description":"Details"}]' | uv run python scripts/batch/batch_create.py --stdin

    # From a file:
    uv run python scripts/batch/batch_create.py --file tickets.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mcp_client import MCPPool, MCPToolError, run_async


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-create Jira issues via MCP")
    parser.add_argument("summaries", nargs="*", help="Issue summaries (one per arg)")
    parser.add_argument("--type", default="Task", help="Issue type name: Story|Task|Sub-task|Bug (default: Task)")
    parser.add_argument("--parent", default="", help="Parent issue key for sub-tasks")
    parser.add_argument("--stdin", action="store_true", help="Read JSON array from stdin")
    parser.add_argument("--file", type=str, help="Read JSON array from a file")
    parser.add_argument("--description", default="", help="Default description for CLI-arg tickets")
    parser.add_argument("--project", default="", help="Project key override (default: JIRA_PROJECT_KEY env)")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel sessions (default: 3)")
    parser.add_argument("--json-output", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    tickets: list[dict] = []
    if args.stdin:
        tickets = json.load(sys.stdin)
    elif args.file:
        tickets = json.loads(Path(args.file).read_text())
    elif args.summaries:
        tickets = [{"summary": s, "description": args.description} for s in args.summaries]
    else:
        parser.print_help()
        sys.exit(1)

    if not tickets:
        print("No tickets to create.", file=sys.stderr)
        sys.exit(1)

    concurrency = min(args.concurrency, len(tickets))
    print(f"Creating {len(tickets)} {args.type}(s) via MCP ({concurrency} parallel sessions)...")

    async with MCPPool(concurrency=concurrency) as pool:
        cid = await pool.cloud_id()
        project = args.project or pool._queue._queue[0].project_key

        if not project:
            print("ERROR: Set JIRA_PROJECT_KEY env var or use --project.", file=sys.stderr)
            sys.exit(1)

        if args.parent:
            print(f"  Parent: {args.parent}")

        call_args = []
        for t in tickets:
            kwargs = {
                "cloudId": cid,
                "projectKey": project,
                "issueTypeName": args.type,
                "summary": t.get("summary", ""),
            }
            if t.get("description"):
                kwargs["description"] = t["description"]
            if args.parent:
                kwargs["parent"] = args.parent
            call_args.append(kwargs)

        raw_results = await pool.map("createJiraIssue", call_args)

    results = []
    for i, r in enumerate(raw_results):
        summary = tickets[i].get("summary", "")
        if isinstance(r, Exception):
            print(f"  FAILED — {summary}: {r}", file=sys.stderr)
            results.append({"key": None, "summary": summary, "status": "failed", "error": str(r)})
        else:
            key = r.get("key", "???") if isinstance(r, dict) else str(r)
            print(f"  Created {key} — {summary}")
            results.append({"key": key, "summary": summary, "status": "created"})

    created = sum(1 for r in results if r["status"] == "created")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n=== Summary ===")
    print(f"  Created: {created}")
    print(f"  Failed:  {failed}")
    print(f"  Total:   {len(results)}")

    if args.json_output:
        print(json.dumps(results, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_async(main())
