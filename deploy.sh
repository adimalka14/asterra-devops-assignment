#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "${SCRIPT_DIR}" rev-parse --short HEAD)}"
PROJECT_NAME="asterra-devops-assignment"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die()  { echo "[ERROR] $*" >&2; exit 1; }
step() { echo; log "==> [$1/4] $2"; }

# ── Prerequisites ──────────────────────────────────────────────────────────────
for cmd in terraform aws docker helmfile git; do
  command -v "$cmd" &>/dev/null || die "Missing required tool: $cmd"
done

# ── 1. Bootstrap ───────────────────────────────────────────────────────────────
step 1 "Terraform bootstrap (S3 state backend + DynamoDB lock table)"
cd "${SCRIPT_DIR}/terraform/bootstrap"
terraform init -input=false
terraform apply -auto-approve -input=false

# ── 2. Main Terraform ──────────────────────────────────────────────────────────
step 2 "Terraform main (VPC, ECR, k3s, RDS, SQS, S3, IAM, Secrets Manager)"
cd "${SCRIPT_DIR}/terraform"
# -reconfigure picks up the S3 backend that bootstrap just created
terraform init -input=false -reconfigure
terraform apply -auto-approve -input=false

ECR_URL="$(terraform output -raw ecr_repository_url)"
ECR_REGISTRY="${ECR_URL%%/*}"          # 123456789.dkr.ecr.us-east-1.amazonaws.com
SQS_QUEUE_URL="$(terraform output -raw sqs_queue_url)"
S3_BUCKET_NAME="$(terraform output -raw s3_bucket_name)"

# gdal-service gets its own ECR repository (separate from data-processor)
ECR_GDAL_URL="${ECR_REGISTRY}/${PROJECT_NAME}-gdal"
if ! aws ecr describe-repositories \
      --repository-names "${PROJECT_NAME}-gdal" \
      --region "$REGION" &>/dev/null; then
  log "Creating ECR repository for gdal-service..."
  aws ecr create-repository \
    --repository-name "${PROJECT_NAME}-gdal" \
    --image-scanning-configuration scanOnPush=true \
    --region "$REGION" &>/dev/null
fi

log "ECR data-processor : ${ECR_URL}"
log "ECR gdal-service   : ${ECR_GDAL_URL}"
log "SQS queue URL      : ${SQS_QUEUE_URL}"
log "S3 bucket          : ${S3_BUCKET_NAME}"

# ── 3. Build & Push Docker images ─────────────────────────────────────────────
step 3 "Build & push Docker images (tag: ${IMAGE_TAG})"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

log "Building data-processor..."
docker build -t "${ECR_URL}:${IMAGE_TAG}" "${SCRIPT_DIR}/app/data-processor"
docker push "${ECR_URL}:${IMAGE_TAG}"

log "Building gdal-service..."
docker build -t "${ECR_GDAL_URL}:${IMAGE_TAG}" "${SCRIPT_DIR}/app/gdal-service"
docker push "${ECR_GDAL_URL}:${IMAGE_TAG}"

# mapserver uses the public camptocamp/mapserver image — no build or push needed

# ── 4. Helm deploy ─────────────────────────────────────────────────────────────
step 4 "Helmfile apply"
cd "${SCRIPT_DIR}/helm"
helmfile apply \
  --state-values-set "dataProcessorImage=${ECR_URL}" \
  --state-values-set "gdalServiceImage=${ECR_GDAL_URL}" \
  --state-values-set "imageTag=${IMAGE_TAG}" \
  --state-values-set "sqsQueueUrl=${SQS_QUEUE_URL}" \
  --state-values-set "s3BucketName=${S3_BUCKET_NAME}"

log "Deploy complete! Image tag: ${IMAGE_TAG}"
