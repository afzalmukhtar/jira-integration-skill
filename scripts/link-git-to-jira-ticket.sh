#!/bin/bash
# link-git-to-jira-ticket.sh - Link git branch/commits to a JIRA ticket
#
# Auto-detects ticket ID from branch name, adds a comment with the latest
# commit info, and optionally transitions the ticket to "In Progress".
#
# Usage:
#   ./scripts/link-git-to-jira-ticket.sh                  # Auto-detect from branch
#   ./scripts/link-git-to-jira-ticket.sh PROJ-123          # Explicit ticket
#   ./scripts/link-git-to-jira-ticket.sh --no-transition   # Skip auto-transition

set -e

TICKET=""
AUTO_TRANSITION=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-transition)
            AUTO_TRANSITION=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [TICKET-KEY] [--no-transition]"
            echo ""
            echo "Links the current git branch and latest commit to a JIRA ticket."
            echo ""
            echo "Options:"
            echo "  TICKET-KEY        Explicit ticket key (default: auto-detect from branch)"
            echo "  --no-transition   Don't auto-transition ticket to In Progress"
            echo ""
            echo "Auto-detection examples:"
            echo "  Branch 'feature/PROJ-123-auth'  ->  PROJ-123"
            echo "  Branch 'PROJ-456-fix-login'     ->  PROJ-456"
            echo "  Branch 'bugfix/PROJ-789'        ->  PROJ-789"
            exit 0
            ;;
        *)
            TICKET="$1"
            shift
            ;;
    esac
done

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]]; then
    echo "Error: Required environment variables not set."
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

# Check we're in a git repo
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo "❌ Not inside a git repository."
    exit 1
fi

# Auto-detect ticket from branch name
if [[ -z "$TICKET" ]]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    echo "Current branch: $BRANCH"

    # Extract ticket pattern (LETTERS-NUMBERS) from branch name
    TICKET=$(echo "$BRANCH" | grep -oE '[A-Z]+-[0-9]+' | head -1 || true)

    if [[ -z "$TICKET" ]]; then
        echo "❌ Could not detect ticket ID from branch name '$BRANCH'"
        echo "   Expected pattern: feature/PROJ-123-description"
        echo "   Or specify explicitly: $0 PROJ-123"
        exit 1
    fi

    echo "Detected ticket: $TICKET"
fi

echo ""

# Get latest commit info
COMMIT_HASH=$(git log -1 --format="%H" 2>/dev/null)
COMMIT_SHORT=$(git log -1 --format="%h" 2>/dev/null)
COMMIT_MSG=$(git log -1 --format="%s" 2>/dev/null)
COMMIT_AUTHOR=$(git log -1 --format="%an" 2>/dev/null)
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)" 2>/dev/null)

# Build comment text
COMMENT_TEXT="Git activity from $REPO_NAME:\n\nBranch: $BRANCH\nCommit: $COMMIT_SHORT - $COMMIT_MSG\nAuthor: $COMMIT_AUTHOR"

echo "Linking to $TICKET..."
echo "  Branch: $BRANCH"
echo "  Commit: $COMMIT_SHORT - $COMMIT_MSG"

# Add comment to JIRA ticket
PAYLOAD=$(python3 -c "
import json
text = '''$COMMENT_TEXT'''
payload = {
    'body': {
        'type': 'doc',
        'version': 1,
        'content': [{
            'type': 'paragraph',
            'content': [{'type': 'text', 'text': text}]
        }]
    }
}
print(json.dumps(payload))
")

RESULT=$(curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/comment" 2>/dev/null)

COMMENT_ID=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")

if [[ -n "$COMMENT_ID" ]]; then
    echo "✓ Comment added to $TICKET"
else
    echo "❌ Failed to add comment to $TICKET"
    echo "  $RESULT"
    exit 1
fi

# Auto-transition to In Progress (if ticket is in To Do)
if [[ "$AUTO_TRANSITION" == true ]]; then
    CURRENT_STATUS=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
        "$JIRA_BASE_URL/rest/api/3/issue/$TICKET?fields=status" 2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['fields']['status']['name'])" 2>/dev/null || echo "")

    if [[ "$CURRENT_STATUS" == "To Do" || "$CURRENT_STATUS" == "Open" || "$CURRENT_STATUS" == "Backlog" ]]; then
        # Find In Progress transition
        TRANS_ID=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
            "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" 2>/dev/null \
            | python3 -c "
import json,sys
data = json.load(sys.stdin)
for t in data.get('transitions', []):
    if 'progress' in t['name'].lower():
        print(t['id'])
        break
" 2>/dev/null || echo "")

        if [[ -n "$TRANS_ID" ]]; then
            curl -s -k -X POST -u "$JIRA_USER:$JIRA_API_TOKEN" \
                -H "Content-Type: application/json" \
                -d "{\"transition\":{\"id\":\"$TRANS_ID\"}}" \
                "$JIRA_BASE_URL/rest/api/3/issue/$TICKET/transitions" 2>/dev/null
            echo "✓ $TICKET -> In Progress (was $CURRENT_STATUS)"
        fi
    else
        echo "  Status: $CURRENT_STATUS (no transition needed)"
    fi
fi

echo ""
echo "✓ Done - $JIRA_BASE_URL/browse/$TICKET"
