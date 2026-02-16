---
name: jira-integration
description: Manage Jira tickets using the official Atlassian MCP server and Python batch scripts. Search, create, update, view, bulk operations, sprint sync, and reports — all without leaving the IDE. Use when the user mentions Jira, tickets, sprint planning, or asks to sync work with Jira.
---

# Jira Integration Skill

This is the **orchestrator skill**. It routes Jira operations to the right tool or sub-skill based on what the user needs.

**Two interfaces available:**

1. **Atlassian MCP Server** — Real-time single operations via OAuth 2.1
2. **Python Batch Scripts** — Parallel bulk operations via asyncio + aiohttp

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
| Update 1-2 issues | MCP transition / `addCommentToJiraIssue` | Direct MCP call |
| Update 3+ issues | `scripts/batch/batch_update.py` | Shell: run Python script |
| Run multiple JQL queries | `scripts/batch/batch_search.py` | Shell: run Python script |
| Sprint sync (JIRA_TODO.md) | `scripts/batch/sprint_sync.py` | Shell: run Python script |
| Sprint report | `scripts/batch/sprint_report.py` | Shell: run Python script |
| Triage a bug / check duplicates | **`skills/triage-issue/SKILL.md`** | Read and follow sub-skill |
| Meeting notes to Jira tasks | **`skills/capture-tasks-from-meeting-notes/SKILL.md`** | Read and follow sub-skill |
| Spec/requirements to backlog | **`skills/spec-to-backlog/SKILL.md`** | Read and follow sub-skill |
| Status/progress report | **`skills/generate-status-report/SKILL.md`** | Read and follow sub-skill |

**Rule:** For complex multi-step workflows (triage, meeting notes, specs, reports), always read and follow the sub-skill SKILL.md. For direct operations (search, create, update), use MCP or batch scripts directly.

---

## MCP Server

Configured via `.mcp.json` — the official Atlassian Rovo MCP server:

```json
{
  "servers": {
    "Atlassian-MCP-Server": {
      "url": "https://mcp.atlassian.com/v1/mcp"
    }
  }
}
```

**Prerequisites:** Atlassian Cloud site with Jira, Node.js v18+, browser for OAuth 2.1 login.

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

Located in `scripts/batch/`. Install dependencies: `uv sync`

Auth via environment variables:
```bash
export JIRA_USER="your-email@company.com"
export JIRA_API_TOKEN="your-api-token"
export JIRA_BASE_URL="https://your-instance.atlassian.net"
export JIRA_PROJECT_KEY="PROJ"
```

### batch_create.py — Parallel Issue Creation

```bash
# From CLI args
uv run python scripts/batch/batch_create.py --type story "Implement auth" "Add logging" "Write tests"

# Sub-tasks under a parent
uv run python scripts/batch/batch_create.py --type subtask --parent PROJ-100 "Unit tests" "Integration tests"

# From JSON stdin
echo '[{"summary":"Task A","description":"Details"}]' | uv run python scripts/batch/batch_create.py --stdin

# From JSON file
uv run python scripts/batch/batch_create.py --file tickets.json
```

### batch_update.py — Parallel Transitions & Comments

```bash
# Transition to Done
uv run python scripts/batch/batch_update.py --transition done PROJ-101 PROJ-102 PROJ-103

# Add comment to multiple
uv run python scripts/batch/batch_update.py --comment "Deployed to staging" PROJ-101 PROJ-102

# Combined
uv run python scripts/batch/batch_update.py --transition done --comment "Sprint 5 complete" PROJ-101 PROJ-102

# From stdin
echo -e "PROJ-101\nPROJ-102" | uv run python scripts/batch/batch_update.py --stdin --transition done
```

### batch_search.py — Concurrent JQL Queries

```bash
# Shortcut queries (all run in parallel)
uv run python scripts/batch/batch_search.py mine sprint bugs recent

# Custom JQL
uv run python scripts/batch/batch_search.py "priority=High AND status!=Done" "assignee=currentUser()"

# JSON output
uv run python scripts/batch/batch_search.py --json-output mine sprint
```

**Shortcuts:** `mine`, `sprint`, `recent`, `bugs`, `done`, `blocked`, `high`, `unassigned`

### sprint_sync.py — Bidirectional JIRA_TODO.md Sync

```bash
# Full sync (push completions + pull fresh state)
uv run python scripts/batch/sprint_sync.py

# Pull only (skip pushing local completions)
uv run python scripts/batch/sprint_sync.py --pull-only

# Push only (sync local [x] to Jira, skip pull)
uv run python scripts/batch/sprint_sync.py --push-only
```

### sprint_report.py — Sprint Progress Report

```bash
# Pretty-printed with progress bar
uv run python scripts/batch/sprint_report.py

# Flag stale after 5 days instead of default 3
uv run python scripts/batch/sprint_report.py --stale-days 5

# JSON output
uv run python scripts/batch/sprint_report.py --json-output
```

---

## Sub-Skills

These handle complex multi-step Jira workflows. When the user's request matches one of these, **read the sub-skill's SKILL.md and follow its workflow**.

### Capture Tasks from Meeting Notes
**Path:** `skills/capture-tasks-from-meeting-notes/SKILL.md`
**Trigger:** User has meeting notes and wants to create Jira tasks from action items.
**What it does:** Parses pasted text, extracts action items with assignees, looks up Jira accounts via MCP, creates tasks. For 5+ tasks, delegates to `batch_create.py`.

### Spec to Backlog
**Path:** `skills/spec-to-backlog/SKILL.md`
**Trigger:** User has a spec or requirements doc and wants a structured Jira backlog.
**What it does:** Analyzes spec, creates Epic first, then child tickets (Story/Task/Bug) linked to Epic. For 5+ children, delegates to `batch_create.py`.

### Triage Issue
**Path:** `skills/triage-issue/SKILL.md`
**Trigger:** User has a bug report or error and wants to check for duplicates before filing.
**What it does:** Extracts error signature, runs multiple JQL searches via MCP (or `batch_search.py`), presents findings, creates new issue or adds comment to existing.

### Generate Status Report
**Path:** `skills/generate-status-report/SKILL.md`
**Trigger:** User needs a status report, sprint summary, or progress update.
**What it does:** Queries Jira via MCP or `batch_search.py`, analyzes metrics, formats report as markdown. Quick alternative: `uv run python scripts/batch/sprint_report.py`.

---

## Core Workflows

### Start of Session
```bash
uv run python scripts/batch/sprint_report.py      # Quick overview
uv run python scripts/batch/sprint_sync.py        # Sync JIRA_TODO.md
```

### During Development
- **Search:** MCP `searchJiraIssuesUsingJql`
- **View:** MCP `getJiraIssue`
- **Update:** MCP `addCommentToJiraIssue` to log progress

### End of Session
```bash
uv run python scripts/batch/sprint_sync.py        # Push completions, pull updates
uv run python scripts/batch/sprint_report.py      # Final report
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
- Stories/Epics as `##` headers with sub-tasks below
- Standalone tasks under "Other Tasks"

---

## Environment Variables

**Required:**
```bash
export JIRA_USER="your-email@company.com"
export JIRA_API_TOKEN="your-api-token"
export JIRA_BASE_URL="https://your-instance.atlassian.net"
export JIRA_PROJECT_KEY="PROJ"
```

**Optional:**
```bash
export JIRA_ACCOUNT_ID="your-account-id"
export JIRA_STORY_TYPE_ID="10001"
export JIRA_SUBTASK_TYPE_ID="10003"
export JIRA_TASK_TYPE_ID="10002"
export JIRA_BUG_TYPE_ID="10004"
export JIRA_COMPONENT_ID=""
export JIRA_SPRINT_ID=""
export JIRA_SPRINT_FIELD="customfield_10020"
```

Generate API token at: https://id.atlassian.com/manage-profile/security/api-tokens

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| MCP OAuth failure | Token expired | Re-authenticate in browser |
| `Client must be authenticated` | Wrong batch credentials | Verify JIRA_USER and JIRA_API_TOKEN |
| `Components is required` | Missing required field | Set JIRA_COMPONENT_ID |
| `Field 'customfield_10020' cannot be set` | Wrong sprint field | Check correct field ID for your project |
| Rate limit (429) | Too many requests | Batch scripts auto-retry with backoff |
