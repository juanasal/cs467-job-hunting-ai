# Testing Guide

This guide explains how to develop tests alongside features for the Job Hunting AI project. The [CI guide](CI_GUIDE.md) explains how GitHub Actions runs checks; the [contribution guide](CONTRIBUTION_GUIDE.md) explains the pull request process.

Automated checks only verify the behavior covered by their assertions. A successful build or a green CI check does not mean every feature works.

## 1. Ownership and Timing

- The developer changing a feature adds or updates its relevant tests in the same pull request.
- The reviewer checks the tests as well as the implementation, including important missing cases.
- A teammate may coordinate shared fixtures and CI setup, but feature authors remain responsible for testing their changes.
- Add cross-feature tests when a complete workflow becomes usable. Do not wait until the end of the project to start testing.
- For a bug fix, add a regression test that reproduces the bug where practical, then confirm the fix makes it pass.

Before implementation, identify the feature's acceptance criteria and the cases that demonstrate them. Tests can be written before or alongside the code; they should be ready before merge.

## 2. Current Support and Planned Support

| Area | Current repository support | What to do now |
|---|---|---|
| Backend | pytest, FastAPI TestClient, and mocked Adzuna requests | Extend tests under `backend/tests/` |
| Frontend | Lint and production build commands | Run these checks; component testing requires additional setup |
| Database | MySQL migrations, development seed data, database helper tests, and job repository integration tests | Extend the existing tests and use a disposable MySQL database for integration testing |
| Browser workflows | No end-to-end test setup | Add Playwright when a connected user workflow exists |
| Recommendations | Data contract defines match results | Add scoring and quality tests alongside the matching engine |

Vitest with React Testing Library is the proposed frontend test setup. Playwright is the proposed browser test tool. Neither has a runnable test command in the current frontend package. Do not report these checks as passing until they have been implemented and run.

The [CI workflow](../.github/workflows/ci.yml) runs backend pytest tests and frontend lint/build checks on pull requests and pushes to `main`. It can also be started manually.

Database integration tests are available locally but require a separately configured MySQL test database. They are skipped when the required `TEST_DB_*` settings are not provided. A passing CI run does not, by itself, confirm that these MySQL integration tests were executed.

See the [CI guide](CI_GUIDE.md) for environments, reports, and merge enforcement.

## 3. Choose Tests for the Change

Use the smallest test scope that meaningfully verifies the behavior. Add integration or browser coverage where connections between components matter.

| Change | Relevant tests | Project example |
|---|---|---|
| Calculation, transformation, or validation | Unit tests | Normalize missing salary to `None`; enforce score bounds |
| API endpoint | API tests using TestClient | Validate request fields, status codes, response shape, and access rules |
| Database schema or persistence | Integration tests against MySQL | Prevent duplicate source/job IDs and verify transaction rollback |
| React component or form | Component tests once tooling exists | Validate preferences and display loading, empty, success, and error states |
| Connected user workflow | End-to-end tests once tooling exists | Enter preferences, find jobs, save one, and confirm it remains after reload |
| Matching algorithm | Unit tests and fixed evaluation cases | Rank a relevant job above an unrelated job for a known profile |
| Authentication or user-owned data | API and database access tests | User A cannot read or modify user B's profile or tracking records |

A documentation-only change usually needs review and link checks rather than new automated tests. Avoid tests that merely repeat implementation details without checking useful behavior.

## 4. Select Meaningful Cases

For each change, consider the cases that apply:

- **Expected behavior:** valid input produces the intended result.
- **Invalid input:** missing required fields, invalid enum values, and malformed values are rejected appropriately.
- **Boundaries:** empty lists, minimum/maximum values, pagination limits, and duplicate operations behave as specified.
- **Dependency failures:** timeouts, rate limits, unavailable services, and malformed responses are handled predictably.
- **Access and privacy:** unauthorized requests are rejected and responses do not expose passwords, hashes, or API credentials.
- **Persistence:** data survives a new request or reload when required.

Use [DATA_CONTRACT.md](DATA_CONTRACT.md) as the source for shared field rules. Examples include nullable salaries, `unknown` workplace types for incomplete external listings, match scores from 0–100, and tracking statuses of `saved`, `dismissed`, or `applied`.

Test the agreed behavior. If a requirement is unclear, resolve it with the team before encoding an assumption into tests.

### Example: Save a Job

When the user-facing job-saving feature is implemented, its tests should verify that:

1. Saving creates the correct relationship for the authenticated user and job.
2. Saving again follows the agreed duplicate-save behavior and leaves one current tracking record.
3. Invalid job IDs receive the agreed response.
4. Another user cannot change the first user's tracking record.
5. The UI reports success and handles an API failure.

Once the workflow is connected, add a browser test that saves a job, reloads, and confirms it remains saved.

This user-facing save workflow is separate from JH-028, which inserts or updates job postings retrieved from external sources.

## 5. Write and Organize Backend Tests

Place backend tests in `backend/tests/` using filenames such as `test_tracking.py` and function names beginning with `test_`. Group tests by feature or module. Put reusable pytest fixtures in `backend/tests/conftest.py` when multiple tests need them.

Structure tests as **arrange → act → assert**: prepare inputs, perform one meaningful action, and check the observable result.

This example uses the existing settings loader and can be run without a database or real credentials:

```python
from app.config import get_settings


def test_settings_convert_database_port_to_integer():
    # Arrange: use explicitly fake settings.
    env = {
        "DB_HOST": "localhost",
        "DB_PORT": "3306",
        "DB_NAME": "job_hunting_ai_test",
        "DB_USER": "test_user",
        "DB_PASSWORD": "fake-test-password",
    }

    # Act.
    settings = get_settings(env)

    # Assert: check the behavior callers rely on.
    assert settings.db_port == 3306
    assert isinstance(settings.db_port, int)
```

This illustrates the pattern; related settings coverage already exists, so do not add a duplicate just to increase the test count.

Use these existing tests as starting points:

- [test_main.py](../backend/tests/test_main.py): settings, health responses, and error privacy.
- [test_adzuna_client.py](../backend/tests/test_adzuna_client.py): saved response data, request assertions, pagination, and mocked HTTP failures.
- [test_job_normalizer.py](../backend/tests/test_job_normalizer.py): normalized job fields, missing values, timestamps, URLs, and workplace types.
- [test_db.py](../backend/tests/test_db.py): database connection helpers and transaction behavior.
- [test_job_repository.py](../backend/tests/test_job_repository.py): job upsert behavior, duplicate handling, timestamp validation, older imports, and database failures.

For API tests, assert the relevant response body and side effects as well as the status code. The existing basic API tests skip startup. When testing startup/settings behavior, use `with TestClient(app) as client:` and provide fake environment settings so the application lifespan runs.

Keep tests independent: restore environment variables and other changes through fixtures such as `monkeypatch`. Avoid leaking test routes or shared mutable data into unrelated tests.

## 6. Test Data and External Dependencies

- Use fake accounts and synthetic profile/job data. Never use real user records or production credentials.
- Mock Adzuna requests for ordinary tests. Saved responses are available in `documentation/samples/`; the current client tests show how to use `httpx.MockTransport`.
- Cover failures such as timeouts, HTTP 429/500 responses, invalid JSON, and unexpected response shapes where relevant to the client behavior.
- Keep ordinary tests independent of live network services, paid AI calls, and changing external job listings.
- If live-service smoke tests are added, run them separately with explicit configuration. They should not be required for ordinary local tests.
- Control timestamps, randomness, and ordering when they affect assertions. Avoid arbitrary sleeps.

### Database integration tests

Database integration tests are implemented in `backend/tests/test_db.py` and `backend/tests/test_job_repository.py`.

They use a separate MySQL test database configured through `TEST_DB_*` environment variables. Without these settings, the database-dependent tests are skipped.

Use a dedicated disposable database, apply migrations in numerical order, and isolate test data. Never run destructive test operations against shared development or production databases.

The job repository tests cover:

- Inserting new job postings.
- Updating existing postings without creating duplicates.
- Identifying jobs by the combination of `source` and `external_job_id`.
- Preserving `job_id` and `first_seen_at` during updates.
- Preventing older imports from overwriting newer job details.
- Validating retrieval timestamps.
- Preserving existing records when an import fails and its transaction rolls back.

Development seed data may help as a reference, but each test should establish the records it needs.

For the MySQL setup and test environment commands, see the [backend README](../backend/README.md#run-the-tests).

## 7. Recommendation Testing

When the matching engine is implemented, maintain a small versioned set of synthetic profiles and job listings with expected outcomes.

- Check score bounds and required output fields.
- Check expected ranking relationships, such as a Python role ranking above an unrelated role for a Python-focused profile.
- Cover missing job data, empty skills, duplicate skills, and case normalization where supported.
- Verify that matched skills and explanations are supported by the supplied profile and job data.

For deterministic scoring, assert exact results where they form part of the intended behavior. If an AI service is introduced, mock it for ordinary CI tests and evaluate live output separately against a documented quality rubric. Avoid exact text comparisons for variable generated explanations. Human review still helps assess recommendation usefulness.

## 8. Run Checks Locally

Run commands from the repository root unless shown otherwise. Use the project's supported Python and Node versions and install dependencies first.

### Backend

Follow [backend setup instructions](../backend/README.md) to create and activate a virtual environment. Then:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

While developing, run a specific file or test:

```bash
python -m pytest tests/test_adzuna_client.py
python -m pytest tests/test_main.py::test_health_returns_ok
python -m pytest tests/test_job_normalizer.py
python -m pytest tests/test_job_repository.py -v
```

These targeted commands also run from `backend/`.

The backend unit tests do not require live database access or Adzuna credentials.

The database integration tests run when a separate MySQL test database and the required `TEST_DB_*` settings are available. Otherwise, those tests are skipped.

Follow the [backend README database test setup](../backend/README.md#run-the-tests) to start a local MySQL container, apply migrations, and configure the test database.

After configuring the database, run:

```bash
python -m pytest tests/test_db.py tests/test_job_repository.py -v
python -m pytest -q
```

Check the pytest output for skipped tests. A passing test suite with skipped database integration tests is not equivalent to running the full integration suite against MySQL.

### Frontend

In a new terminal at the repository root:

```bash
cd frontend/my-react-app
npm ci
npm run lint
npm run build
```

Lint checks code rules; the build checks that the production bundle can be produced. Neither verifies user interactions. When frontend test tooling is added, document its exact local and noninteractive CI commands here. CI commands must exit after one run rather than remain in watch mode.

## 9. Pull Request Checklist

Before requesting review:

- [ ] The tests cover the changed behavior and relevant failure or boundary cases.
- [ ] Bug fixes include a regression test where practical.
- [ ] Tests use isolated fake data and do not require production systems.
- [ ] Relevant local checks pass.
- [ ] The pull request lists the commands run, their results, and any checks not run with the reason.
- [ ] New test prerequisites or commands are documented.

Reviewers should check that assertions could detect an incorrect implementation and that the chosen tests address the acceptance criteria. Passing existing tests alone is insufficient evidence for a new behavior.

A feature is ready to merge when its relevant tests are included, review is complete, and required CI checks pass. If necessary test infrastructure is missing, explicitly agree on how the feature will be validated and track the infrastructure work; do not silently describe untested behavior as covered.

## 10. Handling Failures and Maintaining Tests

Read the failed assertion and reproduce it locally using the same command and setup. Determine whether the implementation, the test, or the environment is wrong before changing anything.

Do not remove assertions, skip tests, or repeatedly rerun a flaky test just to get a green check. Fix the cause; if a temporary exception is necessary, document the reason, owner, and follow-up issue.

Update tests when agreed behavior changes. Keep useful regression tests even after their original bug is fixed. Review coverage as evidence of untested paths, rather than treating a percentage or test count as proof of correctness.
