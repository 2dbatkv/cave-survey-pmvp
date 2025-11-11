# Cave Survey Tool - Cloud Deployment Guide

This guide walks you through deploying the Cave Survey Tool to the cloud using **Render.com** (backend + database) and **Netlify** (frontend).

## Architecture Overview

```
┌─────────────────┐
│   Netlify       │ ← React/Vite Frontend (Static Site)
│  (Frontend)     │
└────────┬────────┘
         │
         │ HTTPS API Calls
         │
┌────────▼────────┐
│   Render.com    │ ← FastAPI Backend
│   (Backend)     │
└────────┬────────┘
         │
         │ PostgreSQL Connection
         │
┌────────▼────────┐
│   Render        │ ← PostgreSQL Database
│   (Database)    │
└─────────────────┘
         │
         │ File Storage
         │
┌────────▼────────┐
│   AWS S3        │ ← Cave survey files (JSON + PNG)
└─────────────────┘
```

## Prerequisites

1. **GitHub Account** - Code repository
2. **Render.com Account** - Free tier available
3. **Netlify Account** - Free tier available
4. **AWS Account** - For S3 storage (optional for demo)
5. **Git installed locally**

---

## Part 1: Database Setup (Render PostgreSQL)

### 1.1 Create PostgreSQL Database

1. Log in to [Render.com](https://render.com)
2. Click **"New +"** → **"PostgreSQL"**
3. Configure database:
   - **Name**: `cave-survey-db`
   - **Database**: `cave_survey`
   - **User**: `cave_user`
   - **Region**: Choose closest to you
   - **Plan**: Free (or Starter for production)
4. Click **"Create Database"**
5. Wait for database to provision (2-3 minutes)

### 1.2 Get Database Connection String

1. Open your new database in Render dashboard
2. Scroll to **"Connections"** section
3. Copy the **"Internal Database URL"** (starts with `postgresql://`)
4. Save this URL - you'll need it for the backend setup

---

## Part 2: Backend Deployment (Render Web Service)

### 2.1 Push Code to GitHub

```bash
cd /mnt/c/Users/ajbir/CaveSurveyTool

# Initialize git repository if not already done
git init
git add .
git commit -m "Initial commit: Cave Survey Tool for cloud deployment"

# Create GitHub repository and push
git remote add origin https://github.com/YOUR_USERNAME/cave-survey-tool.git
git branch -M main
git push -u origin main
```

### 2.2 Deploy Backend to Render

#### Option A: Automated Deployment (Using render.yaml)

1. In Render dashboard, click **"New +"** → **"Blueprint"**
2. Connect your GitHub repository
3. Render will automatically detect `render.yaml`
4. Review the configuration:
   - Database: `cave-survey-db`
   - Web Service: `cave-survey-api`
5. Click **"Apply"**
6. Render will automatically deploy both services

#### Option B: Manual Deployment

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure web service:
   - **Name**: `cave-survey-api`
   - **Region**: Same as database
   - **Branch**: `main`
   - **Root Directory**: `cave-local`
   - **Runtime**: Python 3
   - **Build Command**: `pip install --upgrade pip setuptools wheel && pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
   - **Plan**: Free (or Starter for production)

### 2.3 Configure Environment Variables

In your Render web service dashboard, go to **"Environment"** and add:

#### Required Variables:
```bash
# App Configuration
APP_NAME=Cave Survey API
DEBUG=false

# Database (automatically set from PostgreSQL service)
DATABASE_URL=<your-internal-database-url>

# Authentication
SECRET_KEY=<click "Generate" button to create random secret>
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256

# CORS - Update after deploying frontend
ALLOWED_ORIGINS=http://localhost:5173,https://your-app.netlify.app
```

#### AWS S3 Variables (Optional - Skip for demo mode):
```bash
AWS_ACCESS_KEY_ID=<your-aws-access-key>
AWS_SECRET_ACCESS_KEY=<your-aws-secret-key>
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=<your-bucket-name>
S3_PUBLIC_READ=false
PRESIGN_EXPIRE_SECS=3600
```

#### Datadog APM (Optional - For production monitoring):
```bash
DATADOG_API_KEY=<your-datadog-api-key>
DATADOG_APP_KEY=<your-datadog-app-key>
DD_SERVICE=cave-survey-api
DD_ENV=production
DD_VERSION=1.0.0
```

### 2.4 Initialize Database Schema

Once deployed, use Render Shell to initialize the database:

1. In Render dashboard, open your web service
2. Click **"Shell"** tab (top right)
3. Run the database initialization:

```bash
# Navigate to project directory
cd /opt/render/project/src/cave-local

# Initialize database tables
python -c "from app.database import create_tables; create_tables()"

# Or use psql directly with init_db.sql
psql "$DATABASE_URL" < init_db.sql
```

### 2.5 Populate Demo Data (Optional)

```bash
# In Render Shell
cd /opt/render/project/src/cave-local
python populate_demo_data.py
```

This creates:
- 4 demo users (velma_survey, fred_mapper, sandy_science, finn_adventure)
- 6 fictional cave surveys with realistic data
- 4 sample feedback entries

**Demo Login Credentials:**
```
Username: velma_survey  | Password: VelmaPassword123!
Username: fred_mapper   | Password: FredPassword123!
Username: sandy_science | Password: SandyPassword123!
Username: finn_adventure| Password: FinnPassword123!
```

### 2.6 Verify Backend Health

1. Get your backend URL from Render dashboard (e.g., `https://cave-survey-api.onrender.com`)
2. Visit: `https://cave-survey-api.onrender.com/`
3. You should see JSON response:
```json
{
  "ok": true,
  "service": "Cave Survey API",
  "version": "1.0.0",
  "timestamp": "2025-11-05T...",
  "database_connected": true,
  "s3_configured": false,
  "datadog_configured": false
}
```

---

## Part 3: Frontend Deployment (Netlify)

### 3.1 Configure Frontend API URL

Before deploying, update the frontend to point to your Render backend:

**Create `.env.production` file:**
```bash
cd /mnt/c/Users/ajbir/CaveSurveyTool/cave-frontend
cat > .env.production << 'EOF'
VITE_API_BASE_URL=https://cave-survey-api.onrender.com
EOF
```

### 3.2 Deploy to Netlify

#### Option A: Netlify CLI (Recommended)

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Navigate to frontend directory
cd /mnt/c/Users/ajbir/CaveSurveyTool/cave-frontend

# Login to Netlify
netlify login

# Deploy
netlify deploy --prod

# Follow prompts:
# - Create new site? Yes
# - Site name: cave-survey-tool (or your choice)
# - Build command: npm run build
# - Publish directory: dist
```

#### Option B: Netlify Dashboard

1. Log in to [Netlify](https://netlify.com)
2. Click **"Add new site"** → **"Import an existing project"**
3. Connect to your GitHub repository
4. Configure build settings:
   - **Base directory**: `cave-frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `cave-frontend/dist`
   - **Environment variables**: Add `VITE_API_BASE_URL=https://cave-survey-api.onrender.com`
5. Click **"Deploy site"**

### 3.3 Configure Custom Domain (Optional)

1. In Netlify dashboard, go to **"Site settings"** → **"Domain management"**
2. Click **"Add custom domain"**
3. Follow DNS configuration instructions

### 3.4 Update CORS Settings

After deploying frontend, update backend CORS:

1. Go to Render dashboard → Your web service → Environment
2. Update `ALLOWED_ORIGINS` to include your Netlify URL:
```bash
ALLOWED_ORIGINS=https://your-site.netlify.app,http://localhost:5173
```
3. Save and wait for automatic redeploy

---

## Part 4: AWS S3 Setup (Optional - For File Storage)

### 4.1 Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://cave-survey-data-yourname --region us-east-1
```

Or via AWS Console:
1. Go to S3 service
2. Create bucket: `cave-survey-data-yourname`
3. Region: `us-east-1`
4. Block all public access: ✓ (recommended)

### 4.2 Create IAM User

1. Go to IAM → Users → Create user
2. Username: `cave-survey-app`
3. Attach policy: `AmazonS3FullAccess` (or create custom policy)
4. Create access key → Save Access Key ID and Secret Access Key

### 4.3 Update Render Environment

Add AWS credentials to Render environment variables (see Part 2.3)

---

## Part 5: Testing the Deployment

### 5.1 Test Health Endpoint
```bash
curl https://cave-survey-api.onrender.com/
```

### 5.2 Test Reduce Endpoint
```bash
curl -X POST https://cave-survey-api.onrender.com/reduce \
  -H "Content-Type: application/json" \
  -d '{
    "origin_x": 0,
    "origin_y": 0,
    "origin_z": 0,
    "section": "test",
    "shots": [
      {
        "from_station": "S0",
        "to_station": "S1",
        "slope_distance": 10.0,
        "azimuth_deg": 90,
        "inclination_deg": 0
      }
    ]
  }'
```

### 5.3 Test Frontend
1. Visit your Netlify URL
2. Enter sample survey data
3. Click "Test backend" - should show health check
4. Click "Reduce" - should calculate coordinates
5. Click "Plot" - should display cave map

---

## Part 6: Monitoring and Maintenance

### 6.1 View Logs

**Render Backend Logs:**
1. Render dashboard → Your web service → Logs tab
2. Real-time logs show all API requests and errors

**Netlify Deploy Logs:**
1. Netlify dashboard → Deploys tab
2. Click on a deploy to see build logs

### 6.2 Database Management

**Using Render Shell:**
```bash
# Connect to database
psql "$DATABASE_URL"

# View users
SELECT id, username, email, created_at FROM users;

# View surveys
SELECT id, title, section, num_stations, created_at FROM surveys;

# View feedback
SELECT id, feedback_text, category, priority, submitted_at FROM feedback;
```

### 6.3 Update Demo Mode Setting

```sql
-- Enable demo mode
UPDATE settings SET value = 'true' WHERE key = 'demo_mode_enabled';

-- Disable demo mode
UPDATE settings SET value = 'false' WHERE key = 'demo_mode_enabled';
```

---

## Troubleshooting

### Issue: Database connection failed

**Solution:**
- Verify `DATABASE_URL` is set correctly
- Check database is running in Render dashboard
- Ensure backend and database are in same region

### Issue: CORS errors in browser console

**Solution:**
- Update `ALLOWED_ORIGINS` to include your Netlify URL
- Clear browser cache
- Wait for Render to redeploy after env change

### Issue: Build fails on Render

**Solution:**
- Check Python version compatibility (3.12 recommended)
- Verify `requirements.txt` includes all dependencies
- Check build logs for specific error messages

### Issue: Frontend shows "API connection failed"

**Solution:**
- Verify `VITE_API_BASE_URL` is set correctly in Netlify
- Check backend health endpoint is accessible
- Rebuild frontend after changing environment variables

### Issue: S3 uploads fail

**Solution:**
- Verify AWS credentials are correct
- Check S3 bucket name matches environment variable
- Ensure IAM user has S3 write permissions

---

## Cost Estimate

### Free Tier (Good for demo/testing):
- **Render Database (Free)**: 1GB storage, expires after 90 days
- **Render Web Service (Free)**: Spins down after inactivity, slow cold starts
- **Netlify (Free)**: 100GB bandwidth/month, 300 build minutes/month
- **AWS S3**: Pay as you go (~$0.023/GB/month)

**Total**: ~$0/month for demo usage

### Starter Tier (Recommended for production):
- **Render Database (Starter)**: $7/month - 1GB RAM, 10GB storage
- **Render Web Service (Starter)**: $7/month - 512MB RAM, persistent
- **Netlify (Free)**: Sufficient for most use cases
- **AWS S3**: ~$1-5/month depending on usage

**Total**: ~$15-20/month

---

## Next Steps

1. ✅ Backend deployed to Render
2. ✅ Database initialized with schema
3. ✅ Demo data populated (optional)
4. ✅ Frontend deployed to Netlify
5. ✅ CORS configured
6. ⏭ Add user authentication UI
7. ⏭ Implement survey list/detail pages
8. ⏭ Add file upload for bulk survey data
9. ⏭ Configure custom domain
10. ⏭ Set up monitoring/alerts

---

## Additional Resources

- **Render Documentation**: https://render.com/docs
- **Netlify Documentation**: https://docs.netlify.com
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **React Documentation**: https://react.dev
- **Cave Survey Standards**: https://caves.org/survey/

---

## Support

For issues or questions:
1. Check logs in Render/Netlify dashboards
2. Review error messages in browser console (F12)
3. Verify all environment variables are set
4. Test backend health endpoint independently

---

**⚠️ SECURITY REMINDER:**
- Never commit `.env` files or secrets to git
- Use strong passwords for demo users in production
- Regularly rotate AWS access keys
- Enable MFA on AWS account
- Keep dependencies updated (`pip list --outdated`)
- Review Render/Netlify access logs periodically

---

**📊 DEMO DATA REMINDER:**
The populate_demo_data.py script creates fictional survey data for demonstration purposes. Before using this application for real cave survey projects:
1. Clear all demo data: `DELETE FROM surveys; DELETE FROM users;`
2. Create real user accounts with secure passwords
3. Update settings: `UPDATE settings SET value = 'false' WHERE key = 'demo_mode_enabled';`
