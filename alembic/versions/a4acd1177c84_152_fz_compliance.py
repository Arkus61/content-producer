"""152-FZ compliance additions: users, consent_logs, data_export_logs, data_deletion_logs, audit_logs, and PDn fields on existing tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "a4acd1177c84"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("phone", sa.String(30), unique=True, nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="operator"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("email_verified", sa.Boolean, default=False),
        sa.Column("phone_verified", sa.Boolean, default=False),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── consent_logs ──
    op.create_table(
        "consent_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expert_id", sa.String(36), sa.ForeignKey("expert_cards.id"), nullable=False),
        sa.Column("consent_type", sa.String(50), nullable=False),
        sa.Column("consent_version", sa.String(10), default="1.0"),
        sa.Column("is_granted", sa.Boolean, default=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("document_url", sa.String(512), nullable=True),
        sa.Column("granted_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("withdraw_at", sa.DateTime, nullable=True),
    )
    op.create_index("idx_consent_expert_type", "consent_logs", ["expert_id", "consent_type"])

    # ── data_export_logs ──
    op.create_table(
        "data_export_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expert_id", sa.String(36), sa.ForeignKey("expert_cards.id"), nullable=False),
        sa.Column("export_format", sa.String(20), default="json"),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("include_transcriptions", sa.Boolean, default=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("requested_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
    )

    # ── data_deletion_logs ──
    op.create_table(
        "data_deletion_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expert_id", sa.String(36), sa.ForeignKey("expert_cards.id"), nullable=False),
        sa.Column("reason", sa.Text, default="subject_request"),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("deletion_scope", sa.String(50), default="all"),
        sa.Column("requested_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("executed_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )

    # ── audit_logs ──
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("table_name", sa.String(64), nullable=False, index=True),
        sa.Column("record_id", sa.String(36), nullable=False, index=True),
        sa.Column("action", sa.String(20), nullable=False, index=True),
        sa.Column("performed_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("details", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_audit_time", "audit_logs", ["created_at"])
    op.create_index("idx_audit_user_action", "audit_logs", ["performed_by_user_id", "action"])

    # ── expert_cards: add 152-FZ columns ──
    op.add_column("expert_cards", sa.Column("age", sa.Integer, nullable=True))
    op.add_column("expert_cards", sa.Column("card_data", sa.JSON, nullable=True, default=None))
    op.add_column("expert_cards", sa.Column("data_subject_email", sa.String(255), nullable=True))
    op.add_column("expert_cards", sa.Column("data_subject_phone", sa.String(30), nullable=True))
    op.add_column("expert_cards", sa.Column("consent_granted", sa.Boolean, default=False))
    op.add_column("expert_cards", sa.Column("consent_version", sa.String(10), default="1.0"))
    op.add_column("expert_cards", sa.Column("consent_granted_at", sa.DateTime, nullable=True))
    op.add_column("expert_cards", sa.Column("is_anonymized", sa.Boolean, default=False))
    op.add_column("expert_cards", sa.Column("retention_until", sa.DateTime, nullable=True))
    op.add_column("expert_cards", sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("idx_expert_email", "expert_cards", ["data_subject_email"])
    op.create_index("idx_expert_anon_retention", "expert_cards", ["is_anonymized", "retention_until"])

    # ── interview_sessions: add columns ──
    op.add_column("interview_sessions", sa.Column("creator_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("interview_sessions", sa.Column("retention_until", sa.DateTime, nullable=True))

    # ── transcriptions: add columns ──
    op.add_column("transcriptions", sa.Column("creator_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("transcriptions", sa.Column("retention_until", sa.DateTime, nullable=True))

    # ── content_items: add creator_user_id ──
    op.add_column("content_items", sa.Column("creator_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True))


def downgrade():
    op.drop_column("content_items", "creator_user_id")
    op.drop_column("transcriptions", "retention_until")
    op.drop_column("transcriptions", "creator_user_id")
    op.drop_column("interview_sessions", "retention_until")
    op.drop_column("interview_sessions", "creator_user_id")
    op.drop_index("idx_expert_anon_retention", table_name="expert_cards")
    op.drop_index("idx_expert_email", table_name="expert_cards")
    op.drop_column("expert_cards", "owner_user_id")
    op.drop_column("expert_cards", "retention_until")
    op.drop_column("expert_cards", "is_anonymized")
    op.drop_column("expert_cards", "consent_granted_at")
    op.drop_column("expert_cards", "consent_version")
    op.drop_column("expert_cards", "consent_granted")
    op.drop_column("expert_cards", "data_subject_phone")
    op.drop_column("expert_cards", "data_subject_email")
    op.drop_column("expert_cards", "card_data")
    op.drop_column("expert_cards", "age")

    op.drop_table("audit_logs")
    op.drop_table("data_deletion_logs")
    op.drop_table("data_export_logs")
    op.drop_table("consent_logs")
    op.drop_table("users")
