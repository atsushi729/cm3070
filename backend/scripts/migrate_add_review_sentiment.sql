-- One-time migration: add the `review_sentiments` table for UC2-A.
--
-- A fresh database gets this automatically via Base.metadata.create_all (see
-- app/main.py). Run this only against an EXISTING dev database that predates
-- the sentiment product integration:
--
--     psql "$DATABASE_URL" -f backend/scripts/migrate_add_review_sentiment.sql
--
-- Idempotent: safe to run more than once. No ENUM type — `label` is varchar.

CREATE TABLE IF NOT EXISTS review_sentiments (
    id           SERIAL PRIMARY KEY,
    text         TEXT NOT NULL,
    label        VARCHAR(20),
    score        DOUBLE PRECISION,
    latency_sec  DOUBLE PRECISION,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_review_sentiments_created_at
    ON review_sentiments (created_at);
