Playbook: Rotação de chaves e credenciais

1) AWS IAM access keys
- Use console/CLI to identify the key(s) to rotate.
- Create a new key + update services/CI to use the new key.
- Revoke the old key only after confirming services use the new key.
- Example CLI:

```bash
aws iam create-access-key --user-name my-service-account
# update deployment secrets/store
aws iam delete-access-key --user-name my-service-account --access-key-id OLDKEY
```

2) OpenAI / LLM provider API keys
- Generate a new API key at provider portal.
- Update environment variables / secrets manager used by the service.
- Revoke the old key.

3) Database credentials
- Create a new DB user or rotate password for existing user.
- Deploy update to services with new credentials and restart.
- Revoke or remove old credentials.

4) CI / Deployment secrets
- Update GitHub/GitLab/CI secret store.
- For automated pipelines, ensure no plaintext credentials exist in pipeline logs or configs.

5) After rotation
- Run integration smoke tests to validate.
- Update docs/ops runbook with new secret locations.
- Perform history-rewrite (git-filter-repo) if secrets were committed, following `scripts/prepare_git_filter_repo.md`.

6) Evidence and audit
- Keep a secure record of rotated keys (not in repo) and actions taken.
- Notify stakeholders and rotate keys in other dependent systems if needed.
