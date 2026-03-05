# Lessons Learned

## Infrastructure
- Redis in Docker has password `omarbit123` — REDIS_URL must include `:omarbit123@`
- npm workspaces hoist packages to root node_modules — Turbopack can't resolve them. Avoid heavy deps or use built-in components
- Celery worker is a separate process — never runs FastAPI startup. Must init DB pool in task
- `.npmrc` has `ignore-scripts=true` — some packages with postinstall won't work
- Docker image digests go stale — use tag-only refs (e.g., `redis:7` not `redis:7@sha256:...`)

## Code Patterns
- Use `celery.send_task("task_name", args=[...])` for cross-package Celery calls (avoids import issues in monorepo)
- `chess.pgn` needs explicit `import chess.pgn` — not auto-imported with `import chess`
- Next.js `dynamic()` with `ssr: false` for client-only components
- `get_conn()` context manager requires `init_pool()` to have been called first

## Testing
- MatchClock flagging: use `active_remaining() <= 0` not inline math (floating point precision)
- Always run `ruff check --fix` after moving imports around (I001 unsorted imports)

## Git
- `.env.local` is gitignored (correctly) — don't try to `git add` it
- Always create NEW commits, never amend unless explicitly asked
