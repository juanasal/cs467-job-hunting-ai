ALTER TABLE search_preferences
    ADD COLUMN strict_location BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN strict_workplace BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN strict_salary BOOLEAN NOT NULL DEFAULT FALSE;

-- Legacy Adzuna imports did not verify salary units.
START TRANSACTION;

UPDATE match_results AS matches
JOIN jobs AS job ON job.job_id = matches.job_id
SET matches.needs_recalculation = TRUE
WHERE job.source = 'adzuna'
  AND (job.salary_min IS NOT NULL OR job.salary_max IS NOT NULL
       OR job.salary_currency IS NOT NULL);

UPDATE jobs
SET salary_min = NULL, salary_max = NULL, salary_currency = NULL
WHERE source = 'adzuna'
  AND (salary_min IS NOT NULL OR salary_max IS NOT NULL
       OR salary_currency IS NOT NULL);

COMMIT;
