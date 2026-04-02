#!/usr/bin/env python3
"""Batch-transition Jira issues to a target status via MCP.

Usage:
    # Transition tickets to Done:
    uv run python scripts/batch/batch_transition.py --status "Done" PROJ-101 PROJ-102

    # List available transitions for a ticket:
    uv run python scripts/batch/batch_transition.py --list-transitions PROJ-101
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from mcp_client import MCPPool, run_async


async def list_transitions(pool: MCPPool, cid: str, key: str) -> None:
    result = await pool.call("getTransitionsForJiraIssue", cloudId=cid, issueIdOrKey=key)
    transitions = result.get("transitions", []) if isinstance(result, dict) else []
    print(f"\nAvailable transitions for {key}:")
    for t in transitions:
        print(f"  id={t['id']:>4}  name={t['name']}")


async def transition_one(
    pool: MCPPool,
    cid: str,
    key: str,
    target_status: str,
) -> dict:
    result: dict = {"key": key, "status": "ok"}
    try:
        # Get available transitions
        resp = await pool.call("getTransitionsForJiraIssue", cloudId=cid, issueIdOrKey=key)
        transitions = resp.get("transitions", []) if isinstance(resp, dict) else []

        # Find matching transition (case-insensitive)
        match = next(
            (t for t in transitions if t["name"].lower() == target_status.lower()),
            None,
        )
        if match is None:
            available = [t["name"] for t in transitions]
            raise ValueError(f"No transition named '{target_status}'. Available: {available}")

        await pool.call(
            "transitionJiraIssue",
            cloudId=cid,
            issueIdOrKey=key,
            transition={"id": match["id"]},
        )
        print(f"  {key}: → {target_status} (transition id={match['id']})")
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        print(f"  {key}: FAILED — {exc}", file=sys.stderr)
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-transition Jira issues via MCP")
    parser.add_argument("keys", nargs="*", help="Issue keys (e.g. PROJ-101 PROJ-102)")
    parser.add_argument("--status", type=str, help="Target status name (e.g. 'Done')")
    parser.add_argument("--list-transitions", metavar="KEY", help="List transitions for a single issue and exit")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel sessions (default: 3)")
    args = parser.parse_args()

    if args.list_transitions:
        async with MCPPool(concurrency=1) as pool:
            cid = await pool.cloud_id()
            await list_transitions(pool, cid, args.list_transitions)
        return

    if not args.keys or not args.status:
        parser.print_help()
        sys.exit(1)

    keys = args.keys
    concurrency = min(args.concurrency, len(keys))
    print(f"Transitioning {len(keys)} ticket(s) to '{args.status}' ({concurrency} parallel sessions)...")

    async with MCPPool(concurrency=concurrency) as pool:
        cid = await pool.cloud_id()
        tasks = [transition_one(pool, cid, k, args.status) for k in keys]
        results = await asyncio.gather(*tasks)

    ok = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "failed")
    print("\n=== Summary ===")
    print(f"  Succeeded: {ok}")
    print(f"  Failed:    {failed}")
    print(f"  Total:     {len(results)}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_async(main())
