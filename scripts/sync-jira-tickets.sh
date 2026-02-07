#!/bin/bash
# sync-jira-tickets.sh - Bidirectional sync between JIRA and JIRA_TODO.md
#
# If JIRA_TODO.md exists:
#   1. Read locally completed tickets (marked [x])
#   2. Push completions to JIRA (transition to Done)
#   3. Pull fresh sprint state from JIRA
#   4. Regenerate JIRA_TODO.md with merged state
#
# If JIRA_TODO.md does not exist:
#   1. Pull sprint tickets from JIRA
#   2. Create JIRA_TODO.md
#
# Usage: ./scripts/sync-jira-tickets.sh [output-file]

set -e

# Check required environment variables
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]]; then
    echo "Error: Required environment variables not set."
    echo "Please set: JIRA_USER, JIRA_API_TOKEN, JIRA_BASE_URL"
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

OUTPUT_FILE="${1:-JIRA_TODO.md}"
PROJECT_KEY="${JIRA_PROJECT_KEY:-}"

# ============================================================
# PHASE 1: Push local completions to JIRA (if TODO file exists)
# ============================================================

PUSH_SUCCESS=0
PUSH_FAILED=0
PUSH_ALREADY=0

if [[ -f "$OUTPUT_FILE" && -n "$PROJECT_KEY" ]]; then
    echo "=== Phase 1: Pushing local completions to JIRA ==="
    echo ""

    # Extract completed tickets from the existing TODO file
    COMPLETED_TICKETS=$(grep -oE "\[x\].*\[($PROJECT_KEY-[0-9]+)\]" "$OUTPUT_FILE" 2>/dev/null | grep -oE "$PROJECT_KEY-[0-9]+" || true)

    if [[ -n "$COMPLETED_TICKETS" ]]; then
        TICKET_COUNT=$(echo "$COMPLETED_TICKETS" | wc -l | tr -d ' ')
        echo "Found $TICKET_COUNT locally completed ticket(s):"
        echo "$COMPLETED_TICKETS"
        echo ""

        for TICKET in $COMPLETED_TICKETS; do
            echo -n "  [$TICKET] "

            # Get current status
            CURRENT_STATUS=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
                "$JIRA_BASE_URL/rest/api/3/issue/$TICKET?fields=status" 2>/dev/null \
                | python3 -c "import json,sys; print(json.load(sys.stdin)['fields']['status']['name'])" 2>/dev/null || echo "")

            if [[ "$CURRENT_STATUS" == "Done" || "$CURRENT_STATUS" == "Closed" || "$CURRENT_STATUS" == "Resolved" ]]; then
                echo "already Done ✓"
                PUSH_ALREADY=$((PUSH_ALREADY + 1))
                continue
            fi

            # Get available transitions and find Done
            DONE_ID=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
                "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" 2>/dev/null \
                | python3 -c "
import json,sys
data = json.load(sys.stdin)
for t in data.get('transitions', []):
    if t['name'].lower() in ['done', 'closed', 'resolved', 'complete']:
        print(t['id'])
        break
" 2>/dev/null || echo "")

            if [[ -z "$DONE_ID" ]]; then
                echo "FAILED (no Done transition)"
                PUSH_FAILED=$((PUSH_FAILED + 1))
                continue
            fi

            # Perform transition
            RESULT=$(curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
                -H "Content-Type: application/json" \
                -d "{\"transition\":{\"id\":\"$DONE_ID\"}}" \
                "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" 2>/dev/null)

            if [[ -z "$RESULT" || "$RESULT" == "{}" ]]; then
                echo "Done ✓"
                PUSH_SUCCESS=$((PUSH_SUCCESS + 1))
            else
                echo "FAILED"
                PUSH_FAILED=$((PUSH_FAILED + 1))
            fi
        done

        echo ""
        echo "Push summary: $PUSH_SUCCESS updated, $PUSH_ALREADY already done, $PUSH_FAILED failed"
    else
        echo "No locally completed tickets to push."
    fi
    echo ""
fi

# ============================================================
# PHASE 2: Pull fresh state from JIRA and regenerate TODO
# ============================================================

echo "=== Phase 2: Pulling tickets from JIRA ==="

# Build JQL query
JQL="assignee=currentUser() AND sprint in openSprints() ORDER BY rank"
if [[ -n "$PROJECT_KEY" ]]; then
    JQL="project=$PROJECT_KEY AND $JQL"
fi

# URL encode the JQL
JQL_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$JQL'))")

echo "Fetching sprint tickets..."

# Fetch tickets and generate TODO.md
curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/search?jql=$JQL_ENCODED&fields=key,summary,status,issuetype,parent&maxResults=100" \
  | python3 << 'PYTHON_SCRIPT' > "$OUTPUT_FILE"
import json
import sys
import os
from datetime import datetime

data = json.load(sys.stdin)
base_url = os.environ.get('JIRA_BASE_URL', '')

print("# JIRA Sprint TODO")
print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"Source: {base_url}")
print()

# Organize issues by parent
stories = {}
standalone = []

for issue in data.get('issues', []):
    key = issue['key']
    fields = issue['fields']
    summary = fields['summary']
    status = fields['status']['name']
    itype = fields['issuetype']['name']
    parent = fields.get('parent', {}).get('key') if fields.get('parent') else None

    item = {
        'key': key,
        'summary': summary,
        'status': status,
        'type': itype,
        'done': status.lower() in ('done', 'closed', 'resolved')
    }

    if itype in ('Story', 'Epic', 'Bug'):
        stories[key] = {**item, 'children': []}
    elif parent and parent in stories:
        stories[parent]['children'].append(item)
    elif parent:
        # Parent exists but not fetched - create placeholder
        if parent not in stories:
            stories[parent] = {'key': parent, 'summary': '(Parent)', 'status': 'Unknown', 'type': 'Story', 'done': False, 'children': []}
        stories[parent]['children'].append(item)
    else:
        standalone.append(item)

def checkbox(done):
    return '[x]' if done else '[ ]'

def link(key):
    return f"[{key}]({base_url}/browse/{key})"

# Print stories with their children
for key, story in stories.items():
    print(f"## {checkbox(story['done'])} {link(key)} {story['summary']}")
    print()
    if story['children']:
        for child in story['children']:
            print(f"- {checkbox(child['done'])} {link(child['key'])} {child['summary']}")
        print()

# Print standalone items
if standalone:
    print("## Other Tasks")
    print()
    for item in standalone:
        print(f"- {checkbox(item['done'])} {link(item['key'])} {item['summary']}")
    print()

# Summary
total = len(data.get('issues', []))
done = sum(1 for i in data.get('issues', []) if i['fields']['status']['name'].lower() in ('done', 'closed', 'resolved'))
print("---")
print(f"**Progress:** {done}/{total} completed")
PYTHON_SCRIPT

TASK_COUNT=$(grep -c '^\- \[' "$OUTPUT_FILE" 2>/dev/null || echo 0)
echo "✓ Generated $OUTPUT_FILE with $TASK_COUNT tasks"

echo ""
echo "=== Sync complete ==="
