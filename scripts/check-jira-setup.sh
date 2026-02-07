#!/bin/bash
# check-jira-setup.sh - Verify JIRA credentials, authentication, and project access
# Usage: ./scripts/check-jira-setup.sh

echo "=== JIRA Setup Verification ==="
echo ""

# Check required environment variables
MISSING_VARS=0

check_var() {
    local var_name=$1
    local var_value="${!var_name}"
    if [ -z "$var_value" ]; then
        echo "❌ $var_name: NOT SET"
        MISSING_VARS=$((MISSING_VARS + 1))
    else
        if [ "$var_name" = "JIRA_API_TOKEN" ]; then
            echo "✓ $var_name: SET (hidden)"
        else
            echo "✓ $var_name: $var_value"
        fi
    fi
}

echo "--- Environment Variables ---"
check_var "JIRA_USER"
check_var "JIRA_API_TOKEN"
check_var "JIRA_BASE_URL"
check_var "JIRA_PROJECT_KEY"
echo ""

if [ $MISSING_VARS -gt 0 ]; then
    echo "❌ Missing $MISSING_VARS required variable(s). Add them to ~/.zshrc:"
    echo ""
    echo '  export JIRA_USER="your-email@company.com"'
    echo '  export JIRA_API_TOKEN="your-api-token"'
    echo '  export JIRA_BASE_URL="https://your-instance.atlassian.net"'
    echo '  export JIRA_PROJECT_KEY="PROJ"'
    echo ""
    echo "Get API token at: https://id.atlassian.com/manage-profile/security/api-tokens"
    exit 1
fi

echo "--- Testing Authentication ---"
AUTH_RESULT=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
    "$JIRA_BASE_URL/rest/api/3/myself" 2>/dev/null)

if echo "$AUTH_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['displayName'])" 2>/dev/null; then
    DISPLAY_NAME=$(echo "$AUTH_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['displayName'])")
    EMAIL=$(echo "$AUTH_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['emailAddress'])")
    ACCOUNT_ID=$(echo "$AUTH_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['accountId'])")
    
    echo "✓ Authentication successful!"
    echo ""
    echo "--- Current User ---"
    echo "  Name: $DISPLAY_NAME"
    echo "  Email: $EMAIL"
    echo "  Account ID: $ACCOUNT_ID"
else
    echo "❌ Authentication FAILED"
    echo "  Check JIRA_USER and JIRA_API_TOKEN"
    echo ""
    echo "  Response: $AUTH_RESULT"
    exit 1
fi

echo ""
echo "--- Project Access ---"
PROJECT_RESULT=$(curl -s -k -u "$JIRA_USER:$JIRA_API_TOKEN" \
    "$JIRA_BASE_URL/rest/api/3/project/$JIRA_PROJECT_KEY" 2>/dev/null)

if echo "$PROJECT_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['name'])" 2>/dev/null; then
    PROJECT_NAME=$(echo "$PROJECT_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['name'])")
    echo "✓ Project access confirmed: $PROJECT_NAME ($JIRA_PROJECT_KEY)"
else
    echo "❌ Cannot access project: $JIRA_PROJECT_KEY"
    echo "  Check JIRA_PROJECT_KEY or permissions"
fi

echo ""
echo "=== Setup verification complete ==="
