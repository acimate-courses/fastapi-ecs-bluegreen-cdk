#!/bin/bash
set -euo pipefail

# Usage: ./create_codedeploy_deployment.sh <application-name> <deployment-group-name> [appspec-file]
APP_NAME="${1:?Missing application name}"
DEPLOYMENT_GROUP="${2:?Missing deployment group name}"
APPSPEC_FILE="${3:-appspec.yaml}"

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
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --revision "$REVISION_JSON" \
  --query "deploymentId" --output text)

echo "✅ Deployment created: $DEPLOYMENT_ID"
