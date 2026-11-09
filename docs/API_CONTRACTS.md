# API contracts (v1)

Base URL for applications: `https://ai-api.quantaedge.in`.
Authentication: `X-API-Key: <service credential>`; credentials are issued to server-side callers only.

## POST /v1/chat/completions

OpenAI-style non-streaming chat request with a QuantaEdge logical profile name.

```json
{
  "model": "qwen3.5-teacher-2b",
  "task": "general_chat",
  "messages": [{"role": "user", "content": "Explain evaporation."}]
}
```

## POST /v1/embeddings

```json
{
  "model": "qwen3-embedding-0.6b",
  "input": ["measurement", "standard unit"]
}
```

Response includes the logical profile, 1,024-dimensional vectors and indexes.

## POST /v1/learning/answers

```json
{
  "learner_ref": "opaque-learner-id",
  "institution_ref": "opaque-institution-id",
  "question": "Why do we need standard units?",
  "curriculum": "NCERT",
  "course_id": "CLASS_6",
  "subject_id": "SCIENCE",
  "chapter_id": "CH_01",
  "language": "en",
  "allow_general_knowledge": false
}
```

Strict mode returns `status: insufficient_evidence` and no invented citations when relevant authorised material is absent. Source references include book title, edition, curriculum, course, subject, chapter and page where available.

## POST /v1/knowledge/documents

Multipart upload, requiring `knowledge:write` scope. Metadata includes optional institution_ref, curriculum, course, subject, book title, edition, language and `rights_status`. The current technical allowlist is `permission_granted`, `owned_content`, or `public_domain`, plus a named attestation. This is not legal verification; legal approval must occur before ingestion.

## Error conventions

- `401`: missing/invalid service key.
- `403`: service key lacks required scope or source rights are not cleared.
- `413`: upload exceeds configured size.
- `415`: unsupported file type.
- `422`: invalid request.
- `503`: model provider or queue unavailable.

Request ID is returned in `X-Request-ID` for support and tracing.


## Learner memory

Memory operations are server-to-server only and require institution_ref + learner_ref. The application backend must confirm the learner's applicable consent and pass a consent_ref when creating a memory. The AI service never silently persists generated memories.

- `POST /v1/memories` — `memory:write`; accepts learning preference, mastered concept, misconception, revision need or learning goal. Requires `consent_confirmed: true` and `consent_ref`.
- `GET /v1/memories?institution_ref=...&learner_ref=...` — `memory:read`; returns active memories within that institution/learner scope.
- `DELETE /v1/memories/{id}?institution_ref=...&learner_ref=...` — `memory:delete`; permanently deletes the matching record.

Memory is used only to personalise teaching, not as textbook evidence. QuantaEdge remains responsible for consent UX, identity verification, data-subject requests and the official learner record.
