terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
  # Local state is fine for the create-test-destroy CI run. For a long-lived
  # cluster, add an S3 backend with locking here.
}

provider "aws" {
  region = var.region
}
