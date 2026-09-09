CREATE TABLE IF NOT EXISTS notification_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_key text NOT NULL,
  locale text NOT NULL,
  title_template text NOT NULL,
  body_template text NOT NULL,
  UNIQUE(template_key, locale)
);

INSERT INTO notification_templates (template_key, locale, title_template, body_template) VALUES
('hazard_critical', 'en', 'Danger near {{beach_name}}', 'Danger near {{beach_name}}. Move to safe zone now. Help has been alerted. Live location shared.'),
('hazard_critical', 'hi', '{{beach_name}} ke paas khatra', '{{beach_name}} ke paas khatra hai. Turant safe zone ki taraf jaayein. Madad ko soochit kar diya gaya hai.'),
('sos_ack', 'en', 'Help is on the way', 'Your SOS was received. {{responder_name}} is en route. ETA {{eta_minutes}} min.'),
('contact_fanout_start', 'en', 'Emergency: {{contact_name}} needs help', 'Emergency near beach. {{instruction}} Live location: {{map_link}}'),
('contact_fanout_update', 'en', 'Rescue update', 'Status: {{status}}. Authority ack: {{ack}}. Live location updated.'),
('contact_fanout_stop', 'en', 'Situation resolved', 'The emergency has been marked {{reason}}. Live sharing has stopped.'),
('manual_ops_required', 'en', 'Manual intervention required', 'Incident {{incident_id}} unacknowledged through 112 fallback. Operator action required now.')
ON CONFLICT (template_key, locale) DO NOTHING;
