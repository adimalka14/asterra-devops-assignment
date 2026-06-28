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

  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Install k3s
    curl -sfL https://get.k3s.io | sh -

    # Install AWS CLI
    dnf install -y aws-cli

    # Configure kubeconfig for root
    mkdir -p /root/.kube
    cp /etc/rancher/k3s/k3s.yaml /root/.kube/config

    # ECR login
    aws ecr get-login-password --region ${var.region} | \
      k3s ctr images pull \
      $(aws ecr describe-repositories \
        --repository-names ${var.project_name} \
        --query 'repositories[0].repositoryUri' \
        --output text)
  EOF

  tags = merge(var.tags, { Name = "${var.project_name}-k3s" })
}