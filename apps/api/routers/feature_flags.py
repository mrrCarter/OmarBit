import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import AuthenticatedUser, get_current_user
from db import get_conn
from models import FeatureFlagResponse, FeatureFlagUpdate

router = APIRouter(prefix="/api/v1", tags=["feature-flags"])


def _error_envelope(request: Request, code: str, message: str, status: int) -> HTTPException:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return HTTPException(
        status_code=status,
        detail={
            "error": {"code": code, "message": message},
            "requestId": request_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )


@router.get("/feature-flags", response_model=list[FeatureFlagResponse])
async def list_feature_flags() -> list[dict]:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, key, enabled, rollout_percent, rules_json, updated_at "
                "FROM feature_flags ORDER BY key"
            )
            rows = await cur.fetchall()
            return [
                {
                    "id": str(r["id"]),
                    "key": r["key"],
                    "enabled": r["enabled"],
                    "rollout_percent": r["rollout_percent"],
                    "rules_json": r["rules_json"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]


@router.patch("/admin/feature-flags/{key}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    key: str,
    body: FeatureFlagUpdate,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    async with get_conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM feature_flags WHERE key = %s", (key,))
            row = await cur.fetchone()
            if not row:
                raise _error_envelope(request, "NOT_FOUND", f"Feature flag '{key}' not found", 404)

            updates = []
            params: list = []
            if body.enabled is not None:
                updates.append("enabled = %s")
                params.append(body.enabled)
            if body.rollout_percent is not None:
                updates.append("rollout_percent = %s")
                params.append(body.rollout_percent)
            if body.rules_json is not None:
                updates.append("rules_json = %s")
                params.append(body.rules_json)

            if not updates:
                raise _error_envelope(request, "BAD_REQUEST", "No fields to update", 400)

            updates.append("updated_at = now()")
            params.append(key)

            set_clause = ", ".join(updates)
            query = (
                f"UPDATE feature_flags SET {set_clause} WHERE key = %s "
                "RETURNING id, key, enabled, rollout_percent, rules_json, updated_at"
            )
            await cur.execute(query, params)
            r = await cur.fetchone()
            await conn.commit()

            if r is None:
                raise _error_envelope(request, "NOT_FOUND", f"Feature flag '{key}' not found", 404)

            return {
                "id": str(r["id"]),
                "key": r["key"],
                "enabled": r["enabled"],
                "rollout_percent": r["rollout_percent"],
                "rules_json": r["rules_json"],
                "updated_at": r["updated_at"],
            }
