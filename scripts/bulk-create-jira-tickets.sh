#!/bin/bash
# bulk-create-jira-tickets.sh - Create multiple JIRA tickets at once
#
# Usage:
#   ./scripts/bulk-create-jira-tickets.sh "Task A" "Task B" "Task C"
#   ./scripts/bulk-create-jira-tickets.sh --type subtask --parent PROJ-100 "Task A" "Task B"
#   ./scripts/bulk-create-jira-tickets.sh --type story "Feature A" "Feature B"
#   echo -e "Task A\nTask B" | ./scripts/bulk-create-jira-tickets.sh --stdin

set -e

# Defaults
TYPE="task"
PARENT=""
FROM_STDIN=false
SUMMARIES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)
            TYPE="$2"
            shift 2
            ;;
        --parent)
            PARENT="$2"
            shift 2
            ;;
        --stdin)
            FROM_STDIN=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options] \"Summary 1\" \"Summary 2\" ..."
            echo ""
            echo "Options:"
            echo "  --type TYPE      Issue type: story|task|subtask|bug (default: task)"
            echo "  --parent KEY     Parent ticket key for sub-tasks (e.g., PROJ-100)"
            echo "  --stdin          Read summaries from stdin (one per line)"
            echo ""
            echo "Examples:"
            echo "  $0 \"Implement login\" \"Implement logout\" \"Add tests\""
            echo "  $0 --type subtask --parent PROJ-100 \"Write unit tests\" \"Write docs\""
            echo "  echo -e \"Task A\nTask B\" | $0 --stdin --type story"
            exit 0
            ;;
        *)
            SUMMARIES+=("$1")
            shift
            ;;
    esac
done

# Read from stdin if requested
if [[ "$FROM_STDIN" == true ]]; then
    while IFS= read -r line; do
        [[ -n "$line" ]] && SUMMARIES+=("$line")
    done
fi

if [[ ${#SUMMARIES[@]} -eq 0 ]]; then
    echo "Error: No ticket summaries provided."
    echo "Run $0 --help for usage."
    exit 1
fi

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" || -z "$JIRA_PROJECT_KEY" ]]; then
    echo "Error: Required environment variables not set."
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

# Get account ID
ACCOUNT_ID=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/myself" | python3 -c "import json,sys; print(json.load(sys.stdin)['accountId'])")

# Map type to ID
case "$TYPE" in
    story) TYPE_ID="${JIRA_STORY_TYPE_ID:-10001}" ;;
    subtask|sub-task) TYPE_ID="${JIRA_SUBTASK_TYPE_ID:-10003}" ;;
    task) TYPE_ID="${JIRA_TASK_TYPE_ID:-10002}" ;;
    bug) TYPE_ID="${JIRA_BUG_TYPE_ID:-10004}" ;;
    *) TYPE_ID="$TYPE" ;;
esac

echo "Creating ${#SUMMARIES[@]} $TYPE ticket(s)..."
if [[ -n "$PARENT" ]]; then
    echo "Parent: $PARENT"
fi
echo "================================================"

SUCCESS=0
FAILED=0
CREATED_KEYS=()

for SUMMARY in "${SUMMARIES[@]}"; do
    echo -n "  Creating: $SUMMARY... "

    # Build payload
    PAYLOAD=$(python3 << PYTHON
import json

payload = {
    "fields": {
        "project": {"key": "$JIRA_PROJECT_KEY"},
        "summary": """$SUMMARY""",
        "description": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": """$SUMMARY"""}]}]
        },
        "issuetype": {"id": "$TYPE_ID"},
        "assignee": {"accountId": "$ACCOUNT_ID"},
        "reporter": {"accountId": "$ACCOUNT_ID"}
    }
}

parent = "$PARENT"
if parent:
    payload["fields"]["parent"] = {"key": parent}

component = "${JIRA_COMPONENT_ID:-}"
if component:
    payload["fields"]["components"] = [{"id": component}]

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

    KEY=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('key', ''))" 2>/dev/null)

    if [[ -n "$KEY" ]]; then
        echo "✓ $KEY"
        CREATED_KEYS+=("$KEY")
        ((SUCCESS++))
    else
        echo "FAILED"
        ((FAILED++))
    fi
done

echo "================================================"
echo "Summary: $SUCCESS created, $FAILED failed"

if [[ ${#CREATED_KEYS[@]} -gt 0 ]]; then
    echo ""
    echo "Created tickets:"
    for KEY in "${CREATED_KEYS[@]}"; do
        echo "  $KEY  $JIRA_BASE_URL/browse/$KEY"
    done
fi

if [[ $FAILED -gt 0 ]]; then
    exit 1
fi
