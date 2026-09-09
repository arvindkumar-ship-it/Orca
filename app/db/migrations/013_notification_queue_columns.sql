-- Module 13 canonical rewrite — matches ORM model app/models/notification.py
ALTER TABLE notification_queue
  ADD COLUMN IF NOT EXISTS delivery_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'en',
  ADD COLUMN IF NOT EXISTS full_screen boolean NOT NULL DEFAULT false;

-- notification_queue.read_at assumed to already exist (Module 23).
