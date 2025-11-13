"""
Quick script to reset a user's password
Usage: python reset_password.py <username> <new_password>
"""
import sys
from app.database import SessionLocal, User
from app.auth import get_password_hash

if len(sys.argv) != 3:
    print("Usage: python reset_password.py <username> <new_password>")
    print("Example: python reset_password.py caver2 NewPassword123")
    sys.exit(1)

username = sys.argv[1]
new_password = sys.argv[2]

db = SessionLocal()
try:
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        print(f"✅ Password reset successfully for user: {username}")
        print(f"   New password: {new_password}")
    else:
        print(f"❌ User not found: {username}")
        print("\nAvailable users:")
        users = db.query(User).all()
        for u in users:
            print(f"   - {u.username}")
except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
finally:
    db.close()
