#!/usr/bin/env python3
"""Smart bidirectional sync between JIRA_TODO.md and Jira via MCP.

Status emojis:
  📋  To Do          👨🏻‍💻  In Progress     🔍  Code Review
  ⏳  Pending External   ✅  Done           ❌  Cancelled

Usage:
    uv run python scripts/batch/sprint_sync.py              # Full bidirectional sync
    uv run python scripts/batch/sprint_sync.py --pull-only  # Fetch from Jira only
    uv run python scripts/batch/sprint_sync.py --push-only  # Push local status changes only
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from mcp_client import MCPPool, run_async

# ── Emoji ↔ JIRA status mapping ──────────────────────────────────────────

ALL_EMOJIS = ["📋", "👨🏻‍💻", "🔍", "⏳", "✅", "❌"]

JIRA_TO_EMOJI: dict[str, str] = {
    "to do": "📋", "open": "📋", "new": "📋", "backlog": "📋",
    "in progress": "👨🏻‍💻", "in development": "👨🏻‍💻",
    "in review": "🔍", "code review": "🔍", "review": "🔍",
    "blocked": "⏳", "waiting": "⏳", "pending external": "⏳", "on hold": "⏳",
    "done": "✅", "closed": "✅", "resolved": "✅",
    "cancelled": "❌", "rejected": "❌", "won't do": "❌", "won't fix": "❌",
}

EMOJI_LABELS: dict[str, str] = {
    "📋": "To Do",
    "👨🏻‍💻": "In Progress",
    "🔍": "Code Review",
    "⏳": "Pending External",
    "✅": "Done",
    "❌": "Cancelled",
}

DONE_EMOJIS = {"✅", "❌"}
IDENTITY_RE = re.compile(r"^> \*\*(\w[\w\s]*):\*\*\s*(.+)$", re.MULTILINE)
TICKET_LINK_RE = re.compile(r"\[([A-Z]+-\d+)\]\(")


def jira_status_to_emoji(status: str) -> str:
    return JIRA_TO_EMOJI.get(status.lower().strip(), "📋")


def line_emoji(line: str) -> str | None:
    """Return the status emoji at the start of a line, or None."""
    stripped = line.strip()
    for emoji in ALL_EMOJIS:
        if stripped.startswith(emoji):
            return emoji
    return None


# ── Identity header ───────────────────────────────────────────────────────


def parse_identity_header(todo_path: Path) -> dict[str, str]:
    """Read the blockquote identity header from JIRA_TODO.md."""
    if not todo_path.exists():
        return {}
    text = todo_path.read_text()
    return {m.group(1).strip(): m.group(2).strip() for m in IDENTITY_RE.finditer(text)}


# ── Phase 1: Push local status changes ───────────────────────────────────


def parse_local_tickets(todo_path: Path) -> dict[str, str]:
    """Parse JIRA_TODO.md and return {ticket_key: emoji} for every ticket line."""
    if not todo_path.exists():
        return {}
    tickets: dict[str, str] = {}
    for line in todo_path.read_text().splitlines():
        emoji = line_emoji(line)
        if emoji:
            match = TICKET_LINK_RE.search(line)
            if match:
                tickets[match.group(1)] = emoji
    return tickets


async def push_status_changes(
    pool: MCPPool, cid: str, local: dict[str, str],
) -> list[dict]:
    """Compare local emoji statuses against Jira and flag drift."""
    results: list[dict] = []
    for key, local_emoji in local.items():
        try:
            issue = await pool.call("getJiraIssue", cloudId=cid, issueIdOrKey=key)
            if not isinstance(issue, dict):
                continue
            jira_status = issue.get("fields", {}).get("status", {}).get("name", "")
            jira_emoji = jira_status_to_emoji(jira_status)

            if local_emoji == jira_emoji:
                results.append({"key": key, "action": "in_sync"})
                continue

            target = EMOJI_LABELS.get(local_emoji, "Unknown")
            comment = (
                f"Status updated locally to {local_emoji} {target} "
                f"(was {jira_emoji} {jira_status} in Jira). "
                f"Please transition this ticket."
            )
            await pool.call(
                "addCommentToJiraIssue",
                cloudId=cid, issueIdOrKey=key, commentBody=comment,
            )
            print(f"  {key}: {jira_emoji} {jira_status} → {local_emoji} {target} (comment added)")
            results.append({
                "key": key, "action": "transition_requested",
                "from": jira_status, "to": target,
            })
        except Exception as exc:
            print(f"  {key}: FAILED — {exc}", file=sys.stderr)
            results.append({"key": key, "action": "failed", "error": str(exc)})
    return results


# ── Phase 2: Pull sprint tickets ─────────────────────────────────────────


async def pull_sprint_tickets(
    pool: MCPPool, cid: str, project_key: str, component: str = "",
) -> list[dict]:
    """Fetch current sprint tickets, optionally filtered by component."""
    jql_parts = [
        f"project={project_key}",
        "assignee=currentUser()",
        "sprint in openSprints()",
    ]
    if component:
        jql_parts.append(f'component="{component}"')
    jql = " AND ".join(jql_parts) + " ORDER BY rank"

    data = await pool.call(
        "searchJiraIssuesUsingJql",
        cloudId=cid, jql=jql,
        fields=["key", "summary", "status", "issuetype", "parent"],
        maxResults=200,
    )
    return data.get("issues", []) if isinstance(data, dict) else []


def generate_todo_md(issues: list[dict], identity: dict[str, str]) -> str:
    """Build JIRA_TODO.md with emoji statuses and identity header."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    base_url = identity.get("Base URL", "")

    lines = [
        "# JIRA Sprint TODO",
        "",
        f"> **Project:** {identity.get('Project', '')}",
        f"> **Assignee:** {identity.get('Assignee', '')}",
        f"> **Component:** {identity.get('Component', '')}",
        f"> **Board:** {identity.get('Board', '')}",
        f"> **Base URL:** {base_url}",
        f"> **Last synced:** {now}",
        "",
        "| Emoji | Meaning | JIRA Statuses |",
        "|-------|---------|---------------|",
        "| 📋 | To Do | To Do, Open, Backlog |",
        "| 👨🏻‍💻 | In Progress | In Progress, In Development |",
        "| 🔍 | Code Review | In Review, Code Review |",
        "| ⏳ | Pending External | Blocked, Waiting, On Hold |",
        "| ✅ | Done | Done, Closed, Resolved |",
        "| ❌ | Cancelled | Cancelled, Rejected, Won't Do |",
        "",
        "---",
        "",
    ]

    stories: dict[str, dict] = {}
    standalone: list[dict] = []

    for issue in issues:
        f = issue.get("fields", {})
        key = issue.get("key", "")
        summary = f.get("summary", "")
        status = f.get("status", {}).get("name", "")
        itype = f.get("issuetype", {}).get("name", "")
        parent_key = f.get("parent", {}).get("key") if f.get("parent") else None
        emoji = jira_status_to_emoji(status)
        url = f"{base_url}/browse/{key}" if base_url else key

        entry = {
            "key": key, "summary": summary, "emoji": emoji,
            "url": url, "status": status, "type": itype,
        }

        if itype in ("Story", "Epic", "Bug") and not parent_key:
            stories[key] = {**entry, "children": []}
        elif parent_key and parent_key in stories:
            stories[parent_key]["children"].append(entry)
        else:
            standalone.append(entry)

    all_entries: list[dict] = []
    for story in stories.values():
        all_entries.append(story)
        all_entries.extend(story["children"])
    all_entries.extend(standalone)

    for story in stories.values():
        if story["emoji"] in DONE_EMOJIS:
            continue
        lines.append(f"### [{story['key']}]({story['url']}) {story['summary']}")
        lines.append("")
        for child in story["children"]:
            lines.append(f"{child['emoji']} [{child['key']}]({child['url']}) {child['summary']}")
        if not story["children"]:
            lines.append(f"{story['emoji']} *(no sub-tasks)*")
        lines.append("")

    active_standalone = [t for t in standalone if t["emoji"] not in DONE_EMOJIS]
    if active_standalone:
        lines.append("### Tasks")
        lines.append("")
        for t in active_standalone:
            lines.append(f"{t['emoji']} [{t['key']}]({t['url']}) {t['summary']}")
        lines.append("")

    all_completed = [e for e in all_entries if e["emoji"] in DONE_EMOJIS]
    if all_completed:
        lines.append("### Completed")
        lines.append("")
        for e in all_completed:
            lines.append(f"{e['emoji']} [{e['key']}]({e['url']}) {e['summary']}")
        lines.append("")

    total = len(all_entries)
    done_count = sum(1 for e in all_entries if e["emoji"] in DONE_EMOJIS)
    ip_count = sum(1 for e in all_entries if e["emoji"] == "👨🏻‍💻")
    review_count = sum(1 for e in all_entries if e["emoji"] == "🔍")
    blocked_count = sum(1 for e in all_entries if e["emoji"] == "⏳")

    stats = [f"{done_count}/{total} done"]
    if ip_count:
        stats.append(f"{ip_count} in progress")
    if review_count:
        stats.append(f"{review_count} in review")
    if blocked_count:
        stats.append(f"{blocked_count} blocked")

    lines.append("---")
    lines.append(f"**Progress:** {' | '.join(stats)}")
    lines.append("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smart bidirectional Jira sync via MCP")
    parser.add_argument("--file", default="JIRA_TODO.md", help="Path to JIRA_TODO.md")
    parser.add_argument("--pull-only", action="store_true", help="Only pull from Jira")
    parser.add_argument("--push-only", action="store_true", help="Only push local changes")
    parser.add_argument("--assignee", default="", help="Assignee for identity header")
    parser.add_argument("--component", default="", help="Component for identity header and JQL filter")
    parser.add_argument("--board", default="", help="Board name for identity header")
    args = parser.parse_args()

    project_key = os.environ.get("JIRA_PROJECT_KEY", "")
    base_url = os.environ.get("JIRA_BASE_URL", "")
    if not project_key:
        print("ERROR: JIRA_PROJECT_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    todo_path = Path(args.file)
    existing = parse_identity_header(todo_path)
    identity: dict[str, str] = {
        "Project": project_key,
        "Assignee": args.assignee or existing.get("Assignee", ""),
        "Component": args.component or existing.get("Component", ""),
        "Board": args.board or existing.get("Board", ""),
        "Base URL": base_url or existing.get("Base URL", ""),
    }
    component_filter = identity["Component"]

    async with MCPPool(concurrency=1) as pool:
        cid = await pool.cloud_id()

        if not args.pull_only:
            local_tickets = parse_local_tickets(todo_path)
            if local_tickets:
                print(f"=== Push: Checking {len(local_tickets)} ticket(s) for status drift ===")
                results = await push_status_changes(pool, cid, local_tickets)
                synced = sum(1 for r in results if r["action"] == "in_sync")
                requested = sum(1 for r in results if r["action"] == "transition_requested")
                failed = sum(1 for r in results if r["action"] == "failed")
                print(f"  In sync: {synced} | Transitions requested: {requested} | Failed: {failed}")
            else:
                print("=== Push: No local tickets to check ===")

            if args.push_only:
                return

        print(f"\n=== Pull: Fetching sprint tickets from Jira ===")
        if component_filter:
            print(f"  Filtering by component: {component_filter}")
        issues = await pull_sprint_tickets(pool, cid, project_key, component_filter)
        print(f"  Fetched {len(issues)} issue(s)")

        md = generate_todo_md(issues, identity)
        todo_path.write_text(md)
        print(f"  Wrote {todo_path}")

        done = sum(1 for line in md.splitlines() if line_emoji(line) in DONE_EMOJIS)
        active = sum(
            1 for line in md.splitlines()
            if line_emoji(line) and line_emoji(line) not in DONE_EMOJIS
        )
        print(f"  Active: {active} | Completed: {done}")


if __name__ == "__main__":
    run_async(main())
