#!/usr/bin/env bash
# One-time setup: monthly budget of 5 EUR with e-mail alerts at 50 %, 90 % and 100 %.
#
# Usage:
#   ./infra/setup_budget.sh --billing-account 0X0X0X-0X0X0X-0X0X0X --email you@example.com [--project ID] [--amount 5] [--dry-run]
# Or with env vars BILLING_ACCOUNT, EMAIL, PROJECT, AMOUNT.
#
# Required rights (to be checked with `gcloud billing accounts list`):
#   - on the billing account: Billing Account Administrator (roles/billing.admin),
#     or Billing Account Costs Manager (roles/billing.costsManager) to create budgets;
#   - on the project: Monitoring Editor (roles/monitoring.editor) to create the e-mail channel;
#   - APIs billingbudgets.googleapis.com and monitoring.googleapis.com enabled on the project.
# Note: --filter-projects may require the project NUMBER (projects/123456) instead of the ID.
# A budget only alerts, it never stops the spending.
#
# --dry-run only prints the commands: nothing is authenticated or modified.
set -euo pipefail

BILLING_ACCOUNT="${BILLING_ACCOUNT:-}"
EMAIL="${EMAIL:-}"
PROJECT="${PROJECT:-lookpyrenees}"
AMOUNT="${AMOUNT:-5}"
DRY_RUN=0

usage() { sed -n '2,17p' "$0"; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --billing-account) BILLING_ACCOUNT="${2:?missing value}"; shift 2 ;;
    --email) EMAIL="${2:?missing value}"; shift 2 ;;
    --project) PROJECT="${2:?missing value}"; shift 2 ;;
    --amount) AMOUNT="${2:?missing value}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown argument: $1" >&2; usage 1 ;;
  esac
done

if [[ -z "${BILLING_ACCOUNT}" || -z "${EMAIL}" ]]; then
  echo "Error: --billing-account and --email are required." >&2
  usage 1
fi

run() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '[dry-run]'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

# 1. E-mail notification channel (Cloud Monitoring), needed to alert an address
#    other than the billing administrators.
if [[ "${DRY_RUN}" -eq 1 ]]; then
  run gcloud beta monitoring channels create --project "${PROJECT}" \
    --display-name "LookPyrenees budget" --type email \
    --channel-labels "email_address=${EMAIL}"
  CHANNEL="projects/${PROJECT}/notificationChannels/<ID>"
else
  CHANNEL="$(gcloud beta monitoring channels create --project "${PROJECT}" \
    --display-name "LookPyrenees budget" --type email \
    --channel-labels "email_address=${EMAIL}" --format='value(name)')"
fi

# 2. Budget with thresholds on actual spend.
run gcloud billing budgets create \
  --billing-account "${BILLING_ACCOUNT}" \
  --display-name "LookPyrenees ${AMOUNT} EUR/month" \
  --budget-amount "${AMOUNT}EUR" \
  --calendar-period month \
  --filter-projects "projects/${PROJECT}" \
  --threshold-rule percent=0.5 \
  --threshold-rule percent=0.9 \
  --threshold-rule percent=1.0 \
  --notifications-rule-monitoring-notification-channels "${CHANNEL}" \
  --project "${PROJECT}"

echo "Done. Check: gcloud billing budgets list --billing-account ${BILLING_ACCOUNT}"
