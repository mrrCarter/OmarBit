import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg import sql

from auth import AuthenticatedUser, get_current_user
from db import get_conn
from models import FeatureFlagResponse, FeatureFlagUpdate

router = APIRouter(prefix="/api/v1", tags=["feature-flags"])

# Allowlisted columns that can be updated via the PATCH endpoint.
_ALLOWED_COLUMNS = frozenset({"enabled", "rollout_percent", "rules_json"})


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
                raise _error_envelope(request, "NOT_FOUND", "Feature flag not found", 404)

            # Build SET clause using psycopg.sql for safe composition.
            # Only allowlisted column names are used (never user input).
            set_parts: list[sql.Composable] = []
            params: list = []
            if body.enabled is not None:
                set_parts.append(sql.SQL("{} = %s").format(sql.Identifier("enabled")))
                params.append(body.enabled)
            if body.rollout_percent is not None:
                set_parts.append(sql.SQL("{} = %s").format(sql.Identifier("rollout_percent")))
                params.append(body.rollout_percent)
            if body.rules_json is not None:
                set_parts.append(sql.SQL("{} = %s").format(sql.Identifier("rules_json")))
                params.append(body.rules_json)

            if not set_parts:
                raise _error_envelope(request, "BAD_REQUEST", "No fields to update", 400)

            set_parts.append(sql.SQL("{} = now()").format(sql.Identifier("updated_at")))
            params.append(key)

            query = sql.SQL(
                "UPDATE {table} SET {sets} WHERE {col} = %s "
                "RETURNING id, key, enabled, rollout_percent, rules_json, updated_at"
            ).format(
                table=sql.Identifier("feature_flags"),
                sets=sql.SQL(", ").join(set_parts),
                col=sql.Identifier("key"),
            )
            await cur.execute(query, params)
            r = await cur.fetchone()
            await conn.commit()

            if r is None:
                raise _error_envelope(request, "NOT_FOUND", "Feature flag not found", 404)

            return {
                "id": str(r["id"]),
                "key": r["key"],
                "enabled": r["enabled"],
                "rollout_percent": r["rollout_percent"],
                "rules_json": r["rules_json"],
                "updated_at": r["updated_at"],
            }
