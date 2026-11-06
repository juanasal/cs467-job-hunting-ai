# Backend Hosting Decision (JH-008)

**Decision:** Run the FastAPI backend as a **Render Free web service**.
**Decided:** 2026-11-04. Prices and limits were checked on each host's own site that day. Check [Render pricing](https://render.com/pricing) again before paying for anything.

This is the hosting decision only. The actual deployment is a separate ticket.

## Where each part of the app runs

The app uses three separate hosts. Each has its own account and settings.

| Part | Host | What it runs | Notes |
| --- | --- | --- | --- |
| Frontend | **Vercel** | The React + Vite app in `frontend/my-react-app/` | Static files only. It calls the backend over HTTPS. |
| Backend API | **Render** (this decision) | The FastAPI app in `backend/` | Reads settings from Render environment variables and connects out to Aiven. |
| Database | **Aiven** | MySQL | Requires SSL. The backend proves it reached the real server using Aiven's `ca.pem`. |
| Job data | Adzuna API | External job listings | Called by the backend or pipeline, never by the browser, so the API key stays secret. |

Changing one host doesn't change the others. For example, moving the backend off Render only changes the backend URL that the frontend calls.

## Options compared

| | Render | Railway | Fly.io |
| --- | --- | --- | --- |
| Cost to start | $0 (Free web service, Hobby workspace) | 30-day trial ($5 credit), then $1/month credit on Free or $5/month on Hobby | No free tier. $1 trial credit for 7 days, then a credit card is required. |
| Cheapest always-on | $7/month (Starter) | Usage-based. A small app probably fits in Hobby's $5. | $2.19/month (256 MB) or $3.69/month (512 MB) |
| Sleep | Spins down after 15 minutes idle. Waking takes about 1 minute. | Optional sleep. The first request after waking may return a 502. | Optional auto-stop |
| HTTPS | Automatic | Automatic | Automatic |
| `ca.pem` as a file | Built-in secret files. No code change. | No file support. The start command would have to write the file. | Supported through `[[files]]` in `fly.toml` (base64 secret) |
| Scheduled jobs | Cron jobs, paid only ($1/month minimum) | Cron schedule per service | Hourly, daily, weekly or monthly machines, or an in-container cron |
| Deploy setup | GitHub repo plus build and start commands | GitHub repo | Dockerfile plus `fly.toml` |

### Why Render

- **It's free and needs no credit card.** That suits a student project that runs for one term.
- **Secret files fit our existing setting.** `DB_SSL_CA` is a file path. On Render we upload `ca.pem` as a secret file and point `DB_SSL_CA` at it, with no change to `app/config.py` or `app/db.py`.
- **It's the simplest deploy.** Render builds Python directly from the repo (no Dockerfile) and provides HTTPS automatically, which the Vercel frontend needs.
- **Runner-up: Fly.io.** It's the cheapest way to avoid cold starts, but it needs a card on file and a Dockerfile.

## What the Free instance gives us

From Render's [compute plans](https://render.com/docs/compute-plans), [pricing](https://render.com/pricing) and [free tier](https://render.com/docs/free) pages:

| Limit | Free web service |
| --- | --- |
| CPU / RAM | **0.1 CPU, 512 MB RAM** (plan ID `free`) |
| Hours | 750 instance hours per workspace per month, enough for one service running all month. Spun-down time doesn't count. If the hours run out, free services are suspended until the next month. |
| Spin-down | After **15 minutes** with no inbound traffic. The next request wakes it in **about 1 minute**. |
| Bandwidth | 5 GB per month included on the Hobby workspace, then $0.15/GB. With no payment method on file, going over suspends free services for the rest of the month. |
| Other limits | One instance only, ephemeral filesystem (files written at runtime are lost on restart or redeploy), no shell access, no persistent disk, outbound email ports blocked. Render may restart the service at any time. |
| Cron jobs | **Not available on Free.** See [Scheduled jobs](#scheduled-jobs-adzuna-pipeline). |

0.1 CPU is slow. It's fine for the API itself, but heavy pandas or scikit-learn work during a request could be slow. If matching turns out to be too slow, the next step up is Starter (0.5 CPU, 512 MB, $7/month).

## Team access (needs a team decision)

**Teammates can't be added to a free workspace.** Render's [workspace docs](https://render.com/docs/team-members) say: "You can't add team members to a **Hobby** workspace." Hobby workspaces have one seat. Inviting members requires the **Pro** workspace plan at **$25/month** plus compute.

What this means for us:

- **One teammate owns the Render account.** Only that person can see the dashboard and logs and change environment variables.
- **Everyone can still deploy.** With auto-deploy on, every merge to `main` redeploys the backend. Teammates don't need dashboard access to ship code.
- **Don't share the login.** It would expose the account to everyone and gets around Render's seat limit.
- **The owner should probably be Jonathan.** The repository belongs to his personal GitHub account (`juanasal`), and only the owner of a personal repository can install a GitHub App such as Render's on it. If someone else owns the Render account, Jonathan still has to grant Render access to the repo.

**Open question for the team:** Who owns the Render account? Is one owner enough, or should we pay for Pro ($25/month) so everyone can see logs?

## Deployment steps (for the deployment ticket)

### 1. Account

1. The account owner signs up at [render.com](https://render.com) with GitHub. New accounts start in a free **Hobby** workspace.
2. Give Render's GitHub App access to `juanasal/cs467-job-hunting-ai` (see [Team access](#team-access-needs-a-team-decision)).

### 2. Create the web service

In the Render Dashboard, choose **New → Web Service**, pick the repository, and use these settings:

| Setting | Value |
| --- | --- |
| Branch | `main` |
| Root Directory | `backend` |
| Language / Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |
| Region | The region closest to the Aiven MySQL service, to reduce database latency |
| Auto-Deploy | On commit (each merge to `main` deploys) |

Render requires the app to listen on `0.0.0.0` and the `PORT` variable it provides. Don't use `--reload` in production.

### 3. Environment variables and the CA file

On the service's **Environment** page:

| Name | Value |
| --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | From the Aiven console (service **Overview → Connection information**) |
| `DB_SSL_CA` | `/etc/secrets/ca.pem` |
| `PYTHON_VERSION` | `3.13.5` (CI tests on 3.13. Render's default for new services is 3.14, which we don't test on.) |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Only once the deployed backend calls Adzuna |

Then, under **Secret Files**, click **+ Add Secret File** and name it `ca.pem`. Paste in the contents of the `ca.pem` downloaded from the Aiven console. Render makes it available at `/etc/secrets/ca.pem`.

Don't set `TEST_DB_*` on Render. Those settings are only for local integration tests. The backend doesn't need a `.env` file on Render because it reads these variables directly from the environment.

### 4. Check it

- Open `https://<service-name>.onrender.com/health`. It should return `{"status": "ok"}`. The first request after the service has been idle can take about a minute.
- Open `https://<service-name>.onrender.com/docs` for the API docs.

### 5. Aiven connection

Aiven MySQL requires SSL, and `app/db.py` turns SSL on whenever `DB_SSL_CA` is set. Render Free doesn't give the service its own fixed IP address. Render's outbound IP ranges (Dashboard → **Connect → Outbound**) are shared by every Render service in that region, so adding them to Aiven's IP allowlist adds little protection. The database is protected by its password and SSL, so keep `DB_PASSWORD` only in Render's environment settings.

## Likely cost

| Item | Cost |
| --- | --- |
| Backend web service (Free) | **$0/month** |
| Optional: Starter instance to avoid cold starts during demos or grading | $7/month, billed by the second, so switching for a few days costs a few dollars |
| Later: Render cron job for the Adzuna pipeline | About **$1/month** (Render's minimum per cron job; a short daily run uses well under $1 of compute) |
| Optional: Pro workspace so all teammates have access | $25/month plus compute |

## Scheduled jobs (Adzuna pipeline)

Free web services can't run on a schedule, and a sleeping service can't run an in-app timer. When the pipeline ticket comes up, there are two options:

- **Render cron job:** about $1/month. It uses full cron syntax, gets its own environment variables and secret files, and each run is limited to 12 hours.
- **GitHub Actions scheduled workflow:** free. It reuses the CI setup from JH-007. It needs the DB and Adzuna settings stored as GitHub Actions secrets.

That choice belongs to the pipeline ticket, not this one. Adzuna's rate limits and storage terms in [ADZUNA_RESEARCH.md](../ADZUNA_RESEARCH.md) apply either way.

## Known limitations and follow-up

- **Cold starts:** the first request after 15 idle minutes takes about 1 minute. The frontend should show a loading state, not treat the slow response as a failure.
- **CORS:** the backend doesn't allow cross-origin requests yet. Before the Vercel frontend can call the Render backend, a ticket needs to add FastAPI's CORS middleware that allows the Vercel domain.
- **Team access:** see the open question above.

## Sources

- Render: [pricing](https://render.com/pricing), [free tier](https://render.com/docs/free), [compute plans](https://render.com/docs/compute-plans), [workspace members](https://render.com/docs/team-members), [workspace plans](https://render.com/docs/new-workspace-plans), [environment variables and secret files](https://render.com/docs/configure-environment-variables), [web services](https://render.com/docs/web-services), [cron jobs](https://render.com/docs/cronjobs), [Python version](https://render.com/docs/python-version), [outbound IPs](https://render.com/docs/outbound-ip-addresses)
- Railway: [pricing](https://railway.com/pricing), [plans](https://docs.railway.com/reference/pricing/plans), [free trial](https://docs.railway.com/reference/pricing/free-trial), [app sleeping](https://docs.railway.com/reference/app-sleeping), [cron jobs](https://docs.railway.com/reference/cron-jobs)
- Fly.io: [pricing](https://docs.fly.io/about/pricing), [fly.toml reference](https://docs.fly.io/reference/configuration), [task scheduling](https://fly.io/docs/blueprints/task-scheduling/)

## AI use

The hosting research and this decision document (JH-008) were generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/LkGsFyhLhJYt2Z7JpRsQNB](https://claude.ai/artifact/LkGsFyhLhJYt2Z7JpRsQNB) documents the GenAI interaction that led to this document.
