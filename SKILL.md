---
name: jira-integration
description: Manage JIRA tickets directly from the terminal. Bidirectional sync with JIRA_TODO.md, create/update/view tickets, link git branches, bulk operations, and sprint reports. Use when the user mentions JIRA, tickets, sprint planning, or asks to sync work with JIRA.
---

# JIRA Integration Skill

Automates JIRA ticket management via REST API v3. Syncs work between your codebase and JIRA without leaving the terminal.

## CRITICAL: Ticket Creation Guidelines

**ALWAYS ask the user before creating tickets:**

1. **Issue Type**: "Should this be a Story, Task, Sub-task, or another type used in your organization?"
2. **Parent Ticket**: "If this is a sub-task, which parent ticket should it be linked to?"

**Default hierarchy:**
- **Story**: Main work item (feature, epic-level work)
- **Task/Sub-task**: Individual work items under a Story

## IMPORTANT: Always Verify Before Starting

**Before performing ANY JIRA operation, ALWAYS confirm with the user:**

1. **Project Key**: Ask "Which JIRA project are we working with?" (e.g., AIPDQ, PROJ)
2. **User Confirmation**: Run `check-jira-setup.sh` to verify credentials and access

## Available Scripts

All scripts use self-documenting names for clarity.

### Single Ticket Operations

| Script | Purpose |
|--------|---------|
| `create-one-jira-ticket.sh` | Create a single ticket (story/task/subtask/bug) |
| `update-one-jira-ticket.sh` | Transition status or add comment to one ticket |
| `view-one-jira-ticket.sh` | Display full ticket details in terminal |

### Bulk Operations

| Script | Purpose |
|--------|---------|
| `bulk-create-jira-tickets.sh` | Create multiple tickets at once (supports --parent for batch sub-tasks) |
| `bulk-update-jira-tickets.sh` | Transition multiple tickets at once |

### Workflows

| Script | Purpose |
|--------|---------|
| `sync-jira-tickets.sh` | Bidirectional sync: push local completions to JIRA, pull fresh state |
| `check-jira-setup.sh` | Verify credentials, authentication, and project access |
| `search-jira-tickets.sh` | JQL search with shortcuts (mine, sprint, recent, bugs) |
| `link-git-to-jira-ticket.sh` | Link git branch/commits to JIRA ticket, auto-transition |
| `jira-sprint-report.sh` | Sprint progress summary with progress bar and stale ticket detection |

## Prerequisites

Environment variables in `~/.zshrc`:

```bash
export JIRA_USER="your-email@company.com"
export JIRA_API_TOKEN="your-api-token"
export JIRA_BASE_URL="https://your-instance.atlassian.net"
export JIRA_PROJECT_KEY="PROJ"
export JIRA_ACCOUNT_ID="your-account-id"
export JIRA_STORY_TYPE_ID="10001"
export JIRA_SUBTASK_TYPE_ID="10003"
export JIRA_SPRINT_FIELD="customfield_10020"
```

Generate API token at: https://id.atlassian.com/manage-profile/security/api-tokens

## Core Workflows

### 1. Bidirectional Sync (sync-jira-tickets.sh)

Single command for full round-trip sync:

```bash
./scripts/sync-jira-tickets.sh
```

**If JIRA_TODO.md exists:**
1. Reads locally completed tickets (marked `[x]`)
2. Pushes completions to JIRA (transitions to Done)
3. Pulls fresh sprint state from JIRA
4. Regenerates JIRA_TODO.md with merged state

**If JIRA_TODO.md does not exist:**
1. Pulls sprint tickets from JIRA
2. Creates JIRA_TODO.md

### 2. Create Tickets

```bash
# Single ticket
./scripts/create-one-jira-ticket.sh "Fix login bug" "Users cannot log in" bug

# Batch sub-tasks under a story
./scripts/bulk-create-jira-tickets.sh --type subtask --parent PROJ-100 "Write tests" "Update docs" "Add logging"

# Batch from stdin
echo -e "Task A\nTask B\nTask C" | ./scripts/bulk-create-jira-tickets.sh --stdin --type task
```

### 3. Update Tickets

```bash
# Single ticket transitions
./scripts/update-one-jira-ticket.sh PROJ-123 done
./scripts/update-one-jira-ticket.sh PROJ-123 progress
./scripts/update-one-jira-ticket.sh PROJ-123 comment "Fixed in commit abc123"

# Bulk transitions
./scripts/bulk-update-jira-tickets.sh done PROJ-123 PROJ-124 PROJ-125
```

### 4. View and Search

```bash
# View ticket details
./scripts/view-one-jira-ticket.sh PROJ-123

# Search with shortcuts
./scripts/search-jira-tickets.sh mine      # My open tickets
./scripts/search-jira-tickets.sh sprint    # Current sprint
./scripts/search-jira-tickets.sh recent    # Updated in last 7 days
./scripts/search-jira-tickets.sh bugs      # Open bugs

# Custom JQL
./scripts/search-jira-tickets.sh "priority = High AND status != Done"
```

### 5. Git-Linked Workflow

```bash
# Auto-detect ticket from branch name and link commit
./scripts/link-git-to-jira-ticket.sh

# Explicit ticket
./scripts/link-git-to-jira-ticket.sh PROJ-123

# Link without auto-transitioning
./scripts/link-git-to-jira-ticket.sh --no-transition
```

Supported branch patterns:
- `feature/PROJ-123-auth` -> `PROJ-123`
- `PROJ-456-fix-login` -> `PROJ-456`
- `bugfix/PROJ-789` -> `PROJ-789`

### 6. Sprint Report

```bash
./scripts/jira-sprint-report.sh
```

Shows:
- Progress bar with completion percentage
- Status breakdown (Done / In Progress / To Do)
- In-progress and to-do ticket details with assignees
- Stale ticket warnings (no update in 3+ days)

## Automated Session Workflow

When starting a coding session:

1. **Check setup**: `./scripts/check-jira-setup.sh`
2. **Sync tickets**: `./scripts/sync-jira-tickets.sh`
3. **Review JIRA_TODO.md**: Pick a ticket to work on
4. **Link git**: `./scripts/link-git-to-jira-ticket.sh` (auto-transitions to In Progress)
5. **Work on code**: Make changes
6. **On completion**: Mark `[x]` in JIRA_TODO.md
7. **Sync again**: `./scripts/sync-jira-tickets.sh` (pushes completion, pulls updates)
8. **Sprint check**: `./scripts/jira-sprint-report.sh`

## JIRA_TODO.md File Format

```markdown
# JIRA Sprint TODO

Generated: 2025-01-15 10:30
Source: https://company.atlassian.net

## [ ] [PROJ-100](https://company.atlassian.net/browse/PROJ-100) Epic/Story Title

- [ ] [PROJ-101](https://company.atlassian.net/browse/PROJ-101) Sub-task 1
- [x] [PROJ-102](https://company.atlassian.net/browse/PROJ-102) Sub-task 2

## Other Tasks

- [ ] [PROJ-200](https://company.atlassian.net/browse/PROJ-200) Standalone task

---
**Progress:** 1/3 completed
```

### Format Rules

- `[ ]` = Pending/In Progress
- `[x]` = Completed (will sync to JIRA as Done)
- Stories/Epics appear as `##` headers with sub-tasks below
- Standalone tasks appear under "Other Tasks"

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `Client must be authenticated` | Wrong credentials | Verify JIRA_USER and JIRA_API_TOKEN |
| `Components is required` | Missing required field | Add JIRA_COMPONENT_ID |
| `Field 'customfield_10020' cannot be set` | Wrong sprint field | Run discovery to get correct field ID |
| `tls: failed to verify certificate` | Corporate proxy | The `-k` flag is already included |
| `Missing required environment variables` | Env vars not set | Run `check-jira-setup.sh` to diagnose |

## Discovery Commands

Run these once to get project-specific IDs:

```bash
# Get your Account ID
curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/myself" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"Account ID: {d['accountId']}\")"

# Get Issue Type IDs
curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issuetype" | python3 -c "import json,sys; [print(f\"{t['name']}: {t['id']}\") for t in json.load(sys.stdin)]"

# Get Component IDs
curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/project/$JIRA_PROJECT_KEY/components" | python3 -c "import json,sys; [print(f\"{c['name']}: {c['id']}\") for c in json.load(sys.stdin)]"
```
