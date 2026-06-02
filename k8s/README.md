# Kubernetes manifests

Arquivos em `k8s/` para deploy mínimo do `assistente_local`.

Aplicar:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Observações:

- Os manifests usam a imagem `assistente_local:latest`. Faça `docker build -t assistente_local:latest .` e envie para seu registry ou use `kind`/`minikube` com carga local.
- A anotação `prometheus.io/scrape: "true"` expõe `metrics` para scraping no `port:8001`.
