#!/usr/bin/env bash
# One-time setup: make the bucket publicly readable and allow the Firebase site to fetch from it.
# Requires gcloud logged in with owner rights on the project.
set -euo pipefail

PROJECT="${PROJECT:-lookpyrenees}"
BUCKET="${BUCKET:-pyrenees_images}"
DIR="$(cd "$(dirname "$0")" && pwd)"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --project "${PROJECT}" \
  --member=allUsers \
  --role=roles/storage.objectViewer

gcloud storage buckets update "gs://${BUCKET}" \
  --project "${PROJECT}" \
  --cors-file="${DIR}/cors.json"

echo "Done. Check: curl -sI https://storage.googleapis.com/${BUCKET}/manifest.json"
