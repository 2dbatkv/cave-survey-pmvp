#!/usr/bin/env python3
"""
Database migration runner for CaveSurveyTool
Run with: python -m migrations.run_migration
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration_001():
    """Add is_admin column to users table"""
    logger.info("Running migration 001: Add is_admin column")

    migration_sql = """
    -- Add is_admin column with default False
    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

    -- Create index for admin queries
    CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);
    """

    try:
        with engine.connect() as conn:
            # Execute the migration
            conn.execute(text(migration_sql))
            conn.commit()

            # Verify
            result = conn.execute(text("""
                SELECT COUNT(*) as total_users,
                       SUM(CASE WHEN is_admin THEN 1 ELSE 0 END) as admin_users
                FROM users
            """))
            row = result.fetchone()
            logger.info(f"Migration complete. Total users: {row[0]}, Admin users: {row[1]}")

            return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def make_user_admin(username: str):
    """Make a specific user an admin"""
    logger.info(f"Making user '{username}' an admin")

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE users SET is_admin = TRUE WHERE username = :username RETURNING id"),
                {"username": username}
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Successfully made user '{username}' an admin")
                return True
            else:
                logger.warning(f"User '{username}' not found")
                return False

    except Exception as e:
        logger.error(f"Failed to make user admin: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--make-admin", type=str, help="Username to make admin")

    args = parser.parse_args()

    if args.make_admin:
        # Make specific user admin
        success = make_user_admin(args.make_admin)
    else:
        # Run migration
        success = run_migration_001()

    sys.exit(0 if success else 1)
