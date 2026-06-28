data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "k3s" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t3.medium"
  subnet_id              = module.vpc.public_subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.k3s.id]
  iam_instance_profile   = aws_iam_instance_profile.k3s.name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  # Note: in a Terraform heredoc, $${VAR} becomes ${VAR} in the actual script.
  # All bash variables must be escaped this way; only ${var.*} are Terraform refs.
  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Install AWS CLI
    dnf install -y aws-cli

    # Install k3s
    curl -sfL https://get.k3s.io | sh -

    # Wait for k3s API to be ready
    until k3s kubectl get nodes &>/dev/null 2>&1; do sleep 5; done

    # Configure ECR authentication for containerd
    REGION="${var.region}"
    ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text)
    ECR_REGISTRY="$${ACCOUNT_ID}.dkr.ecr.$${REGION}.amazonaws.com"
    ECR_TOKEN=$$(aws ecr get-login-password --region "$${REGION}")

    mkdir -p /etc/rancher/k3s
    printf 'configs:\n  "%s":\n    auth:\n      username: AWS\n      password: "%s"\n' \
      "$${ECR_REGISTRY}" "$${ECR_TOKEN}" > /etc/rancher/k3s/registries.yaml

    # Restart k3s to apply registry credentials
    systemctl restart k3s
    until k3s kubectl get nodes &>/dev/null 2>&1; do sleep 5; done

    # Refresh ECR token every 6 hours (tokens expire after 12h)
    cat > /usr/local/bin/refresh-ecr.sh << 'REFRESH'
    #!/bin/bash
    REGION=$$(curl -sf http://169.254.169.254/latest/meta-data/placement/region)
    ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text)
    ECR_REGISTRY="$${ACCOUNT_ID}.dkr.ecr.$${REGION}.amazonaws.com"
    ECR_TOKEN=$$(aws ecr get-login-password --region "$${REGION}")
    printf 'configs:\n  "%s":\n    auth:\n      username: AWS\n      password: "%s"\n' \
      "$${ECR_REGISTRY}" "$${ECR_TOKEN}" > /etc/rancher/k3s/registries.yaml
    systemctl restart k3s
    REFRESH
    chmod +x /usr/local/bin/refresh-ecr.sh
    echo "0 */6 * * * root /usr/local/bin/refresh-ecr.sh" > /etc/cron.d/ecr-refresh
  EOF

  tags = merge(var.tags, { Name = "${var.project_name}-k3s" })
}
