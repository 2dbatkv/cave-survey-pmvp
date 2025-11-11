-- Create hardcoded test user: caver / cave1234
-- This is the bcrypt hash of "cave1234"
-- Run this in Render PostgreSQL console

-- First, check if user exists
SELECT id, username, email FROM users WHERE username = 'caver';

-- If not exists, insert
INSERT INTO users (username, email, hashed_password, is_active, created_at)
SELECT 'caver', 'caver@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5SupWdClOnAGC', true, NOW()
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'caver');

-- Verify
SELECT id, username, email, is_active, created_at FROM users WHERE username = 'caver';
