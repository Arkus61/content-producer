# Content Producer — Адаптация под 152-ФЗ

## Шаги по настройке

### 1. Переменные окружения (`.env`)

Добавьте в `.env`:

```env
# База (PostgreSQL рекомендуется для продакшена)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/content_producer

# JWT
SECRET_KEY=сгенерируйте-через-fernet

# Шифрование полей ПДн
ENCRYPTION_KEY=сгенерируйте-через-Fernet.generate_key()

# Оператор (заполнить обязательно!)
OPERATOR_NAME=ООО Content Producer
OPERATOR_ADDRESS=г. Москва, ...
OPERATOR_INN=7700000000
OPERATOR_EMAIL=privacy@content-producer.ru
OPERATOR_PHONE=+7 (999) 000-00-00
DPO_EMAIL=dpo@content-producer.ru
DPO_PHONE=+7 (999) 000-00-01
```

### 2. Генерация ключей

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Значение — в `SECRET_KEY` и `ENCRYPTION_KEY`.

### 3. Миграции

```bash
alembic upgrade head
```

### 4. Регистрация первого администратора

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@company.ru","password":"StrongPass123","full_name":"Администратор","role":"admin"}'
```

### 5. Регистрация первого субъекта ПДн (эксперта) с согласием

```bash
curl -X POST http://localhost:8000/api/experts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Иван Иванов",
    "email": "ivan@example.com",
    "consent_granted": true,
    "expertise": ["маркетинг"],
    "city": "Москва"
  }'
```

### 6. Управление правами субъекта ПДн

**Получить копию ПДн (ст. 14.1 152-ФЗ):**
```bash
curl -X POST http://localhost:8000/api/experts/{expert_id}/export \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"export_format":"json","include_transcriptions":true}'
```

**Отозвать согласие (ст. 9 152-ФЗ):**
```bash
curl -X DELETE http://localhost:8000/api/experts/{expert_id}/consent/processing \
  -H "Authorization: Bearer $TOKEN"
```

**Запросить удаление (ст. 14 152-ФЗ):**
```bash
curl -X POST http://localhost:8000/api/experts/{expert_id}/delete \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"deletion_scope":"all","reason":"subject_request"}'
```

### 7. Аудит (админи-панель)

```bash
curl http://localhost:8000/api/audit?limit=100 \
  -H "Authorization: Bearer $TOKEN"
```

### 8. Публичная информация об операторе

```bash
curl http://localhost:8000/api/info/operator
```

---

## Структура новых таблиц

- **users** — операторы системы (не субъекты ПДн)
- **consent_logs** — журнал согласий (ст. 9)
- **data_export_logs** — запросы на копии (ст. 14.1)
- **data_deletion_logs** — запросы на удаление (ст. 14)
- **audit_logs** — журнал операций с ПДн (ст. 18.1)

Модели расширены полями:
- `data_subject_email`, `data_subject_phone` — контакты субъекта
- `consent_granted`, `consent_version`, `consent_granted_at`
- `is_anonymized` — флаг анонимизации
- `retention_until` — дата удаления (автоматический retention)
- `owner_user_id` — кто создал запись (ответственность)
- `creator_user_id` — аудит на interview/transcription/content
- `card_data` — полный JSON дамп карточки для экспорта
