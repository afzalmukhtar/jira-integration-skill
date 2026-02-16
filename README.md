# Jira Integration Skill

Manage Jira tickets without leaving your terminal or editor. Built as an AI agent skill for Cursor and Windsurf.

**Single authentication** — everything goes through the official [Atlassian MCP Server](https://github.com/atlassian/atlassian-mcp-server) with OAuth 2.1. No API tokens needed.

1. **MCP tools** — Direct calls for single operations
2. **Batch scripts** — Multiple parallel MCP calls for bulk operations

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
- Node.js v18+ (for `mcp-remote`)
- Browser for OAuth 2.1 login

On first use, your browser opens for OAuth authentication. The token is cached for subsequent runs.

### 2. Python Batch Scripts

```bash
uv sync
```

**Configuration** (not credentials, just project settings):

```bash
export JIRA_PROJECT_KEY="PROJ"                              # Which project to target
export JIRA_BASE_URL="https://your-instance.atlassian.net"  # Optional, for browse URLs
```

The batch scripts connect to the **same MCP server** through `mcp-remote`. On first run, the browser opens for OAuth — same flow as the IDE.

## Python Batch Scripts

All scripts are in `scripts/batch/` and use multiple parallel MCP sessions for concurrent operations.

### Batch Create

```bash
uv run python scripts/batch/batch_create.py --type Story "Implement auth" "Add logging" "Write tests"

uv run python scripts/batch/batch_create.py --type Sub-task --parent PROJ-100 "Unit tests" "Integration tests"

uv run python scripts/batch/batch_create.py --file tickets.json

echo '[{"summary":"Task A","description":"Details"}]' | uv run python scripts/batch/batch_create.py --stdin
```

### Batch Update (Comments)

```bash
uv run python scripts/batch/batch_update.py --comment "Deployed to staging" PROJ-101 PROJ-102

echo -e "PROJ-101\nPROJ-102" | uv run python scripts/batch/batch_update.py --stdin --comment "Done"
```

For status transitions, use the AI agent directly: "Transition PROJ-101, PROJ-102 to Done."

### Batch Search

```bash
uv run python scripts/batch/batch_search.py mine sprint bugs recent

uv run python scripts/batch/batch_search.py "priority=High AND status!=Done"

uv run python scripts/batch/batch_search.py --json-output mine sprint
```

**Shortcuts:** `mine`, `sprint`, `recent`, `bugs`, `done`, `blocked`, `high`, `unassigned`

### Sprint Sync

Bidirectional sync between `JIRA_TODO.md` and Jira:

```bash
uv run python scripts/batch/sprint_sync.py

uv run python scripts/batch/sprint_sync.py --pull-only

uv run python scripts/batch/sprint_sync.py --push-only
```

### Sprint Report

```bash
uv run python scripts/batch/sprint_report.py

uv run python scripts/batch/sprint_report.py --stale-days 5

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

One command. Push completions up, pull new state down. All MCP calls run concurrently.

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
│  AI Agent (Cursor / Windsurf)                       │
│                                                     │
│  Orchestrator SKILL.md                              │
│    │                                                │
│    ├─ Single ops ──> MCP tool call                  │
│    │                      │                         │
│    ├─ Bulk ops ───> Batch scripts (parallel MCP)    │
│    │                      │                         │
│    └─ Workflows ──> Sub-Skills (skills/*.md)        │
│                           │                         │
│                    Atlassian MCP Server              │
│                      (OAuth 2.1)                    │
│                           │                         │
│                    Jira Cloud REST API               │
└─────────────────────────────────────────────────────┘
```

All paths converge on the same MCP server. One auth, one connection.

## Requirements

- Python 3.11+ with [uv](https://docs.astral.sh/uv/) package manager
- Jira Cloud instance
- Node.js v18+ (for `mcp-remote`)

## License

MIT
