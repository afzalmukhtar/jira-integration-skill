#!/usr/bin/env python3
"""Batch-update (transition / comment) Jira issues in parallel.

Usage:
    # Transition multiple tickets to Done:
    python batch_update.py --transition done PROJ-101 PROJ-102 PROJ-103

    # Transition to In Progress:
    python batch_update.py --transition progress PROJ-101 PROJ-102

    # Add comment to multiple tickets:
    python batch_update.py --comment "Deployed to staging" PROJ-101 PROJ-102

    # Combined: transition + comment:
    python batch_update.py --transition done --comment "Completed in sprint 5" PROJ-101 PROJ-102

    # From stdin (one ticket key per line):
    echo -e "PROJ-101\\nPROJ-102" | python batch_update.py --stdin --transition done
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from jira_client import JiraClient, JiraConfig, run_async

TRANSITION_ALIASES = {
    "done": "Done",
    "progress": "In Progress",
    "in-progress": "In Progress",
    "todo": "To Do",
    "to-do": "To Do",
    "review": "In Review",
    "in-review": "In Review",
    "blocked": "Blocked",
}


async def update_one(
    client: JiraClient,
    key: str,
    transition_name: str | None,
    comment: str | None,
) -> dict:
    """Update a single ticket: transition and/or add comment."""
    result: dict = {"key": key, "actions": [], "status": "ok"}
    try:
        if transition_name:
            tid = await client.find_transition_id(key, transition_name)
            if tid:
                await client.transition_issue(key, tid)
                result["actions"].append(f"transitioned to {transition_name}")
                print(f"  {key}: transitioned to {transition_name}")
            else:
                result["actions"].append(f"transition '{transition_name}' not found")
                result["status"] = "partial"
                print(f"  {key}: transition '{transition_name}' not available", file=sys.stderr)

        if comment:
            await client.add_comment(key, comment)
            result["actions"].append("comment added")
            print(f"  {key}: comment added")

    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        print(f"  {key}: FAILED — {exc}", file=sys.stderr)

    return result


async def batch_update(
    client: JiraClient,
    keys: list[str],
    transition_name: str | None,
    comment: str | None,
) -> list[dict]:
    tasks = [update_one(client, k, transition_name, comment) for k in keys]
    return await asyncio.gather(*tasks)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-update Jira issues in parallel")
    parser.add_argument("keys", nargs="*", help="Issue keys (e.g. PROJ-101 PROJ-102)")
    parser.add_argument("--transition", type=str, help="Target status: done|progress|todo|review|blocked")
    parser.add_argument("--comment", type=str, help="Comment to add to each ticket")
    parser.add_argument("--stdin", action="store_true", help="Read keys from stdin (one per line)")
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

    if not args.transition and not args.comment:
        print("Provide --transition and/or --comment.", file=sys.stderr)
        sys.exit(1)

    transition_name = TRANSITION_ALIASES.get(args.transition, args.transition) if args.transition else None

    config = JiraConfig.from_env()

    print(f"Updating {len(keys)} ticket(s)...")
    if transition_name:
        print(f"  Transition: {transition_name}")
    if args.comment:
        print(f"  Comment: {args.comment[:80]}...")

    async with JiraClient(config=config) as client:
        results = await batch_update(client, keys, transition_name, args.comment)

    ok = sum(1 for r in results if r["status"] == "ok")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"\n=== Summary ===")
    print(f"  Succeeded: {ok}")
    print(f"  Partial:   {partial}")
    print(f"  Failed:    {failed}")
    print(f"  Total:     {len(results)}")

    if args.json_output:
        print(json.dumps(results, indent=2))

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_async(main())
