---
name: generate-status-report
description: "Generate project status reports from Jira issues. When the agent needs to: (1) Create a status report, (2) Summarize project progress, (3) Generate weekly/daily reports from Jira, or (4) Analyze project blockers and completion. Queries Jira via MCP, categorizes issues, and creates formatted markdown reports."
---

# Generate Status Report

## Keywords
status report, project status, weekly update, daily standup, Jira report, project summary, blockers, progress update, sprint report, project update

## Overview

Query Jira for project status, analyze issues, and generate formatted status reports as markdown output. Reports can be printed to terminal or saved to a local file.

**Use this skill when:** Users need a status report, sprint summary, or progress update from Jira data.

**Primary tools:** Atlassian MCP tools (`searchJiraIssuesUsingJql`), Python batch scripts for parallel queries.

**Quick report:** For a fast sprint overview, run `uv run python scripts/batch/sprint_report.py`.

---

## Workflow

**CRITICAL**: Always clarify scope (time period, audience) with the user before generating the report.

### Step 1: Identify Scope

Clarify these details with the user:

**Project:** Which Jira project key? If unsure, call `getVisibleJiraProjects`.

**Time period:** "What time period should this report cover?"
- Weekly (7 days) — default
- Daily (24 hours)
- Sprint-based (2 weeks)
- Custom period

**Audience:**
- **Executive/Delivery Managers** — High-level summary with metrics and blockers
- **Team-level** — Detailed breakdown with issue-by-issue status
- **Daily standup** — Brief yesterday/today/blockers format

### Step 2: Query Jira

Use MCP for single queries, or the batch search script for parallel queries:

**Via MCP (single query):**
```
searchJiraIssuesUsingJql(
  cloudId="...",
  jql='project = "PROJ" AND updated >= -7d ORDER BY priority DESC',
  fields=["summary","status","priority","assignee","updated","resolved"],
  maxResults=100
)
```

**Via batch script (multiple queries in parallel):**
```bash
uv run python scripts/batch/batch_search.py \
  "project=PROJ AND status=Done AND resolved >= -7d" \
  "project=PROJ AND status='In Progress'" \
  "project=PROJ AND status=Blocked" \
  "project=PROJ AND priority IN (Highest, High) AND status!=Done"
```

**Standard query set for reports:**
1. **Completed:** `status = Done AND resolved >= -7d`
2. **In progress:** `status IN ("In Progress", "In Review")`
3. **Blocked:** `status = Blocked`
4. **High priority open:** `priority IN (Highest, High) AND status != Done`

### Step 3: Analyze Data

Process retrieved issues to identify:

**Metrics:**
- Total issues by status
- Completion rate
- High priority item count
- Unassigned issue count

**Key insights:**
- Major accomplishments (recently completed high-value items)
- Critical blockers (blocked high priority issues)
- At-risk items (overdue or stuck)
- Resource bottlenecks (one assignee with many issues)

### Step 4: Format Report

#### Executive / Delivery Manager Format

```markdown
# [Project] Status Report — [Date]

## Overall Status: [On Track / At Risk / Blocked]

### Key Metrics
| Metric | Count |
|--------|-------|
| Total Issues | XX |
| Completed (this period) | XX |
| In Progress | XX |
| Blocked | XX |

### Highlights
- [Major accomplishment 1]
- [Major accomplishment 2]

### Blockers
- [PROJ-123] [Blocker description] — Impact: [impact]
- [PROJ-456] [Blocker description] — Impact: [impact]

### Upcoming Priorities
- [Priority 1]
- [Priority 2]
```

#### Team-Level Format

```markdown
# [Project] Sprint Status — [Date]

## Completed ([count])
- [PROJ-101] [Summary] — [Assignee]
- [PROJ-102] [Summary] — [Assignee]

## In Progress ([count])
- [PROJ-201] [Summary] — [Assignee] | Priority: [P]
- [PROJ-202] [Summary] — [Assignee] | Priority: [P]

## Blocked ([count])
- [PROJ-301] [Summary] — Blocker: [description]

## To Do ([count])
- [PROJ-401] [Summary] — [Assignee]

## Risks
- [Risk description and mitigation]
```

#### Daily Standup Format

```markdown
# Standup — [Date]

## Completed Yesterday
- [PROJ-101] [Summary]

## Working On Today
- [PROJ-201] [Summary]

## Blockers
- [PROJ-301] [Blocker description]
```

### Step 5: Output Report

Present the formatted report to the user. Offer to save to a local file:

"Here's the status report. Would you like me to save it to a file (e.g., `status-report-2025-12-03.md`)?"

**Quick alternative:** For an instant sprint report:
```bash
uv run python scripts/batch/sprint_report.py
```

Or as JSON for further processing:
```bash
uv run python scripts/batch/sprint_report.py --json-output
```

---

## Tips for Quality Reports

- **Be data-driven** — Include specific numbers, reference issue keys
- **Highlight what matters** — Lead with blockers and accomplishments
- **Make it actionable** — For blockers, state what action is needed and from whom
- **Keep it consistent** — Use the same format for recurring reports
- **Show trends** — Compare with previous period when possible

---

## When NOT to Use This Skill

- Creating tickets from meeting notes (use `capture-tasks-from-meeting-notes`)
- Triaging bugs (use `triage-issue`)
- Creating backlog from specs (use `spec-to-backlog`)

**Use only when:** A status report, sprint summary, or progress update is needed.
