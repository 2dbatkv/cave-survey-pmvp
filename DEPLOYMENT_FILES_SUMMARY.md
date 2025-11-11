# Cave Survey Tool - Deployment Files Summary

This document summarizes all the deployment configuration files created for deploying the Cave Survey Tool to the cloud.

## Overview

The Cave Survey Tool has been prepared for cloud deployment with the following architecture:
- **Frontend**: React/Vite SPA hosted on Netlify
- **Backend**: FastAPI application on Render.com
- **Database**: PostgreSQL on Render.com
- **File Storage**: AWS S3 (optional)

---

## Created Files

### 1. `render.yaml` (Root directory)

**Purpose**: Automated deployment configuration for Render.com (Infrastructure as Code)

**What it does**:
- Defines both database and web service in one file
- Automatically creates PostgreSQL database with proper credentials
- Configures FastAPI backend with all environment variables
- Links database to web service automatically
- Enables one-click deployment via Render Blueprint

**Key Configuration**:
```yaml
services:
  - PostgreSQL database (cave-survey-db)
  - Python web service (cave-survey-api)
    - Build: pip install dependencies
    - Start: uvicorn with 2 workers
    - Health check: /health endpoint
    - Environment variables for database, auth, AWS, Datadog
```

**Location**: `/mnt/c/Users/ajbir/CaveSurveyTool/render.yaml`

---

### 2. `cave-frontend/netlify.toml`

**Purpose**: Frontend deployment configuration for Netlify

**What it does**:
- Specifies build directory and commands
- Configures SPA routing (redirects all routes to index.html)
- Sets security headers (XSS protection, frame options)
- Enables asset caching for performance

**Key Configuration**:
```toml
[build]
  base = "cave-frontend"
  command = "npm run build"
  publish = "dist"
  NODE_VERSION = "20"

- SPA redirects
- Security headers
- Asset caching (1 year)
```

**Location**: `/mnt/c/Users/ajbir/CaveSurveyTool/cave-frontend/netlify.toml`

---

### 3. `cave-local/init_db.sql`

**Purpose**: PostgreSQL database schema initialization

**What it does**:
- Creates all required database tables
- Sets up indexes for performance
- Creates views for statistics
- Adds triggers for auto-updating timestamps
- Inserts default settings

**Tables Created**:
1. **users** - User accounts with authentication
   - id, username, email, hashed_password, is_active, created_at
   - Indexes on username and email

2. **surveys** - Cave survey records
   - id, title, section, description, owner_id
   - S3 storage keys (s3_json_key, s3_png_key)
   - URLs (json_url, png_url)
   - Survey metadata (num_stations, num_shots, distances)
   - Bounding box coordinates (min_x, max_x, min_y, max_y, min_z, max_z)
   - Timestamps (created_at, updated_at)
   - Indexes on title, section, owner, created_at

3. **feedback** - User feedback/ideas
   - id, feedback_text, submitted_at, user_session
   - category, priority, status
   - Indexes on submitted_at, status, category

4. **settings** - Application configuration
   - key, value, description, category, updated_at
   - Default settings for app_name, demo_mode, limits

**Views Created**:
- **v_survey_stats** - Per-user survey statistics
  - username, email, survey_count, total_stations, total_shots
  - total_distance_mapped, latest_survey_date

**Triggers**:
- Auto-update `updated_at` timestamp on surveys table modifications

**Location**: `/mnt/c/Users/ajbir/CaveSurveyTool/cave-local/init_db.sql`

**How to use**:
```bash
# Via psql
psql "postgresql://cave_user:password@hostname/cave_survey" < init_db.sql

# Or via Python
python -c "from app.database import create_tables; create_tables()"
```

---

### 4. `cave-local/populate_demo_data.py`

**Purpose**: Populate database with fictional demonstration data

**What it does**:
- Clears existing demo data (safe for fresh installations)
- Creates 4 demo user accounts with hashed passwords
- Generates 6 fictional cave surveys with realistic metadata
- Adds 4 sample feedback entries
- Displays login credentials for testing

**Demo Users Created**:
```
1. velma_survey (Mystery Inc. team)
   Email: velma@mysteryinc.demo
   Password: VelmaPassword123!

2. fred_mapper (Mystery Inc. team)
   Email: fred@mysteryinc.demo
   Password: FredPassword123!

3. sandy_science (SpongeBob universe)
   Email: sandy@bikinibottom.demo
   Password: SandyPassword123!

4. finn_adventure (Adventure Time)
   Email: finn@ooo.demo
   Password: FinnPassword123!
```

**Demo Surveys Created**:
1. **Mystery Cave - Main Passage**
   - Section A, 12 stations, 11 shots
   - 287.5m slope distance, 265.3m horizontal
   - Owner: velma_survey

2. **Crystal Onyx Cave - Formation Room**
   - B-Series, 24 stations, 23 shots
   - 412.8m slope distance, 385.6m horizontal
   - Owner: velma_survey

3. **Adventure Cave System - Upper Level**
   - Mathematical Traverse, 18 stations, 17 shots
   - 325.4m slope distance, 298.7m horizontal
   - Owner: finn_adventure

4. **Sandy's Science Cave - Research Section**
   - Lab Area, 30 stations, 29 shots
   - 523.7m slope distance, 487.2m horizontal
   - Owner: sandy_science

5. **Mystery Machine Cave - Lower Section**
   - Deep Passage, 15 stations, 14 shots
   - 198.3m slope distance, 175.6m horizontal
   - Owner: fred_mapper

6. **Bikini Bottom Cave - Underwater Survey**
   - Zone C, 20 stations, 19 shots
   - 367.9m slope distance, 342.1m horizontal
   - Owner: sandy_science

**Demo Feedback Created**:
- Feature request: 3D visualization
- Positive feedback: Accurate calculations
- Feature request: DistoX instrument import
- Positive feedback: Clean interface

**Location**: `/mnt/c/Users/ajbir/CaveSurveyTool/cave-local/populate_demo_data.py`

**How to use**:
```bash
# Via Render Shell or local terminal
cd cave-local
python populate_demo_data.py
```

**Expected Output**:
```
======================================================================
🗺️ Cave Survey Application - Demo Data Population
   Using fictional cave surveys for demonstration
======================================================================

🧹 Clearing existing data...
✓ Cleared existing data

👥 Adding demo users (fictional cave surveyors)...
✓ Added 4 demo users
  Login credentials (demo only):
    - velma_survey / VelmaPassword123!
    - fred_mapper / FredPassword123!
    - sandy_science / SandyPassword123!
    - finn_adventure / FinnPassword123!

🗺️ Adding demo cave surveys...
✓ Added 6 demo cave surveys

💬 Adding demo feedback...
✓ Added 4 feedback entries

⚠️ Enabling demonstration mode...
✓ Demo mode markers added to survey descriptions

======================================================================
✅ SUCCESS! Demo data populated successfully!

📊 Summary:
   - 4 Demo users (Velma, Fred, Sandy, Finn)
   - 6 Fictional cave surveys with realistic data
   - 4 Sample feedback entries

🔐 Demo Login Credentials:
   Username: velma_survey  | Password: VelmaPassword123!
   Username: fred_mapper   | Password: FredPassword123!
   Username: sandy_science | Password: SandyPassword123!
   Username: finn_adventure| Password: FinnPassword123!

⚠️  REMINDER: This is demonstration data using fictional surveys.
   Clear this data before using for real cave survey projects!
======================================================================
```

---

### 5. `DEPLOY_TO_CLOUD.md`

**Purpose**: Comprehensive deployment guide with step-by-step instructions

**What it covers**:
1. Architecture overview with diagram
2. Prerequisites and account setup
3. Database deployment (Render PostgreSQL)
4. Backend deployment (Render Web Service)
   - Automated deployment via render.yaml
   - Manual deployment option
   - Environment variable configuration
   - Database initialization
   - Demo data population
5. Frontend deployment (Netlify)
   - Configuration
   - Build settings
   - Environment variables
6. AWS S3 setup (optional)
7. Testing procedures
8. Monitoring and maintenance
9. Troubleshooting common issues
10. Cost estimates (free tier vs starter tier)
11. Security reminders

**Location**: `/mnt/c/Users/ajbir/CaveSurveyTool/DEPLOY_TO_CLOUD.md`

---

## Deployment Workflow

### Quick Start (Recommended)

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Add deployment configuration"
   git push origin main
   ```

2. **Deploy Backend** (Render):
   - New → Blueprint
   - Connect GitHub repo
   - Render detects render.yaml
   - Click "Apply" (auto-creates database + web service)

3. **Initialize Database** (Render Shell):
   ```bash
   cd cave-local
   psql "$DATABASE_URL" < init_db.sql
   python populate_demo_data.py
   ```

4. **Deploy Frontend** (Netlify):
   ```bash
   cd cave-frontend
   netlify deploy --prod
   ```

5. **Update CORS**:
   - Copy Netlify URL
   - Update ALLOWED_ORIGINS in Render environment
   - Wait for automatic redeploy

6. **Test**:
   - Visit Netlify URL
   - Login with demo credentials
   - Test cave survey reduction/plotting

---

## File Dependencies

```
Cave Survey Tool
├── render.yaml                     # Render infrastructure config
├── cave-frontend/
│   ├── netlify.toml                # Netlify deployment config
│   ├── src/
│   │   ├── App.jsx                 # React app (unchanged)
│   │   └── api.js                  # API client (unchanged)
│   └── .env.production             # Production API URL (create this)
│
└── cave-local/
    ├── init_db.sql                 # Database schema
    ├── populate_demo_data.py       # Demo data script
    ├── app/
    │   ├── main.py                 # FastAPI app (unchanged)
    │   ├── database.py             # SQLAlchemy models (unchanged)
    │   ├── models.py               # Pydantic models (unchanged)
    │   └── config.py               # Settings (unchanged)
    └── requirements.txt            # Python dependencies (unchanged)
```

---

## Environment Variables Reference

### Render Backend (Required)

```bash
# App
APP_NAME=Cave Survey API
DEBUG=false

# Database (auto-set from PostgreSQL service)
DATABASE_URL=postgresql://...

# Auth
SECRET_KEY=<generate-random>
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256

# CORS
ALLOWED_ORIGINS=https://your-app.netlify.app
```

### Render Backend (Optional)

```bash
# AWS S3
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=<your-bucket>
S3_PUBLIC_READ=false
PRESIGN_EXPIRE_SECS=3600

# Datadog APM
DATADOG_API_KEY=<your-key>
DATADOG_APP_KEY=<your-app-key>
DD_SERVICE=cave-survey-api
DD_ENV=production
DD_VERSION=1.0.0
```

### Netlify Frontend

```bash
VITE_API_BASE_URL=https://cave-survey-api.onrender.com
```

---

## Database Schema ER Diagram

```
┌─────────────────────┐
│      users          │
│─────────────────────│
│ id (PK)             │
│ username (UNIQUE)   │
│ email (UNIQUE)      │
│ hashed_password     │
│ is_active           │
│ created_at          │
└──────────┬──────────┘
           │
           │ 1:N
           │
┌──────────▼──────────┐
│     surveys         │
│─────────────────────│
│ id (PK)             │
│ title               │
│ section             │
│ description         │
│ owner_id (FK)       │◄───┐
│ s3_json_key         │    │
│ s3_png_key          │    │ References
│ json_url            │    │ users.id
│ png_url             │    │
│ num_stations        │    │
│ num_shots           │    │
│ total_slope_dist    │    │
│ total_horiz_dist    │    │
│ min_x, max_x        │    │
│ min_y, max_y        │    │
│ min_z, max_z        │    │
│ created_at          │    │
│ updated_at          │    │
└─────────────────────┘    │
                           │
┌─────────────────────┐    │
│     feedback        │    │
│─────────────────────│    │
│ id (PK)             │    │
│ feedback_text       │    │
│ submitted_at        │    │
│ user_session        │    │
│ category            │    │
│ priority            │    │
│ status              │    │
└─────────────────────┘    │
                           │
┌─────────────────────┐    │
│     settings        │    │
│─────────────────────│    │
│ key (PK)            │    │
│ value               │    │
│ description         │    │
│ category            │    │
│ updated_at          │    │
└─────────────────────┘────┘
```

---

## API Endpoints

### Public Endpoints (No Auth)
- `GET /` - Health check
- `POST /register` - Create user account
- `POST /token` - Login (get JWT token)
- `POST /reduce` - Reduce cave survey traverse
- `POST /plot` - Generate cave survey plot (PNG)
- `POST /feedback` - Submit feedback/ideas

### Protected Endpoints (Requires Auth)
- `POST /save` - Save survey to database + S3
- `GET /surveys` - List user's surveys
- `GET /admin/feedback` - View all feedback (admin)

---

## Testing Checklist

After deployment, verify:

- [ ] Backend health endpoint returns 200 OK
- [ ] Database connection successful (`database_connected: true`)
- [ ] Frontend loads without errors
- [ ] "Test backend" button shows health response
- [ ] Cave survey reduction works (POST /reduce)
- [ ] Cave survey plotting works (POST /plot)
- [ ] Feedback submission works
- [ ] Demo user login works (if populated)
- [ ] CORS allows frontend to call backend
- [ ] No console errors in browser (F12)

---

## Security Considerations

### Implemented
✅ Password hashing (bcrypt via passlib)
✅ JWT authentication with expiration
✅ SQL injection protection (SQLAlchemy ORM)
✅ CORS configuration
✅ Input validation (Pydantic models)
✅ Security headers (Netlify)
✅ S3 private buckets (presigned URLs)

### Recommended for Production
⚠️ Enable HTTPS everywhere (enforced by Render/Netlify)
⚠️ Rotate SECRET_KEY periodically
⚠️ Use strong passwords for demo users
⚠️ Enable MFA on AWS account
⚠️ Regularly update dependencies
⚠️ Monitor logs for suspicious activity
⚠️ Rate limiting on API endpoints
⚠️ Database backups (Render auto-backups on paid plans)

---

## Comparison: CKKC App vs Cave Survey Tool

| Feature | CKKC Expedition | Cave Survey Tool |
|---------|----------------|------------------|
| **Backend** | Flask | FastAPI |
| **Database** | PostgreSQL (psycopg2) | PostgreSQL (SQLAlchemy ORM) |
| **Frontend** | Jinja2 templates | React/Vite SPA |
| **Auth** | Simple password | JWT tokens |
| **File Storage** | N/A | AWS S3 |
| **API Style** | Server-rendered | REST API |
| **Monitoring** | None | Datadog APM (optional) |
| **Deployment** | Manual Render | Automated (render.yaml) |
| **Demo Data** | Fictional participants/trips | Fictional cave surveys |

---

## Next Steps

After successful deployment:

1. **Test with real cave survey data** (replace demo data)
2. **Implement user authentication UI** (login/register forms in React)
3. **Add survey list page** (show all user surveys)
4. **Add survey detail page** (view/edit individual surveys)
5. **Implement file upload** (bulk import survey data)
6. **Add 3D visualization** (three.js or similar)
7. **Export to Compass/Survex formats**
8. **Mobile-responsive design improvements**
9. **User profile/settings page**
10. **Admin dashboard** (feedback management, user management)

---

## Support and Resources

- **Render Docs**: https://render.com/docs
- **Netlify Docs**: https://docs.netlify.com
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **React Docs**: https://react.dev
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org
- **Pydantic Docs**: https://docs.pydantic.dev

---

**Created**: 2025-11-05
**Author**: Claude Code
**Version**: 1.0.0
