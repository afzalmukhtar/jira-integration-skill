#!/bin/bash
# bulk-update-jira-tickets.sh - Transition multiple JIRA tickets at once
# Usage:
#   ./scripts/bulk-update-jira-tickets.sh done PROJ-123 PROJ-124 PROJ-125
#   ./scripts/bulk-update-jira-tickets.sh progress PROJ-123 PROJ-124
#   ./scripts/bulk-update-jira-tickets.sh todo PROJ-200 PROJ-201

set -e

ACTION="$1"
shift
TICKETS=("$@")

if [[ -z "$ACTION" || ${#TICKETS[@]} -eq 0 ]]; then
    echo "Usage: $0 <action> <ticket1> <ticket2> ..."
    echo ""
    echo "Actions: done, progress, todo"
    echo ""
    echo "Examples:"
    echo "  $0 done PROJ-123 PROJ-124 PROJ-125"
    echo "  $0 progress PROJ-200 PROJ-201"
    exit 1
fi

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]]; then
    echo "Error: Required environment variables not set."
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

# Map action to transition name patterns
case "$ACTION" in
    done|complete|resolved)
        PATTERNS="done|resolved|closed"
        ;;
    progress|inprogress|start)
        PATTERNS="progress"
        ;;
    todo|backlog|open)
        PATTERNS="to do|todo|open|backlog"
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: done, progress, todo"
        exit 1
        ;;
esac

echo "Bulk updating ${#TICKETS[@]} tickets to '$ACTION'..."
echo "================================================"

SUCCESS=0
FAILED=0

for TICKET in "${TICKETS[@]}"; do
    echo -n "[$TICKET] "
    
    # Get available transitions
    TRANS_RESPONSE=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
        "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" 2>/dev/null)
    
    # Find matching transition ID
    TRANS_ID=$(echo "$TRANS_RESPONSE" | python3 -c "
import json, sys, re
try:
    data = json.load(sys.stdin)
    transitions = data.get('transitions', [])
    patterns = '$PATTERNS'.split('|')
    for t in transitions:
        name_lower = t['name'].lower()
        if any(p in name_lower for p in patterns):
            print(t['id'])
            break
except:
    pass
" 2>/dev/null)
    
    if [[ -z "$TRANS_ID" ]]; then
        echo "FAILED (no matching transition)"
        ((FAILED++))
        continue
    fi
    
    # Perform transition
    RESULT=$(curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"transition\":{\"id\":\"$TRANS_ID\"}}" \
        "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" 2>/dev/null)
    
    # Check if successful (empty response = success)
    if [[ -z "$RESULT" || "$RESULT" == "{}" ]]; then
        echo "✓ -> $ACTION"
        ((SUCCESS++))
    else
        ERROR=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('errorMessages',['Unknown error'])[0])" 2>/dev/null || echo "Unknown error")
        echo "FAILED ($ERROR)"
        ((FAILED++))
    fi
done

echo "================================================"
echo "Summary: $SUCCESS succeeded, $FAILED failed"

if [[ $FAILED -gt 0 ]]; then
    exit 1
fi
