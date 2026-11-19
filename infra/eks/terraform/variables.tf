variable "name" {
  description = "Cluster and resource name prefix"
  type        = string
  default     = "oslab"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "owner" {
  description = "Tag value for the owner of these resources"
  type        = string
  default     = "sai337"
}

variable "kubernetes_version" {
  description = "EKS version (OpenShell's minimum tested is 1.33)"
  type        = string
  default     = "1.34"
}

variable "sandbox_instance_type" {
  description = "Instance type for the tainted agent-sandbox node group"
  type        = string
  default     = "m7i.xlarge"
}

variable "api_allowed_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "budget_email" {
  description = "Email for the budget alarm (empty = no budget resource)"
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly budget limit in USD"
  type        = number
  default     = 150
}
