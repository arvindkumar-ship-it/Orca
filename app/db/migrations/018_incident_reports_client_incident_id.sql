ALTER TABLE incident_reports ADD COLUMN client_incident_id text;
CREATE UNIQUE INDEX uniq_incident_reports_client_incident_id
  ON incident_reports(client_incident_id) WHERE client_incident_id IS NOT NULL;