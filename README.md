# Jira Integration Skill

Manage Jira tickets without leaving your terminal or editor. Built as an AI agent skill for Cursor, Windsurf, Claude Code, MoltBot, Warp, etc. to name a few.

**Single authentication** — everything goes through the official [Atlassian MCP Server](https://github.com/atlassian/atlassian-mcp-server) with OAuth 2.1. No API tokens needed.

## Features

- **MCP tools** — Direct calls for single operations (search, view, create, comment)
- **Batch scripts** — Parallel MCP calls for bulk operations (5+ tickets)
- **Smart sync** — Bidirectional sync between local `JIRA_TODO.md` and Jira with emoji status tracking
- **Sub-skills** — Specialized workflows for meeting notes, specs, and bug triage

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
export JIRA_BASE_URL="https://your-instance.atlassian.net"  # For browse URLs in JIRA_TODO.md
```

The batch scripts connect to the **same MCP server** through `mcp-remote`. On first run, the browser opens for OAuth — same flow as the IDE.

## Python Batch Scripts

All scripts are in `scripts/batch/` and use multiple parallel MCP sessions for concurrent operations.

### Batch Create

```bash
# Create issues with component and assignee
uv run python scripts/batch/batch_create.py --type Story --component "My Component" --assignee "John Doe" "Implement auth" "Add logging"

# Create sub-tasks under a parent
uv run python scripts/batch/batch_create.py --type Sub-task --parent PROJ-100 --component "My Component" "Unit tests" "Docs"

# From JSON file
uv run python scripts/batch/batch_create.py --file tickets.json --component "My Component" --assignee "John Doe"

# From stdin
echo '[{"summary":"Task A","description":"Details"}]' | uv run python scripts/batch/batch_create.py --stdin --component "My Component"
```

### Batch Update (Comments)

```bash
uv run python scripts/batch/batch_update.py --comment "Deployed to staging" PROJ-101 PROJ-102

echo -e "PROJ-101\nPROJ-102" | uv run python scripts/batch/batch_update.py --stdin --comment "Done"
```

For status transitions, use `batch_transition.py` below.

### Batch Transition

```bash
# Transition tickets to Done
uv run python scripts/batch/batch_transition.py --status "Done" PROJ-101 PROJ-102 PROJ-103

# List available transitions for a ticket (discovery)
uv run python scripts/batch/batch_transition.py --list-transitions PROJ-101

# Control parallelism
uv run python scripts/batch/batch_transition.py --status "In Progress" --concurrency 5 PROJ-101 PROJ-102
```

The script handles the two-step transition pattern internally: discovers the matching transition ID by name (case-insensitive), then executes it.

### Batch Search

```bash
uv run python scripts/batch/batch_search.py mine sprint bugs recent

uv run python scripts/batch/batch_search.py "priority=High AND status!=Done"

uv run python scripts/batch/batch_search.py --json-output mine sprint
```

**Shortcuts:** `mine`, `sprint`, `recent`, `bugs`, `done`, `blocked`, `high`, `unassigned`

### Sprint Sync

Smart bidirectional sync between `JIRA_TODO.md` and Jira:

```bash
# Full sync: push local emoji changes, then pull from Jira
uv run python scripts/batch/sprint_sync.py

# Pull only: fetch sprint tickets and regenerate JIRA_TODO.md
uv run python scripts/batch/sprint_sync.py --pull-only

# Push only: detect local emoji changes and add transition comments
uv run python scripts/batch/sprint_sync.py --push-only

# Filter by component
uv run python scripts/batch/sprint_sync.py --component "My Component"
```

### Sprint Report

```bash
uv run python scripts/batch/sprint_report.py

uv run python scripts/batch/sprint_report.py --stale-days 5

uv run python scripts/batch/sprint_report.py --json-output
```

## JIRA_TODO.md Format

The sync creates a local `JIRA_TODO.md` file with emoji-based status tracking:

| Emoji | Status | Jira Statuses |
|-------|--------|---------------|
| 📋 | To Do | To Do, Open, Backlog |
| 👨🏻‍💻 | In Progress | In Progress, In Development |
| 🔍 | Code Review | In Review, Code Review |
| ⏳ | Pending External | Blocked, Waiting, On Hold |
| ✅ | Done | Done, Closed, Resolved |
| ❌ | Cancelled | Cancelled, Rejected, Won't Do |

**Example:**

```markdown
# JIRA Sprint TODO

> **Project:** PROJ
> **Assignee:** John Doe (account: abc123)
> **Component:** My Component
> **Last synced:** 2025-01-15 10:30

### [PROJ-200](https://company.atlassian.net/browse/PROJ-200) Story Title

👨🏻‍💻 [PROJ-201](https://company.atlassian.net/browse/PROJ-201) Sub-task 1
📋 [PROJ-202](https://company.atlassian.net/browse/PROJ-202) Sub-task 2

### Tasks

📋 [PROJ-100](https://company.atlassian.net/browse/PROJ-100) Standalone task
🔍 [PROJ-103](https://company.atlassian.net/browse/PROJ-103) PR under review

### Completed

✅ [PROJ-300](https://company.atlassian.net/browse/PROJ-300) Done task
```

**Workflow:** Change an emoji locally (e.g., 📋 → 👨🏻‍💻), then run `sprint_sync.py` — the script detects drift and adds transition comments to Jira.

## Sub-Skills

The `skills/` directory contains specialized agent workflows for complex multi-step Jira operations:

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `capture-tasks-from-meeting-notes` | Meeting notes with action items | Parse notes, extract action items, look up assignees, create tasks |
| `spec-to-backlog` | Spec or requirements doc | Analyze spec, create Epic first, then child tickets linked to Epic |
| `triage-issue` | Bug report or error message | Search for duplicates, present findings, create or comment on issues |

Each skill directory contains a `SKILL.md` with full workflow documentation. The main `SKILL.md` at the project root acts as an orchestrator that routes requests to the appropriate sub-skill.

## Available MCP Tools

| Tool | Purpose |
|------|---------|
| `searchJiraIssuesUsingJql` | Search issues with JQL |
| `getJiraIssue` | Get full issue details |
| `createJiraIssue` | Create a new issue |
| `editJiraIssue` | Update fields on an existing issue |
| `transitionJiraIssue` | Change issue status |
| `getTransitionsForJiraIssue` | List available status transitions |
| `addCommentToJiraIssue` | Add comment to issue |
| `createIssueLink` | Link two issues |
| `getIssueLinkTypes` | List available link type names |
| `addWorklogToJiraIssue` | Log time against an issue |
| `getVisibleJiraProjects` | List accessible projects |
| `getJiraProjectIssueTypesMetadata` | Get issue types for a project |
| `getJiraIssueTypeMetaWithFields` | Get required fields for an issue type |
| `lookupJiraAccountId` | Find user by name/email |
| `getAccessibleAtlassianResources` | List connected Atlassian sites |
| `atlassianUserInfo` | Get current authenticated user info |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  AI Agent (Cursor / Windsurf / Warp / Claude Code)  │
│                                                     │
│  Orchestrator SKILL.md                              │
│    │                                                │
│    ├─ Single ops ──> MCP tool call                  │
│    │                      │                         │
│    ├─ Bulk ops ───> Batch scripts (parallel MCP)    │
│    │                      │                         │
│    └─ Workflows ──> Sub-Skills (skills/*.md)        │
│                           │                         │
│                    Atlassian MCP Server             │
│                      (OAuth 2.1)                    │
│                           │                         │
│                    Jira Cloud REST API              │
└─────────────────────────────────────────────────────┘
```

All paths converge on the same MCP server. One auth, one connection.

## Requirements

- Python 3.11+ with [uv](https://docs.astral.sh/uv/) package manager
- Jira Cloud instance
- Node.js v18+ (for `mcp-remote`)

## License

MIT
