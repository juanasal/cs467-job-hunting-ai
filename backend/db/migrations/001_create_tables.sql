-- 001_create_tables.sql
-- Creates the MVP tables described in documentation/DATA_CONTRACT.md.
-- Run once on an empty database (see backend/db/README.md).
-- Timestamps are stored in UTC.

-- ---------------------------------------------------------------------------
-- User account
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    user_id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- User profile (one per user)
-- ---------------------------------------------------------------------------
CREATE TABLE user_profiles (
    user_id          INT UNSIGNED NOT NULL,
    education_level  ENUM('high_school', 'associate', 'bachelor', 'master', 'doctorate', 'other') NOT NULL,
    experience_level ENUM('entry', 'mid', 'senior') NOT NULL,
    PRIMARY KEY (user_id),
    CONSTRAINT fk_user_profiles_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Profile skills list. The primary key stops the same skill being added twice
-- for one user (comparison is case-insensitive, so "SQL" and "sql" match).
CREATE TABLE user_skills (
    user_id INT UNSIGNED NOT NULL,
    skill   VARCHAR(100) NOT NULL,
    PRIMARY KEY (user_id, skill),
    CONSTRAINT fk_user_skills_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Search preferences (one per user)
-- ---------------------------------------------------------------------------
CREATE TABLE search_preferences (
    user_id         INT UNSIGNED  NOT NULL,
    salary_min      DECIMAL(12,2) NULL,
    salary_max      DECIMAL(12,2) NULL,
    salary_currency CHAR(3)       NOT NULL DEFAULT 'USD',
    result_count    INT UNSIGNED  NOT NULL,
    PRIMARY KEY (user_id),
    CONSTRAINT fk_search_preferences_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT chk_search_preferences_result_count CHECK (result_count > 0),
    CONSTRAINT chk_search_preferences_salary_range
        CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Preference lists. Each primary key prevents duplicate entries per user.
CREATE TABLE preference_job_titles (
    user_id   INT UNSIGNED NOT NULL,
    job_title VARCHAR(150) NOT NULL,
    PRIMARY KEY (user_id, job_title),
    CONSTRAINT fk_preference_job_titles_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE preference_locations (
    user_id  INT UNSIGNED NOT NULL,
    location VARCHAR(150) NOT NULL,
    PRIMARY KEY (user_id, location),
    CONSTRAINT fk_preference_locations_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE preference_workplace_types (
    user_id        INT UNSIGNED NOT NULL,
    workplace_type ENUM('remote', 'hybrid', 'onsite') NOT NULL,
    PRIMARY KEY (user_id, workplace_type),
    CONSTRAINT fk_preference_workplace_types_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Job postings (standardized listings from Adzuna or another source)
-- ---------------------------------------------------------------------------
CREATE TABLE jobs (
    job_id              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    external_job_id     VARCHAR(100)  NOT NULL,
    source              VARCHAR(50)   NOT NULL,
    title               VARCHAR(255)  NOT NULL,
    company             VARCHAR(255)  NULL,
    location            VARCHAR(255)  NULL,
    workplace_type      ENUM('remote', 'hybrid', 'onsite', 'unknown') NOT NULL DEFAULT 'unknown',
    salary_min          DECIMAL(12,2) NULL,
    salary_max          DECIMAL(12,2) NULL,
    salary_currency     CHAR(3)       NULL,
    salary_is_predicted BOOLEAN       NULL,
    description         TEXT          NOT NULL,
    date_posted         DATE          NULL,
    job_url             VARCHAR(2048) NOT NULL,
    retrieved_at        DATETIME      NOT NULL,
    PRIMARY KEY (job_id),
    -- The same source listing is stored only once; re-fetches should update it.
    UNIQUE KEY uq_jobs_source_external_id (source, external_job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Match results (one current score per user/job)
-- ---------------------------------------------------------------------------
CREATE TABLE match_results (
    user_id           INT UNSIGNED NOT NULL,
    job_id            INT UNSIGNED NOT NULL,
    match_score       DECIMAL(5,2) NOT NULL,
    match_explanation TEXT         NOT NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, job_id),
    KEY idx_match_results_job (job_id),
    CONSTRAINT fk_match_results_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_match_results_job
        FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE CASCADE,
    CONSTRAINT chk_match_results_score CHECK (match_score BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Skills that matched for a given result. Removed automatically with the result.
CREATE TABLE match_result_skills (
    user_id INT UNSIGNED NOT NULL,
    job_id  INT UNSIGNED NOT NULL,
    skill   VARCHAR(100) NOT NULL,
    PRIMARY KEY (user_id, job_id, skill),
    CONSTRAINT fk_match_result_skills_result
        FOREIGN KEY (user_id, job_id) REFERENCES match_results (user_id, job_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Job tracking (one current status per user/job)
-- ---------------------------------------------------------------------------
CREATE TABLE job_tracking (
    user_id    INT UNSIGNED NOT NULL,
    job_id     INT UNSIGNED NOT NULL,
    status     ENUM('saved', 'dismissed', 'applied') NOT NULL,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, job_id),
    KEY idx_job_tracking_job (job_id),
    CONSTRAINT fk_job_tracking_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_job_tracking_job
        FOREIGN KEY (job_id) REFERENCES jobs (job_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
