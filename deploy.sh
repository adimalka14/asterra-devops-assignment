#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "${SCRIPT_DIR}" rev-parse --short HEAD)}"
PROJECT_NAME="asterra-devops-assignment"
K3S_KUBECONFIG="${SCRIPT_DIR}/.k3s-kubeconfig"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die()  { echo "[ERROR] $*" >&2; exit 1; }
step() { echo; log "==> [$1/4] $2"; }

# ── Prerequisites ──────────────────────────────────────────────────────────────
for cmd in terraform aws helmfile git; do
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
terraform init -input=false -reconfigure
terraform apply -auto-approve -input=false

ECR_URL="$(terraform output -raw ecr_repository_url)"
ECR_REGISTRY="${ECR_URL%%/*}"
ECR_GDAL_URL="${ECR_REGISTRY}/${PROJECT_NAME}-gdal"
SQS_QUEUE_URL="$(terraform output -raw sqs_queue_url)"
S3_BUCKET_NAME="$(terraform output -raw s3_bucket_name)"
K3S_IP="$(terraform output -raw k3s_public_ip)"
K3S_INSTANCE_ID="$(terraform output -raw k3s_instance_id)"

log "ECR data-processor : ${ECR_URL}"
log "ECR gdal-service   : ${ECR_GDAL_URL}"
log "SQS queue URL      : ${SQS_QUEUE_URL}"
log "S3 bucket          : ${S3_BUCKET_NAME}"
log "k3s instance       : ${K3S_INSTANCE_ID} (${K3S_IP})"

# ── 3. Kubeconfig ──────────────────────────────────────────────────────────────
step 3 "Fetch kubeconfig from k3s instance via SSM"

log "Waiting for SSM agent to come online..."
until aws ssm describe-instance-information \
      --filters "Key=InstanceIds,Values=${K3S_INSTANCE_ID}" \
      --query 'InstanceInformationList[0].PingStatus' \
      --output text --region "$REGION" 2>/dev/null | grep -q "^Online$"; do
  sleep 10
done
log "SSM agent online"

log "Waiting for k3s to finish initializing (may take a few minutes)..."
while true; do
  CMD_ID="$(aws ssm send-command \
    --instance-ids "$K3S_INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["test -f /etc/rancher/k3s/k3s.yaml && echo ready || echo not-ready"]' \
    --region "$REGION" \
    --query 'Command.CommandId' --output text)"
  sleep 5
  OUT="$(aws ssm get-command-invocation \
    --command-id "$CMD_ID" --instance-id "$K3S_INSTANCE_ID" \
    --region "$REGION" \
    --query 'StandardOutputContent' --output text 2>/dev/null | tr -d '[:space:]')"
  [[ "$OUT" == "ready" ]] && break
  log "k3s not ready yet, retrying in 20s..."
  sleep 20
done
log "k3s ready"

CMD_ID="$(aws ssm send-command \
  --instance-ids "$K3S_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cat /etc/rancher/k3s/k3s.yaml"]' \
  --region "$REGION" \
  --query 'Command.CommandId' --output text)"
sleep 5
aws ssm get-command-invocation \
  --command-id "$CMD_ID" --instance-id "$K3S_INSTANCE_ID" \
  --region "$REGION" \
  --query 'StandardOutputContent' --output text \
  | sed "s|127.0.0.1|${K3S_IP}|g" > "$K3S_KUBECONFIG"
chmod 600 "$K3S_KUBECONFIG"
export KUBECONFIG="$K3S_KUBECONFIG"
log "Kubeconfig ready: https://${K3S_IP}:6443"

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
