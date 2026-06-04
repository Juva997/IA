# Especificação técnica — MVP (App de aprendizado de idiomas)

Visão geral
-----------
Aplicativo móvel para prática de vocabulário e pronúncia, inspirado no Duolingo.

Objetivo do MVP
---------------
- Permitir cadastro/login de usuários.
- CRUD de vocabulário (palavra, tradução, exemplo, idioma).
- Sessões de prática simples (múltipla escolha / completar / digitar tradução).
- Playback de áudio (TTS) e envio de gravações para avaliar pronúncia (STT stub).
- Persistência de progresso e pontuação básica.

Arquitetura proposta
--------------------
- Frontend: React Native (Expo) — App móvel multiplataforma.
- Backend: FastAPI (Python) — API REST simples.
- Armazenamento: inicialmente JSON files (dev); PostgreSQL em produção.
- TTS/STT: integração opcional com Google Cloud TTS/STT ou modelos locais (Whisper/Coqui).

Modelos de dados (resumo)
-------------------------
- User: {id, username}
- VocabItem: {id, word, translation, example?, language}
- PracticeSession: {session_id, user_id, items[], answers[]}

Endpoints principais
--------------------

1) Autenticação
- POST /auth/register
  - Body: { "username": "...", "password": "..." }
  - Response: { "id": "...", "username": "..." }

- POST /auth/login
  - Body: { "username": "...", "password": "..." }
  - Response: { "token": "<session-token>" }

2) Usuário
- GET /users/me
  - Header: `Authorization: Bearer <token>`
  - Response: User

3) Vocabulário
- GET /vocab
  - Header optional
  - Response: [VocabItem]

- POST /vocab
  - Body: { word, translation, example?, language }
  - Response: VocabItem

- GET /vocab/{id}
- PUT /vocab/{id}
- DELETE /vocab/{id}

4) Sessões de prática
- POST /practice/start
  - Body: { language?: 'en', count?: 5 }
  - Response: { session_id, items: [VocabItem] }

- POST /practice/submit
  - Body: { session_id, answers: ["resposta1", ...] }
  - Response: { session_id, score, total, feedback: [...] }

5) Áudio (TTS / STT)
- POST /tts
  - Body: { text, language }
  - Response: { url: "https://..." } (MVP: placeholder or base64)

- POST /stt (multipart file)
  - Form file upload (audio)
  - Response: { transcript: "..." } (MVP: stub)

Regras de segurança e limites
----------------------------
- No MVP usar token simples (UUID) com expiração curta; migrar para JWT+refresh para produção.
- Não executar código do usuário no servidor.

Persistência
------------
- Dev: armazenamento baseado em JSON (backend/data/*.json). Fácil de auditar.
- Prod: PostgreSQL + migrations (Alembic) e bucket S3 para áudios.

Deploy (dev)
------------
- Backend: `uvicorn backend.app.main:app --reload --port 8000`
- Frontend: `expo start` (ou `npx react-native` para fluxo nativo)

Notas e próximos passos
----------------------
- Sprint inicial: scaffolding, auth, CRUD vocab, endpoints de practice.
- Sprint 2: UI de prática, gravação no app, TTS playback.
- Sprint 3: STT, feedback de pronúncia, métricas.
