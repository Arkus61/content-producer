from pydantic_settings import BaseSettings
from pydantic import Field
from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # ── LLM ──
    openai_api_key: str = ""

    # ── Database ──
    database_url: str = "sqlite+aiosqlite:///./content_producer.db"

    # ── Server ──
    debug: bool = False
    cors_origins: str = "*"
    host: str = "127.0.0.1"
    port: int = 8000

    # ── Security (152-FZ) ──
    secret_key: str = Field(default="change-me-please", description="JWT secret — 32+ bytes")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    max_login_attempts: int = 5
    lockout_minutes: int = 30

    # ── 152-FZ Operator Info ──
    operator_name: str = "ООО Content Producer"          # наименование оператора
    operator_address: str = "г. Москва, ..."               # адрес
    operator_inn: str = ""                                   # ИНН
    operator_email: str = "privacy@content-producer.ru"     # контакт privacy
    operator_phone: str = "+7 (999) 000-00-00"
    operator_dpo_email: str = "dpo@content-producer.ru"    # контакт ДПО
    operator_dpo_phone: str = "+7 (999) 000-00-01"

    # ── 152-FZ Retention & Processing ──
    default_retention_days: int = 365 * 5   # 5 лет по умолчанию (ст. 14)
    interview_retention_days: int = 365 * 2 # 2 года для интервью
    transcription_retention_days: int = 365 * 1
    audit_retention_days: int = 365 * 3
    consent_retention_days: int = 365 * 10  # согласия хранить дольше

    # ── 152-FZ Encryption ──
    enable_field_encryption: bool = True
    # Fernet key for field-level encryption of sensitive PDn
    # Generate with cryptography.fernet.Fernet.generate_key()
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")

    # ── 152-FZ Logging ──
    enable_audit_logging: bool = True
    anonymize_audit_ips: bool = True   # маскировать IP в логах

    # ── Consent ──
    consent_document_url: str = "/docs/consent.pdf"
    privacy_policy_url: str = "/docs/privacy-policy.pdf"
    minimum_consent_version: str = "1.0"

    # ── Export & Deletion ──
    export_ttl_hours: int = 72         # сколько часов доступна ссылка на экспорт
    deletion_grace_hours: int = 72     # отсрочка перед физическим удалением

    def __post_init__(self):
        if not self.secret_key or self.secret_key == "change-me-please":
            # try env fallback
            self.secret_key = os.getenv("SECRET_KEY", self.secret_key)
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.database_url:
            self.database_url = os.getenv("DATABASE_URL", self.database_url)
        self.cors_origins = os.getenv("CORS_ORIGINS", self.cors_origins)
        self.debug = os.getenv("DEBUG", str(self.debug)).lower() == "true"
        if not self.encryption_key:
            self.encryption_key = os.getenv("ENCRYPTION_KEY", "")
        self.enable_field_encryption = os.getenv("ENABLE_ENCRYPTION", str(self.enable_field_encryption)).lower() == "true"


settings = Settings()
