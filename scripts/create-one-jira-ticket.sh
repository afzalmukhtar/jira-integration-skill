#!/bin/bash
# create-one-jira-ticket.sh - Create a single JIRA ticket
# Usage: ./scripts/create-one-jira-ticket.sh "Summary" ["Description"] [story|task|subtask|bug] [parent-key]

set -e

SUMMARY="$1"
DESCRIPTION="${2:-$1}"
TYPE="${3:-task}"
PARENT="$4"

if [[ -z "$SUMMARY" ]]; then
    echo "Usage: $0 \"Summary\" [\"Description\"] [story|task|subtask|bug] [parent-key]"
    echo ""
    echo "Examples:"
    echo "  $0 \"Fix login bug\"                                    # Create task"
    echo "  $0 \"Fix login bug\" \"Users can't log in\" bug           # Create bug"
    echo "  $0 \"Implement auth\" \"Auth flow\" story                  # Create story"
    echo "  $0 \"Write tests\" \"Unit tests\" subtask PROJ-100         # Create sub-task"
    exit 1
fi

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" || -z "$JIRA_PROJECT_KEY" ]]; then
    echo "Error: Required environment variables not set."
    echo "Please set: JIRA_USER, JIRA_API_TOKEN, JIRA_BASE_URL, JIRA_PROJECT_KEY"
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

# Get account ID
ACCOUNT_ID=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/myself" | python3 -c "import json,sys; print(json.load(sys.stdin)['accountId'])")

# Map type to ID (common defaults - may need adjustment per project)
case "$TYPE" in
    story) TYPE_ID="${JIRA_STORY_TYPE_ID:-10001}" ;;
    subtask|sub-task) TYPE_ID="${JIRA_SUBTASK_TYPE_ID:-10003}" ;;
    task) TYPE_ID="${JIRA_TASK_TYPE_ID:-10002}" ;;
    bug) TYPE_ID="${JIRA_BUG_TYPE_ID:-10004}" ;;
    *) TYPE_ID="$TYPE" ;;  # Allow passing ID directly
esac

# Build JSON payload
PAYLOAD=$(python3 << PYTHON
import json

payload = {
    "fields": {
        "project": {"key": "$JIRA_PROJECT_KEY"},
        "summary": """$SUMMARY""",
        "description": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": """$DESCRIPTION"""}]}]
        },
        "issuetype": {"id": "$TYPE_ID"},
        "assignee": {"accountId": "$ACCOUNT_ID"},
        "reporter": {"accountId": "$ACCOUNT_ID"}
    }
}

# Add parent for subtasks
parent = "$PARENT"
if parent:
    payload["fields"]["parent"] = {"key": parent}

# Add component if set
component = "${JIRA_COMPONENT_ID:-}"
if component:
    payload["fields"]["components"] = [{"id": component}]

# Add sprint if set
sprint = "${JIRA_SPRINT_ID:-}"
sprint_field = "${JIRA_SPRINT_FIELD:-customfield_10020}"
if sprint:
    payload["fields"][sprint_field] = int(sprint)

print(json.dumps(payload))
PYTHON
)

# Create the ticket
RESULT=$(curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "$JIRA_BASE_URL/rest/api/3/issue")

# Parse result
KEY=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('key', ''))" 2>/dev/null)

if [[ -n "$KEY" ]]; then
    echo "✓ Created: $KEY"
    echo "  URL: $JIRA_BASE_URL/browse/$KEY"
else
    echo "❌ Error creating ticket:"
    echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
    exit 1
fi
