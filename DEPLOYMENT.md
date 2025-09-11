# Cave Survey Application - Deployment Guide

## Overview
This guide walks you through deploying the cave survey application with:
- **Frontend**: React/Vite on Netlify
- **Backend**: FastAPI on Render
- **Database**: PostgreSQL on Render
- **Storage**: AWS S3

## Prerequisites
- GitHub account
- AWS account
- Render account
- Netlify account

## Phase 1: AWS S3 Setup

### 1.1 Create S3 Bucket
```bash
# Choose a globally unique name
BUCKET_NAME="cavemapper-pmvp-yourusername"
REGION="us-east-1"
```

1. Go to AWS S3 Console
2. Create bucket with the name above
3. Keep bucket private (recommended)
4. Enable versioning (optional)

### 1.2 Configure CORS
Add this CORS configuration to your bucket:
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": ["ETag"]
  }
]
```

### 1.3 Create IAM User
1. Go to IAM Console
2. Create user: `cave-survey-api`
3. Attach this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:AbortMultipartUpload"
      ],
      "Resource": "arn:aws:s3:::BUCKET_NAME/*"
    }
  ]
}
```

4. Save Access Key ID and Secret Access Key

## Phase 2: Database Setup (Render)

### 2.1 Create PostgreSQL Database
1. Go to Render Dashboard
2. New → PostgreSQL
3. Name: `cave-survey-db`
4. Choose region close to your API
5. Note the connection string

## Phase 3: Backend Deployment (Render)

### 3.1 Deploy to Render
1. Go to Render Dashboard
2. New → Web Service
3. Connect your GitHub repo
4. Configure:
   - **Root Directory**: `cave-local`
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 3.2 Environment Variables
Add these environment variables in Render:

```
DATABASE_URL=<your_render_postgresql_connection_string>
AWS_ACCESS_KEY_ID=<your_aws_access_key>
AWS_SECRET_ACCESS_KEY=<your_aws_secret_key>
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=<your_bucket_name>
S3_PUBLIC_READ=false
PRESIGN_EXPIRE_SECS=3600
SECRET_KEY=<generate_a_secure_random_string>
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALLOWED_ORIGINS=http://localhost:5173,https://your-app.netlify.app
DEBUG=false
APP_NAME=Cave Survey API
```

### 3.3 Generate Secret Key
```python
import secrets
print(secrets.token_urlsafe(32))
```

## Phase 4: Frontend Deployment (Netlify)

### 4.1 Update Frontend Environment
Create `cave-frontend/.env.production`:
```
VITE_API_BASE_URL=https://your-api.onrender.com
```

### 4.2 Deploy to Netlify
1. Go to Netlify Dashboard
2. New site from Git
3. Choose your repository
4. Configure:
   - **Base directory**: `cave-frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `dist`

### 4.3 Environment Variables
Add in Netlify:
```
VITE_API_BASE_URL=https://your-api.onrender.com
```

## Phase 5: Final Configuration

### 5.1 Update CORS Origins
Update your Render backend environment variables:
```
ALLOWED_ORIGINS=https://your-app.netlify.app,http://localhost:5173
```

### 5.2 Test the Application

1. **Health Check**: `https://your-api.onrender.com/`
2. **API Docs**: `https://your-api.onrender.com/docs`
3. **Frontend**: `https://your-app.netlify.app`

### 5.3 Testing Workflow
1. Register a new user
2. Log in and get authentication token
3. Submit a cave survey with multiple shots
4. Verify data saves to S3 and database
5. Check PNG visualization generates correctly

## Troubleshooting

### Common Issues

**CORS Errors**:
- Verify `ALLOWED_ORIGINS` includes your Netlify URL
- Check both frontend and backend are using HTTPS in production

**Database Connection**:
- Verify `DATABASE_URL` format is correct
- Check Render PostgreSQL service is running

**S3 Upload Failures**:
- Verify AWS credentials are correct
- Check IAM policy allows `s3:PutObject`
- Ensure bucket name matches environment variable

**Authentication Issues**:
- Verify `SECRET_KEY` is set and secure
- Check token expiration settings

## Security Checklist

- [ ] AWS S3 bucket is private
- [ ] IAM user has minimal required permissions
- [ ] Database uses strong password
- [ ] `SECRET_KEY` is cryptographically secure
- [ ] CORS origins are restricted to your domains
- [ ] Environment variables are not in source code

## Monitoring

Set up basic monitoring:
1. Enable Render service health checks
2. Monitor S3 usage and costs
3. Check database connection pooling
4. Review application logs regularly

## Cost Estimation

**Monthly costs (development tier)**:
- Render Web Service: $7/month
- Render PostgreSQL: $7/month
- AWS S3: ~$1-5/month (depending on usage)
- Netlify: Free tier
- **Total**: ~$15-20/month

## Next Steps

After successful deployment:
1. Set up custom domain names
2. Implement more comprehensive error monitoring
3. Add automated backups
4. Consider adding Redis for session management
5. Implement audit logging for survey data changes