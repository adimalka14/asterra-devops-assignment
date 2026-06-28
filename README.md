# Asterra DevOps Assignment

## Overview
This project contains the complete infrastructure and CI/CD pipelines to deploy a microservices architecture on AWS. It uses Terraform for infrastructure provisioning, K3s for Kubernetes, Helm for deployments, and GitHub Actions for continuous integration and delivery.

The system includes three microservices:
1. **data-processor**: Processes incoming data and interacts with an RDS PostgreSQL database.
2. **gdal-service**: A geospatial processing service exposing an API.
3. **mapserver**: A standard map server for rendering maps.

## Architecture & Infrastructure

- **Compute**: A single EC2 instance (Amazon Linux 2023) running a lightweight K3s cluster.
- **Database**: AWS RDS PostgreSQL.
- **Messaging**: AWS SQS for asynchronous processing.
- **Storage**: AWS S3 for storing GeoJSON files.
- **Secrets Management**: AWS Secrets Manager, securely synchronized to Kubernetes using External-Secrets Operator (ESO).
- **Container Registry**: AWS ECR, fully managed by Terraform.

## Prerequisites
- **AWS CLI** configured with the correct permissions.
- **Terraform** (`~1.9`).
- **Helm & Helmfile**.
- **Docker**.

## How to Run Locally

### 1. Bootstrap State Backend
To store Terraform state in S3 and lock it with DynamoDB, initialize the bootstrap module:
```bash
cd terraform/bootstrap
terraform init
terraform apply
```

### 2. Provision Infrastructure
Run the main Terraform configuration to create the VPC, EC2, RDS, ECR, SQS, S3, and IAM roles:
```bash
cd terraform
terraform init
terraform apply
```

### 3. Deploy Kubernetes Resources (Helmfile)
Once the infrastructure is up, you can deploy the microservices and operators using the unified deploy script. This script automatically handles Docker builds, pushes to ECR, fetches the K3s kubeconfig via AWS SSM, and runs `helmfile apply`.
```bash
./deploy.sh
```

## CI/CD Pipelines
The project uses GitHub Actions for automation:
- **`ci.yml`**: Runs on PRs and pushes to non-main branches. It runs Python tests for the microservices and validates the Terraform code formatting and syntax.
- **`deploy-app.yml`**: Runs on pushes to the `main` branch. It runs tests, builds the Docker images, pushes them to ECR, and executes `helmfile apply` to roll out changes to the Kubernetes cluster automatically.
- **`deploy-infra.yml`**: Deploys infrastructure changes (Terraform) automatically upon merges to `main`.

## Testing the Flow
To test the full system integration (S3 -> SQS -> `data-processor` -> `gdal-service` -> RDS):

1. **Connect to the Cluster (Logs)**
   Export the Kubeconfig and tail the logs of the `data-processor` pod:
   ```bash
   export KUBECONFIG=~/test/projects/asterra-devops-assignment/.k3s-kubeconfig
   kubectl logs -l app=data-processor-data-processor -f
   ```

2. **Upload a Sample GeoJSON to S3**
   In a separate terminal, create a test file and upload it using AWS CLI:
   ```bash
   cat <<EOF > sample.geojson
   {
     "type": "FeatureCollection",
     "features": [
       {
         "type": "Feature",
         "geometry": { "type": "Point", "coordinates": [34.7818, 32.0853] },
         "properties": { "name": "Tel Aviv" }
       }
     ]
   }
   EOF

   # Replace the bucket name if your terraform state generated a different one
   aws s3 cp sample.geojson s3://asterra-devops-assignment-geojson-us-east-1/
   ```

3. **Observe the Magic**
   In the terminal running the `kubectl logs` command, you should immediately see the `data-processor` receive the SQS message, download the file from S3, validate it using `gdal-service`, and save the metadata to PostgreSQL!

### Test Results

![Test Log Output 1](public/test-result-1.png)

![Test Log Output 2](public/test-result-2.png)
