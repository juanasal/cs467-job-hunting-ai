# CI / GitHub Actions Quick Guide

This project uses **Continuous Integration (CI)** through **GitHub Actions** to automatically check code changes before they are merged.

The goal is simple: catch build errors and failed tests early.

For ownership, test selection, examples, and local testing commands, see the [Testing Guide](TESTING_GUIDE.md). Developers should add or update relevant tests alongside their features in the same pull request.

## How It Works

When a pull request is opened or updated, GitHub can automatically run checks such as:

```text
Pull Request
    ↓
GitHub Actions workflow starts
    ↓
Runner checks out the code
    ↓
Frontend build runs
    ↓
Backend tests run
    ↓
Checks pass or fail
```

A green check means the automated checks passed.

A red check means something failed and should be reviewed before merge.

---

## Key Terms

### Workflow

A **workflow** is the full automated CI process.

Workflow files are stored in:

```text
.github/workflows/
```

They are written in YAML.

### Trigger

A **trigger** determines when the workflow runs.

Common triggers for this project are:

```yaml
on:
  pull_request:
  push:
    branches:
      - main
```

This runs CI when a pull request changes and when code is pushed to `main`.

### Job

A **job** is a group of related CI steps.

Example:

```text
Build and Test
```

### Runner

A **runner** is the temporary computer that executes the job.

For example:

```yaml
runs-on: ubuntu-latest
```

means GitHub provides an Ubuntu machine to run the checks.

### Step

A **step** is one command or action inside a job.

Example:

```yaml
- name: Run tests
  run: pytest
```

---

## Typical Project Checks

### Frontend

```bash
npm ci
npm run build
```

`npm ci` installs the project's dependencies.

`npm run build` verifies that the frontend can successfully build.

### Backend

```bash
pytest
```

`pytest` runs the Python test suite.

If a test fails, the CI workflow fails.

---

## Why Commands Pass or Fail

Programs return an **exit code** when they finish.

```text
0       = success
nonzero = failure
```

GitHub Actions uses these exit codes to determine whether a step passed.

For example:

```text
pytest
   ↓
test fails
   ↓
nonzero exit code
   ↓
GitHub Action fails
```

---

## Debugging Failed CI

If a check fails:

1. Open the repository's **Actions** tab.
2. Open the failed workflow run.
3. Open the failed job.
4. Find the failed step.
5. Read the command output.

The same command can usually be run locally to reproduce the problem.

For example:

```bash
npm run build
```

or:

```bash
pytest
```

---

## Secrets

Do not place API keys, passwords, or tokens directly in workflow files.

Bad:

```yaml
API_KEY: my-secret-key
```

Sensitive values should use GitHub Secrets or local environment configuration.

Example:

```yaml
API_KEY: ${{ secrets.API_KEY }}
```

---

## Developer Expectation

Before merging a pull request:

- CI checks should pass.
- Build errors should be fixed.
- Failed tests should be investigated.
- Secrets should not be committed.
- Developers should understand what each automated check is validating.

The purpose of CI is not to replace code review. It gives reviewers an automated signal that the code still builds and passes the project's tests.

---

## CI Crash Course

For more information on the CI process, see https://chatgpt.com/s/t_6ae38d83a7f88191921af58d31f153df for a crash course.
