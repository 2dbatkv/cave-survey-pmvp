-- Migration: Add is_admin column to users table
-- Date: 2025-01-11
-- Description: Adds admin flag to user accounts

-- Add is_admin column with default False
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

-- Update the first user to be admin (optional - comment out if not needed)
-- UPDATE users SET is_admin = TRUE WHERE id = 1;

-- Create index for admin queries (optional but recommended)
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);

-- Verify the migration
SELECT COUNT(*) as total_users,
       SUM(CASE WHEN is_admin THEN 1 ELSE 0 END) as admin_users
FROM users;
