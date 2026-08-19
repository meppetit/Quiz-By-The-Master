# Production database — Supabase Postgres (5 minutes)

MEP Quiz needs PostgreSQL. Emergent's production platform provisions MongoDB only, so production points at a free managed Postgres instead. Supabase is the quickest.

---

## Step 1 — Create the project

1. Go to **https://supabase.com** and sign in with GitHub or email.
2. Click **New project**.
3. Fill in:
   - **Name**: `mep-quiz`
   - **Database password**: click *Generate a password* and **copy it somewhere safe** — you cannot see it again.
   - **Region**: pick the one closest to where the event happens (e.g. `South Asia (Mumbai)` for India).
4. Click **Create new project** and wait ~2 minutes for it to finish provisioning.

## Step 2 — Copy the connection string

1. In your project, click **Connect** (top bar) — or **Project Settings → Database → Connection string**.
2. Choose the **Connection pooling / Transaction pooler** tab (port **6543**), not the direct one. The pooler is what survives the QR-scan burst.
3. Copy the URI. It looks like:

```
postgresql://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

4. Replace `[YOUR-PASSWORD]` with the database password from Step 1. No square brackets, no spaces.

## Step 3 — Give it to me / set it in production

Paste that finished URL into the chat, or set it yourself as the production environment variable:

```
DATABASE_URL=postgresql://postgres.xxxx:YOURPASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

Also set these production values (never reuse the preview ones):

```
JWT_SECRET=<run: openssl rand -hex 32>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<a long unique password>
CORS_ORIGINS=https://<your-production-domain>
```

The app accepts any standard Postgres URL — `postgresql://`, `postgres://`, with or without `?sslmode=require`. It converts it to the async driver, enables SSL for remote hosts, and turns off prepared-statement caching automatically when it detects a pooler host. You do not need to reformat anything.

## Step 4 — First boot

On startup the backend creates its own tables and seeds 20 question sets × 20 placeholder questions if the database is empty. Nothing to run by hand. Then:

1. Open `/admin/login` on production and sign in.
2. **Questions** tab → import your real questions per set (tick *Replace existing*).
3. **Set health** tab → confirm all 20 sets are READY.
4. `GET /api/health` should return `{"status":"ok","database":"postgresql","question_sets":20}`.

## Already wired up for this project

The app is currently pointed at the Supabase project `arfywtfdaovlrzjhqmdq` (Mumbai) using the **transaction pooler**:

```
DATABASE_URL='postgresql://postgres.arfywtfdaovlrzjhqmdq:<your-password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres'
```

Two gotchas worth remembering:

- The **direct** host `db.<ref>.supabase.co` is IPv6-only on new Supabase projects. Most hosting containers are IPv4-only, so that host fails with "No address associated with hostname". Always use the `...pooler.supabase.com` host.
- The password contains a `$`, so wrap the value in **single quotes** in `.env` files to stop shells and dotenv from touching it.

## Notes

- Free tier is plenty for one event (500 MB, ~200 pooled connections). 5,000 participants × 21 rows each is a few MB.
- Supabase pauses free projects after a week of inactivity — open the dashboard once the day before the event so it is warm.
- Back up after the event: **Project Settings → Database → Backups**, or `pg_dump "$DATABASE_URL" > mep-quiz.sql`.
- Neon (https://neon.tech) works identically — use its pooled connection string.
