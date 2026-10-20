# Adzuna API Research

## Test Setup

Tested the Adzuna Job Search API for JH-025 using a project API application created for the CS 467 Job Hunting AI project.

Four API requests were tested:

| Search term | Results saved |
| --- | ---: |
| `software engineer` | 3 |
| `remote software engineer` | 5 |
| `data analyst` | 5 |
| `project manager` | 5 |

All requests used:
- Country: US
- Page: 1
- Endpoint: `/v1/api/jobs/us/search/1`
- Test date: October 20, 2026

All four requests returned a successful `200` response, for a total sample of 18 job postings. The responses are saved in `documentation/samples/`. The saved responses do not contain the application ID or API key.

## Field Checklist

Based on the 18 job postings collected across the four test searches:

| Field | Observed in samples? | Notes |
| --- | --- | --- |
| Job ID | Yes | `id` identifies each job posting. |
| Title | Yes | `title` was available in the tested results. |
| Company | Yes | Company name is available through `company.display_name`. |
| Location | Yes | Usually includes `location.display_name` and an `area` hierarchy. Location detail can vary; some results only identify the country. |
| Latitude / Longitude | Usually | Coordinates were available for most tested jobs, but should not be assumed to be required fields. |
| Description | Yes, but shortened | Descriptions in the tested results were snippets rather than complete job descriptions and ended with an ellipsis. |
| Created date | Yes | `created` provides the posting date/time returned by Adzuna. |
| Job URL | Yes | `redirect_url` provides a link to the job through Adzuna. |
| Category | Yes | Includes a category `label` and `tag`. |
| Salary minimum / maximum | Yes in tested results | `salary_min` and `salary_max` were present in the tested samples. |
| Salary predicted flag | Yes | `salary_is_predicted` indicates whether the salary was predicted rather than directly provided. |
| Contract time | Sometimes | `contract_time`, such as `full_time` or `part_time`, was only present in some results. |
| Contract type | Sometimes | `contract_type`, such as `contract`, was only present in some results. |
| Remote / hybrid status | No structured field observed | No dedicated remote-work field was observed. Remote, hybrid, or onsite information sometimes appeared in the job description instead. |

## Key Findings and Limitations

- **Full job descriptions are not available in the tested search results.** All 18 descriptions were shortened and ended with an ellipsis. The application should therefore treat the `description` field as a snippet rather than a complete job description.
- **Remote-work status is not structured.** No dedicated remote, hybrid, or onsite field was observed. This information sometimes appears in the description, but relying only on keywords can be unreliable. For example, a search for `remote software engineer` also returned "Remote Sensing Software Engineer," where "remote" refers to remote sensing rather than remote work.
- **Some fields are optional or inconsistent.** Fields such as `contract_time` and `contract_type` appeared only in some results, so the application should handle them as optional.
- **Location detail varies.** Some jobs include a detailed city/state hierarchy and coordinates, while others may only identify the country.
- **Salary data may be predicted.** The `salary_is_predicted` field should be checked before treating salary values as employer-provided information.

## API Usage Requirements

The following requirements were reviewed using the official Adzuna API documentation and Terms of Service.

### API Limits

Adzuna's Terms of Service list the following default API limits:

- 25 requests per minute
- 250 requests per day
- 1,000 requests per week
- 2,500 requests per month

Adzuna notes that these default limits may change. The project account dashboard currently shows a 25-call test allowance and offers full API access with limits of 500 requests per day and 5,000 requests per month. The application should therefore not assume that the general default limits are the same as the limits assigned to the project account.

### Academic Use

Adzuna's Terms state that API use by an academic organization is permitted for a 14-day trial period for validating data coverage, quality, and usability. Continued academic use beyond this testing period may require written consent or a license agreement from Adzuna.

This should be clarified before the project depends on Adzuna for ongoing data collection or production use.

### Attribution

For personal or academic research, Adzuna requires published salary and vacancy data to acknowledge Adzuna as the source. The attribution should refer to "The Adzuna API" and link to the appropriate Adzuna website.

If the application displays Adzuna job listings, the Terms also contain specific attribution requirements for displayed advertisements.

### Job Descriptions

Adzuna's Search API documentation states that only a snippet of the job description is provided in search results. This matches all 18 postings collected during testing.

The project should not assume that complete job descriptions can be retrieved from the Search API.

### Data Use and Storage

Adzuna's Terms do not specify a general retention period for storing API job data in a database.

For academic organizations, API use beyond the 14-day validation and testing period may require written consent or a license agreement. The Terms also require data acquired from Adzuna to be removed from website pages when the API agreement is terminated.

Because the project plans to store and refresh Adzuna job data in its own database, the team should confirm that the planned storage and expiration approach is permitted before relying on the API for continued use.

## Questions / Decisions for the Team

The testing identified several items that should be considered before building features that depend on Adzuna data:

- **Job descriptions:** The Search API provides description snippets rather than complete job descriptions. Confirm whether snippets are sufficient for the planned job matching and AI features.
- **Remote status:** There is no structured remote/hybrid/onsite field in the tested results. Decide whether this information should be inferred from description text or treated as unavailable when it cannot be determined reliably.
- **Salary:** Some salary values are predicted by Adzuna. Decide whether predicted salaries should be displayed or processed differently from non-predicted salaries.
- **Optional fields:** Fields such as `contract_time` and `contract_type` are not consistently available. The data model should allow these fields to be missing.
- **API access:** The current project account has limited test access. Confirm whether paid or otherwise approved API access will be needed for continued development and the final demo.
- **Academic use and storage:** Confirm that the project's planned database storage, refresh, and expiration approach is permitted for continued academic use before implementing the full data pipeline.