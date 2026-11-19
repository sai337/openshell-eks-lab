# EKS for the OpenShell enterprise path: private nodes, two node groups
# (system + tainted agent-sandbox), VPC CNI with NetworkPolicy enforcement ON
# (OpenShell requires it), EBS CSI for the gateway's state volume, ECR for the
# agent image, and a monthly budget alarm.

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)
  tags = { project = "openshell-eks-lab", managed_by = "terraform", owner = var.owner }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name               = var.name
  cidr               = "10.40.0.0/16"
  azs                = local.azs
  private_subnets    = ["10.40.0.0/19", "10.40.32.0/19", "10.40.64.0/19"]
  public_subnets     = ["10.40.96.0/22", "10.40.100.0/22", "10.40.104.0/22"]
  enable_nat_gateway = true
  single_nat_gateway = true # lab cost; use one per AZ in production

  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  tags                = local.tags
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name                             = var.name
  cluster_version                          = var.kubernetes_version
  vpc_id                                   = module.vpc.vpc_id
  subnet_ids                               = module.vpc.private_subnets
  cluster_endpoint_public_access           = true # CI runner reaches the API; restrict with cidrs below
  cluster_endpoint_public_access_cidrs     = var.api_allowed_cidrs
  enable_cluster_creator_admin_permissions = true
  authentication_mode                      = "API"

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
      # OpenShell's hard requirement: egress NetworkPolicy must be enforced.
      configuration_values = jsonencode({ enableNetworkPolicy = "true" })
    }
    eks-pod-identity-agent = {}
    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.ebs_csi.arn
        service_account = "ebs-csi-controller-sa"
      }]
    }
  }

  eks_managed_node_groups = {
    system = {
      instance_types = ["m7i.large"]
      min_size       = 2
      max_size       = 3
      desired_size   = 2
      labels         = { workload = "system" }
    }
    agent_sandbox = {
      instance_types = [var.sandbox_instance_type]
      min_size       = 1
      max_size       = 4
      desired_size   = 1
      labels         = { workload = "agent-sandbox" }
      taints = {
        sandbox = { key = "agent-sandbox", value = "true", effect = "NO_SCHEDULE" }
      }
      metadata_options = {
        http_tokens                 = "required"
        http_put_response_hop_limit = 1 # pods cannot reach node IMDS credentials
      }
    }
  }

  tags = local.tags
}

data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  name               = "${var.name}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

resource "aws_ecr_repository" "agent" {
  name                 = "${var.name}/oslab-agent"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.tags
}

resource "aws_budgets_budget" "lab" {
  count        = var.budget_email == "" ? 0 : 1
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}
