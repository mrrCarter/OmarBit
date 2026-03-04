# 0. EXECUTIVE SUMMARY
OmarBit Sentinel Chess Arena is a greenfield, security-conscious web platform where registered AI agents (platform-managed and user-supplied BYOAI keys) play timed chess matches under Stockfish-refereed legality, stream live moves and moderated AI “table talk” to spectators via Server-Sent Events (SSE), and persist results into an ELO leaderboard with replay support (IndexedDB client cache + PostgreSQL server truth), delivered in phased PRs with strict contract-first APIs, idempotent mutation handling, runtime DB-backed feature flags, CI/Hook quality gates (Omar Gate), and progressive rollout controls.

# 1. PROJECT OVERVIEW
## 1.1 Scope (MVP)
- AI vs AI live matches (5+0 blitz initially) with move-by-move updates.
- Live spectator stream (SSE) for:
  - game state updates
  - clock updates
  - AI chat lines (guardrailed for teen-safe language)
  - optional model “thought summary” stream (not raw chain-of-thought)
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
mkdir -p omarbit/{apps/web,apps/api,workers,infra,.claude/hooks}
cd omarbit
npm init -y
python3 -m venv .venv && source .venv/bin/activate
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
- No raw chain-of-thought storage requirement (store summaries only).

## Open Questions
- Who can view private AI keys metadata in admin panel?
- Should spectators require login to chat or purely read-only?
- Are AI chat logs public forever or user-deletable?
- Should BYOAI owners cap spend per day?
- What moderation strictness for “unfiltered but teen-safe” chat?
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

## docker-compose.yml
```yaml
version: "3.9"
services:
  db:
    image: postgres:16@sha256:6f8b8b...
    environment:
      POSTGRES_USER: omarbit
      POSTGRES_PASSWORD: omarbit
      POSTGRES_DB: omarbit
    ports: ["5432:5432"]
  redis:
    image: redis:7@sha256:1f4c3d...
    ports: ["6379:6379"]
  minio:
    image: minio/minio:RELEASE.2024-05-10T01-41-38Z@sha256:5a2b...
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: omarbit
      MINIO_ROOT_PASSWORD: omarbit123
    ports: ["9000:9000","9001:9001"]
  api:
    build: ./apps/api
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [db, redis]
  web:
    build: ./apps/web
    env_file: .env
    ports: ["3000:3000"]
    depends_on: [api]
  worker:
    build: ./workers
    env_file: .env
    depends_on: [api, redis, db]
```

## .env.example
```bash
NODE_ENV=development
DATABASE_URL=postgresql://omarbit:omarbit@localhost:5432/omarbit
REDIS_URL=redis://localhost:6379/0
NEXTAUTH_URL=http://localhost:3000
GITHUB_CLIENT_ID=github_client_id_here
GITHUB_CLIENT_SECRET=github_client_secret_here
API_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000
KMS_KEY_ID=local-dev-key
ENCRYPTION_MASTER_KEY_BASE64=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
ANTHROPIC_API_URL=https://api.anthropic.com
OPENAI_API_URL=https://api.openai.com
GROK_API_URL=https://api.x.ai
GEMINI_API_URL=https://generativelanguage.googleapis.com
STOCKFISH_URL=http://stockfish:8080
```

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
- Commit this workflow to `.github/workflows/omar-gate.yml`.
- Keep `sentinelayer_spec_id` bound to this spec for policy-aware reviews.

```yaml
# Omar Gate — AI-powered security review for pull requests.
# Runs the SentinelLayer Omar action on every PR to surface security,
# compliance, and code-quality issues before merge. Findings are posted
# as inline PR comments with severity levels (P1-P4).
# Docs: https://docs.sentinelayer.com/omar-gate

name: Omar Gate Security Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  checks: write
  pull-requests: write

jobs:
  quality-gates:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Run quality gates
        shell: bash
        run: |
          set -euo pipefail
          if [ -f pnpm-lock.yaml ]; then
            corepack enable
            pnpm i --frozen-lockfile
          elif [ -f package-lock.json ]; then
            npm ci
          elif [ -f yarn.lock ]; then
            yarn install --frozen-lockfile
          elif [ -f package.json ]; then
            npm install
          fi
          if [ -f package.json ]; then
            npm run typecheck --if-present
            npm run lint --if-present
            npm test --if-present
            npm run build --if-present
          fi
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then
            python -m pip install -r requirements.txt
          elif [ -f pyproject.toml ]; then
            python -m pip install -e .
          fi
          if [ -f requirements.txt ] || [ -f pyproject.toml ]; then
            python -m pip install ruff pytest
            ruff check .
            python -m pytest -q
          fi
  security-gate:
    needs: quality-gates
    runs-on: ubuntu-latest
    permissions:
      contents: read
      checks: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: mrrCarter/sentinelayer-v1-action@14ca51c75ca81fdb6e6b7668d417d6a5abc39018
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          use_codex: 'true'
          codex_only: 'true'
          codex_model: gpt-5.3-codex
          codex_timeout: '480'
          model_fallback: gpt-4.1-mini
          llm_failure_policy: block
          run_harness: 'true'
          fork_policy: block
          telemetry: 'true'
          telemetry_tier: '1'
          sentinelayer_managed_llm: 'false'
          training_opt_in: 'false'
          max_input_tokens: '120000'
          sentinelayer_spec_id: 31a72b526381f229fd006d3748b239cbb5afd6ba3705518cd182f4be9fae9e5c
          severity_gate: P2
          scan_mode: deep
          share_metadata: 'true'
          policy_pack: omar
          policy_pack_version: v1
```