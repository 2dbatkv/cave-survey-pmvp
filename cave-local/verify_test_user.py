#!/usr/bin/env python3
"""
Verify the test user exists and test password verification
Run this in Render shell
"""

from app.database import SessionLocal, User
from app.auth import get_user_by_username, verify_password
import bcrypt

def verify_test_user():
    db = SessionLocal()

    try:
        # Check if user exists
        user = get_user_by_username(db, "caver")

        if not user:
            print("✗ User 'caver' does NOT exist in database")
            print("\nPlease run create_test_user.py first")
            return

        print("✓ User 'caver' exists in database")
        print(f"  - ID: {user.id}")
        print(f"  - Username: {user.username}")
        print(f"  - Email: {user.email}")
        print(f"  - Hashed password: {user.hashed_password[:50]}...")
        print(f"  - Is active: {user.is_active}")

        # Test password verification with our auth.py function
        print("\nTesting password verification with auth.py:")
        try:
            result = verify_password("cave1234", user.hashed_password)
            print(f"  verify_password('cave1234', hash) = {result}")
        except Exception as e:
            print(f"  ✗ Error in verify_password: {e}")

        # Test with direct bcrypt
        print("\nTesting password verification with direct bcrypt:")
        try:
            password_bytes = "cave1234".encode('utf-8')
            hashed_bytes = user.hashed_password.encode('utf-8')
            result = bcrypt.checkpw(password_bytes, hashed_bytes)
            print(f"  bcrypt.checkpw('cave1234', hash) = {result}")
        except Exception as e:
            print(f"  ✗ Error in bcrypt.checkpw: {e}")

        # Try to update password with direct bcrypt hash
        print("\nRecreating password hash with direct bcrypt:")
        try:
            password = "cave1234"
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            new_hash = bcrypt.hashpw(password_bytes, salt)
            new_hash_str = new_hash.decode('utf-8')

            print(f"  New hash: {new_hash_str[:50]}...")

            # Update user
            user.hashed_password = new_hash_str
            db.commit()

            # Verify new hash
            check = bcrypt.checkpw(password_bytes, new_hash)
            print(f"  Verification: {check}")

            if check:
                print("\n✓ Password updated successfully!")
                print("  Try logging in again with: caver / cave1234")

        except Exception as e:
            print(f"  ✗ Error updating password: {e}")
            db.rollback()

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Verifying test user and password...")
    print("=" * 60)
    verify_test_user()
    print("=" * 60)
