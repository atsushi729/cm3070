-- One-time migration: add booking + Google Calendar columns to `reservations`.
--
-- A fresh database gets these automatically via Base.metadata.create_all (see
-- app/main.py). Run this only against an EXISTING dev database that predates the
-- booking/calendar feature:
--
--     psql "$DATABASE_URL" -f backend/scripts/migrate_add_booking_columns.sql
--
-- Idempotent: safe to run more than once.

DO $$ BEGIN
    CREATE TYPE bookingstatus AS ENUM ('draft', 'confirmed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE calendarsyncstatus AS ENUM ('not_synced', 'synced', 'failed', 'disabled');
EXCEPTION WHEN duplicate_object THEN null; END $$;

ALTER TABLE reservations
    ADD COLUMN IF NOT EXISTS booking_status bookingstatus NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS confirmation_ref varchar(16),
    ADD COLUMN IF NOT EXISTS confirmed_at timestamptz,
    ADD COLUMN IF NOT EXISTS calendar_event_id varchar(256),
    ADD COLUMN IF NOT EXISTS calendar_html_link varchar(512),
    ADD COLUMN IF NOT EXISTS calendar_sync_status calendarsyncstatus NOT NULL DEFAULT 'not_synced',
    ADD COLUMN IF NOT EXISTS calendar_synced_at timestamptz,
    ADD COLUMN IF NOT EXISTS calendar_sync_error text;

CREATE INDEX IF NOT EXISTS ix_reservations_booking_status
    ON reservations (booking_status);
CREATE INDEX IF NOT EXISTS ix_reservations_calendar_sync_status
    ON reservations (calendar_sync_status);
