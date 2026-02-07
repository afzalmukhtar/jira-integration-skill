#!/bin/bash
# search-jira-tickets.sh - Search JIRA tickets using JQL or built-in shortcuts
#
# Usage:
#   ./scripts/search-jira-tickets.sh mine                    # My open tickets
#   ./scripts/search-jira-tickets.sh sprint                  # Current sprint tickets
#   ./scripts/search-jira-tickets.sh recent                  # Recently updated
#   ./scripts/search-jira-tickets.sh bugs                    # Open bugs
#   ./scripts/search-jira-tickets.sh "priority = High"       # Custom JQL

set -e

QUERY="$1"

if [[ -z "$QUERY" ]]; then
    echo "Usage: $0 <shortcut|jql-query>"
    echo ""
    echo "Shortcuts:"
    echo "  mine     - My open tickets"
    echo "  sprint   - Current sprint tickets"
    echo "  recent   - Recently updated tickets (last 7 days)"
    echo "  bugs     - Open bugs in project"
    echo "  done     - Completed in current sprint"
    echo ""
    echo "Custom JQL:"
    echo "  $0 \"priority = High AND status != Done\""
    echo "  $0 \"summary ~ 'authentication'\""
    exit 1
fi

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]]; then
    echo "Error: Required environment variables not set."
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

PROJECT_KEY="${JIRA_PROJECT_KEY:-}"
PROJECT_FILTER=""
if [[ -n "$PROJECT_KEY" ]]; then
    PROJECT_FILTER="project=$PROJECT_KEY AND "
fi

# Map shortcuts to JQL
case "$QUERY" in
    mine)
        JQL="${PROJECT_FILTER}assignee=currentUser() AND status != Done ORDER BY updated DESC"
        ;;
    sprint)
        JQL="${PROJECT_FILTER}assignee=currentUser() AND sprint in openSprints() ORDER BY rank"
        ;;
    recent)
        JQL="${PROJECT_FILTER}updated >= -7d ORDER BY updated DESC"
        ;;
    bugs)
        JQL="${PROJECT_FILTER}issuetype = Bug AND status != Done ORDER BY priority DESC, created DESC"
        ;;
    done)
        JQL="${PROJECT_FILTER}status = Done AND sprint in openSprints() ORDER BY updated DESC"
        ;;
    *)
        # Custom JQL - use as-is
        JQL="$QUERY"
        ;;
esac

# URL encode
JQL_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$JQL'''))")

# Fetch results
RESPONSE=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
    "$JIRA_BASE_URL/rest/api/3/search?jql=$JQL_ENCODED&fields=key,summary,status,issuetype,priority,assignee&maxResults=50" 2>/dev/null)

# Display results
python3 << 'PYTHON_SCRIPT' <<< "$RESPONSE"
import json
import sys

data = json.load(sys.stdin)

if 'errorMessages' in data:
    for err in data['errorMessages']:
        print(f"Error: {err}")
    sys.exit(1)

issues = data.get('issues', [])
total = data.get('total', 0)

if not issues:
    print("No tickets found.")
    sys.exit(0)

# Calculate column widths
key_width = max(len(i['key']) for i in issues)
status_width = max(len(i['fields']['status']['name']) for i in issues)
type_width = max(len(i['fields']['issuetype']['name']) for i in issues)

# Header
header = f"{'KEY':<{key_width}}  {'STATUS':<{status_width}}  {'TYPE':<{type_width}}  SUMMARY"
print(header)
print("-" * len(header))

# Rows
for issue in issues:
    key = issue['key']
    status = issue['fields']['status']['name']
    itype = issue['fields']['issuetype']['name']
    summary = issue['fields']['summary']

    # Truncate summary for terminal width
    max_summary = 60
    if len(summary) > max_summary:
        summary = summary[:max_summary - 3] + "..."

    print(f"{key:<{key_width}}  {status:<{status_width}}  {itype:<{type_width}}  {summary}")

print(f"\nShowing {len(issues)} of {total} results")
PYTHON_SCRIPT
