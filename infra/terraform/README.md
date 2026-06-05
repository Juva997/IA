# Infra Terraform — instruções iniciais

Este diretório contém um esqueleto Terraform para provisionar infra (cluster k8s,
serviços gerenciados). O `main.tf` é um placeholder; adapte para seu provedor:

- AWS: configurar provider `aws`, módulos EKS e recursos gerenciados (Elasticache, RDS).
- GCP: provider `google` e GKE.
- Azure: provider `azurerm` e AKS.

Passos recomendados:
1. Criar state backend (S3/GCS/Azure storage).
2. Preencher variáveis (VPC, subnets, nodegroups).
3. Aplicar infra em staging antes de produção.
