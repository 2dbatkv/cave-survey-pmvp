#!/usr/bin/env python3
"""
Create hardcoded test user: caver / cave1234
Run this in Render shell or locally
"""

from app.database import SessionLocal, User
from app.auth import get_user_by_username
import bcrypt

def create_test_user():
    db = SessionLocal()

    try:
        # Check if user exists
        existing = get_user_by_username(db, "caver")
        if existing:
            print("✓ User 'caver' already exists")
            return

        # Hash the password directly with bcrypt (bypassing our auth.py)
        password = "cave1234"
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        hashed_str = hashed.decode('utf-8')

        print(f"✓ Password hashed: {hashed_str[:50]}...")

        # Create user
        db_user = User(
            username="caver",
            email="caver@example.com",
            hashed_password=hashed_str,
            is_active=True
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        print(f"✓ User 'caver' created successfully!")
        print(f"  - ID: {db_user.id}")
        print(f"  - Username: {db_user.username}")
        print(f"  - Email: {db_user.email}")
        print(f"  - Active: {db_user.is_active}")
        print(f"\nLogin credentials:")
        print(f"  Username: caver")
        print(f"  Password: cave1234")

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Creating hardcoded test user...")
    print("=" * 60)
    create_test_user()
    print("=" * 60)
