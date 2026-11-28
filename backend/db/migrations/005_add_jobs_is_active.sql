-- JH-041: Mark jobs that should no longer appear in recommendation feeds.
-- Existing jobs stay active. Inactive jobs are kept so saved/applied rows remain.

ALTER TABLE jobs
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
