# MEP Quiz — PRD

## Original problem statement
Mobile-web live-event quiz app. PostgreSQL is a hard requirement. Participant flow: registration (name/email/phone required + validated, school optional, duplicate email/phone rejected) → 20-question quiz, one question per screen, no going back, count-up timer from started_at, each answer logged → completion screen with thank-you only (no score). Admin dashboard: auth-protected stats (participants, avg score, avg time, completion rate), searchable/sortable table, leaderboard (score, tie-break fastest time), CSV export, question content management for 20 sets × 20 questions with paste/upload parser. Set assignment must pick the least-loaded set and stay correct under concurrent QR-scan bursts (FOR UPDATE SKIP LOCKED). Score/time computed server-side only; question API must never leak correct answers.

## Architecture
- FastAPI + SQLAlchemy 2 async + asyncpg + PostgreSQL 15 (supervisor program `postgresql`), React 19 CRA + Tailwind.
- Backend: `server.py` (routes), `models.py`, `db.py` (pooled engine 20/40), `auth.py` (env admin + JWT bearer), `parser.py` (paste parser), `seed.py` (20 sets × 20 seeded questions).
- Frontend: `pages/Registration|Quiz|Completion|AdminLogin|AdminDashboard|QuestionManager`, `components/Shell`, `lib/api.js`.
- Tables: participants, question_sets (+attempt_count counter), questions (jsonb options), attempts (unique participant_id, uuid token), answers (unique attempt_id+question_id).

## User personas
- Participant: scans QR on phone, registers once, runs 20 questions, sees thank-you.
- Organiser/admin: desktop control room — live stats, leaderboard, CSV export, question content management.

## Core requirements (static)
Server-side scoring/time, no answer leakage, one attempt per person, least-loaded set assignment safe under bursts, mobile-first participant UI matching supplied screenshots, desktop admin.

## Implemented (2026-06)
- **Deployment note**: Emergent-native deploy provisions MongoDB only, so this app (PostgreSQL hard requirement) must deploy on a Postgres-friendly host with an external managed Postgres (`DATABASE_URL`). Mongo leftovers (MONGO_URL/DB_NAME env, motor/pymongo deps) removed; `db.py` normalises any Postgres URL for asyncpg (SSL for remote hosts, pooler-safe statement caching); `GET /api/health` added for platform probes. Guides: `/app/DEPLOYMENT.md`, `/app/SUPABASE_SETUP.md`.
- Registration with validation + duplicate email/phone 409 with clear message.
- Least-loaded set assignment via `FOR UPDATE SKIP LOCKED` on question_sets + atomic attempt_count, with retry/backoff. Verified: 35 concurrent registrations → per-set skew of 1.
- Quiz: server-driven single-question endpoint (no correct_option, no sibling questions), answer logging, resume from started_at on refresh, count-up timer, progress bar.
- Completion screen (thank-you only), attempt token cleared.
- Admin: JWT login from env, stats, searchable/sortable participants table, leaderboard, CSV export, per-set question CRUD, bulk paste/file import with error flagging, reset-attempts utility.
- Design implemented from screenshots: near-black + lime (#C6F24E), Outfit/DM Sans, grid texture.
- QA: 21/21 backend pytest + full Playwright participant & admin flows passing (`/app/test_reports/iteration_1.json`).

- **Set health**: pre-event checklist endpoint `/api/admin/health-check` + admin tab flagging sets with missing questions, missing/blank options, invalid correct answers or duplicate texts (over-provisioned sets are a warning, not a blocker).
- **Live leaderboard**: `/admin/live` full-screen projector view, ranked score/time rows, 5s auto-refresh (paused when tab hidden), native fullscreen toggle.
- **Deployment**: `/app/DEPLOYMENT.md` guide + `/app/deploy/` (docker-compose with tuned Postgres + PgBouncer transaction pooling, gunicorn/uvicorn 4-worker backend image, nginx with rate-limited `/api/register` and static caching).

- **Real content loaded (2026-06)**: all 400 questions from the user's "Question Bank 400 Qns.docx" imported into the 20 sets via `/app/scripts/import_question_bank.py` (docx paragraphs use `<w:br>` inside a single `<w:p>` — the extractor splits on those). The source key was heavily A-biased (sets 10–20 were 100% A), so option order was shuffled once in place with `/app/scripts/shuffle_options.py` (correct answer tracked, wording untouched): key spread is now A131/B103/C89/D77 and an all-A run scores ~7/20.

## Backlog
- P0: import the real 400-question document (20 sets × 20) via the admin paste/upload panel; then remove seeded placeholders.
- P1: deployment hardening for the burst (multiple uvicorn workers/replicas, PgBouncer, explicit CORS origins instead of `*`).
- P1: live big-screen leaderboard view for the event.
- P2: per-set analytics (hardest questions), admin ability to reorder questions, rate limiting on /api/register.

## Next tasks
1. Get the 400-question document and bulk-import it per set, then re-run Set health.
2. Deploy with `/app/deploy/docker-compose.yml` (see DEPLOYMENT.md) and load test at expected peak concurrency.
