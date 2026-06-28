#!/usr/bin/env bash
# Build and push Docker images to ECR.
# Can run standalone (reads ECR URL from terraform output) or be called from
# deploy.sh with ECR_URL and ECR_GDAL_URL already set as environment variables.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "${SCRIPT_DIR}" rev-parse --short HEAD)}"
PROJECT_NAME="asterra-devops-assignment"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }

for cmd in aws docker git; do
  command -v "$cmd" &>/dev/null || die "Missing required tool: $cmd"
done

# If not provided by the caller, read from terraform output
if [[ -z "${ECR_URL:-}" ]]; then
  log "ECR_URL not set — reading from terraform output"
  ECR_URL="$(cd "${SCRIPT_DIR}/terraform" && terraform output -raw ecr_repository_url)"
fi

if [[ -z "${ECR_GDAL_URL:-}" ]]; then
  log "ECR_GDAL_URL not set — reading from terraform output"
  ECR_GDAL_URL="$(cd "${SCRIPT_DIR}/terraform" && terraform output -raw ecr_gdal_repository_url)"
fi

ECR_REGISTRY="${ECR_URL%%/*}"



log "Image tag          : ${IMAGE_TAG}"
log "ECR data-processor : ${ECR_URL}"
log "ECR gdal-service   : ${ECR_GDAL_URL}"

# ECR login
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

# data-processor
log "Building data-processor..."
docker build -t "${ECR_URL}:${IMAGE_TAG}" "${SCRIPT_DIR}/app/data-processor"
docker push "${ECR_URL}:${IMAGE_TAG}"

# gdal-service
log "Building gdal-service..."
docker build -t "${ECR_GDAL_URL}:${IMAGE_TAG}" "${SCRIPT_DIR}/app/gdal-service"
docker push "${ECR_GDAL_URL}:${IMAGE_TAG}"

# mapserver uses the public camptocamp/mapserver image — no build or push needed

log "Build complete! Tag: ${IMAGE_TAG}"
