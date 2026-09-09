CREATE TABLE ack_timers (
    id              UUID PRIMARY KEY,
    incident_report_id UUID NOT NULL REFERENCES incident_reports(id) ON DELETE CASCADE,
    on_timeout_state TEXT NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uniq_active_ack_timer_per_incident
    ON ack_timers (incident_report_id)
    WHERE active = true;

CREATE INDEX idx_ack_timers_due
    ON ack_timers (expires_at)
    WHERE active = true;