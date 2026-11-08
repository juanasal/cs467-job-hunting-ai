-- Track when each job was first seen.

ALTER TABLE jobs
    ADD COLUMN first_seen_at DATETIME NULL AFTER retrieved_at;

UPDATE jobs
SET first_seen_at = retrieved_at;

ALTER TABLE jobs
    MODIFY COLUMN first_seen_at DATETIME NOT NULL;