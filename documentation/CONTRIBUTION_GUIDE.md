# Contribution Guide

This project uses a simple **branch → review → merge** workflow so team members can work in parallel without committing directly to `main`.

## 1. Pick or Create a Ticket

Before starting work:

- Choose an existing GitHub issue or create a new one.
- Make sure the issue clearly describes the work.
- Assign yourself to the issue.
- Note any dependencies or blockers.
- Use the project ticket ID in the branch name when available.

Example ticket:

```text
JH-012
```

## 2. Create a Branch

Start from the latest `main` branch:

```bash
git checkout main
git pull
git checkout -b feature/JH-012-job-dashboard
```

Recommended branch prefixes:

```text
feature/
fix/
docs/
test/
refactor/
```

Examples:

```text
feature/JH-012-job-dashboard
fix/JH-021-login-error
docs/JH-001-contribution-guide
```

## 3. Make Your Changes

Keep changes focused on the ticket being completed.

Before committing:

- Run relevant tests.
- Verify the application still builds.
- Do not commit secrets, passwords, API keys, or local environment files.
- Update documentation when behavior or configuration changes.
- Avoid unrelated changes in the same branch.

## 4. Commit Your Changes

Use concise commit messages that describe what changed.

Examples:

```text
Add profile preference form
Fix duplicate job handling
Document local database setup
```

## 5. Push Your Branch

Push the branch to GitHub:

```bash
git push -u origin feature/JH-012-job-dashboard
```

## 6. Open a Pull Request

Open a pull request into `main`.

The pull request should include:

- Related ticket or issue number.
- Short summary of the changes.
- Testing or validation performed.
- Known limitations or follow-up work.
- Any dependencies or risks reviewers should know about.

## 7. Review the Pull Request

At least one teammate should review the pull request before merge when practical.

Reviewers should check:

- The change satisfies the ticket requirements.
- The code is understandable and maintainable.
- Relevant testing or validation has been completed.
- No secrets or generated files were accidentally committed.
- The change does not create obvious conflicts with other project components.

If changes are requested, update the same branch and push the new commits.

## 8. Merge

After review and any required fixes:

- Merge the pull request into `main`.
- Delete the completed branch.
- Close the related issue if the work is complete.

Avoid direct commits to `main` unless the team explicitly agrees they are appropriate.

## Secrets and Local Configuration

Never commit:

```text
.env
API keys
passwords
database credentials
private keys
access tokens
```

Use `.env.example` to document required configuration values.

Each developer should create their own local `.env` file based on the example.

Example:

```bash
ADZUNA_APP_ID=your_app_id_here
ADZUNA_APP_KEY=your_app_key_here

DB_HOST=localhost
DB_PORT=3306
DB_NAME=job_hunting_ai
DB_USER=your_database_user
DB_PASSWORD=your_database_password
```

The real `.env` file should remain excluded through `.gitignore`.
