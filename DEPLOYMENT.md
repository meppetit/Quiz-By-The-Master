# MEP Quiz — Deployment Guide

Everything you need to run this app for one live event with a big registration spike right after the QR code goes up. Plain language, copy-paste commands.

---

## 1. What you are deploying

| Piece | What it is | Notes |
|---|---|---|
| Frontend | React static build | Served by a CDN or nginx. Cheap, scales for free. |
| Backend | FastAPI (uvicorn workers) | The part that must survive the spike. Scale this. |
| Database | PostgreSQL 15 | The single source of truth. Needs a connection pooler. |
| Pooler | PgBouncer | Stops hundreds of app connections from crushing Postgres. |

Rule of thumb for the spike: **the frontend never fails, the backend needs copies, the database needs a pooler.**

---

## 2. Sizing for the burst

Assume everyone scans within ~60 seconds.

| Expected crowd | Backend | Postgres | PgBouncer pool |
|---|---|---|---|
| up to 200 | 1 machine, 4 workers | 2 vCPU / 4 GB | 25 |
| 200–1000 | 2 machines, 4 workers each | 4 vCPU / 8 GB | 50 |
| 1000–5000 | 4 machines, 4 workers each | 8 vCPU / 16 GB | 100 |

Registration is one short transaction, so a modest Postgres goes a long way. Add backend copies before you add database size.

---

## 2.5 Keep the app and the database in the same region (biggest speed factor)

Every query costs one network round-trip. If the backend is in the US and the database is in Mumbai, that is ~450 ms **per query** and the quiz feels sluggish no matter how good the code is. In the same region it is ~1–5 ms.

So: whatever host you pick, deploy the backend in the **same region as your Postgres** (e.g. Supabase Mumbai → Railway/Render/Fly region `ap-south-1` / Singapore as the nearest alternative). This single choice matters more than instance size.

The app is already written to be round-trip frugal: registration, fetching a question and submitting an answer are each **one** database statement, and submitting an answer returns the next question in the same response, so each quiz screen costs one request.



> Deploying on **Emergent**? Emergent provisions MongoDB only, so production must point at an external managed Postgres. Follow **[SUPABASE_SETUP.md](./SUPABASE_SETUP.md)** (5 minutes, free) and set `DATABASE_URL` to the pooled connection string. The backend accepts plain `postgresql://` URLs and handles SSL and pooler settings for you. Nothing else in the app needs MongoDB — the Mongo variables have been removed from `backend/.env`.

Backend (`/app/backend/.env` or your host's env panel):

```
DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@DB_HOST:6432/mepquiz"   # 6432 = PgBouncer
JWT_SECRET="<64 random hex chars: openssl rand -hex 32>"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="<long unique password>"
CORS_ORIGINS="https://quiz.yourdomain.com"
```

Frontend:

```
REACT_APP_BACKEND_URL=https://quiz.yourdomain.com
```

Change `ADMIN_PASSWORD` and `JWT_SECRET` before the event. Never use `CORS_ORIGINS="*"` in production.

---

## 4. Option A — Docker Compose on one big VM (simplest)

Best if you want one machine you fully control. Use a 4–8 vCPU VM.

```bash
cp deploy/.env.example deploy/.env   # then edit the values
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f backend
```

What the compose file gives you: Postgres with tuned settings, PgBouncer in transaction mode, the backend behind gunicorn with 4 uvicorn workers (scale with `--scale backend=3`), and nginx serving the React build plus proxying `/api`.

Scale up right before the event:

```bash
docker compose -f deploy/docker-compose.yml up -d --scale backend=3
```

---

## 5. Option B — Managed platform (least ops work)

> **Using Vercel + Render?** Follow the dedicated step-by-step guide: **[DEPLOY_VERCEL_RENDER.md](./DEPLOY_VERCEL_RENDER.md)** (includes every env var, the SPA rewrite, scaling table and a troubleshooting matrix). `render.yaml` and `frontend/vercel.json` are already in the repo.


1. **Database**: create a managed Postgres (Neon, Supabase, RDS, Railway). Turn on connection pooling and use the *pooled* connection string.
2. **Backend**: deploy `/app/backend` to Render/Railway/Fly with start command:
   ```
   gunicorn server:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8001 --timeout 60
   ```
   Set min instances to 2–4 so nothing is cold when the QR goes live. Disable scale-to-zero.
3. **Frontend**: `cd frontend && yarn build`, deploy `build/` to Vercel/Netlify/Cloudflare Pages with `REACT_APP_BACKEND_URL` set to your backend domain.

---

## 6. Postgres settings that matter

```
max_connections = 200
shared_buffers = 25% of RAM
work_mem = 8MB
synchronous_commit = off      # fine for a single event; slightly faster writes
```

`synchronous_commit = off` trades a few milliseconds of crash-window durability for noticeably faster registration writes. Perfectly reasonable for one evening; drop it if you need bank-grade durability.

Indexes are created automatically by the app (unique on email, phone, attempt token, and `(attempt_id, question_id)`).

---

## 7. Why the burst is safe

- Set assignment uses `SELECT ... ORDER BY attempt_count FOR UPDATE SKIP LOCKED LIMIT 1`, so concurrent registrations never fight over the same row and never all land on Set 01.
- Verified with 35 simultaneous registrations: sets came out even, biggest gap between any two sets was 1.
- `participants.email`, `participants.phone` and `attempts.participant_id` are unique in the database, so even a double-tap cannot create two entries.
- Scores and times are computed only on the server from the stored answers.

---

## 8. Pre-event checklist (do this the day before)

1. Log into `/admin` and open the **Set health** tab. Every set must show **READY** (20 questions, four options each, valid correct answer).
2. Import the real questions on the **Questions** tab, one set at a time, with "Replace existing" ticked.
3. Clear test data: `POST /api/admin/reset-attempts` with your admin token (this wipes participants, attempts and answers, and resets set counters). Then re-check Set health.
4. Do one full run on a real phone end-to-end.
5. Open `/admin/live` on the projector machine and press **Fullscreen**. It refreshes itself every 5 seconds.
6. Print the QR code pointing at `https://quiz.yourdomain.com/`.

---

## 9. During the event

- Keep `/admin/live` on the big screen and the dashboard on a laptop.
- Watch backend logs; if requests slow down, add backend copies (`--scale backend=N`) — do not restart Postgres.
- **Export CSV** at the end from the dashboard. Do this before shutting anything down.

---

## 10. Quick troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "No question sets available" | A set has no questions | Import questions; check Set health |
| Registration slow, then fine | Cold instances | Set minimum instances ≥ 2 before the event |
| "too many connections" | No pooler | Point `DATABASE_URL` at PgBouncer port 6432 |
| Browser CORS error | Wrong `CORS_ORIGINS` | Set it to the exact frontend origin, no trailing slash |
| Admin login fails | `JWT_SECRET`/password changed after tokens were issued | Log out and back in |

---

## 11. After the event

```bash
# keep the results
pg_dump "$DATABASE_URL" > mep-quiz-$(date +%F).sql
docker compose -f deploy/docker-compose.yml down
```
