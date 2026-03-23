---
name: skill-postgres
description: Query and manage the local PostgreSQL database. Covers n8n_apps (Worksafety RAG data, embeddings, sessions) and sintaris_db (knowledge base, chat history).
---

# PostgreSQL Database Skill

## Connection

```
Host:     localhost:5432 (Docker container: local-dev-postgres-1)
User:     n8n_user
Password: N8Nzusammen2019
Databases: n8n, n8n_apps, sintaris_db
```

Connect:
```bash
docker exec -it local-dev-postgres-1 psql -U n8n_user -d n8n_apps
# or via psql if installed locally:
psql postgresql://n8n_user:N8Nzusammen2019@localhost:5432/n8n_apps
```

## Databases Overview

### `n8n_apps` — Main Worksafety data (33 tables)
All tables prefixed `safetywork_*` except nutrition bot tables.

Key tables:
| Table | Description |
|---|---|
| `safetywork_documents` | 16 Russian occupational safety regulation docs |
| `safetywork_document_chunks` | 1665 text chunks with 1536-dim OpenAI embeddings |
| `safetywork_users` | 3 users |
| `safetywork_activation_codes` | 97 codes |
| `rag_nutri_documents` | Nutrition bot documents |
| `inteligentnutritionist_bot_chat_histories` | Nutrition chat history |

pgvector enabled — supports similarity search:
```sql
SELECT chunk_text, embedding <=> '[...]'::vector AS dist
FROM safetywork_document_chunks
ORDER BY dist LIMIT 5;
```

### `sintaris_db` — Session/knowledge data (4 tables)
| Table | Description |
|---|---|
| `knowledge_base` | Knowledge entries |
| `messages` | Message log |
| `n8n_chat_histories` | N8N chat session histories |
| `sessions` | Active sessions |

### `n8n` — N8N application database
Contains N8N workflows, credentials, executions, users. Managed by N8N itself.

## Common Queries

```sql
-- Count documents and chunks
SELECT 'documents' AS t, COUNT(*) FROM safetywork_documents
UNION ALL
SELECT 'chunks', COUNT(*) FROM safetywork_document_chunks;

-- Search by document name
SELECT id, name, created_at FROM safetywork_documents WHERE name ILIKE '%охра%';

-- Recent chat sessions
SELECT session_id, MAX(created_at) AS last_active
FROM sintaris_db.public.n8n_chat_histories
GROUP BY session_id ORDER BY last_active DESC LIMIT 10;
```

## Notes

- pgvector 0.8.2 is installed
- `n8n_user` has limited privileges — use `postgres` superuser for admin tasks:
  `docker exec local-dev-postgres-1 psql -U postgres`
- VPS PostgreSQL: accessible via SSH tunnel (port 5432) — use SSH first
