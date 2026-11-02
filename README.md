# cs467-job-hunting-ai
AI-powered web application for finding job opportunities that match a user's skills and preferences.

## Documentation Index

| Document | Description |
| --- | --- |
| [Contribution Guide](documentation/CONTRIBUTION_GUIDE.md) | Ticket, branch, commit, review, and merge workflow, plus local configuration and secret-handling expectations. |
| [CI / GitHub Actions Guide](documentation/CI_GUIDE.md) | CI concepts, workflow terminology, typical checks, and how to investigate failed runs. |
| [Testing Guide](documentation/TESTING_GUIDE.md) | Test ownership, selecting and writing tests alongside features, test data, local commands, and pull request expectations. |
| [Data Contract](documentation/DATA_CONTRACT.md) | Shared MVP entities, field types, allowed values, relationships, and conventions for the API, database, ingestion, and matching engine. |
| [Adzuna API Research](documentation/ADZUNA_RESEARCH.md) | Findings from sample job searches, available fields, and limitations of the external job data. |
| [Backend README](backend/README.md) | FastAPI setup, environment settings, Adzuna client usage, server startup, tests, and API error format. |
| [Database README](backend/db/README.md) | MySQL setup, migrations, development seed data, table relationships, and schema conventions. |
| [Frontend README](frontend/my-react-app/README.md) | React/Vite starter-template notes, plugin options, and lint configuration guidance. |

### Reference Data

| Resource | Description |
| --- | --- |
| [Software engineer sample](documentation/samples/adzuna_search_sample.json) | Saved Adzuna response used by the client tests. |
| [Remote software engineer sample](documentation/samples/adzuna_remote_software_engineer_sample.json) | Saved response for a remote software engineer search. |
| [Data analyst sample](documentation/samples/adzuna_data_analyst_sample.json) | Saved response for a data analyst search. |
| [Project manager sample](documentation/samples/adzuna_project_manager_sample.json) | Saved response for a project manager search. |
