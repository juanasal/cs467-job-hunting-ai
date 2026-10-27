-- dev_seed.sql
-- Made-up example records for local development. Development databases only.
-- Every name, email, company, and URL here is fictional; the password hashes
-- are placeholders that cannot be used to log in.
-- Run after all migrations, on a database with no existing rows.

INSERT INTO users (user_id, email, password_hash, created_at) VALUES
    (1, 'alex.student@example.com', 'placeholder-not-a-real-hash', '2026-10-19 18:30:00'),
    (2, 'sam.career@example.com',   'placeholder-not-a-real-hash', '2026-10-20 09:15:00');

INSERT INTO user_profiles (user_id, education_level, experience_level) VALUES
    (1, 'bachelor', 'entry'),
    (2, 'master',   'mid');

INSERT INTO user_skills (user_id, skill) VALUES
    (1, 'Python'), (1, 'SQL'), (1, 'React'),
    (2, 'Java'), (2, 'AWS'), (2, 'Docker');

INSERT INTO search_preferences (user_id, salary_min, salary_max, salary_currency, result_count) VALUES
    (1, 80000, NULL,   'USD', 20),
    (2, 110000, 150000, 'USD', 10);

INSERT INTO preference_job_titles (user_id, job_title) VALUES
    (1, 'Software Engineer'), (1, 'Data Engineer'),
    (2, 'Backend Engineer');

INSERT INTO preference_locations (user_id, location) VALUES
    (1, 'Portland, OR'), (1, 'Seattle, WA'),
    (2, 'Denver, CO');

INSERT INTO preference_workplace_types (user_id, workplace_type) VALUES
    (1, 'remote'), (1, 'hybrid'),
    (2, 'remote');

INSERT INTO jobs (job_id, external_job_id, source, title, company, location, workplace_type,
                  salary_min, salary_max, salary_currency, salary_is_predicted,
                  description, date_posted, job_url, retrieved_at) VALUES
    (1001, 'DEV-0001', 'example', 'Junior Software Engineer', 'Example Corp', 'Portland, OR', 'hybrid',
     75000, 90000, 'USD', FALSE,
     'We are seeking a software engineer with Python and SQL experience.',
     '2026-10-18', 'https://example.com/jobs/dev-0001', '2026-10-19 18:30:00'),
    (1002, 'DEV-0002', 'example', 'Frontend Developer', 'Sample Labs', NULL, 'remote',
     NULL, NULL, NULL, NULL,
     'Build accessible user interfaces with React and TypeScript.',
     NULL, 'https://example.com/jobs/dev-0002', '2026-10-19 18:30:00'),
    (1003, 'DEV-0003', 'example', 'Backend Engineer', 'Placeholder Inc', 'Denver, CO', 'unknown',
     120000, 140000, 'USD', TRUE,
     'Design REST APIs in Java and deploy services on AWS using Docker.',
     '2026-10-17', 'https://example.com/jobs/dev-0003', '2026-10-19 18:30:00');

INSERT INTO match_results (user_id, job_id, match_score, match_explanation, created_at) VALUES
    (1, 1001, 86, 'Strong skill alignment and the position matches the preferred experience level and location.', '2026-10-19 18:35:00'),
    (1, 1002, 72, 'React experience aligns with frontend UI work, and the role is remote.', '2026-10-19 18:35:00'),
    (2, 1003, 91, 'Java, AWS, and Docker all appear in the posting, which is in the preferred location.', '2026-10-20 09:20:00');

INSERT INTO match_result_skills (user_id, job_id, skill) VALUES
    (1, 1001, 'Python'), (1, 1001, 'SQL'),
    (1, 1002, 'React'),
    (2, 1003, 'Java'), (2, 1003, 'AWS'), (2, 1003, 'Docker');

INSERT INTO job_tracking (user_id, job_id, status, updated_at) VALUES
    (1, 1001, 'saved',   '2026-10-19 18:40:00'),
    (1, 1002, 'applied', '2026-10-20 10:05:00'),
    (2, 1003, 'saved',   '2026-10-20 09:25:00');
