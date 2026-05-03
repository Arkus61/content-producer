from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # ── LLM ──
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # ── Supabase (Auth + DB + Storage) ──
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")

    # ── Prodamus (Russian Payment System) ──
    prodamus_api_key: str = Field(default="", alias="PRODAMUS_API_KEY")
    prodamus_secret_key: str = Field(default="", alias="PRODAMUS_SECRET_KEY")
    prodamus_base_url: str = Field(default="https://demo.payform.ru", alias="PRODAMUS_BASE_URL")
    prodamus_success_url: str = Field(default="https://localhost/payment/success", alias="PRODAMUS_SUCCESS_URL")
    prodamus_fail_url: str = Field(default="https://localhost/payment/fail", alias="PRODAMUS_FAIL_URL")
    prodamus_webhook_url: str = Field(default="https://localhost/payment/webhook", alias="PRODAMUS_WEBHOOK_URL")

    # ── Supabase Self-Hosted (Russia) ──
    supabase_russia_url: str = Field(default="", alias="SUPABASE_RUSSIA_URL")
    supabase_russia_service_key: str = Field(default="", alias="SUPABASE_RUSSIA_SERVICE_KEY")
    supabase_russia_jwt_secret: str = Field(default="", alias="SUPABASE_RUSSIA_JWT_SECRET")
    supabase_connection_timeout: float = Field(default=10.0, alias="SUPABASE_CONNECTION_TIMEOUT")
    supabase_max_retry: int = Field(default=3, alias="SUPABASE_MAX_RETRY")
    supabase_request_timeout: float = Field(default=30.0, alias="SUPABASE_REQUEST_TIMEOUT")

    # ── Server ──
    debug: bool = Field(default=False, alias="DEBUG")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    allowed_hosts: str = Field(default="*", alias="ALLOWED_HOSTS")
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # ── Social integrations ──
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    instagram_access_token: str = Field(default="", alias="INSTAGRAM_ACCESS_TOKEN")
    instagram_account_id: str = Field(default="", alias="INSTAGRAM_ACCOUNT_ID")
    default_telegram_channel: str = Field(default="", alias="DEFAULT_TELEGRAM_CHANNEL")

    # ── 152-FZ Operator Info ──
    operator_name: str = Field(default="ООО Content Producer", alias="OPERATOR_NAME")
    operator_address: str = Field(default="г. Москва, ...", alias="OPERATOR_ADDRESS")
    operator_inn: str = Field(default="", alias="OPERATOR_INN")
    operator_email: str = Field(default="privacy@content-producer.ru", alias="OPERATOR_EMAIL")
    operator_phone: str = Field(default="+7 (999) 000-00-00", alias="OPERATOR_PHONE")
    operator_dpo_email: str = Field(default="dpo@content-producer.ru", alias="DPO_EMAIL")
    operator_dpo_phone: str = Field(default="+7 (999) 000-00-01", alias="DPO_PHONE")

    # ── 152-FZ Retention & Processing ──
    default_retention_days: int = Field(default=365 * 5, alias="DEFAULT_RETENTION_DAYS")
    interview_retention_days: int = Field(default=365 * 2, alias="INTERVIEW_RETENTION_DAYS")
    transcription_retention_days: int = Field(default=365 * 1, alias="TRANSCRIPTION_RETENTION_DAYS")
    audit_retention_days: int = Field(default=365 * 3, alias="AUDIT_RETENTION_DAYS")
    consent_retention_days: int = Field(default=365 * 10, alias="CONSENT_RETENTION_DAYS")

    # ── 152-FZ Encryption ──
    enable_field_encryption: bool = Field(default=False, alias="ENABLE_FIELD_ENCRYPTION")
    encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")

    # ── 152-FZ Logging ──
    enable_audit_logging: bool = Field(default=True, alias="ENABLE_AUDIT_LOGGING")
    anonymize_audit_ips: bool = Field(default=True, alias="ANONYMIZE_AUDIT_IPS")

    # ── Consent ──
    consent_document_url: str = Field(default="/docs/consent.pdf", alias="CONSENT_DOCUMENT_URL")
    privacy_policy_url: str = Field(default="/docs/privacy-policy.pdf", alias="PRIVACY_POLICY_URL")
    minimum_consent_version: str = Field(default="1.0", alias="MINIMUM_CONSENT_VERSION")

    # ── Export & Deletion ──
    export_ttl_hours: int = Field(default=72, alias="EXPORT_TTL_HOURS")
    deletion_grace_hours: int = Field(default=72, alias="DELETION_GRACE_HOURS")


settings = Settings()
