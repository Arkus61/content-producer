"""Geo-aware DB client — retries + fallback between primary and Russia self-hosted Supabase."""
from __future__ import annotations

import logging
import asyncio
from typing import Optional, Any

from .config import settings
from .supabase_client import get_supabase_client, is_russia_available
from .db_client import SupabaseDB, _mem as _inmem

logger = logging.getLogger("content-producer")

_RETRY_DELAY = 1.0
_RETRY_MAX_DELAY = 8.0


class GeoSupabaseDB(SupabaseDB):
    """Extends SupabaseDB with geo-aware failover to Russia self-hosted instance.

    Strategy:
    1. Try primary (cloud) first
    2. If primary fails with connection error, retry up to settings.supabase_max_retry
    3. If primary completely down, transparently fail over to Russia instance
    4. If both down, fall back to in-memory store (non-persistent)
    """

    def __init__(self) -> None:
        super().__init__()
        self._primary_client = get_supabase_client("primary")
        self._russia_client = get_supabase_client("russia")
        self._in_mem = _inmem

    def _primary_available(self) -> bool:
        """Check if primary client is initialized."""
        return self._primary_client is not None and settings.supabase_url

    def _russia_available(self) -> bool:
        """Check if Russia client is initialized."""
        return self._russia_client is not None and settings.supabase_russia_url

    # ── Retry wrapper around table operations ───────────────────

    async def _execute_with_retry(
        self,
        operation: str,
        table: str,
        geo: str = "primary",
        **kwargs: Any,
    ) -> Any:
        """Execute table operation with retry + geo-failover."""
        clients: list[tuple[str, Any]] = []
        if geo == "primary" and self._primary_available():
            clients.append(("primary", self._primary_client))
        if geo != "primary_only" and self._russia_available():
            clients.append(("russia", self._russia_client))

        if not clients:
            # No Supabase configured — silently fall back to in-memory
            logger.debug("No Supabase configured, using in-memory for %s", operation)
            return None

        last_error: Optional[Exception] = None
        for client_name, client in clients:
            max_retry = settings.supabase_max_retry
            delay = _RETRY_DELAY

            for attempt in range(1, max_retry + 1):
                try:
                    return await self._dispatch_client_operation(client, operation, table, **kwargs)
                except (ConnectionError, asyncio.TimeoutError, Exception) as exc:
                    last_error = exc
                    logger.warning(
                        "%s %s attempt %d/%d failed on %s: %s",
                        operation, table, attempt, max_retry, client_name, exc,
                    )
                    if attempt < max_retry:
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, _RETRY_MAX_DELAY)
                    else:
                        logger.error("All retries exhausted on %s for %s %s", client_name, operation, table)
                        break
            # Try next client
            logger.info("Failing over from %s to next client for %s %s", client_name, operation, table)

        # All clients failed
        logger.error("All Supabase clients failed for %s %s. Last error: %s", operation, table, last_error)
        return None

    async def _dispatch_client_operation(self, client: Any, operation: str, table: str, **kwargs: Any) -> Any:
        """Dispatch to actual Supabase client (table + method call)."""
        # Minimal dispatch for common operations
        if operation == "insert":
            result = await client.table(table).insert(kwargs["data"]).execute()
            return result.data[0] if result.data else kwargs["data"]
        elif operation == "select_all":
            query = client.table(table).select("*")
            for k, v in kwargs.get("filters", {}).items():
                if v is not None:
                    query = query.eq(k, v)
            if "order" in kwargs:
                query = query.order(kwargs["order"]["column"], desc=kwargs["order"].get("desc", False))
            if "range" in kwargs:
                start, end = kwargs["range"]
                query = query.range(start, end)
            result = await query.execute()
            return result.data or []
        elif operation == "select_single":
            result = await client.table(table).select("*").eq(kwargs["field"], kwargs["value"]).single().execute()
            return result.data
        elif operation == "update":
            query = client.table(table).update(kwargs["data"])
            for k, v in kwargs.get("filters", {}).items():
                query = query.eq(k, v)
            result = await query.execute()
            return result.data[0] if result.data else kwargs["data"]
        elif operation == "delete":
            query = client.table(table).delete()
            for k, v in kwargs.get("filters", {}).items():
                query = query.eq(k, v)
            await query.execute()
            return True
        else:
            raise ValueError(f"Unknown operation: {operation}")

    # ── Override key methods to use geo-aware dispatch ───────────────────

    # Expert Cards
    async def expert_list(self, skip: int = 0, limit: int = 50, owner_user_id: Optional[str] = None):
        result = await self._execute_with_retry(
            "select_all", "expert_cards",
            filters={"owner_user_id": owner_user_id} if owner_user_id else {},
            order={"column": "created_at", "desc": True},
            range=(skip, skip + limit - 1),
        )
        if result is not None:
            return result
        return await super().expert_list(skip, limit, owner_user_id)

    async def expert_get(self, expert_id: str):
        result = await self._execute_with_retry(
            "select_single", "expert_cards",
            field="id", value=expert_id,
        )
        if result is not None:
            return result
        return await super().expert_get(expert_id)

    async def expert_insert(self, data: dict):
        result = await self._execute_with_retry(
            "insert", "expert_cards",
            data=data,
        )
        if result is not None:
            return result
        return await super().expert_insert(data)

    async def expert_update(self, expert_id: str, data: dict):
        result = await self._execute_with_retry(
            "update", "expert_cards",
            data=data,
            filters={"id": expert_id},
        )
        if result is not None:
            return result
        return await super().expert_update(expert_id, data)

    async def expert_delete(self, expert_id: str):
        result = await self._execute_with_retry(
            "delete", "expert_cards",
            filters={"id": expert_id},
        )
        if result is not None:
            return True
        return await super().expert_delete(expert_id)

    # Users
    async def user_get_by_supabase_uid(self, uid: str):
        result = await self._execute_with_retry(
            "select_all", "users",
            filters={"supabase_uid": uid},
        )
        if result is not None and result:
            return result[0]
        return await super().user_get_by_supabase_uid(uid)

    async def user_create(self, data: dict):
        result = await self._execute_with_retry("insert", "users", data=data)
        if result is not None:
            return result
        return await super().user_create(data)

    # ── Other methods fall back to parent's implementation ──
    # (which uses settings.supabase_url check and _inmem fallback)


# Global geo-aware DB instance
db_geo = GeoSupabaseDB()
