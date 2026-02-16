#!/usr/bin/env python3
"""Batch-create Jira issues in parallel.

Usage:
    # From CLI arguments (one summary per arg):
    python batch_create.py --type story "Implement auth" "Add logging" "Write tests"

    # With a parent for sub-tasks:
    python batch_create.py --type subtask --parent PROJ-100 "Unit tests" "Integration tests"

    # From JSON stdin (full control):
    echo '[{"summary":"Task A","description":"Details"},{"summary":"Task B"}]' | python batch_create.py --stdin

    # From a file:
    python batch_create.py --file tickets.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from jira_client import JiraClient, JiraConfig, run_async


async def batch_create(
    client: JiraClient,
    tickets: list[dict],
    issue_type_id: str,
    parent_key: str = "",
) -> list[dict]:
    """Create multiple issues concurrently. Returns list of results."""

    async def _create_one(ticket: dict) -> dict:
        summary = ticket.get("summary", "")
        description = ticket.get("description", "")
        try:
            payload = client.build_issue_payload(
                summary,
                issue_type_id=issue_type_id,
                description=description,
                parent_key=parent_key,
            )
            result = await client.create_issue(payload)
            key = result.get("key", "???")
            print(f"  Created {key} — {summary}")
            return {"key": key, "summary": summary, "status": "created"}
        except Exception as exc:
            print(f"  FAILED — {summary}: {exc}", file=sys.stderr)
            return {"key": None, "summary": summary, "status": "failed", "error": str(exc)}

    tasks = [_create_one(t) for t in tickets]
    return await asyncio.gather(*tasks)


def resolve_type_id(config: JiraConfig, type_name: str) -> str:
    """Map a friendly type name to the configured type ID."""
    mapping = {
        "story": config.story_type_id,
        "task": config.task_type_id,
        "subtask": config.subtask_type_id,
        "sub-task": config.subtask_type_id,
        "bug": config.bug_type_id,
    }
    return mapping.get(type_name.lower(), config.task_type_id)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-create Jira issues in parallel")
    parser.add_argument("summaries", nargs="*", help="Issue summaries (one per arg)")
    parser.add_argument("--type", default="task", help="Issue type: story|task|subtask|bug (default: task)")
    parser.add_argument("--parent", default="", help="Parent issue key for sub-tasks")
    parser.add_argument("--stdin", action="store_true", help="Read JSON array from stdin")
    parser.add_argument("--file", type=str, help="Read JSON array from a file")
    parser.add_argument("--description", default="", help="Default description for CLI-arg tickets")
    parser.add_argument("--json-output", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    # Build ticket list
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

    config = JiraConfig.from_env()
    type_id = resolve_type_id(config, args.type)

    print(f"Creating {len(tickets)} {args.type}(s) in {config.project_key}...")
    if args.parent:
        print(f"  Parent: {args.parent}")

    async with JiraClient(config=config) as client:
        results = await batch_create(client, tickets, type_id, args.parent)

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
