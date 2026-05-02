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

    # ── Database ──
    database_url: str = Field(default="sqlite+aiosqlite:///./content_producer.db", alias="DATABASE_URL")

    # ── Server ──
    debug: bool = Field(default=False, alias="DEBUG")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # ── Security (152-FZ) ──
    secret_key: str = Field(default="change-me-please", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    max_login_attempts: int = Field(default=5, alias="MAX_LOGIN_ATTEMPTS")
    lockout_minutes: int = Field(default=30, alias="LOCKOUT_MINUTES")

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
    enable_field_encryption: bool = Field(default=True, alias="ENABLE_FIELD_ENCRYPTION")
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
