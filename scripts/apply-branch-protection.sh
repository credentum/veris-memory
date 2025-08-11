#!/bin/bash
#
# Apply branch protection rules via GitHub API
# Requires: gh CLI tool and appropriate permissions
#

set -e

# Configuration
REPO_OWNER=${REPO_OWNER:-"credentum"}
REPO_NAME=${REPO_NAME:-"agent-context-template"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Functions
status() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    error "gh CLI is not installed. Please install it first."
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    error "Not authenticated with GitHub. Run 'gh auth login' first."
fi

echo "========================================="
echo "Applying Branch Protection Rules"
echo "========================================="
echo "Repository: $REPO_OWNER/$REPO_NAME"
echo ""

# Function to apply protection rules
apply_protection() {
    local branch=$1
    local rules=$2
    
    echo "Applying protection to branch: $branch"
    
    gh api \
        --method PUT \
        -H "Accept: application/vnd.github+json" \
        "/repos/$REPO_OWNER/$REPO_NAME/branches/$branch/protection" \
        --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Parity Verification / Verify Manifest Parity",
      "Parity Verification / Check Dimension Consistency",
      "Parity Verification / Run Smoke Tests"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismissal_restrictions": {},
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
    
    if [ $? -eq 0 ]; then
        status "Protection applied to $branch"
    else
        warning "Failed to apply protection to $branch"
    fi
}

# Apply protection to main branch
echo "1. Protecting main branch..."
apply_protection "main"

echo ""
echo "2. Setting up CODEOWNERS..."

# Check if CODEOWNERS file exists
if [ -f "CODEOWNERS" ]; then
    status "CODEOWNERS file exists"
    
    # Verify it's in the right location
    if [ -f ".github/CODEOWNERS" ]; then
        status "CODEOWNERS is in .github directory"
    else
        echo "Moving CODEOWNERS to .github directory..."
        mkdir -p .github
        mv CODEOWNERS .github/CODEOWNERS
        status "CODEOWNERS moved to .github/"
    fi
else
    warning "CODEOWNERS file not found"
fi

echo ""
echo "3. Verifying protection status..."

# Get current protection status
protection_status=$(gh api \
    -H "Accept: application/vnd.github+json" \
    "/repos/$REPO_OWNER/$REPO_NAME/branches/main/protection" \
    2>/dev/null || echo "{}")

if [ "$protection_status" != "{}" ]; then
    status "Branch protection is active on main"
    
    # Check specific rules
    if echo "$protection_status" | grep -q '"enforce_admins".*true'; then
        status "Admin enforcement is enabled"
    else
        warning "Admin enforcement is disabled"
    fi
    
    if echo "$protection_status" | grep -q '"required_approving_review_count".*2'; then
        status "Requires 2 approving reviews"
    else
        warning "Review count requirement not set to 2"
    fi
    
    if echo "$protection_status" | grep -q '"require_code_owner_reviews".*true'; then
        status "Code owner reviews required"
    else
        warning "Code owner reviews not required"
    fi
else
    error "Failed to verify protection status"
fi

echo ""
echo "========================================="
echo "Branch Protection Summary"
echo "========================================="
echo ""
echo "Protected branches:"
echo "  - main (strict protection)"
echo ""
echo "Key protection rules:"
echo "  ✓ Require pull request reviews (2 approvals)"
echo "  ✓ Dismiss stale reviews"
echo "  ✓ Require code owner reviews"
echo "  ✓ Require status checks to pass"
echo "  ✓ Require branches to be up to date"
echo "  ✓ Include administrators"
echo "  ✓ Restrict force pushes"
echo "  ✓ Require conversation resolution"
echo ""
echo "Next steps:"
echo "  1. Verify teams exist in GitHub organization"
echo "  2. Add team members to appropriate teams"
echo "  3. Test protection by creating a test PR"
echo ""

status "Branch protection setup complete!"