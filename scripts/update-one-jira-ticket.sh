#!/bin/bash
# update-one-jira-ticket.sh - Transition status or add comment to a single JIRA ticket
# Usage:
#   ./scripts/update-one-jira-ticket.sh PROJ-123 done              # Transition to Done
#   ./scripts/update-one-jira-ticket.sh PROJ-123 progress           # Transition to In Progress
#   ./scripts/update-one-jira-ticket.sh PROJ-123 todo               # Transition to To Do
#   ./scripts/update-one-jira-ticket.sh PROJ-123 comment "text"     # Add comment
#   ./scripts/update-one-jira-ticket.sh PROJ-123 transitions        # List available transitions

set -e

TICKET="$1"
ACTION="$2"
VALUE="$3"

if [[ -z "$TICKET" || -z "$ACTION" ]]; then
    echo "Usage:"
    echo "  $0 TICKET-KEY done|progress|todo      # Transition ticket"
    echo "  $0 TICKET-KEY comment \"Your comment\"  # Add comment"
    echo "  $0 TICKET-KEY transitions              # List transitions"
    echo ""
    echo "Examples:"
    echo "  $0 PROJ-123 done"
    echo "  $0 PROJ-123 comment \"Fixed the login bug\""
    exit 1
fi

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]]; then
    echo "Error: Required environment variables not set."
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

case "$ACTION" in
    transitions|trans|t)
        echo "Available transitions for $TICKET:"
        curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" \
          | python3 -c "import json,sys; [print(f\"  {t['id']}: {t['name']}\") for t in json.load(sys.stdin)['transitions']]"
        ;;
    
    comment|c)
        if [[ -z "$VALUE" ]]; then
            echo "Error: Comment text required"
            exit 1
        fi
        PAYLOAD=$(python3 -c "import json; print(json.dumps({'body':{'type':'doc','version':1,'content':[{'type':'paragraph','content':[{'type':'text','text':'''$VALUE'''}]}]}}))")
        curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
          -H "Content-Type: application/json" \
          -d "$PAYLOAD" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/comment" > /dev/null
        echo "✓ Comment added to $TICKET"
        ;;
    
    done|complete|resolved)
        TRANS_ID=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" \
          | python3 -c "import json,sys; ts=json.load(sys.stdin)['transitions']; done=[t for t in ts if t['name'].lower() in ('done','resolved','closed')]; print(done[0]['id'] if done else '')")
        
        if [[ -z "$TRANS_ID" ]]; then
            echo "❌ Could not find 'Done' transition. Available:"
            curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
              "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" \
              | python3 -c "import json,sys; [print(f\"  {t['id']}: {t['name']}\") for t in json.load(sys.stdin)['transitions']]"
            exit 1
        fi
        
        curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"transition\":{\"id\":\"$TRANS_ID\"}}" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions"
        echo "✓ $TICKET -> Done"
        ;;
    
    progress|inprogress|start)
        TRANS_ID=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" \
          | python3 -c "import json,sys; ts=json.load(sys.stdin)['transitions']; prog=[t for t in ts if 'progress' in t['name'].lower()]; print(prog[0]['id'] if prog else '')")
        
        if [[ -z "$TRANS_ID" ]]; then
            echo "❌ Could not find 'In Progress' transition."
            exit 1
        fi
        
        curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"transition\":{\"id\":\"$TRANS_ID\"}}" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions"
        echo "✓ $TICKET -> In Progress"
        ;;
    
    todo|backlog|open)
        TRANS_ID=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" \
          | python3 -c "import json,sys; ts=json.load(sys.stdin)['transitions']; todo=[t for t in ts if t['name'].lower() in ('to do','todo','open','backlog')]; print(todo[0]['id'] if todo else '')")
        
        if [[ -z "$TRANS_ID" ]]; then
            echo "❌ Could not find 'To Do' transition."
            exit 1
        fi
        
        curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"transition\":{\"id\":\"$TRANS_ID\"}}" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions"
        echo "✓ $TICKET -> To Do"
        ;;
    
    *)
        # Assume it's a transition ID
        curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"transition\":{\"id\":\"$ACTION\"}}" \
          "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions"
        echo "✓ $TICKET transitioned (ID: $ACTION)"
        ;;
esac
