---
name: jira-integration
description: Manage Jira tickets using the official Atlassian MCP server and Python batch scripts. Search, create, update, view, bulk operations, sprint sync, and reports — all without leaving the IDE. Use when the user mentions Jira, tickets, sprint planning, or asks to sync work with Jira.
---

# Jira Integration Skill

This is the **orchestrator skill**. It routes Jira operations to the right tool or sub-skill based on what the user needs.

**Single authentication:** Everything goes through the Atlassian MCP server with OAuth 2.1. No API tokens needed. The batch scripts connect to the same MCP server via `mcp-remote`, so there is one auth mechanism for everything.

1. **MCP tools** — Direct calls for single operations
2. **Batch scripts** — Multiple parallel MCP calls for bulk operations

## CRITICAL: Ticket Creation Guidelines

**ALWAYS ask the user before creating tickets:**

1. **Issue Type**: "Should this be a Story, Task, Sub-task, or another type used in your organization?"
2. **Parent Ticket**: "If this is a sub-task, which parent ticket should it be linked to?"
3. **Project Key**: "Which Jira project are we working with?" (e.g., PROJ, ENG)

---

## Routing Table

Use this table to decide which tool or sub-skill to invoke:

| User Intent | Route To | How |
|-------------|----------|-----|
| Search issues | MCP `searchJiraIssuesUsingJql` | Direct MCP call |
| View one issue | MCP `getJiraIssue` | Direct MCP call |
| Create 1-4 issues | MCP `createJiraIssue` | Direct MCP call per issue |
| Create 5+ issues | `scripts/batch/batch_create.py` | Shell: run Python script |
| Add comment to 1-2 issues | MCP `addCommentToJiraIssue` | Direct MCP call |
| Add comment to 3+ issues | `scripts/batch/batch_update.py` | Shell: run Python script |
| Run multiple JQL queries | `scripts/batch/batch_search.py` | Shell: run Python script |
| Sprint sync (JIRA_TODO.md) | `scripts/batch/sprint_sync.py` | Shell: run Python script |
| Sprint report | `scripts/batch/sprint_report.py` | Shell: run Python script |
| Triage a bug / check duplicates | **`skills/triage-issue/SKILL.md`** | Read and follow sub-skill |
| Meeting notes to Jira tasks | **`skills/capture-tasks-from-meeting-notes/SKILL.md`** | Read and follow sub-skill |
| Spec/requirements to backlog | **`skills/spec-to-backlog/SKILL.md`** | Read and follow sub-skill |
| Status/progress report | **`skills/generate-status-report/SKILL.md`** | Read and follow sub-skill |

**Rule:** For complex multi-step workflows, read and follow the sub-skill. For direct operations, use MCP or batch scripts directly.

---

## Authentication

**OAuth 2.1 everywhere.** No API tokens, no credentials in env vars.

- **MCP tools** (agent calls): Cursor handles OAuth automatically via `.mcp.json`
- **Batch scripts**: Connect through `mcp-remote` which handles the same OAuth flow
- **First run**: Browser opens for Atlassian login. Token is cached by `mcp-remote` for subsequent runs.

**Prerequisites:** Atlassian Cloud site with Jira, Node.js v18+ (for `mcp-remote`), browser for OAuth.

---

## MCP Server

Configured via `.mcp.json`:

```json
{
  "servers": {
    "Atlassian-MCP-Server": {
      "url": "https://mcp.atlassian.com/v1/mcp"
    }
  }
}
```

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `searchJiraIssuesUsingJql` | Search issues with JQL |
| `getJiraIssue` | Get full issue details |
| `createJiraIssue` | Create a new issue |
| `addCommentToJiraIssue` | Add comment to issue |
| `getVisibleJiraProjects` | List accessible projects |
| `getJiraProjectIssueTypesMetadata` | Get issue types for a project |
| `getJiraIssueTypeMetaWithFields` | Get required fields for an issue type |
| `lookupJiraAccountId` | Find user by name/email |
| `getAccessibleAtlassianResources` | List connected Atlassian sites |

---

## Python Batch Scripts

Located in `scripts/batch/`. Install: `uv sync`

These scripts connect to the **same MCP server** via `mcp-remote`. They open multiple parallel MCP sessions to execute bulk operations concurrently.

**Configuration (env vars, not credentials):**
```bash
export JIRA_PROJECT_KEY="PROJ"                              # Which project to target
export JIRA_BASE_URL="https://your-instance.atlassian.net"  # Optional, for browse URLs
```

### batch_create.py — Parallel Issue Creation

```bash
uv run python scripts/batch/batch_create.py --type Story "Implement auth" "Add logging" "Write tests"

uv run python scripts/batch/batch_create.py --type Sub-task --parent PROJ-100 "Unit tests" "Integration tests"

echo '[{"summary":"Task A","description":"Details"}]' | uv run python scripts/batch/batch_create.py --stdin

uv run python scripts/batch/batch_create.py --file tickets.json
```

### batch_update.py — Parallel Comments

```bash
uv run python scripts/batch/batch_update.py --comment "Deployed to staging" PROJ-101 PROJ-102

echo -e "PROJ-101\nPROJ-102" | uv run python scripts/batch/batch_update.py --stdin --comment "Done"
```

Note: For status transitions, use the AI agent directly ("Transition PROJ-101 to Done").

### batch_search.py — Concurrent JQL Queries

```bash
uv run python scripts/batch/batch_search.py mine sprint bugs recent

uv run python scripts/batch/batch_search.py "priority=High AND status!=Done"

uv run python scripts/batch/batch_search.py --json-output mine sprint
```

**Shortcuts:** `mine`, `sprint`, `recent`, `bugs`, `done`, `blocked`, `high`, `unassigned`

### sprint_sync.py — Bidirectional JIRA_TODO.md Sync

```bash
uv run python scripts/batch/sprint_sync.py

uv run python scripts/batch/sprint_sync.py --pull-only

uv run python scripts/batch/sprint_sync.py --push-only
```

### sprint_report.py — Sprint Progress Report

```bash
uv run python scripts/batch/sprint_report.py

uv run python scripts/batch/sprint_report.py --stale-days 5

uv run python scripts/batch/sprint_report.py --json-output
```

---

## Sub-Skills

When the user's request matches one of these, **read the sub-skill's SKILL.md and follow its workflow**.

### Capture Tasks from Meeting Notes
**Path:** `skills/capture-tasks-from-meeting-notes/SKILL.md`
**Trigger:** User has meeting notes and wants Jira tasks from action items.
**What it does:** Parses text, extracts action items, looks up accounts via MCP, creates tasks. For 5+ tasks, delegates to `batch_create.py`.

### Spec to Backlog
**Path:** `skills/spec-to-backlog/SKILL.md`
**Trigger:** User has a spec and wants a structured Jira backlog.
**What it does:** Analyzes spec, creates Epic first, then child tickets linked to Epic. For 5+ children, delegates to `batch_create.py`.

### Triage Issue
**Path:** `skills/triage-issue/SKILL.md`
**Trigger:** User has a bug report or error and wants to check for duplicates.
**What it does:** Extracts error signature, runs JQL searches via MCP (or `batch_search.py`), creates new issue or adds comment.

### Generate Status Report
**Path:** `skills/generate-status-report/SKILL.md`
**Trigger:** User needs a status report or sprint summary.
**What it does:** Queries Jira via MCP or `batch_search.py`, formats report. Quick alternative: `uv run python scripts/batch/sprint_report.py`.

---

## Core Workflows

### Start of Session
```bash
uv run python scripts/batch/sprint_report.py
uv run python scripts/batch/sprint_sync.py
```

### During Development
- **Search:** MCP `searchJiraIssuesUsingJql`
- **View:** MCP `getJiraIssue`
- **Update:** MCP `addCommentToJiraIssue`

### End of Session
```bash
uv run python scripts/batch/sprint_sync.py
uv run python scripts/batch/sprint_report.py
```

---

## JIRA_TODO.md File Format

```markdown
# JIRA Sprint TODO

Generated: 2025-01-15 10:30
Source: https://company.atlassian.net

## [ ] [PROJ-100](https://company.atlassian.net/browse/PROJ-100) Story Title

- [ ] [PROJ-101](https://company.atlassian.net/browse/PROJ-101) Sub-task 1
- [x] [PROJ-102](https://company.atlassian.net/browse/PROJ-102) Sub-task 2

## Other Tasks

- [ ] [PROJ-200](https://company.atlassian.net/browse/PROJ-200) Standalone task

---
**Progress:** 1/3 completed
```

- `[ ]` = Pending/In Progress
- `[x]` = Completed (syncs to Jira as Done)

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| MCP OAuth failure | Token expired | Re-authenticate in browser |
| `No accessible Atlassian resources` | OAuth not completed | Run any batch script to trigger browser login |
| `Components is required` | Missing required field | Use `additional_fields` in `createJiraIssue` |
| Rate limit (429) | Too many requests | Reduce `--concurrency` on batch scripts |
