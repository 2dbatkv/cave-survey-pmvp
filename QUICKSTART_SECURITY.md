# Quick Start: Applying Security Fixes

Follow these steps IN ORDER to apply the security fixes to your CaveSurveyTool deployment.

## Step 1: Generate SECRET_KEY (2 minutes)

```bash
# Generate a secure secret key
openssl rand -hex 32
```

Copy the output (e.g., `a1b2c3d4e5f6...`)

## Step 2: Update Environment Variables (3 minutes)

### For Local Development:

```bash
cd cave-local
cp .env.example .env
```

Edit `.env` and set:
```bash
SECRET_KEY=<your-generated-key-from-step-1>
DATABASE_URL=postgresql://user:password@localhost:5432/cave_survey
ALLOWED_ORIGINS=http://localhost:5173
```

### For Render Deployment:

1. Go to Render Dashboard
2. Select your `cave-survey-api` service
3. Go to "Environment" tab
4. Update/Add these variables:
   - `SECRET_KEY` = your generated key
   - `ALLOWED_ORIGINS` = `https://your-frontend.netlify.app`

## Step 3: Run Database Migration (2 minutes)

```bash
cd cave-local
python -m migrations.run_migration
```

Expected output:
```
INFO:__main__:Running migration 001: Add is_admin column
INFO:__main__:Migration complete. Total users: X, Admin users: 0
```

## Step 4: Create Admin User (1 minute)

Replace `your_username` with your actual username:

```bash
cd cave-local
python -m migrations.run_migration --make-admin your_username
```

Expected output:
```
INFO:__main__:Making user 'your_username' an admin
INFO:__main__:Successfully made user 'your_username' an admin
```

## Step 5: Test Locally (3 minutes)

```bash
cd cave-local
uvicorn app.main:app --reload
```

You should see:
```
INFO:app.main:Configuration validation passed
INFO:     Application startup complete.
```

Test the health endpoint:
```bash
curl http://localhost:8000/
```

## Step 6: Handle Existing Users (Important!)

⚠️ **All existing users need new passwords** (old passwords used broken hashing).

Options:

**A. Reset passwords manually:**
```bash
cd cave-local
python
```
```python
from app.database import SessionLocal, User
from app.auth import get_password_hash

db = SessionLocal()
user = db.query(User).filter(User.username == "username").first()
if user:
    user.hashed_password = get_password_hash("new_password")
    db.commit()
    print(f"Password updated for {user.username}")
db.close()
```

**B. Have users re-register** (delete old accounts if needed)

**C. Implement password reset feature** (recommended for production)

## Step 7: Deploy to Render (5 minutes)

```bash
# Commit the changes
git add .
git commit -m "Apply critical security fixes

- Fix password hashing to use bcrypt
- Fix CORS configuration
- Add admin authentication
- Remove default secret key
- Add startup validation"

# Push to trigger deployment
git push
```

Monitor the deployment logs for:
```
INFO:app.main:Configuration validation passed
```

## Verification Checklist

After deployment, verify:

- [ ] Application starts without errors
- [ ] Health endpoint returns 200: `curl https://your-api.onrender.com/`
- [ ] Can register new user with proper password hashing
- [ ] Can login with new credentials
- [ ] Admin endpoints require authentication
- [ ] Non-admin users get 403 on `/admin/feedback`
- [ ] CORS only allows your frontend origin

## Troubleshooting

### Error: "SECRET_KEY environment variable is not set"
→ Set SECRET_KEY in your .env file or Render environment

### Error: "Configuration validation failed"
→ Check all required env vars are set correctly

### Error: "relation 'users' does not exist"
→ Run database tables creation first (should happen automatically on startup)

### Error: Migration fails with "column 'is_admin' already exists"
→ Migration was already applied, safe to ignore

### Users can't login with old passwords
→ Expected! Old passwords used broken hashing. Reset passwords using Step 6.

---

## Next Steps (Optional but Recommended)

1. **Review full documentation:** See `SECURITY_FIXES.md` for complete details
2. **Test all endpoints:** Verify functionality after fixes
3. **Monitor logs:** Check for any authentication issues
4. **Implement password reset:** Allow users to self-service password resets
5. **Add rate limiting:** Protect against brute force attacks

---

**Estimated Total Time:** 15-20 minutes

For detailed information, see `SECURITY_FIXES.md`.
