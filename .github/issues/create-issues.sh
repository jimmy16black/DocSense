#!/usr/bin/env bash
# Bulk-create GitHub issues from the markdown files in this directory.
# Usage: gh auth login && bash .github/issues/create-issues.sh [owner/repo]
set -euo pipefail
cd "$(dirname "$0")"
REPO_ARG=""
if [ $# -ge 1 ]; then REPO_ARG="--repo $1"; fi

# Ensure labels exist (safe to re-run; ignores duplicates/errors)
for L in "bug:red" "security:red" "critical:red" "compliance:red" "high:orange" "medium:yellow" \
         "backend:blue" "mobile:blue" "ai:blue" "ux:blue" "infra:blue" "api:blue" "database:blue" \
         "testing:blue" "qa:blue" "cost:blue" "ci-cd:blue" "enhancement:green" "core:red"; do
  NAME="${L%%:*}"; COLOR="${L##*:}"
  gh label create "$NAME" --color "$COLOR" --force $REPO_ARG 2>/dev/null || true
done

for F in ISSUE-*.md; do
  TITLE=$(grep -m1 '^title:' "$F" | sed 's/^title:[[:space:]]*//' | sed 's/^"//;s/"$//')
  LABELS=$(grep -m1 '^labels:' "$F" | sed 's/^labels:[[:space:]]*//')
  echo "Creating: $TITLE"
  # Strip frontmatter for body
  awk 'BEGIN{fm=0} /^---$/{fm++; next} fm>=2{print}' "$F" > /tmp/issue_body.md
  IFS=', ' read -r -a ARR <<< "$LABELS"
  LABEL_ARGS=""
  for x in "${ARR[@]}"; do LABEL_ARGS="$LABEL_ARGS --label $x"; done
  # shellcheck disable=SC2086
  gh issue create --title "$TITLE" --body-file /tmp/issue_body.md $LABEL_ARGS $REPO_ARG
done
echo "All issues created."
