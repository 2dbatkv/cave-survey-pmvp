# Cave Survey Application - Unified Deployment Guide

## Overview

This comprehensive deployment guide consolidates best practices for deploying the cave survey application to production. The stack consists of:

- **Frontend**: React/Vite application on Netlify
- **Backend**: FastAPI service on Render
- **Database**: PostgreSQL on Render (with option for Aiven)
- **Storage**: AWS S3 for file storage (PNG/JSON artifacts)
- **Infrastructure**: Optional Terraform for AWS resources

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React/Vite    │    │   FastAPI       │    │   PostgreSQL    │
│   (Netlify)     │───▶│   (Render)      │───▶│   (Render)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   AWS S3        │
                       │   (File Storage)│
                       └─────────────────┘
```

## Prerequisites

### Required Accounts
- [x] GitHub account (code repository)
- [x] AWS account (S3 storage)
- [x] Render account (backend + database)
- [x] Netlify account (frontend hosting)

### Local Development Tools
- [x] Node.js 22+ via nvm: `nvm install 22 && nvm use 22`
- [x] Python 3.10+ with FastAPI/Uvicorn environment
- [x] AWS CLI (optional): `aws --version`
- [x] Terraform 1.5+ (if using Infrastructure as Code)

### Repository Structure
Ensure your monorepo follows this structure:
```
PreMVP/
├── cave-local/                 # FastAPI backend
│   ├── app/main.py
│   ├── requirements.txt
│   └── .env.example
├── cave-frontend/              # React frontend
│   ├── src/
│   ├── package.json
│   ├── .env.example
│   └── netlify.toml
├── infra/                      # Infrastructure as Code
│   ├── render.yaml
│   └── terraform/
└── docs/
    └── deployment/
```

## Deployment Sequence

### Phase 1: Infrastructure Setup (AWS S3)

#### 1.1 Create S3 Bucket

Choose a globally unique bucket name:
```bash
BUCKET_NAME="cavemapper-pmvp-$(whoami)-$(date +%Y%m%d)"
REGION="us-east-1"
```

**Manual Setup:**
1. Navigate to AWS S3 Console
2. Create bucket with chosen name
3. Select region close to your backend deployment
4. **Security**: Keep bucket private (recommended for production)
5. Enable versioning (optional but recommended)

**Terraform Setup (Recommended):**
See [Infrastructure as Code](#infrastructure-as-code-terraform) section below.

#### 1.2 Configure CORS Policy

Add CORS configuration to allow browser access:
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

**Production Note**: Replace `"*"` in `AllowedOrigins` with your actual domain after deployment.

#### 1.3 Create IAM User for API Access

Create IAM user `cave-survey-api` with minimal permissions:

**For Private Bucket (Recommended):**
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
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
    }
  ]
}
```

**For Public Read Bucket (Development Only):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:AbortMultipartUpload"
      ],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
    }
  ]
}
```

**Critical**: Save the Access Key ID and Secret Access Key securely.

### Phase 2: Database Setup

#### 2.1 PostgreSQL on Render

1. Navigate to Render Dashboard
2. Select **New** → **PostgreSQL**
3. Configure:
   - **Name**: `cave-survey-db`
   - **Database Name**: `cave_survey`
   - **User**: Auto-generated
   - **Region**: Match your API region for optimal performance
   - **Plan**: Select based on expected load

4. **Important**: Save the connection string format:
   ```
   postgresql://user:password@host:port/database
   ```

#### 2.2 Alternative: Aiven PostgreSQL

For production workloads requiring higher availability:

1. Create Aiven account
2. Deploy PostgreSQL service
3. Configure networking (whitelist Render IPs)
4. Save connection details

### Phase 3: Backend Code Preparation

#### 3.1 Update Dependencies

Add to `cave-local/requirements.txt`:
```txt
boto3>=1.26.0
psycopg2-binary>=2.9.0
```

#### 3.2 Backend Code Updates

Update `app/main.py` to support both local development and cloud deployment:

```python
import os
import boto3
from botocore.client import Config

# S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_PUBLIC_READ = os.getenv("S3_PUBLIC_READ", "false").lower() == "true"
PRESIGN_EXPIRE_SECS = int(os.getenv("PRESIGN_EXPIRE_SECS", "3600"))

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# CORS Configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/save")
def save_endpoint(trav: TraverseIn):
    """
    Save outputs to S3 or local filesystem based on configuration.
    Returns URLs for accessing saved files.
    """
    # Compute geometry
    origin_label = trav.shots[0].from_station
    pos, edges, meta = reduce_graph(
        trav.shots,
        origin_name=origin_label,
        ox=trav.origin_x, oy=trav.origin_y, oz=trav.origin_z,
    )

    day = datetime.utcnow().strftime("%Y-%m-%d")
    section = trav.section.lower().replace(" ", "_")
    
    # Build JSON document
    json_doc = {
        "origin": {"station": origin_label, "x": trav.origin_x, "y": trav.origin_y, "z": trav.origin_z},
        "shots": [s.model_dump() for s in trav.shots],
        "stations": {k: {"x": v[0], "y": v[1], "z": v[2]} for k, v in pos.items()},
        "edges": list(edges),
        "meta": meta,
        "saved_at": datetime.utcnow().isoformat()
    }

    # Render PNG
    img = plot_graph_png(pos, edges)
    png_bytes = img.getvalue()

    if not S3_BUCKET:
        # Local fallback for development
        base_dir = os.path.join("data", section, day)
        os.makedirs(base_dir, exist_ok=True)
        
        json_path = os.path.join(base_dir, f"{day}.json")
        png_path = os.path.join(base_dir, f"{day}.png")
        
        with open(json_path, "w") as f:
            json.dump(json_doc, f, indent=2)
        with open(png_path, "wb") as f:
            f.write(png_bytes)
            
        return JSONResponse({
            "saved": True,
            "mode": "local",
            "json_path": json_path,
            "png_path": png_path,
            "meta": meta
        })

    # S3 Cloud Storage
    s3 = boto3.client("s3", region_name=AWS_REGION, config=Config(signature_version="s3v4"))
    
    key_base = f"{section}/{day}/{day}"
    json_key = f"{key_base}.json"
    png_key = f"{key_base}.png"

    # Upload JSON
    s3.put_object(
        Bucket=S3_BUCKET, Key=json_key,
        Body=json.dumps(json_doc).encode("utf-8"),
        ContentType="application/json",
        **({"ACL": "public-read"} if S3_PUBLIC_READ else {})
    )

    # Upload PNG
    s3.put_object(
        Bucket=S3_BUCKET, Key=png_key,
        Body=png_bytes,
        ContentType="image/png",
        **({"ACL": "public-read"} if S3_PUBLIC_READ else {})
    )

    # Generate URLs
    if S3_PUBLIC_READ:
        json_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{json_key}"
        png_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{png_key}"
    else:
        json_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": json_key},
            ExpiresIn=PRESIGN_EXPIRE_SECS,
        )
        png_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": png_key},
            ExpiresIn=PRESIGN_EXPIRE_SECS,
        )

    return JSONResponse({
        "saved": True,
        "mode": "s3",
        "s3_bucket": S3_BUCKET,
        "json_key": json_key,
        "png_key": png_key,
        "json_url": json_url,
        "png_url": png_url,
        "meta": meta,
    })
```

#### 3.3 Generate Secure Keys

```python
import secrets
SECRET_KEY = secrets.token_urlsafe(32)
print(f"SECRET_KEY={SECRET_KEY}")
```

### Phase 4: Backend Deployment (Render)

#### 4.1 Create Web Service

1. Navigate to Render Dashboard
2. Select **New** → **Web Service**
3. Connect your GitHub repository
4. Configure service:
   - **Name**: `cavemapper-api`
   - **Root Directory**: `cave-local`
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Region**: Match your database region
   - **Plan**: Select based on expected load

#### 4.2 Environment Variables Configuration

Set these environment variables in Render:

**Required AWS Variables:**
```env
AWS_ACCESS_KEY_ID=<your_aws_access_key>
AWS_SECRET_ACCESS_KEY=<your_aws_secret_key>
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=<your_bucket_name>
S3_PUBLIC_READ=false
PRESIGN_EXPIRE_SECS=3600
```

**Database Variables:**
```env
DATABASE_URL=<your_render_postgresql_connection_string>
```

**Security Variables:**
```env
SECRET_KEY=<generated_secure_random_string>
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Application Variables:**
```env
APP_NAME=Cave Survey API
DEBUG=false
PYTHONUNBUFFERED=1
```

**CORS Variables (Update after frontend deployment):**
```env
ALLOWED_ORIGINS=http://localhost:5173,https://your-app.netlify.app
```

#### 4.3 Verify Backend Deployment

1. Wait for build completion in Render dashboard
2. Check service logs for any errors
3. Test endpoints:
   - **Health Check**: `https://your-api.onrender.com/`
   - **API Documentation**: `https://your-api.onrender.com/docs`

### Phase 5: Frontend Configuration

#### 5.1 Environment Configuration

Create production environment configuration:

**Option A: Netlify Environment Variables (Recommended)**
Set in Netlify dashboard:
```env
VITE_API_BASE_URL=https://your-api.onrender.com
```

**Option B: Environment File**
Create `cave-frontend/.env.production`:
```env
VITE_API_BASE_URL=https://your-api.onrender.com
```

#### 5.2 Netlify Configuration

Create `cave-frontend/netlify.toml`:
```toml
[build]
  command = "npm ci && npm run build"
  publish = "dist"

[build.environment]
  NODE_VERSION = "22"

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "SAMEORIGIN"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
    X-XSS-Protection = "1; mode=block"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### Phase 6: Frontend Deployment (Netlify)

#### 6.1 Deploy Frontend

1. Navigate to Netlify Dashboard
2. Select **Add new site** → **Import from Git**
3. Choose your GitHub repository
4. Configure build settings:
   - **Base directory**: `cave-frontend`
   - **Build command**: `npm ci && npm run build`
   - **Publish directory**: `dist`
   - **Node version**: 22

#### 6.2 Environment Variables

In Netlify site settings → Environment variables:
```env
VITE_API_BASE_URL=https://your-api.onrender.com
```

#### 6.3 Verify Frontend Deployment

1. Wait for build completion
2. Visit your Netlify URL
3. Test frontend functionality:
   - API connectivity indicator
   - Basic survey form submission
   - Graph visualization

### Phase 7: Final Integration

#### 7.1 Update CORS Configuration

Update your backend environment variables in Render:
```env
ALLOWED_ORIGINS=https://your-app.netlify.app,http://localhost:5173
```

Redeploy the backend service.

#### 7.2 Domain Configuration (Optional)

**Custom Domain Setup:**
1. **Netlify**: Site settings → Domain management → Add custom domain
2. **Render**: Service settings → Custom domains → Add domain
3. Configure DNS records as instructed by each platform

## Testing and Validation

### Automated Testing Checklist

#### Phase 1: Infrastructure Validation
- [ ] S3 bucket accessible with correct permissions
- [ ] IAM user can upload objects to S3
- [ ] CORS configuration allows frontend domain access
- [ ] Database connection string works from Render

#### Phase 2: Backend API Testing
```bash
# Health check
curl https://your-api.onrender.com/

# API documentation
curl https://your-api.onrender.com/docs

# Test save endpoint (requires valid payload)
curl -X POST https://your-api.onrender.com/save \
  -H "Content-Type: application/json" \
  -d @test-survey-data.json
```

#### Phase 3: Frontend Integration Testing
- [ ] Frontend loads without errors
- [ ] API base URL correctly configured
- [ ] Authentication flow works (if implemented)
- [ ] Survey form submission successful
- [ ] File upload and storage verification
- [ ] Graph visualization displays correctly

#### Phase 4: End-to-End Workflow Testing
1. **User Registration/Login** (if authentication enabled)
2. **Survey Data Entry**:
   - Enter station data
   - Add multiple shots
   - Verify calculations
3. **Graph Generation**:
   - Click "Plot" button
   - Verify PNG generation
   - Check graph accuracy
4. **Data Persistence**:
   - Click "Save" button
   - Verify S3 upload success
   - Test file access via returned URLs
   - Confirm database entry (if applicable)

#### Phase 5: Performance and Security Testing
- [ ] Load testing with realistic data sizes
- [ ] Mobile responsiveness verification
- [ ] HTTPS enforcement
- [ ] Security headers present
- [ ] Environment variables not exposed in frontend
- [ ] API rate limiting (if implemented)

### Testing Data

Use this sample data for testing:
```json
{
  "section": "Test Chamber",
  "origin_x": 0.0,
  "origin_y": 0.0,
  "origin_z": 0.0,
  "shots": [
    {
      "from_station": "A1",
      "to_station": "A2",
      "distance": 10.5,
      "azimuth": 45.0,
      "inclination": 0.0
    },
    {
      "from_station": "A2",
      "to_station": "A3",
      "distance": 8.2,
      "azimuth": 90.0,
      "inclination": -5.0
    }
  ]
}
```

## Infrastructure as Code (Terraform)

### Directory Structure
```
infra/
├── terraform/
│   ├── versions.tf
│   ├── provider.tf
│   ├── variables.tf
│   ├── main.tf
│   ├── outputs.tf
│   └── README.md
└── render.yaml
```

### Terraform Configuration

#### versions.tf
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}
```

#### provider.tf
```hcl
provider "aws" {
  region = var.aws_region
}

# Optional: Remote state storage
# terraform {
#   backend "s3" {
#     bucket = "your-terraform-state-bucket"
#     key    = "cavemapper/terraform.tfstate"
#     region = "us-east-1"
#   }
# }
```

#### variables.tf
```hcl
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "cavemapper-pmvp"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 bucket name (must be globally unique)"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "public_read" {
  description = "Allow public read access to bucket objects"
  type        = bool
  default     = false
}
```

#### main.tf
```hcl
locals {
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# S3 Bucket for file storage
resource "aws_s3_bucket" "artifacts" {
  bucket = var.bucket_name
  tags   = local.tags
}

# Bucket versioning
resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Public access block
resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = !var.public_read
  block_public_policy     = !var.public_read
  ignore_public_acls      = !var.public_read
  restrict_public_buckets = !var.public_read
}

# CORS configuration
resource "aws_s3_bucket_cors_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]  # Update with specific domains in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Bucket policy for public read (conditional)
resource "aws_s3_bucket_policy" "public_read" {
  count  = var.public_read ? 1 : 0
  bucket = aws_s3_bucket.artifacts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["s3:GetObject"]
        Resource  = "${aws_s3_bucket.artifacts.arn}/*"
      }
    ]
  })
}

# IAM user for application
resource "aws_iam_user" "app_user" {
  name = "${var.project_name}-app-user"
  tags = local.tags
}

# Access key for the application user
resource "aws_iam_access_key" "app_user" {
  user = aws_iam_user.app_user.name
}

# IAM policy for S3 operations
data "aws_iam_policy_document" "app_s3_policy" {
  statement {
    sid    = "AllowPutObject"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload"
    ]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }

  dynamic "statement" {
    for_each = var.public_read ? [1] : []
    content {
      sid    = "AllowPutObjectAcl"
      effect = "Allow"
      actions = [
        "s3:PutObjectAcl"
      ]
      resources = ["${aws_s3_bucket.artifacts.arn}/*"]
    }
  }
}

# Attach policy to user
resource "aws_iam_user_policy" "app_s3_policy" {
  name   = "${var.project_name}-s3-policy"
  user   = aws_iam_user.app_user.name
  policy = data.aws_iam_policy_document.app_s3_policy.json
}
```

#### outputs.tf
```hcl
output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.artifacts.bucket
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.artifacts.arn
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "iam_user_name" {
  description = "IAM user name for application"
  value       = aws_iam_user.app_user.name
}

output "aws_access_key_id" {
  description = "AWS access key ID"
  value       = aws_iam_access_key.app_user.id
  sensitive   = true
}

output "aws_secret_access_key" {
  description = "AWS secret access key"
  value       = aws_iam_access_key.app_user.secret
  sensitive   = true
}
```

### Terraform Deployment

```bash
# Initialize Terraform
cd infra/terraform
terraform init

# Plan deployment
terraform plan -var="bucket_name=cavemapper-pmvp-$(whoami)-$(date +%Y%m%d)"

# Apply configuration
terraform apply -var="bucket_name=cavemapper-pmvp-$(whoami)-$(date +%Y%m%d)"

# View outputs (including sensitive values)
terraform output
terraform output -raw aws_access_key_id
terraform output -raw aws_secret_access_key
```

### Render Blueprint

Create `infra/render.yaml`:
```yaml
services:
  - type: web
    name: cavemapper-api
    rootDirectory: cave-local
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    plan: starter  # or free for development
    autoDeploy: true
    envVars:
      - key: PYTHONUNBUFFERED
        value: "1"
      - key: AWS_DEFAULT_REGION
        sync: false  # Set in Render dashboard
      - key: AWS_ACCESS_KEY_ID
        sync: false
      - key: AWS_SECRET_ACCESS_KEY
        sync: false
      - key: S3_BUCKET_NAME
        sync: false
      - key: S3_PUBLIC_READ
        value: "false"
      - key: PRESIGN_EXPIRE_SECS
        value: "3600"
      - key: SECRET_KEY
        sync: false
      - key: ACCESS_TOKEN_EXPIRE_MINUTES
        value: "30"
      - key: ALLOWED_ORIGINS
        value: "http://localhost:5173"  # Update after frontend deployment

  # Optional: Deploy frontend on Render instead of Netlify
  # - type: static
  #   name: cavemapper-frontend
  #   rootDirectory: cave-frontend
  #   buildCommand: npm ci && npm run build
  #   staticPublishPath: dist
  #   envVars:
  #     - key: VITE_API_BASE_URL
  #       value: https://cavemapper-api.onrender.com
```

## Environment Management

### Development Environment

#### Backend (.env)
```env
# Local development - no S3 configured, saves to ./data/
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_DEFAULT_REGION=us-east-1
# S3_BUCKET_NAME=
# S3_PUBLIC_READ=false
# PRESIGN_EXPIRE_SECS=3600

SECRET_KEY=dev-secret-key-not-for-production
DEBUG=true
```

#### Frontend (.env.local)
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### Production Environment

#### Render Environment Variables
```env
PYTHONUNBUFFERED=1
AWS_ACCESS_KEY_ID=<from_terraform_output>
AWS_SECRET_ACCESS_KEY=<from_terraform_output>
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=<your_bucket_name>
S3_PUBLIC_READ=false
PRESIGN_EXPIRE_SECS=3600
SECRET_KEY=<secure_random_string>
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALLOWED_ORIGINS=https://your-app.netlify.app,http://localhost:5173
DEBUG=false
APP_NAME=Cave Survey API
```

#### Netlify Environment Variables
```env
VITE_API_BASE_URL=https://your-api.onrender.com
```

## Security Best Practices

### AWS Security
- [ ] Use private S3 bucket with presigned URLs
- [ ] IAM user has minimal required permissions
- [ ] Enable S3 bucket versioning
- [ ] Configure S3 access logging
- [ ] Regularly rotate access keys

### Application Security
- [ ] Use strong, random SECRET_KEY
- [ ] Enable HTTPS on all services
- [ ] Restrict CORS origins to actual domains
- [ ] Implement input validation and sanitization
- [ ] Use environment variables for all secrets
- [ ] Enable security headers in frontend

### Deployment Security
- [ ] Never commit sensitive data to repository
- [ ] Use service-specific environment variables
- [ ] Implement monitoring and alerting
- [ ] Regular dependency updates
- [ ] Security scanning in CI/CD pipeline

## Monitoring and Maintenance

### Health Monitoring

#### Application Health Checks
```bash
# Backend health
curl -f https://your-api.onrender.com/health || echo "Backend unhealthy"

# Database connectivity
curl -f https://your-api.onrender.com/db-health || echo "Database unhealthy"

# S3 connectivity
curl -f https://your-api.onrender.com/storage-health || echo "Storage unhealthy"
```

#### Frontend Monitoring
- Use Netlify's built-in analytics
- Monitor bundle size and performance
- Set up error tracking (e.g., Sentry)

### Logging Strategy

#### Backend Logging
```python
import logging
import structlog

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# Log important events
logger.info("Survey saved", survey_id=survey_id, user_id=user_id, file_count=2)
logger.error("S3 upload failed", error=str(e), bucket=S3_BUCKET)
```

#### Frontend Logging
```javascript
// Error boundary and monitoring
window.addEventListener('error', (event) => {
  console.error('Frontend error:', event.error);
  // Send to monitoring service
});
```

### Performance Monitoring

#### Key Metrics to Track
- API response times
- S3 upload success rates
- Database query performance
- Frontend page load times
- Error rates and types

#### Alerting Thresholds
- API response time > 5 seconds
- Error rate > 5%
- S3 upload failures
- Database connection failures

## Troubleshooting Guide

### Common Issues and Solutions

#### CORS Errors
**Symptoms**: Browser console shows CORS policy errors
**Solutions**:
1. Verify `ALLOWED_ORIGINS` includes frontend URL
2. Ensure both frontend and backend use HTTPS in production
3. Check CORS middleware configuration in FastAPI
4. Redeploy backend after CORS changes

#### S3 Upload Failures
**Symptoms**: Save operation fails, S3-related errors in logs
**Solutions**:
1. Verify AWS credentials are correct
2. Check IAM policy includes `s3:PutObject` permission
3. Confirm bucket name matches environment variable
4. Validate AWS region configuration
5. Test bucket access with AWS CLI

#### Database Connection Issues
**Symptoms**: Backend fails to start, database errors
**Solutions**:
1. Verify `DATABASE_URL` format and credentials
2. Check Render PostgreSQL service status
3. Confirm network connectivity between services
4. Review database connection pooling settings

#### Authentication Problems
**Symptoms**: Login failures, token validation errors
**Solutions**:
1. Verify `SECRET_KEY` is set and consistent
2. Check token expiration settings
3. Ensure clock synchronization between services
4. Review authentication middleware configuration

#### Build and Deployment Failures
**Symptoms**: Services fail to deploy or start
**Solutions**:
1. Check build logs for specific error messages
2. Verify all required environment variables are set
3. Confirm dependency versions are compatible
4. Test build process locally first

### Performance Issues

#### Slow API Responses
1. Check database query performance
2. Optimize S3 upload process
3. Review memory and CPU usage
4. Consider adding caching layer

#### Large File Uploads
1. Implement multipart uploads for large files
2. Add progress indicators
3. Consider file size limits
4. Optimize image compression

### Rollback Procedures

#### Backend Rollback
1. Navigate to Render service dashboard
2. Select previous deployment from history
3. Redeploy previous version
4. Verify service health

#### Frontend Rollback
1. Navigate to Netlify deployments
2. Select previous successful build
3. Publish previous version
4. Clear CDN cache if necessary

#### Database Rollback
1. Use PostgreSQL backup/restore
2. Consider point-in-time recovery
3. Test rollback in staging environment first

## Cost Optimization

### Current Cost Estimates

#### Development/Staging Environment
- **Render Web Service**: $7/month (Starter plan)
- **Render PostgreSQL**: $7/month (Starter plan)
- **AWS S3**: $1-5/month (depending on usage)
- **Netlify**: Free tier sufficient
- **Total**: ~$15-20/month

#### Production Environment
- **Render Web Service**: $25/month (Standard plan)
- **Render PostgreSQL**: $20/month (Standard plan)
- **AWS S3**: $5-20/month (depending on traffic)
- **Netlify**: Free tier or $19/month (Pro)
- **Total**: ~$50-85/month

### Cost Optimization Strategies

#### Immediate Optimizations
1. **S3 Lifecycle Policies**: Archive old files to cheaper storage classes
2. **Database Optimization**: Regular cleanup of unused data
3. **Image Optimization**: Compress PNG files before upload
4. **Monitoring**: Set up billing alerts

#### Long-term Optimizations
1. **CDN Integration**: Use CloudFront for S3 file distribution
2. **Caching**: Implement Redis for session management and caching
3. **Auto-scaling**: Use Render's auto-scaling features
4. **Resource Right-sizing**: Monitor and adjust service plans

### Scaling Considerations

#### Horizontal Scaling
- **API**: Multiple Render instances with load balancing
- **Database**: Read replicas for query distribution
- **Storage**: S3 handles scaling automatically

#### Vertical Scaling
- **Monitor**: CPU, memory, and storage usage
- **Upgrade**: Service plans based on actual usage
- **Optimize**: Code performance before scaling hardware

## Maintenance Schedule

### Daily Tasks
- [ ] Monitor service health and error rates
- [ ] Review application logs for issues
- [ ] Check storage usage and costs

### Weekly Tasks
- [ ] Review performance metrics
- [ ] Update dependencies (security patches)
- [ ] Backup verification
- [ ] Cost analysis and optimization

### Monthly Tasks
- [ ] Security audit and access review
- [ ] Performance optimization analysis
- [ ] Capacity planning review
- [ ] Documentation updates

### Quarterly Tasks
- [ ] Disaster recovery testing
- [ ] Security penetration testing
- [ ] Architecture review and optimization
- [ ] Technology stack evaluation

## Disaster Recovery

### Backup Strategy

#### Database Backups
- **Automated**: Render provides daily backups
- **Manual**: Create backups before major changes
- **Testing**: Regularly test restore procedures

#### File Storage Backups
- **S3 Versioning**: Enabled for accidental deletion recovery
- **Cross-region Replication**: For critical data
- **Local Backups**: Export important survey data

#### Code and Configuration
- **Git Repository**: Primary source of truth
- **Environment Variables**: Document and backup securely
- **Infrastructure**: Terraform state and configurations

### Recovery Procedures

#### Service Outage Recovery
1. **Identify**: Scope and cause of outage
2. **Communicate**: Status to users and stakeholders
3. **Restore**: From most recent stable deployment
4. **Verify**: All services operational
5. **Post-mortem**: Document and improve

#### Data Loss Recovery
1. **Assess**: Extent of data loss
2. **Restore**: From most recent backup
3. **Validate**: Data integrity and completeness
4. **Reconcile**: Any missing data with users

## Support and Documentation

### Documentation Maintenance
- Keep deployment guides updated with changes
- Document all configuration changes
- Maintain troubleshooting knowledge base
- Version control all documentation

### Team Onboarding
- Provide access to all necessary accounts
- Review security practices and procedures
- Hands-on training with deployment process
- Emergency response procedures

### External Resources
- [Render Documentation](https://render.com/docs)
- [Netlify Documentation](https://docs.netlify.com)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [React/Vite Documentation](https://vitejs.dev)

## Conclusion

This unified deployment guide provides a comprehensive approach to deploying the cave survey application with production-ready security, monitoring, and maintenance practices. The modular approach allows for incremental deployment and scaling as requirements evolve.

Key success factors:
- **Security-first**: Private S3 bucket, minimal IAM permissions, secure secrets management
- **Scalability**: Cloud-native services that scale with demand
- **Maintainability**: Infrastructure as Code, comprehensive monitoring, clear procedures
- **Cost-effectiveness**: Right-sized resources with optimization strategies
- **Reliability**: Automated backups, health monitoring, disaster recovery procedures

Follow the phase-by-phase deployment sequence, use the provided checklists for validation, and maintain the recommended monitoring and maintenance practices for a robust production deployment.

## Development Strategy

Target: Individual Cavers in Kentucky Region

  - Focus: Personal cave mapping tools rather than enterprise features
  - Scale: Optimized for individual or small team survey projects
  - Regional: Kentucky karst region initially (specific coordinate systems, declination
  values)

  Open Source Development Approach

  - Community-driven: Engage caver community for feedback and testing
  - Transparent: All development decisions documented and visible
  - Collaborative: Accept contributions from other cave surveyors
  - Standards-based: Follow established cave survey data standards

  ---
  📋 Revised MVP Priorities (Quality-First Approach)

  Phase 1: Pre-MVP Completion (Current Focus)

  1.1 Mathematical Accuracy (Critical)

  - Kentucky-specific magnetic declination implementation
    - Use NOAA declination models for Kentucky region
    - Date-based declination calculations
    - User override capability for known declination values

  1.2 Core Survey Validation

  - Real cave survey testing with Kentucky caves
    - Test with Mammoth Cave system data (if available)
    - Validate against known survey benchmarks
    - Compare with existing survey software results

  1.3 Essential Data Quality

  - Survey closure validation for loop surveys
  - Reasonable bounds checking (shot lengths, angles)
  - Data consistency validation (station connectivity)

  Phase 2: MVP - Manual Data Entry Excellence

  2.1 User Experience for Individual Cavers

  - Intuitive survey data entry (optimized for cave survey workflow)
  - Survey project organization (by cave system, trip date)
  - Data persistence (save/load survey projects)
  - Visualization improvements (plan view, profile view options)

  2.2 Kentucky-Specific Features

  - Local coordinate systems (Kentucky state plane coordinates)
  - Regional cave database integration (known cave entrance coordinates)
  - Export to common formats used by Kentucky cavers

  2.3 Quality Assurance Tools

  - Survey error analysis (closure error reporting)
  - Data validation warnings (unusual shots, potential errors)
  - Survey comparison tools (overlay multiple surveys)

  Phase 3: PoC - Automated Data Input

  3.1 TopoDroid Integration Research

  - TopoDroid data format analysis (understand file formats)
  - Import/export compatibility with TopoDroid
  - Data synchronization workflows

  3.2 Photo-Based Data Entry (Innovative)

  - OCR for handwritten survey notes (research phase)
  - Cave survey book photo processing (table recognition)
  - Manual verification workflows (OCR accuracy checking)

  3.3 Device Integration Planning

  - DistoX data import (common survey instrument)
  - Survey instrument API research
  - Real-time data collection workflows

  ---
  🔬 Technical Deep-Dive Areas

  Mathematical Precision Focus

  Priority 1: Kentucky Magnetic Declination
  - NOAA declination model implementation
  - Historical declination for older surveys
  - Grid vs magnetic vs true north conversions

  Priority 2: Survey Network Adjustment
  - Weighted least squares adjustment
  - Error propagation through survey network
  - Loop closure distribution algorithms

  Regional Specialization

  Kentucky Karst Considerations:
  - Complex multi-level cave systems
  - Large horizontal cave passages
  - Significant vertical components (pits/domes)
  - Connection between cave systems

  Data Quality Standards

  Cave Survey Data Validation:
  - BCRA Grade standards compliance
  - NSS survey standards alignment
  - Error tolerance recommendations
  - Survey loop closure criteria

  ---
  📈 Success Metrics (Quality-First)

  Pre-MVP Completion

  - Accurate processing of 5+ real Kentucky cave surveys
  - Mathematical validation against existing survey data
  - Error rates < 0.1% compared to professional survey software
  - Positive feedback from 3+ local cave surveyors

  MVP Success

  - Used successfully by 10+ individual Kentucky cavers
  - Processing surveys from 5+ different cave systems
  - Integration with local caver workflows
  - Community adoption and contribution

  PoC Success

  - Successful TopoDroid data import/export
  - Prototype OCR for handwritten survey notes
  - Validation with 100+ survey shots from photos
  - Community feedback on automation features

  ---
  🎯 Immediate Next Steps (Quality Focus)

  Week 1-2: Mathematical Foundation

  1. Research Kentucky-specific magnetic declination values
  2. Implement NOAA declination model
  3. Test against known survey data

  Week 3-4: Real-World Validation

  1. Obtain sample Kentucky cave survey data
  2. Process with current system
  3. Compare results with existing tools
  4. Document accuracy improvements needed

  Week 5-8: Community Engagement

  1. Connect with Kentucky cave survey community
  2. Get feedback on current Pre-MVP
  3. Identify priority features for MVP
  4. Establish testing partnerships

  ---
  🤝 Community Development Strategy

  Open Source Engagement

  - GitHub repository with clear contribution guidelines
  - Documentation wiki for cave survey mathematics
  - Community forum for feedback and feature requests
  - Regular progress updates to caver community

  Testing Partners

  - Local grotto survey chairs
  - Experienced cave surveyors in Kentucky
  - Cave survey software users (Compass, Survex users)
  - Academic researchers (WKU, UK speleology programs)

  This approach prioritizes mathematical accuracy and real-world validation over speed,
  ensuring each component is thoroughly tested before moving to the next phase. The focus on
  individual cavers and manual data entry for Pre-MVP allows for perfecting the core
  algorithms before tackling the more complex automation challenges.

  🚀 Account Setup Sequence

  Step 1: AWS Account Setup

  Priority: First (needed for S3 bucket creation)

  1. Create AWS Account:
    - Go to https://aws.amazon.com
    - Click "Create an AWS Account"
    - Provide email, password, and account name
    - Important: You'll need a credit card, but S3 costs will be minimal (~$1-5/month)
  2. Initial AWS Setup:
    - Complete identity verification
    - Choose "Basic Support Plan" (free)
    - Set up billing alerts (recommended: $10 threshold)
  3. Security Setup:
    - Enable MFA (Multi-Factor Authentication) on root account
    - Create an IAM user for daily use (don't use root account)

  Why First: S3 bucket names must be globally unique, so we want to reserve yours early.

  ---
  Step 2: Render Account Setup

  Priority: Second (backend hosting + PostgreSQL database)

  1. Create Render Account:
    - Go to https://render.com
    - Sign up with GitHub (recommended - easier deployment)
    - Or use email signup
  2. Account Benefits:
    - Free tier includes limited resources
    - Easy GitHub integration
    - Automatic deployments from Git pushes

  Why Second: We'll need Render for both the FastAPI backend and PostgreSQL database.

  ---
  Step 3: Netlify Account Setup

  Priority: Third (frontend hosting)

  1. Create Netlify Account:
    - Go to https://netlify.com
    - Sign up with GitHub (recommended)
    - Or use email signup
  2. Account Benefits:
    - Generous free tier (100GB bandwidth/month)
    - Automatic deployments from Git
    - Built-in CI/CD

  Why Third: Frontend depends on backend API URL, so we set this up after Render.

  ---
  📋 Post-Account Setup Checklist

  Once you have all accounts, we'll proceed with:

  Immediate Next Steps:

  1. AWS S3 Bucket Creation (globally unique name)
  2. IAM User Setup (for API access)
  3. Render Service Configuration (backend + database)
  4. Netlify Site Setup (frontend)
  5. Environment Variables Configuration
  6. Testing and Validation

  Account Cost Estimates:

  - AWS: ~$1-5/month (S3 storage + data transfer)
  - Render: $7/month (web service) + $7/month (PostgreSQL) = $14/month
  - Netlify: Free tier (sufficient for Pre-MVP)
  - Total: ~$15-20/month

  ---
  🎯 Ready to Proceed?

  Let me know when you've created these accounts, and I'll help you with:

  1. AWS Setup: S3 bucket creation and IAM configuration
  2. GitHub Repository: Organizing your code for deployment
  3. Render Configuration: Backend and database setup
  4. Netlify Deployment: Frontend hosting
  5. Environment Variables: Secure configuration management

  Would you like me to provide specific guidance for any of these account setups, or shall we
   proceed once you have them created?

  Tip: When creating the AWS account, consider using an email like your-email+aws@domain.com
  to keep AWS-related emails organized.
