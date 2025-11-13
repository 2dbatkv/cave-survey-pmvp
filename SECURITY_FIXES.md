# Security Fixes - January 2025

This document describes the critical security fixes applied to CaveSurveyTool.

## Summary of Changes

Five critical security vulnerabilities have been fixed:

1. ✅ **Fixed password hashing** - Now using proper bcrypt
2. ✅ **Fixed CORS configuration** - Removed wildcard origin
3. ✅ **Added admin authentication** - Protected admin endpoints
4. ✅ **Removed default secret key** - Now required in environment
5. ✅ **Added startup validation** - Fails fast on misconfiguration

---

## 🔴 CRITICAL: Action Required

### 1. Generate and Set SECRET_KEY (REQUIRED)

The application will **NOT START** without a proper SECRET_KEY.

**Generate a secure key:**
```bash
openssl rand -hex 32
```

**Set it in your environment:**

**For local development:**
```bash
# In cave-local/.env
SECRET_KEY=your-generated-key-here
```

**For Render deployment:**
1. Go to your Render dashboard
2. Navigate to your service → Environment
3. Add/update `SECRET_KEY` with your generated value

---

### 2. Run Database Migration (REQUIRED)

A new `is_admin` column was added to the `users` table.

**Option A: Automatic (Recommended)**
```bash
cd cave-local
python -m migrations.run_migration
```

**Option B: Manual SQL**
```bash
psql your_database_url
```
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);
```

---

### 3. Create an Admin User (REQUIRED)

After running the migration, make at least one user an admin:

**Option A: Using the migration script**
```bash
cd cave-local
python -m migrations.run_migration --make-admin your_username
```

**Option B: Manual SQL**
```sql
UPDATE users SET is_admin = TRUE WHERE username = 'your_username';
```

**Option C: Direct database query**
```python
from app.database import SessionLocal, User

db = SessionLocal()
user = db.query(User).filter(User.username == "your_username").first()
if user:
    user.is_admin = True
    db.commit()
    print(f"User {user.username} is now an admin")
db.close()
```

---

### 4. Update CORS Origins (REQUIRED for Production)

Update the `ALLOWED_ORIGINS` environment variable:

**For local development:**
```bash
ALLOWED_ORIGINS=http://localhost:5173
```

**For production:**
```bash
ALLOWED_ORIGINS=https://your-frontend.netlify.app,http://localhost:5173
```

**For Render deployment:**
Update in Render dashboard → Environment → `ALLOWED_ORIGINS`

---

### 5. Regenerate All User Passwords (CRITICAL)

⚠️ **IMPORTANT:** Old passwords were stored with the broken "TEMP_" prefix.

**All users must reset their passwords:**

1. Users cannot log in with old passwords
2. Options to handle this:
   - **Option A:** Create a password reset endpoint
   - **Option B:** Have users re-register with new accounts
   - **Option C:** Manually reset passwords in database:

```python
from app.database import SessionLocal, User
from app.auth import get_password_hash

db = SessionLocal()
user = db.query(User).filter(User.username == "username").first()
if user:
    user.hashed_password = get_password_hash("new_secure_password")
    db.commit()
db.close()
```

---

## Details of Each Fix

### 1. Password Hashing Fixed

**File:** `cave-local/app/auth.py`

**Before (INSECURE):**
```python
def get_password_hash(password: str) -> str:
    return f"TEMP_{password}"  # Plaintext!
```

**After (SECURE):**
```python
def get_password_hash(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise ValueError("Failed to hash password")
```

**Impact:**
- Passwords now properly hashed with bcrypt
- Old "TEMP_" passwords will not work
- All users need to reset passwords

---

### 2. CORS Configuration Fixed

**File:** `cave-local/app/main.py`

**Before (INSECURE):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ANY WEBSITE can access!
    allow_credentials=False,
)
```

**After (SECURE):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Only whitelisted origins
    allow_credentials=True,
)
```

**Impact:**
- Only explicitly allowed origins can access the API
- Prevents CSRF and data exfiltration attacks

---

### 3. Admin Authentication Added

**Files:**
- `cave-local/app/auth.py` (new function)
- `cave-local/app/database.py` (new column)
- `cave-local/app/main.py` (endpoint updated)

**New Admin Check Function:**
```python
async def get_current_admin_user(current_user: User = Depends(get_current_active_user)):
    """Verify that the current user has admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
```

**Protected Endpoint:**
```python
@app.get("/admin/feedback")
def view_feedback(
    current_user: User = Depends(get_current_admin_user),  # NEW
    db: Session = Depends(get_db)
):
    # Only admins can access
```

**Impact:**
- Admin endpoints now require authentication
- Only users with `is_admin=True` can access
- Prevents unauthorized access to sensitive data

---

### 4. Default Secret Key Removed

**File:** `cave-local/app/config.py`

**Before (INSECURE):**
```python
secret_key: str = "change-this-in-production"
```

**After (SECURE):**
```python
# SECRET_KEY is required - no default provided for security
# Generate with: openssl rand -hex 32
secret_key: str  # No default!
```

**Impact:**
- Application fails to start if SECRET_KEY not set
- Forces proper configuration
- Prevents JWT token forgery

---

### 5. Startup Validation Added

**File:** `cave-local/app/main.py`

**New Startup Check:**
```python
@app.on_event("startup")
async def validate_configuration():
    """Validate critical environment variables and configuration on startup."""
    errors = []

    if not settings.secret_key:
        errors.append("SECRET_KEY environment variable is not set")
    elif len(settings.secret_key) < 32:
        errors.append("SECRET_KEY is too short")

    if not settings.database_url:
        errors.append("DATABASE_URL environment variable is not set")

    if errors:
        raise ValueError("Configuration validation failed")
```

**Impact:**
- Application fails fast on misconfiguration
- Clear error messages for missing config
- Prevents deployment with insecure settings

---

## Testing the Fixes

### 1. Test Password Hashing
```bash
# Register a new user
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"securepass123"}'

# Check database - password should be bcrypt hash
psql your_database_url -c "SELECT username, hashed_password FROM users WHERE username='testuser';"
# Should see: $2b$12$... (bcrypt hash, NOT TEMP_password)
```

### 2. Test CORS
```bash
# This should be rejected (wrong origin)
curl -X GET http://localhost:8000/ \
  -H "Origin: https://evil-site.com"

# This should work (allowed origin)
curl -X GET http://localhost:8000/ \
  -H "Origin: http://localhost:5173"
```

### 3. Test Admin Protection
```bash
# Try to access admin endpoint without auth (should fail)
curl -X GET http://localhost:8000/admin/feedback
# Expected: 401 Unauthorized

# Try with non-admin user (should fail)
curl -X GET http://localhost:8000/admin/feedback \
  -H "Authorization: Bearer <non-admin-token>"
# Expected: 403 Forbidden

# Try with admin user (should work)
curl -X GET http://localhost:8000/admin/feedback \
  -H "Authorization: Bearer <admin-token>"
# Expected: 200 OK with feedback data
```

### 4. Test Startup Validation
```bash
# Remove SECRET_KEY and try to start
unset SECRET_KEY
uvicorn app.main:app
# Expected: ValueError: Configuration validation failed
```

---

## Deployment Checklist

Before deploying to production:

- [ ] Generate secure SECRET_KEY (openssl rand -hex 32)
- [ ] Set SECRET_KEY in production environment
- [ ] Run database migration (add is_admin column)
- [ ] Create at least one admin user
- [ ] Update ALLOWED_ORIGINS for production frontend URL
- [ ] Force all users to reset passwords
- [ ] Test all endpoints with new authentication
- [ ] Verify CORS only allows intended origins
- [ ] Verify admin endpoints reject non-admin users
- [ ] Check logs for startup validation messages

---

## Additional Recommendations

While the immediate critical issues are fixed, consider these additional improvements:

1. **Add rate limiting** to prevent brute force attacks
2. **Implement password reset** endpoint for users
3. **Add email verification** for new registrations
4. **Enable HTTPS only** in production (set `secure=True` on cookies)
5. **Add logging** for failed authentication attempts
6. **Implement account lockout** after multiple failed login attempts
7. **Add 2FA support** for admin accounts

---

## Questions?

If you encounter any issues applying these fixes:

1. Check the logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure database migration completed successfully
4. Verify at least one admin user exists

For additional help, review the code comments in:
- `cave-local/app/auth.py`
- `cave-local/app/main.py`
- `cave-local/migrations/run_migration.py`
