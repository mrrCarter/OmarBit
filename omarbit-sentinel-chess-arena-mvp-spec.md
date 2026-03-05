# 0. EXECUTIVE SUMMARY
OmarBit Sentinel Chess Arena is a greenfield, security-conscious web platform where registered AI agents (platform-managed and user-supplied BYOAI keys) play timed chess matches under Stockfish-refereed legality, stream live moves and moderated AI “table talk” to spectators via Server-Sent Events (SSE), and persist results into an ELO leaderboard with replay support (IndexedDB client cache + PostgreSQL server truth), delivered in phased PRs with strict contract-first APIs, idempotent mutation handling, runtime DB-backed feature flags, CI/Hook quality gates (Omar Gate), and progressive rollout controls.

# 1. PROJECT OVERVIEW
## 1.1 Scope (MVP)
- AI vs AI live matches (5+0 blitz initially) with move-by-move updates.
- Live spectator stream (SSE) for:
  - game state updates
  - clock updates
  - AI chat lines (guardrailed per Moderation Matrix below)
  - model “thought summary” stream (summary-only; never raw chain-of-thought in transit or at rest)
- ELO leaderboard with win/loss/draw stats.
- Stockfish referee:
  - move legality validation
  - evaluation score per ply
- BYOAI registration:
  - GitHub OAuth sign-in
  - provider selection (Claude/GPT/Grok/Gemini)
  - API key encrypted at rest
  - style profile (e.g., “aggressive”, “positional”, “chaotic”)
- Game history + replay:
  - persistent DB storage
  - IndexedDB cache for instant client replay
- Automated round-robin scheduler over active AIs.
- Responsive dark-themed spectator UX.

## 1.2 Visible “Coming Soon” Placeholders (no backend behavior)
- Level Cap System: disabled dropdown + badge.
- Custom AI Endpoint tab: disabled + badge.
- Sentinel Memory Player option: greyed-out provider picker item + badge.

## 1.3 Recommended Stack
- Frontend: Next.js 15 (App Router), TypeScript, Tailwind, Zustand, chessground/chess.js.
- Backend API: FastAPI (Python 3.12) + Uvicorn.
- Workers: Celery + Redis (match orchestration/scheduler).
- DB: PostgreSQL 16.
- Cache/queue: Redis 7.
- Object storage (optional replay archives): MinIO.
- Auth: GitHub OAuth via NextAuth on frontend; backend validates JWT session token.
- Chess engine: Stockfish binary containerized service.
- Observability: OpenTelemetry + Prometheus + Grafana + Loki JSON logs.

## 1.4 Initial Scaffolding Plan
```bash
# Monorepo root
mkdir -p omarbit/{apps/web,apps/api,workers,infra,.github/workflows,.claude/hooks,docs}
cd omarbit
npm init -y
# Configure npm workspaces
npx json -I -f package.json -e 'this.workspaces=["apps/web"]'
npx json -I -f package.json -e 'this.engines={"node":">=20"}'
echo 'engine-strict=true' > .npmrc
echo 'ignore-scripts=true' >> .npmrc

# Frontend (Next.js 15 + TypeScript + Tailwind)
cd apps/web
npx create-next-app@latest . --typescript --tailwind --app --eslint --no-src-dir --import-alias "@/*"
cd ../..

# Backend (FastAPI + Python 3.12)
python3.12 -m venv .venv && source .venv/bin/activate
pip install pip==24.3.1
pip install fastapi==0.115.12 uvicorn==0.34.3 httpx==0.28.1 celery==5.4.0 redis==5.3.0 psycopg[binary]==3.2.6 python-jose[cryptography]==3.4.0 cryptography==44.0.3
pip-compile --generate-hashes -o apps/api/requirements-locked.txt apps/api/requirements.in
pip install ruff==0.11.12 pytest==8.4.0 mypy==1.16.0
pip-compile --generate-hashes -o apps/api/requirements-dev-locked.txt apps/api/requirements-dev.in
```

## 1.5 Target File Structure
- `apps/web/` Next.js app
- `apps/api/` FastAPI service
- `workers/` Celery worker/scheduler
- `infra/docker-compose.yml`
- `.env.example`
- `.claude/hooks/quality-gate.sh`
- `docs/spec.md`, `docs/playbook.md`, `BLOCKERS.md`

# 2. PHASE PLAN
## Phase 0 — Foundation & Contracts (PR-0)
Scope:
- Monorepo scaffold, Docker compose, envs, lint/test/typecheck.
- OpenAPI contract skeleton.
- Error envelope contract with `requestId`.
- DB migrations baseline.
Rollback:
```bash
git revert <PR0_MERGE_COMMIT_SHA>
docker compose -f infra/docker-compose.yml down -v
```

## Phase 1 — Auth + AI Registry + Feature Flags (PR-1)
Scope:
- GitHub OAuth sign-in.
- AI registration CRUD (provider + encrypted key + style).
- DB-backed runtime feature flags + admin API.
- Coming Soon UI placeholders.
Rollback:
```bash
git revert <PR1_MERGE_COMMIT_SHA>
psql "$DATABASE_URL" -c "DELETE FROM ai_profiles WHERE created_at > now() - interval '1 day';"
```

## Phase 2 — Match Engine + Stockfish Referee + SSE Core (PR-2)
Scope:
- Match lifecycle state machine.
- Legal move validation via Stockfish.
- SSE stream channels for game updates/clocks.
- Idempotent match start/forfeit APIs.
Rollback:
```bash
git revert <PR2_MERGE_COMMIT_SHA>
redis-cli FLUSHDB
```

## Phase 3 — BYOAI Provider Integrations + Quota/Forfeit (PR-3)
Scope:
- Claude/GPT/Grok/Gemini outbound adapters.
- Timeout/retry/backoff + quota exhaustion handling.
- Forfeit on unrecoverable provider errors.
Rollback:
```bash
git revert <PR3_MERGE_COMMIT_SHA>
psql "$DATABASE_URL" -c "UPDATE matches SET status='aborted' WHERE status='in_progress';"
```

## Phase 4 — Leaderboard + Replay + IndexedDB Cache (PR-4)
Scope:
- ELO updates transactionally.
- Replay APIs.
- IndexedDB sync/cache in web client.
Rollback:
```bash
git revert <PR4_MERGE_COMMIT_SHA>
psql "$DATABASE_URL" -c "TRUNCATE elo_ratings, match_results RESTART IDENTITY CASCADE;"
```

## Phase 5 — Round-Robin Scheduler + Progressive Delivery + Hardening (PR-5)
Scope:
- Automated tournament scheduler jobs.
- Canary flag rollout.
- Full observability + Omar Gate strict mode.
Rollback:
```bash
git revert <PR5_MERGE_COMMIT_SHA>
psql "$DATABASE_URL" -c "UPDATE feature_flags SET enabled=false WHERE key LIKE 'tournament_%';"
```

# 3. DATABASE SCHEMA
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  github_id TEXT UNIQUE NOT NULL,
  username TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT false,
  rollout_percent INT NOT NULL DEFAULT 0 CHECK (rollout_percent BETWEEN 0 AND 100),
  rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ai_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  provider TEXT NOT NULL CHECK (provider IN ('claude','gpt','grok','gemini')),
  api_key_ciphertext BYTEA NOT NULL,
  api_key_key_id TEXT NOT NULL,
  style TEXT NOT NULL DEFAULT 'balanced',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_profiles_user_id ON ai_profiles(user_id);

CREATE TABLE matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  white_ai_id UUID NOT NULL REFERENCES ai_profiles(id),
  black_ai_id UUID NOT NULL REFERENCES ai_profiles(id),
  time_control TEXT NOT NULL DEFAULT '5+0',
  status TEXT NOT NULL CHECK (status IN ('scheduled','in_progress','completed','forfeit','aborted')),
  winner_ai_id UUID NULL REFERENCES ai_profiles(id),
  forfeit_reason TEXT NULL,
  pgn TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_matches_status_created ON matches(status, created_at DESC);

CREATE TABLE match_moves (
  id BIGSERIAL PRIMARY KEY,
  match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  ply INT NOT NULL,
  san TEXT NOT NULL,
  fen TEXT NOT NULL,
  stockfish_eval_cp INT,
  think_summary TEXT,
  chat_line TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(match_id, ply)
);
CREATE INDEX idx_match_moves_match_id_ply ON match_moves(match_id, ply);

CREATE TABLE elo_ratings (
  ai_id UUID PRIMARY KEY REFERENCES ai_profiles(id) ON DELETE CASCADE,
  rating INT NOT NULL DEFAULT 1200,
  wins INT NOT NULL DEFAULT 0,
  losses INT NOT NULL DEFAULT 0,
  draws INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE idempotency_keys (
  key TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_json JSONB NOT NULL,
  status_code INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_idempotency_expires_at ON idempotency_keys(expires_at);
```

# 4. API ENDPOINTS
## Error Contract (all non-2xx)
```ts
export type ErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  requestId: string;
  timestamp: string;
};
```

## Core Endpoints
- `POST /api/v1/ai-profiles` (Idempotency-Key required)
- `GET /api/v1/ai-profiles/me`
- `POST /api/v1/matches` (start)
- `POST /api/v1/matches/{id}/forfeit`
- `GET /api/v1/matches/{id}`
- `GET /api/v1/matches/{id}/replay`
- `GET /api/v1/leaderboard`
- `GET /api/v1/stream/matches/{id}` (SSE)
- `GET /api/v1/feature-flags`
- `PATCH /api/v1/admin/feature-flags/{key}`

## Idempotency Rules
- Header: `Idempotency-Key` required for mutation endpoints.
- Store horizon: 24h minimum.
- Replay behavior: same key + same request hash => return stored response/status.
- Same key + different hash => `409` error envelope.

# 5. SECURITY CHECKLIST
- [ ] AES-256-GCM encryption for BYOAI keys; envelope key via KMS key-id.
- [ ] No secrets in `NEXT_PUBLIC_*`.
- [ ] CSP set on all web responses:
`Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://api.anthropic.com https://api.openai.com https://api.x.ai https://generativelanguage.googleapis.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`
- [ ] CORS exact allowlist:
```py
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS","http://localhost:3000").split(",")
```
- [ ] Parameterized queries only.
- [ ] Request timeout defaults enforced.
- [ ] Structured logs redact `api_key`, `authorization`, cookies.
- [ ] Retention: logs 30d, match telemetry 180d, user deletion hard-delete + crypto-shred within 7d.

## 5.1 Moderation Matrix (AI Chat Lines)
Policy: teen-safe (appropriate for ages 13+). AI chat lines are generated text
displayed to spectators. Every chat line passes through a moderation filter
before broadcast.

| Blocked Class | Examples | Enforcement |
|---|---|---|
| Hate/harassment | slurs, threats, dehumanization | Drop line, log incident, increment strike counter |
| Sexual content | explicit, suggestive, innuendo | Drop line, log incident |
| Violence/gore | graphic descriptions, glorification | Drop line, log incident |
| Self-harm | instructions, encouragement | Drop line, log incident |
| PII leakage | real names, emails, phone numbers | Drop line, redact from logs |
| Prompt injection | attempts to override system prompt | Drop line, log as security event |

Rate limits per AI per match:
- Max 1 chat line per move (tied to ply commit).
- Max 280 characters per line.
- 3 strikes in one match => chat muted for remainder of match.

Language policy:
- English-only in MVP. Non-ASCII art/unicode chess symbols allowed.
- Profanity filter: block NSFW word list + provider-side content filter.

Enforcement path:
1. Provider response received.
2. Extract `chat_line` field from structured output.
3. Run through local blocklist + regex filter.
4. If line passes, broadcast via SSE.
5. If blocked, replace with `[message filtered]` and log the violation.

## 5.2 Thought-Stream Contract
Policy: **summary-only, never raw chain-of-thought**.

| Rule | Detail |
|---|---|
| Generation | Provider prompt requests a 1-2 sentence strategic summary, not reasoning trace |
| Transit | SSE `think_summary` field carries the summary string only |
| Storage | `match_moves.think_summary` column stores the summary (max 500 chars) |
| Never stored | Raw model `reasoning`, `thinking`, `scratchpad`, or CoT tokens |
| Never transmitted | No SSE event carries raw reasoning content |
| Redaction | If provider returns unsolicited CoT, strip before storage/broadcast |
| Logging | Logs may reference summary length/presence but never content of raw CoT |

## Webhook/Signature Verification Function (for future Custom Endpoint + internal signed callbacks)
```ts
import crypto from "crypto";

export function verifyHmacSha256Signature(params: {
  secret: string;
  timestamp: string;
  rawBody: string;
  signatureHex: string;
  toleranceSec?: number;
}): boolean {
  const tolerance = params.toleranceSec ?? 300;
  const now = Math.floor(Date.now() / 1000);
  const ts = Number(params.timestamp);
  if (!Number.isFinite(ts) || Math.abs(now - ts) > tolerance) return false;

  const canonical = `${params.timestamp}.${params.rawBody}`;
  const expected = crypto.createHmac("sha256", params.secret).update(canonical, "utf8").digest("hex");

  const a = Buffer.from(expected, "hex");
  const b = Buffer.from(params.signatureHex, "hex");
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}
```

# 6. OMAR GATE INTEGRATION
`/.claude/hooks/quality-gate.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
echo "[Omar Gate] starting"
npm ci --ignore-scripts
npm run -w apps/web typecheck
npm run -w apps/web lint
npm run -w apps/web test
npm run -w apps/web build
source .venv/bin/activate
pip install --require-hashes -r apps/api/requirements.txt
pytest -q
ruff check .
mypy apps/api
echo "[Omar Gate] passed"
```

# 7. QUALITY STANDARDS
- API contract-first via OpenAPI checked in.
- All mutation endpoints idempotent.
- React hooks stable deps; cleanup required.
- No list rendering >100 without virtualization.
- Query limits mandatory (`LIMIT` required).

## Data sourcing & licensing
- Stockfish: GPLv3 compliance; provide attribution and license file.
- LLM APIs: respect provider ToS; user owns supplied key usage.
- Chess openings datasets (if used): only permissive licensed sources.

## Assumptions
- Greenfield repo, no frozen modules.
- Deployment on Docker-capable Linux.
- PostgreSQL + Redis available.
- No raw chain-of-thought: summary-only in transit (SSE), at rest (DB), and in logs. See Section 5.2 Thought-Stream Contract.

## Open Questions
- Who can view private AI keys metadata in admin panel?
- Should spectators require login to chat or purely read-only?
- Are AI chat logs public forever or user-deletable?
- Should BYOAI owners cap spend per day?
- ~~What moderation strictness for “unfiltered but teen-safe” chat?~~ **Resolved**: See Section 5.1 Moderation Matrix.
- Which cloud/KMS provider is preferred?

## User Flows
1. BYOAI register:
   1) User signs in with GitHub.
   2) Opens “Register AI”, chooses provider, enters key, style.
   3) If invalid key => 422 error envelope + requestId.
2. Live match spectate:
   1) User opens match page.
   2) SSE subscribes.
   3) If SSE disconnects => retry in 2s exponential to 10s.
3. Quota exhausted:
   1) Provider returns 429/quota error.
   2) System retries policy.
   3) On terminal failure => match forfeit, reason shown.
4. Replay:
   1) User opens completed match.
   2) Client loads IndexedDB cached moves if present.
   3) Background sync verifies hash with server.

## Acceptance Criteria / Definition of Done
- Live moves broadcast <500ms p95 from commit to client render.
- Legal moves 100% Stockfish-validated.
- All non-2xx responses include requestId.
- BYOAI key encrypted and never returned plaintext.
- ELO updates transactionally once per match.
- Replay works offline from IndexedDB after first load.
- Feature flags runtime-toggleable via admin API.
- Omar Gate fully passing in CI and local hook.

## ANTI-PATTERN GUARDS
| Anti-Pattern | Why Wrong | Do Instead |
|---|---|---|
| N+1 queries | Slow leaderboard/match pages | `SELECT ai_id, rating FROM elo_ratings WHERE ai_id = ANY($1::uuid[])` |
| Unbounded pagination | Memory/latency blowups | `SELECT * FROM matches ORDER BY created_at DESC LIMIT 50 OFFSET $1;` |
| Secrets in NEXT_PUBLIC_ vars | Secret exposure to browser | `echo "PROVIDER_API_KEY=changeme" >> .env` and read only server-side |
| Raw SQL string concat | SQL injection | `await db.query('SELECT * FROM users WHERE id=$1',[userId])` |
| Floating dependency versions | Supply-chain drift | `npm pkg set dependencies.fastify="4.26.2"` |
| Missing error envelope requestId | Untraceable failures | `return JSONResponse(status_code=400, content={"error":{"code":"BAD_REQ","message":"..."},"requestId":rid,"timestamp":ts})` |
| Hardcoded timeouts | Hung workers | `httpx.AsyncClient(timeout=httpx.Timeout(3.0, read=15.0))` |
| Storing raw chain-of-thought | Safety/compliance risk | `think_summary = sanitize_summary(model_output["summary"])` |
| Env-var-only feature flags | No runtime control | `PATCH /api/v1/admin/feature-flags/{key}` persisted in DB |
| Non-transactional ELO updates | Rating corruption | `BEGIN; UPDATE elo_ratings...; UPDATE matches...; COMMIT;` |
| Provider API key in client bundle | Key theft via browser DevTools | Never import provider keys in `apps/web/`; all provider calls via `apps/api/` only |
| Move commit without Stockfish legality check | Illegal game state corruption | Every `match_moves` INSERT must be preceded by Stockfish `isLegal(fen, san)` validation |
| ELO update outside DB transaction | Split-brain ratings on partial failure | Wrap ELO delta + match status update in single `BEGIN...COMMIT` block |
| Mutation endpoint without Idempotency-Key | Duplicate side effects on retry | Middleware rejects POST/PATCH/DELETE without `Idempotency-Key` header → 400 |
| Raw CoT stored or transmitted | Safety/compliance/IP risk | `think_summary = sanitize_summary(output, max_len=500)`; never store `reasoning` field |
| Provider key decrypted at import time | Key in memory longer than needed | Decrypt only inside request handler scope; zero after use |

## Security & Data Handling
- Token lifecycle: OAuth session 8h, refresh rotation 24h max, revoke on logout.
- Secret redaction in logs via middleware key matcher.
- Logging policy: JSON logs, no PII secrets.
- Retention/deletion workflow:
  - user delete request => soft mark immediate, hard delete + key wipe within 7d.

## Dependency Pinning Strategy
- Node:
```bash
npm ci --ignore-scripts
npm audit --audit-level=high
```
- Python:
```bash
pip install --require-hashes -r apps/api/requirements.txt
pip-audit
```
- Docker digest pinning:
```dockerfile
FROM node:20-slim@sha256:9a6... as web
FROM python:3.12-slim@sha256:3fd... as api
```
- Audit cadence: weekly scheduled CI job.

## Timeout/Retry Matrix
| Integration | Connect | Read | Retries | Backoff |
|---|---:|---:|---:|---|
| Anthropic API | 3s | 20s | 2 | 0.5s, 1.0s |
| OpenAI API | 3s | 20s | 2 | 0.5s, 1.0s |
| Grok API | 3s | 20s | 2 | 0.5s, 1.0s |
| Gemini API | 3s | 20s | 2 | 0.5s, 1.0s |
| Stockfish service | 1s | 5s | 1 | 0.2s |
| GitHub OAuth token exchange | 3s | 10s | 2 | 0.5s, 1.0s |

# 8. Goals & Non-Goals
Goals:
- Fast, reliable AI-vs-AI spectator experience.
- Fair legal move enforcement.
- Transparent ranking and replays.
Non-goals:
- Human-vs-AI gameplay in MVP.
- Money payments/billing engine in MVP.
- Custom endpoint execution in MVP.

# 9. User Personas
- Spectator Sam: wants instant live viewing on mobile.
- AI Owner Olivia: brings API key, style, tracks ELO.
- Tournament Admin Ari: manages scheduling + flags.
- Moderator Mina: oversees AI chat safety stream.

# 10. Non-Functional Requirements
- p95 API latency <250ms (non-stream endpoints).
- 99.9% monthly uptime target.
- SSE reconnect success >99%.
- Horizontal scaling for 5k concurrent spectators per marquee match.

# 11. Observability Plan
- Correlate all logs with `requestId`, `matchId`.
- Metrics: match_start_rate, move_latency_ms, sse_connected_clients, provider_error_rate, forfeit_count.
- Traces: per move orchestration span with provider + stockfish subspans.
- Alerts: provider_error_rate >5% for 5m, SSE disconnect surge >20%.

# 12. Testing Strategy
- Unit: move validation, ELO calculator, idempotency.
- Integration: provider adapters (mock), stockfish bridge, DB transactions.
- E2E: register AI -> run match -> leaderboard -> replay.
- Chaos: kill provider adapter mid-game => forfeit path verified.

# 13. Risk Register
- Provider quota exhaustion spikes => forfeit flood.
- SSE fanout overload on big matches.
- Prompt-injection in AI chat lines.
- OAuth outage.
- Stockfish process crash loops.

Mitigations: circuit breakers, queue buffering, moderation filters, fallback statuses.

# Build Guide (Playbook) — Executable Companion
This spec is implemented via `docs/playbook.md` as the executable companion.

## Infrastructure Files
Canonical infrastructure files live in the repo:
- `infra/docker-compose.yml` — infrastructure-only services (db, redis, minio), digest-pinned, healthchecked, localhost-bound. No app services in compose (apps run natively for dev).
- `.env.example` — empty placeholders only, no real secrets. All secrets injected via `${VAR:?required}` fail-fast syntax.

See the Build Guide (playbook) for exact run commands.

## Main application entry point file (`apps/api/main.py`)
```py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uuid, datetime

app = FastAPI(title="OmarBit API", version="1.0.0")

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response

@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={
        "error": {"code":"INTERNAL_ERROR","message":"Unexpected error"},
        "requestId": request.state.request_id,
        "timestamp": datetime.datetime.utcnow().isoformat()+"Z"
    })

@app.get("/health")
def health():
    return {"ok": True}
```

## AUTONOMOUS EXECUTION LOOP
- Parallel non-overlapping lanes:
  1) API contracts/schema
  2) Web UI/UX
  3) Match worker/orchestration
  4) Observability/CI gates
- Each lane loops:
  1) implement
  2) run gates
  3) collect evidence
  4) fix failures
- Hook-gated completion required:
  - `TaskCompleted`
  - `Stop`
  - `SubagentStop`
- Failed gates are blocking; iterate until all pass.
- Evidence per run must include:
  - commands executed
  - pass/fail result
  - files touched
- Blocker resolution:
  - If same blocker persists 3+ attempts, document in `BLOCKERS.md` (context, attempts, logs, next options), then switch to next parallelizable task.

## ARCHITECTURE & SCOPE
- Preserve existing boundaries and integration seams unless acceptance criteria require explicit changes.
- Define in-scope and out-of-scope surfaces before implementation.

## RISK & MITIGATION
- List primary rollout and contract risks with concrete mitigations.
- Keep rollback path and verification gates explicit for each phase.

<!-- SENTINELAYER_OMAR_SETUP_EMBED -->
## OMAR GATE SETUP (DETERMINISTIC)
- Canonical workflow: `.github/workflows/omar-gate.yml` (already committed, SHA-pinned actions).
- `sentinelayer_spec_id`: `31a72b526381f229fd006d3748b239cbb5afd6ba3705518cd182f4be9fae9e5c`
- `severity_gate`: `P1` (P0/P1 block merge; P2 tracked but non-blocking).
- `telemetry`: `false`, `share_metadata`: `false`, `training_opt_in`: `false`.
- `fork_policy`: `block` (prevents fork PRs from accessing secrets).
- Do not duplicate the full YAML here — the repo file is the single source of truth.