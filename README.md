# JIRA Integration Skill

Manage JIRA tickets without leaving your terminal or editor. Built as an AI agent skill for Cursor and Codex, but works standalone too.

## What It Does

Bidirectional sync between a local `JIRA_TODO.md` file and your JIRA board. Mark tickets done locally, sync pushes to JIRA. New tickets in JIRA get pulled into your TODO. One command.

Plus: create tickets, bulk operations, search, git-branch linking, and sprint reports — all from the terminal.

## Scripts

### Single Ticket Operations

| Script | What it does |
|--------|-------------|
| `create-one-jira-ticket.sh` | Create a single ticket (story, task, subtask, bug) |
| `update-one-jira-ticket.sh` | Transition status or add a comment |
| `view-one-jira-ticket.sh` | View ticket details in terminal (no browser needed) |

### Bulk Operations

| Script | What it does |
|--------|-------------|
| `bulk-create-jira-tickets.sh` | Create multiple tickets at once, supports `--parent` for batch sub-tasks |
| `bulk-update-jira-tickets.sh` | Transition multiple tickets in one go |

### Workflows

| Script | What it does |
|--------|-------------|
| `sync-jira-tickets.sh` | Bidirectional sync: push local completions, pull fresh JIRA state |
| `check-jira-setup.sh` | Verify credentials, auth, and project access |
| `search-jira-tickets.sh` | JQL search with shortcuts (`mine`, `sprint`, `recent`, `bugs`) |
| `link-git-to-jira-ticket.sh` | Link git branch and commits to a JIRA ticket |
| `jira-sprint-report.sh` | Sprint progress with progress bar and stale ticket warnings |

## Setup

### 1. Environment Variables

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
export JIRA_USER="your-email@company.com"
export JIRA_API_TOKEN="your-api-token"
export JIRA_BASE_URL="https://your-instance.atlassian.net"
export JIRA_PROJECT_KEY="PROJ"
```

Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens

### 2. Verify Setup

```bash
./scripts/check-jira-setup.sh
```

### 3. Optional Configuration

```bash
export JIRA_STORY_TYPE_ID="10001"       # Issue type IDs (vary per project)
export JIRA_SUBTASK_TYPE_ID="10003"
export JIRA_COMPONENT_ID=""              # If your project requires components
export JIRA_SPRINT_ID=""                 # Current sprint ID
export JIRA_SPRINT_FIELD="customfield_10020"
```

Use the discovery commands in `SKILL.md` to find your project-specific IDs.

## Quick Start

```bash
# Sync JIRA tickets to local TODO file (and push any local completions back)
./scripts/sync-jira-tickets.sh

# View a ticket
./scripts/view-one-jira-ticket.sh PROJ-123

# Search
./scripts/search-jira-tickets.sh mine

# Create a ticket
./scripts/create-one-jira-ticket.sh "Fix authentication bug" "Login fails for SSO users" bug

# Create batch sub-tasks
./scripts/bulk-create-jira-tickets.sh --type subtask --parent PROJ-100 "Write tests" "Update docs"

# Link your current git branch to a JIRA ticket
./scripts/link-git-to-jira-ticket.sh

# Sprint progress
./scripts/jira-sprint-report.sh
```

## How Bidirectional Sync Works

```
JIRA Board                          JIRA_TODO.md
┌──────────┐    sync-jira-tickets   ┌──────────────┐
│ PROJ-101 │ ◄────────────────────  │ [x] PROJ-101 │  (you marked it done locally)
│ PROJ-102 │ ──────────────────►    │ [ ] PROJ-102 │  (new ticket pulled from JIRA)
│ PROJ-103 │ ──────────────────►    │ [x] PROJ-103 │  (already done in JIRA)
└──────────┘                        └──────────────┘
```

One command. Push completions up, pull new state down.

## Using as an AI Agent Skill

This was built as a skill for AI coding agents (Cursor, Codex). The `SKILL.md` file contains the full agent-facing documentation with guidelines on when and how to use each script.

To install as a Cursor skill, copy the `jira-integration/` directory to your skills folder and reference `SKILL.md`.

## Requirements

- `bash`
- `curl`
- `python3`
- JIRA Cloud instance with API access

## License

MIT
