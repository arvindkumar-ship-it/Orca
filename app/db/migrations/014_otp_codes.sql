-- 014_otp_codes.sql
-- otp_codes: matches app/models/otp.py's OTPCode model exactly.
-- Missing from the original Module 2A-2D migrations (model was added later for
-- POST /v1/auth/otp/* but the corresponding migration was never written).

CREATE TABLE IF NOT EXISTS otp_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_otp_codes_phone ON otp_codes (phone);
