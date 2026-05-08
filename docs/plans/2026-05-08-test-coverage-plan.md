# Test Coverage Plan — Payment, Social, Transcriber, Compliance, Auth, DB Client

## Design

Все тесты используют in-memory store (`_InMemoryStore`) — SupabaseDB сам переключается в in-memory режим при отсутствии `SUPABASE_URL`. Мокаем только внешние сервисы (OpenAI, YouTube, Telegram API, Prodamus).

Порядок:
1. `test_db_client.py` — CRUD для всех таблиц
2. `test_auth.py` — JWT, user creation
3. `test_compliance.py` — consent, export, deletion, audit
4. `test_payment.py` — subscription, webhook
5. `test_transcriber.py` — YouTube/upload
6. `test_social.py` — Telegram/Instagram posting

## File Structure

```
tests/
  test_db_client.py     — NEW: SupabaseDB crud tests (~25)
  test_auth.py          — NEW: auth functions (~15)
  test_compliance.py    — NEW: 152-FZ functions (~20)
  test_payment.py       — NEW: payment module (~12)
  test_social.py        — NEW: social integrations (~12)
  test_transcriber.py   — NEW: transcription (~8)
```

## Tasks

### Task 1: test_db_client.py
- Test InMemoryStore CRUD for all 9 tables
- Test SupabaseDB expert_list, expert_get, expert_insert, expert_update, expert_delete
- Test user methods
- Test consent, audit, export, deletion logs
- Test interview, transcription, content methods
- Test storage_upload and storage_get_url

### Task 2: test_auth.py
- Test decode_supabase_token with mock JWKS (RS256)
- Test decode_supabase_token with HS256 fallback
- Test decode_supabase_token failure (invalid token → None)
- Test get_user_id/email/role_from_payload
- Test get_or_create_user (create new, get existing, update stale)
- Test require_admin (raise 403)

### Task 3: test_compliance.py
- Test log_consent (insert consent + update expert)
- Test withdraw_consent
- Test request_export (creates request, triggers background)
- Test _prepare_export (builds payload, uploads to storage)
- Test request_deletion (creates request)
- Test _execute_deletion (anonymize expert + cascade delete)
- Test audit_log (insert + IP anonymization)
- Test list_audit_logs
- Test build_export_response, build_deletion_response

### Task 4: test_payment.py
- Test SubscriptionService.create_subscription
- Test SubscriptionService.get_subscription
- Test ProdamusWebhookHandler (signature validation, payment success, payment failure)
- Test ProdamusClient.create_payment_link

### Task 5: test_transcriber.py
- Test transcribe (mock OpenAI)
- Test is_youtube_url
- Test YouTube transcription path
- Test file upload transcription path

### Task 6: test_social.py
- Test SocialPublisher.publish
- Test TelegramPoster.post
- Test InstagramPoster.post
- Test preview generation
- Test PublishRequest/Response models
