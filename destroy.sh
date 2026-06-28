#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="asterra-devops-assignment"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die()  { echo "[ERROR] $*" >&2; exit 1; }
step() { echo; log "==> [$1/4] $2"; }

# ── Prerequisites ──────────────────────────────────────────────────────────────
for cmd in terraform aws helmfile; do
  command -v "$cmd" &>/dev/null || die "Missing required tool: $cmd"
done

# ── Confirmation ───────────────────────────────────────────────────────────────
echo
echo "  WARNING: This will permanently destroy ALL infrastructure:"
echo "    - All Helm releases (K8s workloads)"
echo "    - ECR repositories and all images"
echo "    - k3s EC2 instance, RDS, VPC, SQS, S3, IAM, Secrets Manager"
echo "    - Terraform state bucket and lock table"
echo
read -r -p "  Type 'yes' to confirm: " CONFIRM
[[ "$CONFIRM" == "yes" ]] || { log "Aborted."; exit 0; }

# ── 1. Helm releases ───────────────────────────────────────────────────────────
step 1 "Helmfile destroy (all K8s releases)"
cd "${SCRIPT_DIR}/helm"
helmfile destroy || log "Warning: helmfile destroy encountered errors — the cluster may already be gone, continuing"

# ── 2. ECR gdal-service repo ───────────────────────────────────────────────────
# This repo was created by deploy.sh outside of Terraform, so it is not tracked
# in state and must be deleted manually before the main destroy.
step 2 "Delete gdal-service ECR repository (not tracked by Terraform)"
GDAL_REPO="${PROJECT_NAME}-gdal"
if aws ecr describe-repositories \
     --repository-names "$GDAL_REPO" \
     --region "$REGION" &>/dev/null; then
  aws ecr delete-repository \
    --repository-name "$GDAL_REPO" \
    --region "$REGION" \
    --force
  log "Deleted ECR repository: ${GDAL_REPO}"
else
  log "ECR repository ${GDAL_REPO} not found — skipping"
fi

# ── 3. Main Terraform ──────────────────────────────────────────────────────────
# ECR data-processor repo has force_delete=true so Terraform removes it with images.
# RDS has skip_final_snapshot=true and deletion_protection=false — safe to destroy.
step 3 "Terraform destroy main (VPC, ECR, k3s, RDS, SQS, S3, IAM, Secrets Manager)"
cd "${SCRIPT_DIR}/terraform"
terraform destroy -auto-approve -input=false

# ── 4. Bootstrap ───────────────────────────────────────────────────────────────
# bootstrap/main.tf sets force_destroy=false on the S3 state bucket, so
# Terraform will refuse to delete it while it still contains objects.
# We must empty all versions and delete markers first.
step 4 "Terraform bootstrap destroy (S3 state bucket + DynamoDB lock table)"
cd "${SCRIPT_DIR}/terraform/bootstrap"

STATE_BUCKET="$(terraform output -raw bucket_id 2>/dev/null || true)"
if [[ -n "$STATE_BUCKET" ]]; then
  log "Emptying versioned S3 bucket: ${STATE_BUCKET}"

  # Delete all object versions
  VERSIONS="$(aws s3api list-object-versions \
    --bucket "$STATE_BUCKET" \
    --query 'Versions[].{Key:Key,VersionId:VersionId}' \
    --output json 2>/dev/null || echo '[]')"
  if [[ "$VERSIONS" != "[]" && "$VERSIONS" != "null" && "$VERSIONS" != "" ]]; then
    aws s3api delete-objects \
      --bucket "$STATE_BUCKET" \
      --delete "{\"Objects\":${VERSIONS},\"Quiet\":true}" &>/dev/null
  fi

  # Delete all delete markers
  MARKERS="$(aws s3api list-object-versions \
    --bucket "$STATE_BUCKET" \
    --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' \
    --output json 2>/dev/null || echo '[]')"
  if [[ "$MARKERS" != "[]" && "$MARKERS" != "null" && "$MARKERS" != "" ]]; then
    aws s3api delete-objects \
      --bucket "$STATE_BUCKET" \
      --delete "{\"Objects\":${MARKERS},\"Quiet\":true}" &>/dev/null
  fi

  log "Bucket emptied"
else
  log "Could not read bootstrap state bucket name — skipping manual empty"
fi

terraform destroy -auto-approve -input=false

log "All infrastructure destroyed."
