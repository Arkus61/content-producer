"""152-FZ compliance services: consent, export, deletion, audit, encryption, retention."""
import json
import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from uuid import uuid4
from cryptography.fernet import Fernet
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db.models import (
    ExpertCardModel, InterviewSessionModel, TranscriptionModel,
    ConsentLog, DataExportLog, DataDeletionLog, AuditLog,
)


# ── Encryption Service ───────────────────────────────────

class EncryptionService:
    def __init__(self, key: Optional[str] = None):
        self.key = key or settings.encryption_key or ""
        if self.key and len(self.key) != 44:
            # Generate a key if not valid Fernet key (44 chars)
            try:
                self._fernet = Fernet(self.key.encode())
            except Exception:
                self._fernet = None
        else:
            self._fernet = None

    def is_available(self) -> bool:
        return self._fernet is not None and settings.enable_field_encryption

    def encrypt(self, raw: str) -> str:
        if not self.is_available() or not raw:
            return raw
        return self._fernet.encrypt(raw.encode()).decode()

    def decrypt(self, cipher: str) -> str:
        if not self.is_available() or not cipher:
            return cipher
        return self._fernet.decrypt(cipher.encode()).decode()

    def mask(self, raw: str, visible_start: int = 2, visible_end: int = 2) -> str:
        """Partial masking for logs/displays: +7-9XX-XXX-XX-45."""
        if len(raw) <= visible_start + visible_end:
            return "*" * len(raw)
        return raw[:visible_start] + "*" * (len(raw) - visible_start - visible_end) + raw[-visible_end:]

encryption_service = EncryptionService()


# ── Consent Service ──────────────────────────────────────

class ConsentService:
    @staticmethod
    async def log_consent(
        session: AsyncSession,
        expert_id: str,
        consent_type: str,
        is_granted: bool,
        consent_version: str = "1.0",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ConsentLog:
        log = ConsentLog(
            id=str(uuid4()),
            expert_id=expert_id,
            consent_type=consent_type,
            is_granted=is_granted,
            consent_version=consent_version,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(log)

        # Also update the master record
        if is_granted:
            await session.execute(
                update(ExpertCardModel)
                .where(ExpertCardModel.id == expert_id)
                .values(
                    consent_granted=True,
                    consent_version=consent_version,
                    consent_granted_at=datetime.now(timezone.utc),
                )
            )
        await session.commit()
        return log

    @staticmethod
    async def check_consent(session: AsyncSession, expert_id: str, consent_type: str = "processing") -> bool:
        result = await session.execute(
            select(ConsentLog)
            .where(
                ConsentLog.expert_id == expert_id,
                ConsentLog.consent_type == consent_type,
                ConsentLog.is_granted == True,
            )
            .order_by(ConsentLog.granted_at.desc())
        )
        latest = result.scalars().first()
        return latest is not None

    @staticmethod
    async def withdraw_consent(
        session: AsyncSession,
        expert_id: str,
        consent_type: str = "processing",
        ip_address: Optional[str] = None,
    ) -> None:
        await session.execute(
            update(ConsentLog)
            .where(
                ConsentLog.expert_id == expert_id,
                ConsentLog.consent_type == consent_type,
            )
            .values(withdraw_at=datetime.now(timezone.utc))
        )
        await session.execute(
            update(ExpertCardModel)
            .where(ExpertCardModel.id == expert_id)
            .values(consent_granted=False)
        )
        await session.commit()

consent_service = ConsentService()


# ── Data Export Service ──────────────────────────────────

class DataExportService:
    @staticmethod
    async def request_export(
        session: AsyncSession,
        expert_id: str,
        export_format: str = "json",
        include_transcriptions: bool = True,
    ) -> str:
        request_id = str(uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=settings.export_ttl_hours)
        log = DataExportLog(
            id=request_id,
            expert_id=expert_id,
            export_format=export_format,
            include_transcriptions=include_transcriptions,
            status="processing",
            expires_at=expires,
        )
        session.add(log)
        await session.commit()

        # background: prepare file
        asyncio.create_task(_prepare_export(request_id, expert_id, export_format, include_transcriptions))
        return request_id

    @staticmethod
    async def get_export_status(session: AsyncSession, request_id: str) -> Optional[dict]:
        result = await session.execute(select(DataExportLog).where(DataExportLog.id == request_id))
        log = result.scalar_one_or_none()
        if not log:
            return None
        return {
            "request_id": log.id,
            "status": log.status,
            "file_url": log.file_path,
            "expires_at": log.expires_at,
            "completed_at": log.completed_at,
        }


async def _prepare_export(request_id: str, expert_id: str, export_format: str, include_transcriptions: bool):
    """Background task to assemble and write export file."""
    from .db.engine import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(select(ExpertCardModel).where(ExpertCardModel.id == expert_id))
        expert = result.scalar_one_or_none()
        if not expert:
            await session.execute(
                update(DataExportLog)
                .where(DataExportLog.id == request_id)
                .values(status="error")
            )
            await session.commit()
            return

        # Build export payload
        data = {
            "operator_name": settings.operator_name,
            "operator_address": settings.operator_address,
            "operator_inn": settings.operator_inn,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "expert": {
                "id": expert.id,
                "name": expert.name,
                "nickname": expert.nickname,
                "age": expert.age,
                "city": expert.city,
                "profession": expert.profession,
                "email": expert.data_subject_email,
                "phone": expert.data_subject_phone,
                "expertise": expert.expertise,
                "uvp": expert.uvp,
                "tone": expert.tone_style,
                "stories": expert.stories,
                "achievements": expert.achievements,
            },
            "consents": [],
        }
        consents = await session.execute(select(ConsentLog).where(ConsentLog.expert_id == expert_id))
        for c in consents.scalars().all():
            data["consents"].append({
                "type": c.consent_type,
                "version": c.consent_version,
                "granted": c.is_granted,
                "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                "withdrawn_at": c.withdraw_at.isoformat() if c.withdraw_at else None,
            })

        if include_transcriptions:
            trans = await session.execute(select(TranscriptionModel).where(TranscriptionModel.expert_id == expert_id))
            data["transcriptions"] = [
                {"id": t.id, "source_url": t.source_url, "text": t.text}
                for t in trans.scalars().all()
            ]

        # Write file
        exports_dir = "exports"
        os.makedirs(exports_dir, exist_ok=True)
        file_path = os.path.join(exports_dir, f"export_{request_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        await session.execute(
            update(DataExportLog)
            .where(DataExportLog.id == request_id)
            .values(
                status="ready",
                file_path=file_path,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


# ── Data Deletion Service ────────────────────────────────

class DataDeletionService:
    @staticmethod
    async def request_deletion(
        session: AsyncSession,
        expert_id: str,
        reason: str = "subject_request",
        deletion_scope: str = "all",
        requested_by_user_id: Optional[str] = None,
    ) -> str:
        request_id = str(uuid4())
        log = DataDeletionLog(
            id=request_id,
            expert_id=expert_id,
            reason=reason,
            deletion_scope=deletion_scope,
            status="pending",
        )
        session.add(log)
        await session.commit()

        # background: do deletion after grace period
        asyncio.create_task(_execute_deletion(request_id, expert_id, deletion_scope, requested_by_user_id))
        return request_id

    @staticmethod
    async def get_deletion_status(session: AsyncSession, request_id: str) -> Optional[dict]:
        result = await session.execute(select(DataDeletionLog).where(DataDeletionLog.id == request_id))
        log = result.scalar_one_or_none()
        if not log:
            return None
        return {
            "request_id": log.id,
            "status": log.status,
            "scope": log.deletion_scope,
            "requested_at": log.requested_at,
            "completed_at": log.completed_at,
        }


async def _execute_deletion(request_id: str, expert_id: str, scope: str, user_id: Optional[str] = None):
    """Background task: anonymize or erase after grace period."""
    from .db.engine import async_session_factory
    await asyncio.sleep(settings.deletion_grace_hours * 3600)  # grace period

    async with async_session_factory() as session:
        try:
            if scope == "all":
                # Anonymize expert card
                await session.execute(
                    update(ExpertCardModel)
                    .where(ExpertCardModel.id == expert_id)
                    .values(
                        name="[Удалён]",
                        nickname="",
                        age=None,
                        city="",
                        profession="",
                        data_subject_email=None,
                        data_subject_phone=None,
                        is_anonymized=True,
                        uvp="",
                        expertise="[]",
                        stories="[]",
                        achievements="[]",
                        audience_pains="[]",
                        strategy_goals="[]",
                        strategy_platforms="[]",
                    )
                )
                # Delete linked entities
                await session.execute(delete(InterviewSessionModel).where(InterviewSessionModel.expert_id == expert_id))
                await session.execute(delete(TranscriptionModel).where(TranscriptionModel.expert_id == expert_id))
                # Content items — keep but unlink  (or delete based on scope)
                await session.execute(
                    update(InterviewSessionModel)
                    .where(InterviewSessionModel.expert_id == expert_id)
                    .values(expert_id=None)
                )

            elif scope == "interview":
                await session.execute(delete(InterviewSessionModel).where(InterviewSessionModel.expert_id == expert_id))

            elif scope == "transcriptions":
                await session.execute(delete(TranscriptionModel).where(TranscriptionModel.expert_id == expert_id))

            await session.execute(
                update(DataDeletionLog)
                .where(DataDeletionLog.id == request_id)
                .values(status="completed", completed_at=datetime.now(timezone.utc), executed_by_user_id=user_id)
            )
            await session.commit()
        except Exception as e:
            await session.execute(
                update(DataDeletionLog)
                .where(DataDeletionLog.id == request_id)
                .values(status="failed")
            )
            await session.commit()
            raise


# ── Audit Service ────────────────────────────────────────

class AuditService:
    @staticmethod
    async def log(
        session: AsyncSession,
        table_name: str,
        record_id: str,
        action: str,
        performed_by_user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditLog:
        if ip_address and settings.anonymize_audit_ips:
            parts = ip_address.split(".")
            if len(parts) == 4:
                ip_address = f"{parts[0]}.{parts[1]}.*.*"
        log = AuditLog(
            table_name=table_name,
            record_id=record_id,
            action=action,
            performed_by_user_id=performed_by_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
        session.add(log)
        await session.commit()
        return log

    @staticmethod
    async def list_logs(
        session: AsyncSession,
        table_name: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ):
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if table_name:
            query = query.where(AuditLog.table_name == table_name)
        if action:
            query = query.where(AuditLog.action == action)
        if user_id:
            query = query.where(AuditLog.performed_by_user_id == user_id)
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def cleanup_old(session: AsyncSession) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_retention_days)
        result = await session.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        await session.commit()
        return result.rowcount

audit_service = AuditService()


# ── Retention Service ──────────────────────────────────────

class RetentionService:
    @staticmethod
    def calc_retention(created_at: datetime, days: int) -> datetime:
        return created_at + timedelta(days=days)

    @staticmethod
    async def enforce_retention(session: AsyncSession) -> dict:
        now = datetime.now(timezone.utc)
        deleted = {"interview_sessions": 0, "transcriptions": 0, "audit_logs": 0}

        # Interview sessions
        cutoff_i = now - timedelta(days=settings.interview_retention_days)
        result = await session.execute(
            delete(InterviewSessionModel).where(
                InterviewSessionModel.retention_until < now
                if InterviewSessionModel.retention_until is not None
                else InterviewSessionModel.created_at < cutoff_i
            )
        )
        deleted["interview_sessions"] = result.rowcount or 0

        # Transcriptions
        cutoff_t = now - timedelta(days=settings.transcription_retention_days)
        result = await session.execute(
            delete(TranscriptionModel).where(
                TranscriptionModel.retention_until < now
                if TranscriptionModel.retention_until is not None
                else TranscriptionModel.created_at < cutoff_t
            )
        )
        deleted["transcriptions"] = result.rowcount or 0

        # Audit logs
        deleted["audit_logs"] = await audit_service.cleanup_old(session)

        await session.commit()
        return deleted


# Public instances
consent_service = ConsentService()
data_export_service = DataExportService()
data_deletion_service = DataDeletionService()
retention_service = RetentionService()
