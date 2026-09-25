-- Add human feedback to an existing review_sentiments table without
-- overwriting the original model output. Safe to run repeatedly.
-- Run from the repository root:
--   psql "postgresql://sme:sme_dev_pw@localhost:5432/sme" \
--     -f backend/scripts/migrate_add_sentiment_feedback.sql

ALTER TABLE review_sentiments
    ADD COLUMN IF NOT EXISTS feedback_label VARCHAR(20),
    ADD COLUMN IF NOT EXISTS feedback_at TIMESTAMPTZ;

ALTER TABLE review_sentiments
    DROP CONSTRAINT IF EXISTS ck_review_sentiments_feedback_label;

ALTER TABLE review_sentiments
    ADD CONSTRAINT ck_review_sentiments_feedback_label
    CHECK (feedback_label IS NULL OR feedback_label IN ('positive', 'neutral', 'negative'));
