#!/bin/bash
# jira-sprint-report.sh - Sprint progress summary with terminal progress bar
#
# Shows: total/done/in-progress/todo counts, progress bar, stale tickets
#
# Usage: ./scripts/jira-sprint-report.sh

set -e

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]]; then
    echo "Error: Required environment variables not set."
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

PROJECT_KEY="${JIRA_PROJECT_KEY:-}"

# Build JQL - all tickets in current sprint (not just mine)
JQL="sprint in openSprints() ORDER BY status ASC, rank ASC"
if [[ -n "$PROJECT_KEY" ]]; then
    JQL="project=$PROJECT_KEY AND $JQL"
fi

JQL_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$JQL'''))")

echo "Fetching sprint data..."
echo ""

# Fetch all sprint tickets
RESPONSE=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
    "$JIRA_BASE_URL/rest/api/3/search?jql=$JQL_ENCODED&fields=key,summary,status,assignee,updated,issuetype&maxResults=200" 2>/dev/null)

# Generate report
python3 << 'PYTHON_SCRIPT' <<< "$RESPONSE"
import json
import sys
from datetime import datetime, timezone

data = json.load(sys.stdin)

if 'errorMessages' in data:
    for err in data['errorMessages']:
        print(f"Error: {err}")
    sys.exit(1)

issues = data.get('issues', [])
total = len(issues)

if total == 0:
    print("No tickets found in current sprint.")
    sys.exit(0)

# Categorize by status
done = []
in_progress = []
todo = []
stale = []

now = datetime.now(timezone.utc)

for issue in issues:
    key = issue['key']
    fields = issue['fields']
    summary = fields['summary']
    status = fields['status']['name'].lower()
    assignee = fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned'
    updated = fields.get('updated', '')

    item = {
        'key': key,
        'summary': summary[:50] + ('...' if len(summary) > 50 else ''),
        'status': fields['status']['name'],
        'assignee': assignee,
        'updated': updated
    }

    if status in ('done', 'closed', 'resolved'):
        done.append(item)
    elif status in ('in progress', 'in review', 'in development'):
        in_progress.append(item)
    else:
        todo.append(item)

    # Check for stale tickets (not Done, not updated in 3+ days)
    if status not in ('done', 'closed', 'resolved') and updated:
        try:
            updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
            days_stale = (now - updated_dt).days
            if days_stale >= 3:
                item['days_stale'] = days_stale
                stale.append(item)
        except:
            pass

# Header
print("=" * 60)
print("  SPRINT REPORT")
print("=" * 60)
print()

# Progress bar
done_count = len(done)
progress_pct = (done_count / total * 100) if total > 0 else 0
bar_width = 40
filled = int(bar_width * done_count / total) if total > 0 else 0
bar = "█" * filled + "░" * (bar_width - filled)

print(f"  Progress: [{bar}] {progress_pct:.0f}%")
print()

# Status breakdown
print(f"  ✓ Done:          {done_count:>3}")
print(f"  → In Progress:   {len(in_progress):>3}")
print(f"  ○ To Do:         {len(todo):>3}")
print(f"  ─────────────────────")
print(f"    Total:         {total:>3}")
print()

# In Progress details
if in_progress:
    print("--- In Progress ---")
    for item in in_progress:
        print(f"  {item['key']:<12} {item['assignee']:<18} {item['summary']}")
    print()

# To Do details
if todo:
    print("--- To Do ---")
    for item in todo:
        print(f"  {item['key']:<12} {item['assignee']:<18} {item['summary']}")
    print()

# Stale tickets warning
if stale:
    print("--- ⚠ Stale Tickets (no update in 3+ days) ---")
    for item in stale:
        print(f"  {item['key']:<12} {item['days_stale']}d stale  {item['assignee']:<18} {item['summary']}")
    print()

# Done (collapsed)
if done:
    print(f"--- Done ({done_count}) ---")
    for item in done:
        print(f"  {item['key']:<12} {item['summary']}")
    print()

print("=" * 60)
PYTHON_SCRIPT
