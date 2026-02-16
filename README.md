# Jira Integration Skill

Manage Jira tickets without leaving your terminal or editor. Built as an AI agent skill for Cursor and Codex.

**Two interfaces:**

1. **Atlassian MCP Server** — Real-time single operations via the official [Atlassian Rovo MCP Server](https://github.com/atlassian/atlassian-mcp-server) with OAuth 2.1
2. **Python Batch Scripts** — Parallel bulk operations via asyncio + aiohttp

## Setup

### 1. MCP Server (for Cursor/IDE)

The project includes `.mcp.json` which configures the official Atlassian Rovo MCP server:

```json
{
  "servers": {
    "Atlassian-MCP-Server": {
      "url": "https://mcp.atlassian.com/v1/mcp"
    }
  }
}
```

**Prerequisites:**
- Atlassian Cloud site with Jira
- Node.js v18+ (for `mcp-remote` proxy on older Cursor versions)
- Browser for OAuth 2.1 login

On first use, your browser opens for OAuth authentication. The MCP server respects your existing Jira permissions.

### 2. Python Batch Scripts (for Bulk Operations)

```bash
uv sync
```

Environment variables in `~/.zshrc` or `~/.bashrc`:

```bash
export JIRA_USER="your-email@company.com"
export JIRA_API_TOKEN="your-api-token"
export JIRA_BASE_URL="https://your-instance.atlassian.net"
export JIRA_PROJECT_KEY="PROJ"
```

Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens

**Optional configuration:**

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

## Python Batch Scripts

All batch scripts are in `scripts/batch/` and use asyncio for parallel execution.

### Batch Create

```bash
# Create multiple stories
uv run python scripts/batch/batch_create.py --type story "Implement auth" "Add logging" "Write tests"

# Sub-tasks under a parent
uv run python scripts/batch/batch_create.py --type subtask --parent PROJ-100 "Unit tests" "Integration tests"

# From JSON file
uv run python scripts/batch/batch_create.py --file tickets.json

# From JSON stdin
echo '[{"summary":"Task A","description":"Details"}]' | uv run python scripts/batch/batch_create.py --stdin
```

### Batch Update

```bash
# Transition multiple tickets to Done
uv run python scripts/batch/batch_update.py --transition done PROJ-101 PROJ-102 PROJ-103

# Add comment to multiple tickets
uv run python scripts/batch/batch_update.py --comment "Deployed to staging" PROJ-101 PROJ-102

# Combined
uv run python scripts/batch/batch_update.py --transition done --comment "Sprint 5" PROJ-101 PROJ-102
```

### Batch Search

```bash
# Shortcut queries (run in parallel)
uv run python scripts/batch/batch_search.py mine sprint bugs recent

# Custom JQL
uv run python scripts/batch/batch_search.py "priority=High AND status!=Done"

# JSON output
uv run python scripts/batch/batch_search.py --json-output mine sprint
```

**Shortcuts:** `mine`, `sprint`, `recent`, `bugs`, `done`, `blocked`, `high`, `unassigned`

### Sprint Sync

Bidirectional sync between `JIRA_TODO.md` and Jira:

```bash
# Full sync (push local completions + pull fresh state)
uv run python scripts/batch/sprint_sync.py

# Pull only
uv run python scripts/batch/sprint_sync.py --pull-only

# Push only
uv run python scripts/batch/sprint_sync.py --push-only
```

### Sprint Report

```bash
# Pretty-printed report with progress bar
uv run python scripts/batch/sprint_report.py

# Flag stale after 5 days
uv run python scripts/batch/sprint_report.py --stale-days 5

# JSON output
uv run python scripts/batch/sprint_report.py --json-output
```

## How Bidirectional Sync Works

```
Jira Board                          JIRA_TODO.md
┌──────────┐    sprint_sync.py      ┌──────────────┐
│ PROJ-101 │ <--------------------  │ [x] PROJ-101 │  (you marked done locally)
│ PROJ-102 │ -------------------->  │ [ ] PROJ-102 │  (new ticket pulled)
│ PROJ-103 │ -------------------->  │ [x] PROJ-103 │  (already done in Jira)
└──────────┘                        └──────────────┘
```

One command. Push completions up, pull new state down. All API calls run concurrently.

## Skills

The `skills/` directory contains specialized agent workflows for complex multi-step Jira operations:

| Skill | What it does |
|-------|-------------|
| `capture-tasks-from-meeting-notes` | Parse meeting notes, extract action items, create Jira tasks with assignees |
| `spec-to-backlog` | Convert specs/requirements into Epic + child tickets |
| `triage-issue` | Search for duplicate bugs, create or comment on issues |
| `generate-status-report` | Query Jira, analyze data, format status reports |

Each skill directory contains a `SKILL.md` with full workflow documentation for AI agents. The main `SKILL.md` at the project root acts as an orchestrator that routes requests to the appropriate sub-skill.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  AI Agent (Cursor / Codex)                          │
│                                                     │
│  Orchestrator SKILL.md                              │
│    │                                                │
│    ├─ Single ops ──> Atlassian MCP Server (OAuth)   │
│    │                      │                         │
│    ├─ Bulk ops ───> Python Batch Scripts (asyncio)   │
│    │                      │                         │
│    └─ Workflows ──> Sub-Skills (skills/*.md)         │
│                           │                         │
│                      Jira Cloud REST API            │
└─────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.11+ with [uv](https://docs.astral.sh/uv/) package manager
- Jira Cloud instance with API access
- Node.js v18+ (for MCP proxy on older IDE versions)

## License

MIT
