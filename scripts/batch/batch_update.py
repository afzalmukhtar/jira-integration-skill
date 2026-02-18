#!/usr/bin/env python3
"""Batch-add comments to Jira issues in parallel via MCP.

Usage:
    # Add comment to multiple tickets:
    uv run python scripts/batch/batch_update.py --comment "Deployed to staging" PROJ-101 PROJ-102

    # From stdin (one key per line):
    echo -e "PROJ-101\\nPROJ-102" | uv run python scripts/batch/batch_update.py --stdin --comment "Done"

Note: This script only supports adding comments. For field updates or status
transitions, use the AI agent's MCP tools directly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from mcp_client import MCPPool, run_async


async def update_one(
    pool: MCPPool,
    cid: str,
    key: str,
    comment: str | None,
) -> dict:
    """Update a single ticket: add comment."""
    result: dict = {"key": key, "actions": [], "status": "ok"}
    try:
        if comment:
            await pool.call("addCommentToJiraIssue",
                            cloudId=cid, issueIdOrKey=key, commentBody=comment)
            result["actions"].append("comment added")
            print(f"  {key}: comment added")
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        print(f"  {key}: FAILED — {exc}", file=sys.stderr)
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-update Jira issues via MCP")
    parser.add_argument("keys", nargs="*", help="Issue keys (e.g. PROJ-101 PROJ-102)")
    parser.add_argument("--comment", type=str, help="Comment to add to each ticket")
    parser.add_argument("--stdin", action="store_true", help="Read keys from stdin (one per line)")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel sessions (default: 3)")
    parser.add_argument("--json-output", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    keys: list[str] = []
    if args.stdin:
        keys = [line.strip() for line in sys.stdin if line.strip()]
    elif args.keys:
        keys = args.keys
    else:
        parser.print_help()
        sys.exit(1)

    if not keys:
        print("No ticket keys provided.", file=sys.stderr)
        sys.exit(1)

    if not args.comment:
        print("Provide --comment. For status transitions, use the AI agent directly.", file=sys.stderr)
        sys.exit(1)

    concurrency = min(args.concurrency, len(keys))
    print(f"Updating {len(keys)} ticket(s) via MCP ({concurrency} parallel sessions)...")
    if args.comment:
        print(f"  Comment: {args.comment[:80]}...")

    async with MCPPool(concurrency=concurrency) as pool:
        cid = await pool.cloud_id()
        tasks = [update_one(pool, cid, k, args.comment) for k in keys]
        results = await asyncio.gather(*tasks)

    ok = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n=== Summary ===")
    print(f"  Succeeded: {ok}")
    print(f"  Failed:    {failed}")
    print(f"  Total:     {len(results)}")

    if args.json_output:
        print(json.dumps(results, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_async(main())
