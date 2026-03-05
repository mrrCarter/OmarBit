# STEP-BY-STEP BUILD GUIDE: OmarBit Sentinel Chess Arena MVP

## 1. PREREQUISITES
- Git >= 2.40
- Node.js >= 20 (LTS) + npm >= 10
- Python 3.12 + pip + pip-tools (for `pip-compile --generate-hashes`)
- Docker + Docker Compose v2 (for Postgres, Redis, MinIO)
- GitHub CLI (`gh`) for PR workflows

## 1.5. RECOMMENDED BUILD ENVIRONMENT
- **Primary:** Claude Code — autonomous loop with quality hooks
- **Alternative:** VS Code + GitHub Copilot, Cursor
- **CI:** GitHub Actions (Omar Gate workflow)

## 2. REPOSITORY SETUP (MONOREPO)
```bash
mkdir -p omarbit/{apps/web,apps/api,workers,infra,.github/workflows,.claude/hooks,docs}
cd omarbit
git init

# Root package.json with workspaces
npm init -y
npx json -I -f package.json -e 'this.workspaces=["apps/web"]'
npx json -I -f package.json -e 'this.engines={"node":">=20"}'
echo 'engine-strict=true' > .npmrc
echo 'ignore-scripts=true' >> .npmrc

# Frontend: Next.js 15 (App Router) + TypeScript + Tailwind
cd apps/web
npx create-next-app@latest . --typescript --tailwind --app --eslint --no-src-dir --import-alias "@/*"
cd ../..

# Backend: Python 3.12 + FastAPI
python3.12 -m venv .venv && source .venv/bin/activate
pip install pip==24.3.1
# Create requirements.in, then:
pip-compile --generate-hashes -o apps/api/requirements-locked.txt apps/api/requirements.in
pip-compile --generate-hashes -o apps/api/requirements-dev-locked.txt apps/api/requirements-dev.in

# Infrastructure
docker compose -f infra/docker-compose.yml up -d
```

### Run Commands (monorepo-specific)
```bash
# Start infrastructure
docker compose -f infra/docker-compose.yml up -d

# Start API (dev)
source .venv/bin/activate
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

# Start Web (dev)
npm run -w apps/web dev

# Run all quality gates
npm run -w apps/web typecheck
npm run -w apps/web lint
npm run -w apps/web test
npm run -w apps/web build
source .venv/bin/activate
ruff check .
python -m pytest -q

# Run migrations
psql "$DATABASE_URL" -f apps/api/migrations/001_baseline.sql
```

## 2.6 SPEC CROSS-REFERENCE
- Architecture/scope/schema: spec sections 1, 3, 4 (what/why).
- Security/moderation/thought-stream: spec sections 5, 5.1, 5.2.
- Risk/rollback: spec section 2 (per-phase rollback commands).
- Anti-pattern guards: spec ANTI-PATTERN GUARDS table.
- This guide = commands/runbook only. Do not duplicate spec context here.

## 3. PUSH TO GITHUB
```bash
git add .
git commit -m "chore: initial scaffold"
git branch -M main
git remote add origin git@github.com:YOUR_ORG/YOUR_REPO.git
git push -u origin main
```

## 4. SET UP OMAR GATE
- Create `.github/workflows/omar-gate.yml` with generated YAML.
- Add `OPENAI_API_KEY` to GitHub Actions secrets.
- Omar Gate reviews every PR before merge.

## 4.5 INFRASTRUCTURE FILES
Canonical files in the repo (do not duplicate here):
- `infra/docker-compose.yml` — Postgres 16, Redis 7, MinIO (all digest-pinned, healthchecked, localhost-bound)
- `.env.example` — empty placeholders, no secrets
- `.claude/hooks/quality-gate.sh` — monorepo-specific gate script

### Quality gate commands (what the hook runs):
```bash
set -euo pipefail
npm run -w apps/web typecheck
npm run -w apps/web lint
npm run -w apps/web test
npm run -w apps/web build
source .venv/bin/activate
pip install --require-hashes -r apps/api/requirements-locked.txt
ruff check .
python -m pytest -q
```

## 5. PHASE 0: FOUNDATION
- Install dependencies and set environment variables.
- Create first PR for base architecture and pass Omar Gate.

## 6. PHASE EXECUTION (DYNAMIC)
- Define as many phases as needed by blast radius and dependency order.
- Keep one PR per phase and verify each phase before proceeding.
- Suggested initial dynamic phase plan:

### Phase 0 — Foundation & Contracts
Monorepo scaffold, Docker compose, envs, lint/test/typecheck, OpenAPI skeleton, DB migrations baseline.
### Phase 1 — Auth + AI Registry + Feature Flags
GitHub OAuth sign-in, AI registration CRUD, DB-backed feature flags + admin API, Coming Soon placeholders.
### Phase 2 — Match Engine + Stockfish Referee + SSE Core
Match lifecycle state machine, Stockfish legality validation, SSE stream, idempotent match APIs.
### Phase 3 — BYOAI Provider Integrations + Quota/Forfeit
Claude/GPT/Grok/Gemini adapters, timeout/retry/backoff, forfeit on unrecoverable errors.
### Phase 4 — Leaderboard + Replay + IndexedDB Cache
Transactional ELO updates, replay APIs, IndexedDB sync/cache.
### Phase 5 — Round-Robin Scheduler + Progressive Delivery + Hardening
Tournament scheduler, canary flag rollout, full observability, Omar Gate strict mode.

```bash
git checkout -b feature/phase-<n>-<scope>
# implement scoped feature
git add .
git commit -m "feat: phase <n>"
git push -u origin feature/phase-<n>-<scope>
gh pr create --fill --base main --head feature/phase-<n>-<scope>
```
- Open PR -> Omar review -> fix findings -> merge.
- Repeat for each phase.

## 6.5 AUTONOMOUS AGENT LOOP (PARALLEL + SELF-VERIFY)
1. Parallel lanes: create isolated worktrees for independent scopes to prevent branch collisions.
```bash
git worktree add ../worktrees/phase-1 -b feature/phase-1 origin/main
git worktree add ../worktrees/phase-2 -b feature/phase-2 origin/main
```
2. Hook-gated completion: wire `TaskCompleted`, `Stop`, and `SubagentStop` hooks to run `.claude/hooks/quality-gate.sh`.
```json
{
  "hooks": {
    "TaskCompleted": [{"hooks": [{"type": "command", "command": ".claude/hooks/quality-gate.sh"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": ".claude/hooks/quality-gate.sh"}]}],
    "SubagentStop": [{"hooks": [{"type": "command", "command": ".claude/hooks/quality-gate.sh"}]}]
  }
}
```
3. Quality gate commands (monorepo-specific):
```bash
set -euo pipefail
npm run -w apps/web typecheck
npm run -w apps/web lint
npm run -w apps/web test
npm run -w apps/web build
source .venv/bin/activate
pip install --require-hashes -r apps/api/requirements-locked.txt
ruff check .
python -m pytest -q
```
4. Self-verification loop: if a gate fails, fix root cause and rerun gates; do not mark the phase done early.
5. If your agent runtime lacks hooks, enforce the same commands as required CI checks and block merges until green.
6. Add latency/benchmark checks to this hook when acceptance criteria define numeric performance targets.

## 7. DEPENDENCY-AWARE ORDERING
1. Migration order: apply additive/expand migrations before runtime behavior flips.
2. Feature flag order: ship code with flags default OFF, then enable per environment.
3. Rollout order: canary -> staged cohorts -> full rollout with explicit rollback trigger.
4. Verification order: run typecheck/lint/tests/build before merge and after each stage.

## 8. WORKING WITH OMAR GATE LIKE A PRO
- If Omar blocks PR, fix highest severity findings first.
- Only lower severity gate with documented rationale.
- Add domain rules for project-specific policies.

## 9. OPTIONAL OMAR DOMAIN_RULES SYNTHESIS
- Confidence: medium
- Candidate rules synthesized from acceptance criteria and repo context:

```yaml
domain_rules: |
  - Reject changes that remove `requestId` from non-2xx error envelopes.
  - Require explicit rollback path and feature-flag gating for risky releases.
  - No provider API keys in client bundle (apps/web). All provider calls via apps/api only.
  - No move commit (match_moves INSERT) without prior Stockfish legality validation.
  - No ELO rating update outside a DB transaction that also updates match status.
  - No mutation endpoint (POST/PATCH/DELETE) without Idempotency-Key middleware.
  - No raw chain-of-thought storage or transmission. Summary-only (max 500 chars).
  - No AI chat line broadcast without moderation filter pass.
```

## PLATFORM SETUP & AI MEMORY GUIDE

Pick one environment and inject the same constraints to keep implementation deterministic:

1. VS Code + GitHub Copilot (`.github/copilot-instructions.md`)
2. Cursor (`.cursorrules`)
3. Claude Code (`CLAUDE.md`)

Starter block:

```
Project: OmarBit Sentinel Chess Arena MVP | Spec: 31a72b526381f229fd006d3748b239cbb5afd6ba3705518cd182f4be9fae9e5c
Stack: Next.js 15 (App Router) + TypeScript + Tailwind | FastAPI (Python 3.12) + Celery + Redis | PostgreSQL 16
Follow the spec exactly. Do not guess. Stop and ask when uncertain.
```