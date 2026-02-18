---
name: spec-to-backlog
description: "Convert specification documents into structured Jira backlogs with Epics and implementation tickets. When the agent needs to: (1) Create Jira tickets from a spec, (2) Generate a backlog from requirements, (3) Break down a spec into implementation tasks, or (4) Convert requirements into Jira issues. Handles analyzing specs, creating Epics, and generating detailed tickets linked to the Epic using Atlassian MCP tools."
---

# Spec to Backlog

## Overview

Transform specification documents into structured Jira backlogs automatically. This skill reads requirement documents (pasted text or local files), breaks them down into logical implementation tasks, **creates an Epic first**, then generates individual Jira tickets linked to that Epic.

**Use this skill when:** Users have a spec or requirements document that needs to become a Jira backlog.

**Primary tools:** Atlassian MCP tools (`createJiraIssue`)

**Batch alternative:** For 5+ child tickets, use `scripts/batch/batch_create.py` for parallel creation.

**Project defaults:** Read from `JIRA_TODO.md` identity header in the project root. The header contains Project, Assignee, Component, Board, and Base URL. Do NOT ask the user for these — they are already cached.

---

## Core Workflow

**CRITICAL: Always follow this exact sequence:**

1. **Get Specification** — Obtain pasted text or local file from user
2. **Load Project Defaults** — Read from `JIRA_TODO.md` identity header
3. **Analyze Specification** — Break down into logical tasks (internally)
4. **Present Breakdown** — Show user the planned Epic and tickets
5. **Create Epic FIRST** — Establish parent Epic and capture its key
6. **Create Child Tickets** — Generate tickets linked to the Epic
7. **Provide Summary** — Present all created items with links

**Why Epic must be created first:** Child tickets need the Epic key to link properly during creation.

---

## Step 1: Get Specification

Ask the user for their specification:

"Please paste your specification or requirements document, or provide the path to a local file."

If user provides a file path, read it. If user pastes text, use as-is.

---

## Step 2: Load Project Defaults

Read `JIRA_TODO.md` from the project root to get the identity header. Extract:
- **Project key** (default: `AIPDQ`)
- **Component name** (for `additional_fields`)
- **Assignee account ID** (for the default assignee)
- **Base URL** (for browse links in the summary)

If `JIRA_TODO.md` doesn't exist, follow the initialization workflow in the main SKILL.md to create it first.

**Select appropriate issue types for child tickets:**
- **Bug** — Fixing existing problems ("fix", "resolve", "bug", "error")
- **Story** — New user-facing features ("feature", "user can", "add ability to")
- **Task** — Technical work ("implement", "setup", "configure", "refactor")

---

## Step 3: Analyze Specification

Read the spec and decompose into:

### Epic-Level Goal
What is the overall objective? This becomes the Epic.

### Implementation Tasks
Break into 3-10 logical, independently implementable tasks.

**Breakdown principles:**
- **Size:** 3-10 tasks per spec typically
- **Clarity:** Each task should be specific and actionable
- **Independence:** Tasks can be worked on separately when possible
- **Completeness:** Include backend, frontend, testing, documentation as needed

**Use action verbs:** Implement, Create, Build, Add, Design, Integrate, Update, Fix, Optimize, Configure, Deploy, Test, Document

---

## Step 4: Present Breakdown to User

**Before creating anything**, show the planned breakdown:

```
I've analyzed the spec. Here's the backlog I'll create:

**Epic:** [Epic Summary]
[Brief description]

**Implementation Tickets (7):**
1. [Story] [Task 1 Summary]
2. [Task] [Task 2 Summary]
3. [Bug] [Task 3 Summary]
...

Shall I create these tickets in [PROJECT KEY]?
```

**Wait for confirmation.** Allow user to adjust before proceeding.

---

## Step 5: Create Epic FIRST

Create the Epic via MCP. Always include component from defaults:
```
createJiraIssue(
  cloudId="...",
  projectKey="AIPDQ",
  issueTypeName="Epic",
  summary="[Epic Summary]",
  description="[Epic Description]",
  additional_fields={"components": [{"name": "[component from JIRA_TODO.md]"}]}
)
```

**Epic Description Structure:**
```markdown
## Overview
[1-2 sentence summary]

## Objectives
- [Key objective 1]
- [Key objective 2]

## Scope
[What's included and what's not]

## Success Criteria
- [Measurable criterion 1]
- [Measurable criterion 2]
```

**Save the Epic key** (e.g., "PROJ-123") for child tickets.

---

## Step 6: Create Child Tickets

**For 1-4 tickets:** Use MCP `createJiraIssue` for each. Always include component:
```
createJiraIssue(
  cloudId="...",
  projectKey="AIPDQ",
  issueTypeName="[Story/Task/Bug]",
  summary="[Task Summary]",
  description="[Task Description]",
  parent="AIPDQ-123",
  additional_fields={"components": [{"name": "[component from JIRA_TODO.md]"}]}
)
```

**For 5+ tickets:** Use batch script with component and assignee flags:
```bash
echo '[
  {"summary": "Implement user registration API", "description": "..."},
  {"summary": "Build login form UI", "description": "..."}
]' | uv run python scripts/batch/batch_create.py --stdin --type Story --parent AIPDQ-123 --project AIPDQ --component "[component]" --assignee "[assignee]"
```

**Task Description Structure:**
```markdown
## Context
[Brief context from the spec]

## Requirements
- [Requirement 1]
- [Requirement 2]

## Technical Details
- Technologies: [e.g., Node.js, React]
- Dependencies: [e.g., requires PROJ-124]

## Acceptance Criteria
- [ ] [Testable criterion 1]
- [ ] [Testable criterion 2]
```

---

## Step 7: Provide Summary

```
Backlog created successfully!

**Epic:** PROJ-123 - [Epic Title]
https://yoursite.atlassian.net/browse/PROJ-123

**Implementation Tickets (7):**
1. PROJ-124 - [Task summary]
2. PROJ-125 - [Task summary]
...

Next Steps:
- Review tickets for accuracy
- Assign to team members
- Estimate story points
- Schedule for upcoming sprint
```

---

## Edge Cases

### Existing Epic
If user wants to add to an existing Epic, skip Step 5 and use the provided Epic key.

### Large Specifications (15+ tickets)
Present the full breakdown, ask if user wants all or a subset created first.

### Custom Required Fields
If creation fails due to required fields, use `getJiraIssueTypeMetaWithFields` to identify them and ask the user.

---

## Examples of Good Breakdowns

### New Feature: Search Functionality
**Epic:** Product Search and Filtering
1. [Task] Design search index schema
2. [Task] Implement backend search API
3. [Story] Build search results UI
4. [Story] Add advanced filtering
5. [Story] Implement autocomplete
6. [Task] Optimize search performance
7. [Task] Write search tests and documentation

### Infrastructure: CI/CD Pipeline
**Epic:** Automated Deployment Pipeline
1. [Task] Set up GitHub Actions workflow
2. [Task] Implement automated testing in CI
3. [Task] Configure staging deployment
4. [Task] Implement blue-green production deployment
5. [Task] Add rollback mechanism
6. [Task] Create deployment runbook

---

## When NOT to Use This Skill

- Meeting action items (use `capture-tasks-from-meeting-notes`)
- Triaging bugs (use `triage-issue`)
- Status reports (run `scripts/batch/sprint_report.py`)

**Use only when:** A spec or requirements doc needs to become a structured Jira backlog.
