# STEP-BY-STEP BUILD GUIDE: OmarBit Sentinel Chess Arena MVP

## 1. PREREQUISITES
- Git >= 2.40: https://git-scm.com/downloads

## 1.5. RECOMMENDED BUILD ENVIRONMENT
Choose the tool that matches your style:
- **See every change (recommended for beginners):** VS Code + GitHub Copilot - shows inline diffs for every file
- **Fast AI-assisted building:** Cursor or Claude Code - rapid iteration with AI suggestions
- **Zero setup:** Replit Agent or Bolt - browser-based, no local install needed

**Pro tip:** With a well-structured spec, even smaller models can build your project correctly. You don't need the most expensive model when the spec does the heavy lifting.

## 2. REPOSITORY SETUP
```bash
mkdir my-project
cd my-project
git init
npm create vite@latest . -- --template react-ts
```

## 2.6 SPEC CROSS-REFERENCE
- Architecture/scope source: spec sections `PROJECT OVERVIEW` and `ARCHITECTURE & SCOPE`.
- Risk/rollback source: spec sections `RISK & MITIGATION` and `ROLLOUT & ROLLBACK` (or `ROLLBACK`).
- Keep this guide focused on commands/runbook steps; do not duplicate full spec context here.

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

## 4.5 INFRASTRUCTURE FILES (COPY-PASTE READY)

### docker-compose.yml
```yaml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ':9001'
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data

volumes:
  minio-data:
```

### .env.example
```bash
# Application
NODE_ENV=development
APP_PORT=3000
API_PORT=8000

# Object Storage (MinIO for local, S3 for prod)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=app-uploads

# Auth
JWT_SECRET=change-me-in-production

# External APIs (add as needed)
# OPENAI_API_KEY=sk-...
# PAYMENT_API_KEY=...
# SENDGRID_API_KEY=...
```

### .claude/hooks/quality-gate.sh
```bash
set -euo pipefail
if [ -f package.json ]; then
  npm run typecheck --if-present
  npm run lint --if-present
  npm test --if-present
  npm run build --if-present
fi
if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  ruff check .
  python -m pytest -q
fi
```

## 5. PHASE 0: FOUNDATION
- Install dependencies and set environment variables.
- Create first PR for base architecture and pass Omar Gate.

## 6. PHASE EXECUTION (DYNAMIC)
- Define as many phases as needed by blast radius and dependency order.
- Keep one PR per phase and verify each phase before proceeding.
- Suggested initial dynamic phase plan:

### Phase 0
- Baseline architecture, contracts, CI quality gates, and Omar Gate wiring.
### Phase 1
- Implement: Core implementation.
### Phase 2
- Hardening: observability, performance checks, security review, and rollout readiness.
- Add extra phases when dependency chains or risk profile require narrower increments.

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
3. Example `.claude/hooks/quality-gate.sh`:
```bash
set -euo pipefail
if [ -f package.json ]; then
  npm run typecheck --if-present
  npm run lint --if-present
  npm test --if-present
  npm run build --if-present
fi
if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
  ruff check .
  python -m pytest -q
fi
```
- No deterministic command hints were detected. Discover and lock the repo-native typecheck/lint/test/build commands before phase execution.
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
```

## PLATFORM SETUP & AI MEMORY GUIDE

Pick one environment and inject the same constraints to keep implementation deterministic:

1. VS Code + GitHub Copilot (`.github/copilot-instructions.md`)
2. Cursor (`.cursorrules`)
3. Claude Code (`CLAUDE.md`)

Starter block:

```
Project: OmarBit Sentinel Chess Arena MVP | Spec: 31a72b526381f229fd006d3748b239cbb5afd6ba3705518cd182f4be9fae9e5c
Stack: your tech stack
Follow the spec exactly. Do not guess. Stop and ask when uncertain.
```