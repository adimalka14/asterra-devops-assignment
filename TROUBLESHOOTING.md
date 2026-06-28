# Troubleshooting Guide

This document records the major issues encountered during the setup of the Asterra DevOps Assignment and how they were resolved.

## 1. K3s Service Failure (TLS SAN Issue)
**Symptom:** `k3s.service` failed to start on the EC2 instance, and the logs showed a TLS error when generating certificates.
**Root Cause:** The `user_data` script attempted to fetch the public IP of the EC2 instance to add it to `--tls-san`, but it was using the IMDSv1 `curl` command. However, the EC2 instance was strictly configured for IMDSv2 (`http_tokens = "required"`), causing the command to fail and return an empty string. K3s couldn't parse the empty string.
**Solution:** Updated the `user_data` script to use a proper IMDSv2 token fetch before retrieving the public IPv4 address.

## 2. Invalid Image Name & ImagePullBackOff
**Symptom:** Deployments for `data-processor` and `gdal-service` failed to roll out, showing `InvalidImageName` or `ImagePullBackOff` in Kubernetes events.
**Root Cause:** 
1. Helmfile was triggered without receiving the correct ECR Image URLs and Tags via `--state-values-set`, falling back to literal placeholders (`<account-id>.dkr...`) in `values.yaml`.
2. The infrastructure ECR repositories were created manually outside of Terraform, leading to inconsistencies.
**Solution:** 
- Moved the creation of all ECR repositories fully into Terraform (`aws_ecr_repository.gdal`).
- Modified `deploy.sh` and GitHub Actions to read the ECR repository URLs dynamically using `terraform output`.
- Ensured all variables (URLs, Tags, AWS Region) are passed explicitly to Helmfile using `--state-values-set`.

## 3. Secret "rds-secret" Not Found
**Symptom:** The `data-processor` pod failed to start with `Error: secret "rds-secret" not found`. The ExternalSecret operator reported `could not get secret data from provider`.
**Root Cause:** The `ClusterSecretStore` was configured with an `auth` block using `jwt` tokens (which is meant for IAM Roles for Service Accounts - IRSA, on AWS EKS). Since the cluster is K3s on EC2, this authentication method failed to create a client.
**Solution:** Removed the `auth` block entirely from the `ClusterSecretStore` manifest. By omitting `auth`, the AWS client defaults to using the EC2 Instance Profile associated with the underlying EC2 instance via IMDSv2, successfully pulling the RDS credentials from AWS Secrets Manager.

## 4. Helm Upgrade Locked (Another Operation in Progress)
**Symptom:** `UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress`.
**Root Cause:** An earlier `helmfile apply` command failed mid-execution, leaving the Helm release state locked.
**Solution:** Ran `helm rollback <release-name> 1` (e.g., `helm rollback data-processor 1`) to clear the pending state, then re-ran the deployment successfully.
