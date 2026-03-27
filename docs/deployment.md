# Cloud Deployment Guide

## Architecture

```
┌──────────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  Firebase Hosting │────▶│  Cloud Run (API)   │────▶│  Cloud SQL (PG)  │
│  React SPA        │     │  FastAPI + Uvicorn │     │  PostgreSQL 15   │
│  /api/* → proxy   │     │  Port 8080         │     │  asia-east2      │
└──────────────────┘     └───────────────────┘     └──────────────────┘
         │                        │
         │                 Secret Manager
         │              (API keys, DB URL)
         │
    CDN (global)
```

- **Frontend**: Firebase Hosting (global CDN, SPA mode)
- **Backend**: Cloud Run (asia-east2, Hong Kong)
- **Database**: Cloud SQL PostgreSQL 15 (asia-east2)
- **Secrets**: Secret Manager
- **Container Registry**: Artifact Registry (asia-east2)
- **CI/CD**: GitHub Actions

## Prerequisites

```bash
# Install tools
npm install -g firebase-tools
# gcloud CLI: https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login
firebase login
```

## Step 1: GCP Project Setup

```bash
# Set project
export PROJECT_ID=your-project-id
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  cloudbuild.googleapis.com
```

## Step 2: Artifact Registry

```bash
gcloud artifacts repositories create quant-api \
  --repository-format=docker \
  --location=asia-east2 \
  --description="Quant API Platform containers"
```

## Step 3: Cloud SQL (PostgreSQL)

```bash
# Create instance (takes ~5 minutes)
gcloud sql instances create quant-api-db \
  --database-version=POSTGRES_15 \
  --region=asia-east2 \
  --cpu=1 \
  --memory=3840MB \
  --storage-size=10GB \
  --storage-auto-increase

# Create database
gcloud sql databases create quantdb --instance=quant-api-db

# Create user
gcloud sql users create quantuser \
  --instance=quant-api-db \
  --password=YOUR_SECURE_PASSWORD

# Get connection name (needed for Cloud Run)
gcloud sql instances describe quant-api-db --format='value(connectionName)'
# Output: PROJECT_ID:asia-east2:quant-api-db
```

## Step 4: Secret Manager

```bash
# Create secrets
for SECRET in DATABASE_URL FMP_API_KEY MASSIVE_API_KEY OPENFIGI_API_KEY \
  SEC_USER_AGENT T212_API_KEY T212_API_SECRET; do
  gcloud secrets create $SECRET --replication-policy=automatic
done

# Set DATABASE_URL (use Cloud SQL connection name format)
echo -n "postgresql://quantuser:YOUR_PASSWORD@/quantdb?host=/cloudsql/PROJECT_ID:asia-east2:quant-api-db" \
  | gcloud secrets versions add DATABASE_URL --data-file=-

# Set API keys
echo -n "your-fmp-key" | gcloud secrets versions add FMP_API_KEY --data-file=-
echo -n "your-polygon-key" | gcloud secrets versions add MASSIVE_API_KEY --data-file=-
echo -n "your-email@example.com" | gcloud secrets versions add SEC_USER_AGENT --data-file=-
# ... repeat for each secret

# Grant Cloud Run access to secrets
export SA=$(gcloud iam service-accounts list --filter="Cloud Run" --format='value(email)' | head -1)
for SECRET in DATABASE_URL FMP_API_KEY MASSIVE_API_KEY OPENFIGI_API_KEY \
  SEC_USER_AGENT T212_API_KEY T212_API_SECRET; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
done
```

## Step 5: Build & Deploy Backend

```bash
# Build container
gcloud builds submit \
  --tag asia-east2-docker.pkg.dev/$PROJECT_ID/quant-api/backend:prod

# Deploy to Cloud Run
gcloud run deploy quant-api \
  --image asia-east2-docker.pkg.dev/$PROJECT_ID/quant-api/backend:prod \
  --region asia-east2 \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances $PROJECT_ID:asia-east2:quant-api-db \
  --set-env-vars "FEATURE_T212_LIVE_SUBMIT=false,API_PREFIX=/api,APP_ENV=production" \
  --set-secrets "DATABASE_URL_OVERRIDE=DATABASE_URL:latest,FMP_API_KEY=FMP_API_KEY:latest,MASSIVE_API_KEY=MASSIVE_API_KEY:latest,SEC_USER_AGENT=SEC_USER_AGENT:latest,OPENFIGI_API_KEY=OPENFIGI_API_KEY:latest,T212_API_KEY=T212_API_KEY:latest,T212_API_SECRET=T212_API_SECRET:latest" \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 300
```

## Step 6: Database Migration

```bash
# Run Alembic migration via Cloud Run job or local connection
# Option A: Connect locally via Cloud SQL Auth Proxy
cloud-sql-proxy $PROJECT_ID:asia-east2:quant-api-db &
DATABASE_URL_OVERRIDE="postgresql://quantuser:PASSWORD@localhost:5432/quantdb" \
  alembic -c infra/alembic.ini upgrade head

# Option B: Run via Cloud Run Jobs
gcloud run jobs create db-migrate \
  --image asia-east2-docker.pkg.dev/$PROJECT_ID/quant-api/backend:prod \
  --region asia-east2 \
  --set-env-vars APP_ENV=production \
  --set-secrets DATABASE_URL_OVERRIDE=DATABASE_URL:latest \
  --add-cloudsql-instances $PROJECT_ID:asia-east2:quant-api-db \
  --command "alembic" \
  --args "-c,infra/alembic.ini,upgrade,head"

gcloud run jobs execute db-migrate --region asia-east2
```

## Step 7: Deploy Frontend

```bash
# Build frontend with API prefix
cd frontend-react
VITE_API_BASE=/api npm run build

# Initialize Firebase (first time only)
cd ..
firebase init hosting
# Select: existing project, public: frontend-react/dist, SPA: Yes

# Deploy
firebase deploy --only hosting
```

## Step 8: Verify

```bash
# Check API health
curl https://YOUR_CLOUD_RUN_URL/api/health

# Check frontend
open https://YOUR_FIREBASE_URL

# Check all critical paths
curl https://YOUR_CLOUD_RUN_URL/api/instruments
curl https://YOUR_CLOUD_RUN_URL/api/dq/issues
```

## Security Boundaries (Enforced in Production)

- `FEATURE_T212_LIVE_SUBMIT=false` — live broker submission disabled
- Approval gate is mandatory and cannot be bypassed
- Research and execution layers are decoupled
- Risk checks run before any broker submission
- Trading 212 is readonly by default

## Cost Estimate (Monthly)

| Service | Estimate |
|---------|----------|
| Cloud Run (min 0, low traffic) | $0 - $5 |
| Cloud SQL (1 vCPU, 3.75GB) | ~$30 |
| Artifact Registry | < $1 |
| Secret Manager | < $1 |
| Firebase Hosting | $0 (Spark plan) |
| **Total** | **~$30 - $37/month** |

To reduce costs: stop Cloud SQL when not in use (`gcloud sql instances patch quant-api-db --activation-policy=NEVER`).

## Rollback

```bash
# List recent revisions
gcloud run revisions list --service quant-api --region asia-east2

# Route traffic to previous revision
gcloud run services update-traffic quant-api \
  --to-revisions PREVIOUS_REVISION=100 \
  --region asia-east2
```

## China Access Notes

- Firebase Hosting uses Google's global CDN — may be slow or blocked in mainland China
- Cloud Run in asia-east2 (Hong Kong) provides best latency for China-adjacent access
- For mainland China users, consider Cloudflare or custom domain with CDN
- API calls from China may experience higher latency (~100-300ms)
