#!/bin/bash
set -e

APP_NAME=$1
DEPLOYMENT_GROUP=$2
GITHUB_REPO=$3
GITHUB_COMMIT_ID=$4

aws deploy create-deployment \
  --application-name "$APP_NAME" \
  --deployment-group-name "$DEPLOYMENT_GROUP" \
  --revision "revisionType=GitHub,gitHubLocation={repository=$GITHUB_REPO,commitId=$GITHUB_COMMIT_ID}" \
  --description "Deployment from GitHub Actions"
  