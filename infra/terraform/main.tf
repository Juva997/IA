// Terraform skeleton — preencher conforme provedor (AWS/GCP/Azure)

terraform {
  required_version = ">= 1.0"
}

// Exemplo: provider AWS (descomente e ajuste se for usar AWS)
/*
provider "aws" {
  region = var.aws_region
}

module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  cluster_name    = var.cluster_name
  cluster_version = "1.27"
  subnets         = var.subnets
  vpc_id          = var.vpc_id
}
*/

// Placeholder: adicionar recursos gerenciados (Redis, RDS/Postgres, Object Storage)
