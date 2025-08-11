#!/bin/bash
set -euo pipefail

# Required inputs
CD_APP="${CD_APP:?Application name not set}"
CD_DG="${CD_DG:?Deployment group name not set}"
APPSPEC_FILE="${APPSPEC_FILE:-appspec.yaml}"

# Read and escape appspec content
if [[ ! -f "$APPSPEC_FILE" ]]; then
  echo "Error: $APPSPEC_FILE not found"
  exit 1
fi

APPSPEC_CONTENT=$(perl -pe 's/\n/\\n/g' "$APPSPEC_FILE" | sed 's/"/\\"/g')

# Build revision JSON
REVISION_JSON="{\"appSpecContent\":{\"content\":\"$APPSPEC_CONTENT\"}}"

# Optional: validate JSON
echo "$REVISION_JSON" | jq . > /dev/null || {
  echo "Error: Invalid JSON generated for revision"
  exit 1
}

# Create deployment
DEPLOYMENT_ID=$(aws deploy create-deployment \
  --application-name "$CD_APP" \
  --deployment-group-name "$CD_DG" \
  --revision "$REVISION_JSON" \
  --query "deploymentId" --output text)

echo "✅ Deployment created: $DEPLOYMENT_ID"
