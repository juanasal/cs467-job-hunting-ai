# Database (MySQL)

SQL scripts that create and update the MySQL database. The tables follow [`documentation/DATA_CONTRACT.md`](../../documentation/DATA_CONTRACT.md). Requires MySQL 8.0.16 or newer.

```text
backend/db/
├── migrations/
│   ├── 001_create_tables.sql
│   ├── 002_add_jobs_first_seen_at.sql
│   ├── 003_add_match_results_recalculation_flag.sql
│   ├── 003_create_user_sessions.sql
│   ├── 004_add_strict_preferences.sql
│   └── 005_add_jobs_is_active.sql
└── seed/
    └── dev_seed.sql
```

## Set up a new development database

Run from the repository root. The commands prompt for the database password.

```bash
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/migrations/001_create_tables.sql
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/migrations/002_add_jobs_first_seen_at.sql
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/migrations/003_add_match_results_recalculation_flag.sql
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/migrations/003_create_user_sessions.sql
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/migrations/004_add_strict_preferences.sql
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/migrations/005_add_jobs_is_active.sql

# 2. (Optional) Load the example data
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/seed/dev_seed.sql
```

For Aiven, also add `--ssl-mode=REQUIRED`. In MySQL Workbench, select the target schema and run each migration in the same order.

Migration `004_add_strict_preferences.sql` defaults the three strict flags to
false for existing searches. It also clears legacy Adzuna salary bounds and
currency because the prior importer did not verify units, and marks affected
matches for recalculation. Apply it before deploying the updated preferences API.

Migration `005_add_jobs_is_active.sql` adds `jobs.is_active`, which defaults to
true so existing jobs stay active. The recommendations API uses the preference
columns from migration `004` and the job activity flag from migration `005`.
For an existing development database, check which migrations have been applied
and apply all missing migrations in order before using the API.

The session migration uses `CREATE TABLE IF NOT EXISTS`. This makes it safe to run on a development database where `user_sessions` was already created by the earlier `002_create_sessions.sql` migration. If the table already exists, MySQL leaves it unchanged. Do not rerun migrations `001` or `002` against an existing database; migrations are intended to run once, in order.

Optionally load made-up development data:

```bash
mysql -h <DB_HOST> -P <DB_PORT> -u <DB_USER> -p <DB_NAME> < backend/db/seed/dev_seed.sql
```

Never load `dev_seed.sql` into a database containing real users.

## Changing the schema

1. Never edit a migration that has already been merged or applied by teammates.
2. Add a new migration with the next number and a descriptive name.
3. Update `documentation/DATA_CONTRACT.md` when fields or shared data conventions change.
4. Update `dev_seed.sql` if the example data no longer fits.
5. State in the PR which migration teammates need to run.

## Tables

| Table | Primary key | Holds |
|---|---|---|
| `users` | `user_id` | Login email, password hash, creation time |
| `user_profiles` | `user_id` | Education and experience level |
| `user_skills` | `user_id`, `skill` | Profile skills |
| `search_preferences` | `user_id` | Salary range, currency, result count, and strictness flags for location, workplace, and salary |
| `preference_job_titles` | `user_id`, `job_title` | Desired job titles |
| `preference_locations` | `user_id`, `location` | Preferred locations |
| `preference_workplace_types` | `user_id`, `workplace_type` | Acceptable workplace arrangements |
| `jobs` | `job_id` | Standardized job postings |
| `match_results` | `user_id`, `job_id` | Match score, explanation, creation time |
| `match_result_skills` | `user_id`, `job_id`, `skill` | Skills that matched |
| `job_tracking` | `user_id`, `job_id` | Saved, dismissed, or applied status |
| `user_sessions` | `session_id` | Hashed session token, activity, expiration, and revocation state |

The `user_sessions` table stores only the SHA-256 hash of each session token. `last_activity_at` supports the 30-minute idle timeout, `expires_at` enforces the seven-day absolute lifetime, and `revoked_at` records logout revocation. The table indexes `token_hash`, `user_id`, and `expires_at`; deleting a user cascades to their sessions.

## How the records connect

```mermaid
erDiagram
    users ||--o| user_profiles : "has"
    users ||--o{ user_skills : "has"
    users ||--o| search_preferences : "has"
    users ||--o{ preference_job_titles : "wants"
    users ||--o{ preference_locations : "wants"
    users ||--o{ preference_workplace_types : "accepts"
    users ||--o{ match_results : "receives"
    jobs  ||--o{ match_results : "scored in"
    match_results ||--o{ match_result_skills : "lists"
    users ||--o{ job_tracking : "tracks"
    jobs  ||--o{ job_tracking : "tracked in"
    users ||--o{ user_sessions : "has"
```

Deleting a user deletes all of their rows in the other tables, including their authentication sessions. Deleting a job deletes its match results and tracking rows.

## Conventions

- `DATETIME` timestamps are stored in UTC.
- Missing optional values are `NULL`, not empty strings, zero, or `N/A`.
- Enumerated fields are enforced by MySQL `ENUM` columns.
- Salaries are annual `DECIMAL(12,2)` values with currency stored separately. Job salary bounds require verified annual units and currency at ingestion.
- List fields in the data contract are stored as one row per item and combined by the API.

## Known limitations

- Deleting a job also deletes users' saved/applied rows for it, so don't delete expired jobs. Set `is_active = FALSE` instead: inactive jobs are left out of the recommendations feed but can still be opened from job details, so saved and applied jobs keep working. Nothing marks jobs inactive automatically yet, and re-importing a job doesn't change `is_active`.
- The data contract requires skills, job titles, and locations, but the database can't check that a user has at least one of each. The backend must check this before saving.

## AI use

The database code and documentation (JH-005: `migrations/001_create_tables.sql`, `seed/dev_seed.sql`, and this README) was generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/2KjzB62VP41MYZnzSA9vuH](https://claude.ai/artifact/2KjzB62VP41MYZnzSA9vuH) documents the GenAI interaction that led to my code.
