---
name: triage-issue
description: "Intelligently triage bug reports and error messages by searching for duplicates in Jira and offering to create new issues or add comments to existing ones. When the agent needs to: (1) Triage a bug report, (2) Check for duplicate issues, (3) Find similar past issues, (4) Create a bug ticket, or (5) Add information to an existing ticket. Uses Atlassian MCP tools to search, analyze, and create."
---

# Triage Issue

## Keywords
triage bug, check duplicate, is this a duplicate, search for similar issues, create bug ticket, file a bug, report this error, triage this error, bug report, error message, similar issues, duplicate bug, who fixed this, has this been reported, search bugs, find similar bugs

## Overview

Automatically triage bug reports and error messages by searching Jira for duplicates, identifying similar past issues, and helping create well-structured bug tickets or add context to existing issues.

**Use this skill when:** Users need to triage error messages, bug reports, or issues to determine if they're duplicates.

**Primary tools:** Atlassian MCP tools (`searchJiraIssuesUsingJql`, `createJiraIssue`, `addCommentToJiraIssue`, `getJiraIssue`)

**Project defaults:** Read from `JIRA_TODO.md` identity header in the project root. The header contains Project (default: `AIPDQ`), Assignee, Component, Board, and Base URL. Do NOT ask the user for these — they are already cached.

---

## Workflow

### Step 1: Extract Key Information

Analyze the bug report or error message to identify search terms:

- **Error signature:** Error type, code, specific message text
- **Context:** Component/system affected, environment
- **Symptoms:** Observable behavior, impact

### Step 2: Search for Duplicates

Execute **multiple targeted searches** via MCP to catch duplicates:

**Search 1: Error-focused**
```
searchJiraIssuesUsingJql(
  cloudId="...",
  jql='project = AIPDQ AND text ~ "error signature" AND type = Bug ORDER BY created DESC',
  fields=["summary","description","status","resolution","assignee"],
  maxResults=20
)
```

**Search 2: Component-focused**
```
searchJiraIssuesUsingJql(
  cloudId="...",
  jql='project = AIPDQ AND text ~ "component keywords" AND type = Bug ORDER BY updated DESC',
  fields=["summary","description","status","resolution","assignee"],
  maxResults=20
)
```

**Search 3: Symptom-focused**
```
searchJiraIssuesUsingJql(
  cloudId="...",
  jql='project = AIPDQ AND summary ~ "symptom keywords" ORDER BY priority DESC',
  fields=["summary","description","status","resolution","assignee"],
  maxResults=20
)
```

Use the batch search script for running all queries in parallel:
```bash
uv run python scripts/batch/batch_search.py "text ~ 'timeout' AND type=Bug" "component = auth AND type=Bug"
```

### Step 3: Analyze Search Results

**High confidence duplicate (>90%):** Same error + same component + recent
**Likely duplicate (70-90%):** Similar error with variations
**Possibly related (40-70%):** Similar symptoms, different error
**Likely new issue (<40%):** No similar issues found

Check fix history on resolved issues — who fixed it, how, and when.

### Step 4: Present Findings to User

**CRITICAL:** Always present findings and wait for user decision.

**For likely duplicate:**
```
I found a very similar issue:

PROJ-456 - Connection timeout during mobile login
Status: Open | Priority: High | Created: 3 days ago
Assignee: @john.doe

Similarity: Same error, same component, same symptoms

Would you like me to:
1. Add a comment to PROJ-456 with your details
2. Create a new issue anyway
3. Show more details about PROJ-456
```

**For no duplicates:**
```
No similar issues found. Would you like me to create a new bug ticket?
```

### Step 5: Execute User Decision

**Option A: Add Comment to Existing Issue**
```
addCommentToJiraIssue(
  cloudId="...",
  issueIdOrKey="PROJ-456",
  commentBody="## Additional Instance Reported\n\n**Error Details:**\n[error details]\n\n**Context:**\n[environment, impact]\n\n---\n*Added via triage*"
)
```

**Option B: Create New Issue**

Create with project defaults (component, assignee from `JIRA_TODO.md`):
```
createJiraIssue(
  cloudId="...",
  projectKey="AIPDQ",
  issueTypeName="Bug",
  summary="[Component]: [Error Type] - [Brief Symptom]",
  description="[structured description]",
  additional_fields={"components": [{"name": "[component from JIRA_TODO.md]"}]}
)
```

**Summary format:** `[Component] [Error Type] - [Brief Symptom]`
- "Mobile Login: Connection timeout during authentication"
- "Payment API: NullPointerException in refund processing"

**Description structure:**
```markdown
## Issue Description
[1-2 sentence summary]

## Error Details
[Error message or stack trace]

## Environment
- **Platform:** [e.g., Mobile iOS, Web]
- **Environment:** [Production/Staging]

## Steps to Reproduce
1. [Step 1]
2. [Step 2]

## Expected vs Actual Behavior
Expected: [what should happen]
Actual: [what happens]

## User Impact
- **Frequency:** [Every time / Intermittent]
- **Affected Users:** [scope]

## Related Issues
- See also: PROJ-123 (similar but resolved)
```

### Step 6: Provide Summary

```
New Issue Created:

PROJ-890 - Mobile Login: Connection timeout during authentication
https://yoursite.atlassian.net/browse/PROJ-890
Type: Bug | Priority: Medium | Status: Open

References related issue PROJ-123 for context.
```

---

## Edge Cases

### Multiple Potential Duplicates
Present all candidates ranked by similarity, recommend the best match.

### Possible Regression
If a resolved issue matches, recommend creating a new issue linked to the old one as a possible regression.

### Insufficient Information
Ask for: specific error message, component/system, environment, steps to reproduce.

---

## When NOT to Use This Skill

- Feature requests (use `spec-to-backlog`)
- Task creation from meeting notes (use `capture-tasks-from-meeting-notes`)
- Status reports (run `scripts/batch/sprint_report.py`)

**Use only when:** Bug reports or errors need triage against existing Jira issues.
