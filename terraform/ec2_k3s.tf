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
  # Use $(cmd) directly for command substitution — $( is NOT Terraform syntax.
  # Use $${VAR} to escape bash variable references from Terraform interpolation.
  # set -x prints every command before running — visible in get-console-output.
  user_data = <<-EOF
    #!/bin/bash
    set -ex

    echo "[INFO] user-data started"

    # ── SSM Agent ─────────────────────────────────────────────────
    dnf install -y amazon-ssm-agent || true
    systemctl enable amazon-ssm-agent || true
    systemctl start  amazon-ssm-agent || true
    systemctl status amazon-ssm-agent --no-pager || true

    # ── AWS CLI ───────────────────────────────────────────────────
    dnf install -y aws-cli

    # ── k3s ──────────────────────────────────────────────────────
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --tls-san $PUBLIC_IP" sh -

    until k3s kubectl get nodes >/dev/null 2>&1; do sleep 5; done
    echo "[INFO] k3s is ready"

    # ── ECR Authentication ────────────────────────────────────────
    REGION="${var.region}"

    # Retry STS up to 5× — IAM credentials can take a moment after boot
    for _i in 1 2 3 4 5; do
      ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text) && break
      echo "[WARN] STS attempt $_i failed, retrying in 10s..."
      sleep 10
    done

    ECR_REGISTRY="$${ACCOUNT_ID}.dkr.ecr.$${REGION}.amazonaws.com"

    if ECR_TOKEN=$(aws ecr get-login-password --region "$${REGION}"); then
      mkdir -p /etc/rancher/k3s
      printf 'configs:\n  "%s":\n    auth:\n      username: AWS\n      password: "%s"\n' \
        "$${ECR_REGISTRY}" "$${ECR_TOKEN}" > /etc/rancher/k3s/registries.yaml

      systemctl restart k3s
      until k3s kubectl get nodes >/dev/null 2>&1; do sleep 5; done
      echo "[INFO] ECR registry configured"
    else
      echo "[WARN] ECR token fetch failed — skipping registry config"
    fi

    # ── ECR Refresh Cron ──────────────────────────────────────────
    cat > /usr/local/bin/refresh-ecr.sh << 'REFRESH_SCRIPT'
    #!/bin/bash
    set -e
    REGION=$(curl -sf http://169.254.169.254/latest/meta-data/placement/region)
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REGISTRY="$${ACCOUNT_ID}.dkr.ecr.$${REGION}.amazonaws.com"
    ECR_TOKEN=$(aws ecr get-login-password --region "$${REGION}")
    mkdir -p /etc/rancher/k3s
    printf 'configs:\n  "%s":\n    auth:\n      username: AWS\n      password: "%s"\n' \
      "$${ECR_REGISTRY}" "$${ECR_TOKEN}" > /etc/rancher/k3s/registries.yaml
    systemctl restart k3s
    REFRESH_SCRIPT
    chmod +x /usr/local/bin/refresh-ecr.sh
    dnf install -y cronie || true
    systemctl enable crond || true
    systemctl start  crond || true
    mkdir -p /etc/cron.d
    echo "0 */6 * * * root /usr/local/bin/refresh-ecr.sh" > /etc/cron.d/ecr-refresh

    echo "[INFO] user-data completed successfully"
  EOF

  tags = merge(var.tags, { Name = "${var.project_name}-k3s" })
}
