
-- JH-017: Mark match results that need recalculation
-- after a user updates their matching profile.

ALTER TABLE match_results
ADD COLUMN needs_recalculation BOOLEAN NOT NULL DEFAULT FALSE;
