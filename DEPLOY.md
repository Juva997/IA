# Deploy com Docker Compose

Passos rápidos para rodar a API e métricas localmente usando Docker Compose.

1. Instale Docker e Docker Compose (Docker Desktop no Windows).

2. Se estiver rodando o `ollama` localmente no host, ajuste a variável `LLM_BASE_URL` para:

```
http://host.docker.internal:11434/api/generate
```

3. Build e start:

```bash
docker compose build --no-cache
docker compose up -d
```

4. Ver logs e status:

```bash
docker compose logs -f app
docker compose ps
curl http://localhost:8000/health
```

5. Teste a API `/query`:

```bash
curl -s -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"goal":"oi"}'
```

Notas:
- O `docker-compose.yml` monta o diretório do projeto em `/app` e mapeia `./data` para persistência dos vetores/memória.
- Use variáveis de ambiente (ex.: `LLM_BASE_URL`, `LLM_TIMEOUT`, `EMBEDDINGS_VECTOR_SIZE`) para ajustar comportamento sem editar código.
- Em produção, prefira orquestradores (Kubernetes) e serviços dedicados para inferência de modelos; este compose é um ponto de partida.

## Opções adicionais incluídas

- **Mock LLM embutido**: Um serviço `local-llm` (FastAPI) foi adicionado para testes locais. Ele expõe `/api/generate`, `/api/tags` e `/health` na porta `11434`.

	Rodando com o mock LLM:

	```bash
	docker compose build --no-cache
	docker compose up -d local-llm app prometheus
	```

- **Prometheus**: um container `prometheus` foi adicionado para coletar métricas em `http://localhost:9090`.

	Abra a UI do Prometheus:

	```bash
	http://localhost:9090
	```

## Kubernetes

Manifests mínimos foram adicionados em `k8s/`. Para testar com Minikube/Kind:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

