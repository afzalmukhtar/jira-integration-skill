---
name: jira-integration
description: Manage Jira tickets using the official Atlassian MCP server and Python batch scripts. Search, create, update, view, bulk operations, sprint sync, and reports — all without leaving the IDE. Use when the user mentions Jira, tickets, sprint planning, or asks to sync work with Jira.
---

# Jira Integration Skill

This is the **orchestrator skill**. It routes Jira operations to the right tool or sub-skill based on what the user needs.

**Single authentication:** Everything goes through the Atlassian MCP server with OAuth 2.1. No API tokens needed. The batch scripts connect to the same MCP server via `mcp-remote`, so there is one auth mechanism for everything.

1. **MCP tools** — Direct calls for single operations
2. **Batch scripts** — Multiple parallel MCP calls for bulk operations

**NEVER write custom Python scripts for Jira operations.** All operations must use the MCP tools or the existing batch scripts listed in this skill. If a tool doesn't exist for what you need, tell the user — do not create throwaway scripts.

## Project Defaults

These defaults apply to **every** Jira operation unless the user explicitly overrides them:

| Setting | Default | Notes |
|---------|---------|-------|
| **Project Key** | *(ask user)* | Always verify with user on first interaction: "What is your Jira project key?" |
| **Assignee** | *(current user)* | Always assign all created tickets to the current user. Look up `accountId` via `lookupJiraAccountId` with the user's name. |
| **Component** | *(must be verified)* | Ask user for the component name on first interaction, then verify it exists by searching for an existing issue with that component. Cache the verified name for the session. |
| **Base URL** | *(ask user)* | The Atlassian Cloud URL (e.g., `https://<org>.atlassian.net`). For browse links in JIRA_TODO.md. |

---

## CRITICAL: Project Initialization & JIRA_TODO.md

On the **first Jira interaction in a project**, perform these steps:

### 1. Verify Project Identity

Use the existing MCP tools — do NOT write custom scripts.

1. Ask user for their project key (e.g., `PROJ`)
2. Ask user for their full name, then look up assignee account ID:
   - MCP tool: `lookupJiraAccountId` with `query: "<user's name>"`
3. Ask user for component name, then verify it exists:
   - MCP tool: `searchJiraIssuesUsingJql` with `jql: 'project = <KEY> AND component = "<name>"'`, `maxResults: 1`
   - If no results, try partial matches or ask user to correct.
4. Ask user for their Atlassian base URL (e.g., `https://<org>.atlassian.net`)

### 2. Create `.jira/` Directory and JIRA_TODO.md

After verifying identity, create a `.jira/` directory in the project root and place all Jira-related files there. This keeps Jira artifacts organized and out of the main project tree.

```
.jira/
├── JIRA_TODO.md          # Sprint tracker and work instructions
└── (future: cached responses, reports, etc.)
```

Create `.jira/JIRA_TODO.md` — this file serves as the local sprint tracker and identity cache.

**File format:**

```markdown
# JIRA Sprint TODO

> **Project:** <PROJECT_KEY>
> **Assignee:** <User Name> (account: <accountId>)
> **Component:** <verified component name>
> **Board:** <board name>
> **Base URL:** <https://org.atlassian.net>
> **Last synced:** <timestamp>

| Emoji | Meaning | JIRA Statuses |
|-------|---------|---------------|
| 📋 | To Do | To Do, Open, Backlog |
| 👨🏻‍💻 | In Progress | In Progress, In Development |
| 🔍 | Code Review | In Review, Code Review |
| ⏳ | Pending External | Blocked, Waiting, On Hold |
| ✅ | Done | Done, Closed, Resolved |
| ❌ | Cancelled | Cancelled, Rejected, Won't Do |

---

### [PROJ-200](https://org.atlassian.net/browse/PROJ-200) Story Title

> Story description from Jira goes here. Include all context, links,
> S3 paths, reproduction steps — whatever is in the ticket body.
> This gives the agent full context without needing to re-fetch.
>
> **Reported by:** Person Name | **Comments (3):**
> - *Alice (2026-02-10):* "Confirmed this also affects other products."
> - *Bob (2026-02-12):* "Root cause is in the chunker fallback logic."
> - *Alice (2026-02-14):* "PR #1720 has a proposed fix."

👨🏻‍💻 [PROJ-201](https://org.atlassian.net/browse/PROJ-201) **Sub-task 1**
> Sub-task description from Jira. Explains what this specific task requires.

📋 [PROJ-202](https://org.atlassian.net/browse/PROJ-202) **Sub-task 2**
> Sub-task description from Jira.

### Tasks

📋 [PROJ-100](https://org.atlassian.net/browse/PROJ-100) **Some standalone task**
> Task description from Jira.

🔍 [PROJ-103](https://org.atlassian.net/browse/PROJ-103) **PR under review**
> Task description from Jira.

### Completed

✅ [PROJ-300](https://org.atlassian.net/browse/PROJ-300) Done task
❌ [PROJ-301](https://org.atlassian.net/browse/PROJ-301) Cancelled task

---
**Progress:** 2/6 done | 1 in progress | 1 in review
```

The **identity header** (blockquote section) is the source of truth for all subsequent Jira operations. The agent reads this on session start instead of re-asking the user.

**Description & comments enrichment (MANDATORY):** When pulling tickets into JIRA_TODO.md, the agent MUST also fetch and include:

1. **Descriptions** — For every ticket (stories, tasks, AND sub-tasks), fetch the full description using `getJiraIssue` and include it as a blockquote (`>`) directly below the ticket line. This gives the agent full working context without needing to re-fetch from Jira.
2. **Comments** — For the parent story/task, fetch the latest comments and include them as a bullet list inside the description blockquote. Format: `- *Author (date):* "comment text"`. This captures discussion, decisions, and context from teammates.
3. **Sub-task titles** — Bold the summary text after the ticket link for scannability.

**How to fetch descriptions:** Use `getJiraIssue` (MCP tool) for each ticket. Parse the `fields.description` (Atlassian Document Format) by recursively extracting `text` nodes. Parse `fields.comment.comments[]` for comment bodies, authors (`author.displayName`), and dates (`created`).

**When descriptions are empty:** If a ticket has no description, write `> (no description)` as a placeholder so the agent knows it checked.

**Why this matters:** Without descriptions in the TODO, the agent has no context about what each ticket requires and cannot work autonomously. The descriptions ARE the work instructions.

**Status emoji rules:** Change an emoji locally, then run `sprint_sync.py` to push the change to Jira. The script detects drift between local emojis and Jira statuses and adds transition comments.

### 3. Add to .gitignore

Ensure `.jira/` is in the project's `.gitignore`. If not present, append it:
```
# Jira local data
.jira/
```

---

## CRITICAL: Ticket Creation Guidelines

**ALWAYS ask the user before creating tickets:**

1. **Issue Type**: "Should this be a Story, Task, Sub-task, or another type used in your organization?"
2. **Parent Ticket**: "If this is a sub-task, which parent ticket should it be linked to?"

**ALWAYS apply automatically (do NOT ask):**

- **Project Key**: Read from `.jira/JIRA_TODO.md` header
- **Assignee**: Always set to the user (from cached `accountId` in identity header)
- **Component**: Always set from `.jira/JIRA_TODO.md` header (pass via `additional_fields: { "components": [{"name": "<name>"}] }`)

**How to create tickets (use existing tools only):**

- **1-4 tickets**: Call MCP `createJiraIssue` directly for each ticket. Pass `projectKey`, `issueTypeName`, `summary`, `description`, `additional_fields` (for component). For sub-tasks, also pass `parent`.
- **5+ tickets**: Use `batch_create.py` via Shell. Prepare a JSON file with `[{"summary": "...", "description": "..."}]` and run:
  ```bash
  uv run python scripts/batch/batch_create.py --type Story --project <KEY> --component "<component>" --assignee "<User Name>" --file tickets.json
  uv run python scripts/batch/batch_create.py --type Sub-task --parent <KEY>-XXX --project <KEY> --component "<component>" --assignee "<User Name>" --file subtasks.json
  ```
- **Assigning**: The `--assignee` flag looks up the account ID automatically. For MCP `createJiraIssue`, pass `assignee_account_id` directly.
- **Sprint**: Set via the JIRA board UI or MCP tools if available. Note the sprint in `.jira/JIRA_TODO.md`.

**NEVER** write custom Python scripts. Use only MCP tools and the batch scripts provided by this skill.

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
| Sync Jira / "what's on my plate?" | **Smart Sync Workflow** (see below) | Agent workflow + `sprint_sync.py` |
| Sprint sync (JIRA_TODO.md) | `scripts/batch/sprint_sync.py` | Shell: run Python script |
| Sprint report | `scripts/batch/sprint_report.py` | Shell: run Python script |
| Triage a bug / check duplicates | **`skills/triage-issue/SKILL.md`** | Read and follow sub-skill |
| Meeting notes to Jira tasks | **`skills/capture-tasks-from-meeting-notes/SKILL.md`** | Read and follow sub-skill |
| Spec/requirements to backlog | **`skills/spec-to-backlog/SKILL.md`** | Read and follow sub-skill |

**Rule:** For complex multi-step workflows, read and follow the sub-skill. For direct operations, use MCP or batch scripts directly.

---

## Authentication

**OAuth 2.1 everywhere.** No API tokens, no credentials in env vars.

- **MCP tools** (agent calls): The IDE handles OAuth automatically via `.mcp.json`
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
export JIRA_PROJECT_KEY="<PROJECT_KEY>"                             # Default project
export JIRA_BASE_URL="<https://org.atlassian.net>"                  # For browse URLs
```

### batch_create.py — Parallel Issue Creation

```bash
uv run python scripts/batch/batch_create.py --type Story --component "<component>" --assignee "<User Name>" "Implement auth" "Add logging"

uv run python scripts/batch/batch_create.py --type Sub-task --parent <KEY>-100 --component "<component>" "Unit tests" "Docs"

echo '[{"summary":"Task A","description":"Details"}]' | uv run python scripts/batch/batch_create.py --stdin --component "<component>"

uv run python scripts/batch/batch_create.py --file tickets.json --project <KEY> --component "<component>"
```

### batch_update.py — Batch Comments

```bash
uv run python scripts/batch/batch_update.py --comment "Deployed to staging" <KEY>-101 <KEY>-102

echo -e "<KEY>-101\n<KEY>-102" | uv run python scripts/batch/batch_update.py --stdin --comment "Done"
```

Note: This script only adds comments. For status transitions, use the AI agent's MCP tools directly.

### batch_search.py — Concurrent JQL Queries

```bash
uv run python scripts/batch/batch_search.py mine sprint bugs recent

uv run python scripts/batch/batch_search.py "priority=High AND status!=Done"

uv run python scripts/batch/batch_search.py --json-output mine sprint
```

**Shortcuts:** `mine`, `sprint`, `recent`, `bugs`, `done`, `blocked`, `high`, `unassigned`

### sprint_sync.py — Smart Bidirectional Sync

```bash
# Full sync: push local emoji changes, then pull from Jira
uv run python scripts/batch/sprint_sync.py

# Pull only: fetch sprint tickets and regenerate JIRA_TODO.md
uv run python scripts/batch/sprint_sync.py --pull-only

# Push only: detect local emoji changes and add transition comments
uv run python scripts/batch/sprint_sync.py --push-only

# With explicit component filter (reads from identity header by default)
uv run python scripts/batch/sprint_sync.py --component "<component>"
```

**How it works:**
- **Pull:** Fetches sprint tickets (filtered by assignee, sprint, and component from the identity header), maps Jira statuses to emojis, generates JIRA_TODO.md
- **Push:** Compares local emojis against Jira statuses, adds transition comments on tickets where status has drifted
- **Component filter:** If the identity header has a Component, only tickets with that component are pulled — keeping the TODO focused on the current project

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

---

## Core Workflows

### Start of Session

1. Read `.jira/JIRA_TODO.md` to load identity defaults and current ticket statuses
2. If `.jira/` doesn't exist, run the Project Initialization workflow (see above)
3. Pull latest sprint data (uses component filter from identity header):

```bash
export JIRA_PROJECT_KEY="<from identity header>"
export JIRA_BASE_URL="<from identity header>"
uv run python scripts/batch/sprint_sync.py --pull-only
```

### During Development
- **Search:** MCP `searchJiraIssuesUsingJql`
- **View:** MCP `getJiraIssue`
- **Comment:** MCP `addCommentToJiraIssue`
- **Create:** MCP `createJiraIssue` (always include component from `.jira/JIRA_TODO.md`)
- **Update status:** Edit the emoji in `.jira/JIRA_TODO.md` (e.g., 📋 → 👨🏻‍💻 when starting work)

### End of Session

Push any local status changes and pull latest from Jira:
```bash
uv run python scripts/batch/sprint_sync.py
```

---

## Smart Sync Workflow

When the user asks to sync Jira (e.g., "sync my tickets", "what's on my plate?", "update my todo"):

### 1. Understand Project Context

Before syncing, read the project's `.jira/JIRA_TODO.md` identity header for Project, Component, and Assignee. If `.jira/` doesn't exist, run Project Initialization first.

The **Component** field is the primary filter for keeping the TODO relevant to the current codebase. If unsure, also check the project's README, `package.json`, or `pyproject.toml` to understand what component/area this project covers.

### 2. Pull from Jira

```bash
export JIRA_PROJECT_KEY="<from identity header>"
export JIRA_BASE_URL="<from identity header>"
uv run python scripts/batch/sprint_sync.py --pull-only
```

The script fetches tickets matching: `project = <KEY> AND assignee = currentUser() AND sprint in openSprints() AND component = "<from identity header>"`.

### 3. Enrich with Descriptions & Comments

After pulling ticket keys and statuses, the agent MUST enrich each ticket with its full description and comments before writing JIRA_TODO.md:

1. For each ticket key, call `getJiraIssue` via MCP (or use `mcp_client.py` directly):
   ```python
   result = await ctx.call('getJiraIssue', cloudId=cid, issueIdOrKey='<KEY>-XXX')
   description = extract_text(result['fields']['description'])
   comments = result['fields'].get('comment', {}).get('comments', [])
   ```
2. Extract description text by recursively collecting `text` nodes from the Atlassian Document Format (ADF) tree.
3. Extract comments: author (`comment['author']['displayName']`), date (`comment['created']`), body (same ADF text extraction).
4. Write the description as a blockquote under each ticket line in JIRA_TODO.md.
5. For parent stories, append the latest comments as a bullet list inside the blockquote.

This step is **not optional** — it is what makes the TODO actionable for the agent and the developer.

### 4. Review and Curate

After enriching, review the generated JIRA_TODO.md. The agent should:
- Verify the pulled tickets are relevant to the current codebase
- Remove any that clearly belong to a different project area
- Add context notes if helpful

### 5. Push Local Changes

When the user changes emojis in JIRA_TODO.md (e.g., moves 📋 → 👨🏻‍💻 to mark a ticket as started):

```bash
uv run python scripts/batch/sprint_sync.py --push-only
```

The script detects emoji drift and adds transition comments to the affected Jira tickets.

---

## JIRA_TODO.md File Format

See the full format under **"CRITICAL: Project Initialization & JIRA_TODO.md"** above.

Key rules:
- The **identity header** (blockquote) is always at the top — it's the source of truth for project defaults
- The **emoji legend table** maps each emoji to its JIRA status counterparts
- Each ticket line starts with a status emoji: 📋 👨🏻‍💻 🔍 ⏳ ✅ ❌
- Change an emoji locally → run `sprint_sync.py` → the script pushes the change to Jira
- The file lives in the **`.jira/` directory** in the project root, and `.jira/` must be in `.gitignore`

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| MCP OAuth failure | Token expired | Re-authenticate in browser |
| `No accessible Atlassian resources` | OAuth not completed | Run any batch script to trigger browser login |
| `Components is required` | Missing required field | Use `additional_fields` in `createJiraIssue` |
| Rate limit (429) | Too many requests | Reduce `--concurrency` on batch scripts |
