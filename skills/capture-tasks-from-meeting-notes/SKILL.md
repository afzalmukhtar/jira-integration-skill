---
name: capture-tasks-from-meeting-notes
description: "Analyze meeting notes to find action items and create Jira tasks for assigned work. When the agent needs to: (1) Create Jira tasks from meeting notes, (2) Extract action items from pasted text, (3) Parse notes for assigned tasks, or (4) Generate Jira tickets for team members. Identifies assignees, looks up account IDs, and creates tasks with proper context using Atlassian MCP tools."
---

# Capture Tasks from Meeting Notes

## Keywords
meeting notes, action items, create tasks, create tickets, extract tasks, parse notes, analyze notes, assigned work, assignees, from meeting, post-meeting, capture tasks, generate tasks, turn into tasks, convert to tasks, action item, to-do, task list, follow-up, assigned to, create Jira tasks, create Jira tickets

## Overview

Automatically extract action items from meeting notes and create Jira tasks with proper assignees. This skill parses pasted meeting notes, identifies action items with assignees, looks up Jira account IDs via MCP, and creates tasks — eliminating the tedious post-meeting ticket creation process.

**Use this skill when:** Users have meeting notes with action items that need to become Jira tasks.

**Primary tools:** Atlassian MCP tools (`lookupJiraAccountId`, `createJiraIssue`)

**Batch alternative:** For 5+ tickets, use `scripts/batch/batch_create.py` for parallel creation.

**Project defaults:** Read from `.jira/JIRA_TODO.md` identity header in the project root. The header contains Cloud ID, Project, Assignee, Component, Board, and Base URL. Do NOT ask the user for these — they are already cached.

---

## Workflow

Follow this 7-step process to turn meeting notes into actionable Jira tasks:

### Step 1: Get Meeting Notes

Obtain the meeting notes from the user as pasted text. Ask: "Please paste your meeting notes and I'll extract the action items."

### Step 2: Parse Action Items

Scan the notes for action items with assignees.

#### Common Patterns

**Pattern 1: @mention format** (highest priority)
```
@Sarah to create user stories for chat feature
@Mike will update architecture doc
```

**Pattern 2: Name + action verb**
```
Sarah to create user stories
Mike will update architecture doc
Lisa should review the mockups
```

**Pattern 3: Action: Name - Task**
```
Action: Sarah - create user stories
Action Item: Mike - update architecture
```

**Pattern 4: TODO with assignee**
```
TODO: Create user stories (Sarah)
TODO: Update docs - Mike
```

**Pattern 5: Bullet with name**
```
- Sarah: create user stories
- Mike - update architecture
```

#### Extraction Logic

For each action item, extract:

1. **Assignee Name** — Text after @ symbol, name before "to"/"will"/"should", name after "Action:", or name in parentheses
2. **Task Description** — Text after "to", "will", "should", "-", ":"
3. **Context** (optional) — Meeting title/date, surrounding discussion context

### Step 3: Load Project Defaults

Read `.jira/JIRA_TODO.md` from the project root to get the identity header. Extract:
- **Cloud ID** (for every MCP call)
- **Project key** (from header)
- **Component name** (for `additional_fields`)
- **Assignee account ID** (for the default assignee)
- **Base URL** (for browse links in the summary)

If `JIRA_TODO.md` doesn't exist, follow the initialization workflow in the main SKILL.md to create it first.

### Step 4: Lookup Account IDs

For each unique assignee name, find their Jira account ID via MCP:
```
lookupJiraAccountId(cloudId="<from JIRA_TODO.md>", searchString="[assignee name]")
```

**Handle results:**
- **1 result** — Use the accountId
- **0 results** — Offer to create task unassigned, skip, or try different name
- **2+ results** — Ask user to disambiguate

Cache results so you don't look up the same person twice.

### Step 5: Present Action Items

**CRITICAL:** Always show the parsed action items BEFORE creating any tasks.

```
I found [N] action items. Should I create these Jira tasks in [PROJECT]?

1. [Task description]
   Assigned to: [Name] ([email])

2. [Task description]
   Assigned to: [Name] ([email])

Would you like me to:
1. Create all tasks
2. Skip some tasks (which ones?)
3. Modify any descriptions or assignees
```

**Wait for confirmation.** Do NOT create tasks until user confirms.

### Step 6: Create Tasks

**For 1-4 tasks:** Use MCP tool `createJiraIssue` for each. Always include the component from defaults:
```
createJiraIssue(
  cloudId="<from JIRA_TODO.md>",
  projectKey="<PROJECT_KEY>",
  issueTypeName="Task",
  summary="[Task description]",
  description="[Context from meeting]",
  assignee_account_id="[looked up ID]",
  additional_fields={"components": [{"name": "[component from JIRA_TODO.md]"}]}
)
```

**For 5+ tasks:** Use batch script with component and assignee flags:
```bash
uv run python scripts/batch/batch_create.py --type Task --project <PROJECT_KEY> --component "[component]" --assignee "[assignee]" "Task 1" "Task 2" "Task 3" "Task 4" "Task 5"
```

**Task description format:**
```markdown
**Action Item from Meeting Notes**

**Task:** [Original action item text]

**Context:**
[Meeting title/date]
[Relevant discussion points]

**Original Note:**
> [Exact quote from meeting notes]
```

### Step 7: Provide Summary

```
Created [N] tasks in [PROJECT]:

1. [PROJ-123] - [Task summary]
   Assigned to: [Name]
   https://yoursite.atlassian.net/browse/PROJ-123

2. [PROJ-124] - [Task summary]
   Assigned to: [Name]
   https://yoursite.atlassian.net/browse/PROJ-124

Next Steps:
- Review tasks in Jira for accuracy
- Add additional details or attachments
- Adjust priorities if needed
```

---

## Edge Cases

### No Action Items Found
If no action items with assignees are detected, explain common patterns and ask user to point out specific items.

### Mixed Formats
If some items have assignees and some don't, present both sets and ask which to create.

### Duplicate Action Items
If the same task appears multiple times, ask whether to create one or multiple tickets.

---

## When NOT to Use This Skill

- Summarizing meetings (no task creation)
- Creating calendar events
- General note-taking
- Feature spec decomposition (use `spec-to-backlog` instead)

**Use only when:** Meeting notes exist and action items need to become Jira tasks.
