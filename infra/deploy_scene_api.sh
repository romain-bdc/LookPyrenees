#!/usr/bin/env bash
# Build et déploiement du service Cloud Run "scene-api" (région europe-west1).
# Requiert gcloud connecté avec les droits d'édition sur le projet. Ne s'exécute pas automatiquement.
#
# Étapes :
#   1. compte de service dédié + droits d'écriture limités aux préfixes scene/ et stats/ du bucket
#   2. règle de cycle de vie du bucket (suppression de scene/ après 90 jours)
#   3. build de l'image (Cloud Build) et déploiement Cloud Run
#
# Prérequis one-shot : API run, cloudbuild et artifactregistry activées ; dépôt Artifact Registry "images" existant.
set -euo pipefail

PROJECT="${PROJECT:-lookpyrenees}"
REGION="${REGION:-europe-west1}"
BUCKET="${BUCKET:-pyrenees_images}"
SERVICE="${SERVICE:-scene-api}"
SA_NAME="${SA_NAME:-scene-api}"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/images/${SERVICE}:${TAG:-latest}"
STAC_SOURCE="${STAC_SOURCE:-planetary}"   # ou earth-search (secours)
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "${DIR}")"

# 1. Compte de service dédié (idempotent)
if ! gcloud iam service-accounts describe "${SA}" --project "${PROJECT}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" --project "${PROJECT}" \
    --display-name "Cloud Run scene-api"
  sleep 15  # propagation IAM : sans ça le binding qui suit peut répondre "service account does not exist"
fi

# Lecture/écriture/écrasement uniquement sous scene/ et stats/ (condition IAM, nécessite l'accès uniforme au niveau du bucket)
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --project "${PROJECT}" \
  --member "serviceAccount:${SA}" \
  --role roles/storage.objectUser \
  --condition "title=scene-api-prefixes,expression=resource.name.startsWith('projects/_/buckets/${BUCKET}/objects/scene/') || resource.name.startsWith('projects/_/buckets/${BUCKET}/objects/stats/')"

# 2. Cycle de vie : ATTENTION, remplace toutes les règles existantes du bucket.
# Vérifier d'abord : gcloud storage buckets describe gs://${BUCKET} --format="json(lifecycle_config)"
gcloud storage buckets update "gs://${BUCKET}" --project "${PROJECT}" \
  --lifecycle-file "${DIR}/lifecycle_scene.json"

# 3. Build (Cloud Build, contexte = racine du dépôt) puis déploiement
gcloud builds submit "${ROOT}" --project "${PROJECT}" \
  --config /dev/stdin <<CLOUDBUILD
steps:
- name: gcr.io/cloud-builders/docker
  args: ["build", "-f", "Dockerfile.scene-api", "-t", "${IMAGE}", "."]
images: ["${IMAGE}"]
CLOUDBUILD

gcloud run deploy "${SERVICE}" --project "${PROJECT}" --region "${REGION}" \
  --image "${IMAGE}" \
  --service-account "${SA}" \
  --min-instances 0 --max-instances 2 \
  --cpu 1 --memory 1Gi \
  --concurrency 4 --timeout 60 \
  --allow-unauthenticated \
  --set-env-vars "SCENE_BUCKET=${BUCKET},STAC_SOURCE=${STAC_SOURCE}"

echo "Done. Test: curl -s \$(gcloud run services describe ${SERVICE} --region ${REGION} --project ${PROJECT} --format='value(status.url)')/healthz"
