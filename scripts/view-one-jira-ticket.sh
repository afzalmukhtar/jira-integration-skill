#!/bin/bash
# view-one-jira-ticket.sh - Display full details of a single JIRA ticket in the terminal
# Usage: ./scripts/view-one-jira-ticket.sh PROJ-123

set -e

TICKET="$1"

if [[ -z "$TICKET" ]]; then
    echo "Usage: $0 TICKET-KEY"
    echo ""
    echo "Example: $0 PROJ-123"
    exit 1
fi

# Check environment
if [[ -z "$JIRA_USER" || -z "$JIRA_API_TOKEN" || -z "$JIRA_BASE_URL" ]]; then
    echo "Error: Required environment variables not set."
    echo "Run check-jira-setup.sh to verify."
    exit 1
fi

# Fetch ticket details
RESPONSE=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
    "$JIRA_BASE_URL/rest/api/3/issue/$TICKET?fields=summary,status,assignee,reporter,priority,issuetype,parent,created,updated,description,comment" 2>/dev/null)

# Check for errors
ERROR=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('errorMessages',[''])[0] if 'errorMessages' in d else '')" 2>/dev/null)
if [[ -n "$ERROR" ]]; then
    echo "❌ Error: $ERROR"
    exit 1
fi

# Display ticket
python3 << 'PYTHON_SCRIPT' <<< "$RESPONSE"
import json
import sys
import textwrap

data = json.load(sys.stdin)
fields = data['fields']

key = data['key']
summary = fields.get('summary', 'N/A')
status = fields.get('status', {}).get('name', 'N/A')
issue_type = fields.get('issuetype', {}).get('name', 'N/A')
priority = fields.get('priority', {}).get('name', 'N/A') if fields.get('priority') else 'None'
assignee = fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned'
reporter = fields.get('reporter', {}).get('displayName', 'N/A') if fields.get('reporter') else 'N/A'
parent = fields.get('parent', {}).get('key', '') if fields.get('parent') else ''
created = fields.get('created', 'N/A')[:10]
updated = fields.get('updated', 'N/A')[:10]

# Header
print(f"{'=' * 60}")
print(f"  {key}: {summary}")
print(f"{'=' * 60}")
print()

# Metadata
print(f"  Type:       {issue_type}")
print(f"  Status:     {status}")
print(f"  Priority:   {priority}")
print(f"  Assignee:   {assignee}")
print(f"  Reporter:   {reporter}")
if parent:
    print(f"  Parent:     {parent}")
print(f"  Created:    {created}")
print(f"  Updated:    {updated}")
print()

# Description
def extract_text(node):
    """Recursively extract plain text from Atlassian Document Format."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get('type') == 'text':
            return node.get('text', '')
        children = node.get('content', [])
        parts = [extract_text(c) for c in children]
        if node.get('type') in ('paragraph', 'heading', 'bulletList', 'orderedList'):
            return '\n'.join(parts) + '\n'
        if node.get('type') == 'listItem':
            return '  - ' + ' '.join(parts)
        return ' '.join(parts)
    if isinstance(node, list):
        return '\n'.join(extract_text(c) for c in node)
    return ''

desc = fields.get('description')
if desc:
    print(f"--- Description ---")
    text = extract_text(desc).strip()
    for line in text.split('\n'):
        print(f"  {line}")
    print()

# Comments (last 3)
comments = fields.get('comment', {}).get('comments', [])
if comments:
    recent = comments[-3:]
    print(f"--- Comments ({len(comments)} total, showing last {len(recent)}) ---")
    for c in recent:
        author = c.get('author', {}).get('displayName', 'Unknown')
        date = c.get('created', '')[:10]
        body = extract_text(c.get('body', {})).strip()
        print(f"  [{date}] {author}:")
        for line in textwrap.wrap(body, width=56):
            print(f"    {line}")
        print()

print(f"{'=' * 60}")
PYTHON_SCRIPT
