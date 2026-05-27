# Symphony GCP Deployment Roadmap — June 1 Go-Live

> **Target:** Google Cloud Run (Backend + Frontend) + Cloud SQL (PostgreSQL) + Secret Manager  
> **Timeline:** May 25 → June 1, 2026 (7 days)  
> **Stack:** FastAPI + SQLAlchemy · Next.js 14 · SQLite → PostgreSQL

---

## At a Glance

```
Day 1  ── Pre-flight: Security fixes & missing deps
Day 2  ── Dockerize backend + frontend
Day 3  ── GCP project + Cloud SQL + Secret Manager
Day 4  ── Deploy backend Cloud Run service
Day 5  ── Deploy frontend Cloud Run service
Day 6  ── CI/CD with Cloud Build + domain wiring
Day 7  ── Smoke test + go-live ✅
```

---

## Day 1 — Pre-flight: Fix Blockers Before Any Cloud Work

> These are **not optional**. Deploying the current code to production is a security risk.

### 1.1 — Add `psycopg2-binary` to `requirements.txt`

`database.py` switches to Postgres via `DATABASE_URL`, but the driver is missing.

```diff
# backend/requirements.txt
+psycopg2-binary>=2.9.9
```

### 1.2 — Fix Password Hashing in `main.py`

`passlib[bcrypt]` is already in `requirements.txt` but **not used**.  
`_hash_password()` currently uses plain `hashlib.sha256` — replace it:

```diff
# backend/app/main.py
-import hashlib
+from passlib.context import CryptContext

+pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

-def _hash_password(password: str) -> str:
-    return hashlib.sha256(password.encode()).hexdigest()
-
-def _verify_password(plain: str, hashed: str) -> bool:
-    return hashlib.sha256(plain.encode()).hexdigest() == hashed

+def _hash_password(password: str) -> str:
+    return pwd_context.hash(password)
+
+def _verify_password(plain: str, hashed: str) -> bool:
+    return pwd_context.verify(plain, hashed)
```

### 1.3 — Replace Hardcoded Admin Credentials

The seed function in `main.py` uses `"admin123"` hardcoded. Replace with env var:

```diff
# backend/app/main.py  _seed_admin()
-admin = AdminUser(username="admin", hashed_password=_hash_password("admin123"), ...)
+import os
+_default_pw = os.getenv("ADMIN_DEFAULT_PASSWORD", "changeme")
+admin = AdminUser(username="admin", hashed_password=_hash_password(_default_pw), ...)
```

### 1.4 — Restrict CORS in `main.py`

```diff
# backend/app/main.py
+FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
 app.add_middleware(
     CORSMiddleware,
-    allow_origins=["*"],
+    allow_origins=[FRONTEND_URL],
     allow_credentials=True,
     allow_methods=["*"],
     allow_headers=["*"],
 )
```

### 1.5 — Add `.dockerignore` files

```
# backend/.dockerignore
__pycache__/
*.pyc
*.db
.env
venv/
*.xlsx
*.docx
*.pdf
```

```
# frontend/.dockerignore
node_modules/
.next/
.env*
```

**End of Day 1 checkpoint:** Run `uvicorn app.main:app --reload` locally — confirm it still works.

---

## Day 2 — Dockerize Backend + Frontend

### 2.1 — Backend `Dockerfile`

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects $PORT (default 8080)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

### 2.2 — Frontend `Dockerfile`

Create `frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# NEXT_PUBLIC_API_URL is baked in at build time
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
CMD ["node", "server.js"]
```

> **Important:** Enable Next.js standalone output. Add to `next.config.js`:
> ```js
> module.exports = { output: 'standalone' }
> ```

### 2.3 — Local Docker smoke test

```powershell
# Backend
docker build -t symphony-backend ./backend
docker run -p 8080:8080 -e DATABASE_URL="sqlite:///./test.db" symphony-backend

# Frontend
docker build --build-arg NEXT_PUBLIC_API_URL=http://localhost:8080 -t symphony-frontend ./frontend
docker run -p 3000:3000 symphony-frontend
```

**End of Day 2 checkpoint:** Both containers start and respond locally.

---

## Day 3 — GCP Project + Cloud SQL + Secret Manager

### 3.1 — Enterprise Onboarding & Folder Setup

To set up the project securely under your company’s ownership, follow this structured workflow to create the organization, configure the team directory, nest the project under a folder, and attach the billing account.

#### A. Set up the GCP Organization
1. Go to the [Google Cloud Identity Sign-up page](https://cloud.google.com/identity) (or use your existing Google Workspace console).
2. Complete domain verification for your company domain (e.g., `company.com`).
3. Once verified, Google Cloud automatically creates your root **Organization** resource.
4. Retrieve your Organization ID by running:
   ```bash
   gcloud organizations list
   ```
   *Note the `ORGANIZATION_ID` matching your domain.*

#### B. Add Team Members (Founder, Teammates, and You)
Add all team members to the organization to grant permissions:
1. Log into the Google Admin Console (`admin.google.com`) or Cloud Identity Admin.
2. Go to **Directory > Users > Add new user**.
3. Create accounts for:
   *   The Founder
   *   Teammates
   *   Your professional email
4. Assign team permissions in the GCP console (**IAM & Admin > IAM**):
   *   Grant the Founder/Admins the **Organization Administrator** and **Billing Account Administrator** roles.
   *   Grant yourself and core developers the **Project Creator** and **Folder Creator** roles at the organization level.

#### C. Create a Folder for the Project
Create a Folder under your organization to isolate and group Symphony resources:
```bash
gcloud resource-manager folders create \
  --display-name="Symphony-Project" \
  --organization=YOUR_ORGANIZATION_ID
```
*Note the generated `FOLDER_ID` from the command output.* (You can also find this in **IAM & Admin > Manage Resources** in the GCP Console).

#### D. Link or Create the Project inside the Folder
Depending on whether you are reusing the existing project or starting fresh:

*   **Option 1: Move the existing project into the Folder** (retains settings/names):
    ```bash
    gcloud beta projects move symphony-adaptive --folder=YOUR_FOLDER_ID
    ```
*   **Option 2: Create a brand new project directly in the Folder** (if starting fresh):
    ```bash
    gcloud projects create symphony-adaptive \
      --name="Symphony Adaptive Math" \
      --folder=YOUR_FOLDER_ID
    ```

#### E. Link the Billing Account
A billing account must be attached to the project to enable SQL and Cloud Run.
1. Find your Billing Account ID:
   ```bash
   gcloud billing accounts list
   ```
2. Link the billing account to your project:
   ```bash
   gcloud billing projects link symphony-adaptive \
     --billing-account=YOUR_BILLING_ACCOUNT_ID
   ```

#### F. Enable Services
Configure active project and enable required APIs:
```bash
# Ensure gcloud is targeting the correct project ID
gcloud config set project symphony-adaptive

# Enable services
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

### 3.2 — Create Artifact Registry

```bash
gcloud artifacts repositories create symphony-repo \
  --repository-format=docker \
  --location=asia-south1 \
  --description="Symphony container images"
```

### 3.3 — Create Cloud SQL (PostgreSQL)

```bash
gcloud sql instances create symphony-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=asia-south1 \
  --storage-type=SSD \
  --storage-size=10GB \
  --backup-start-time=02:00

gcloud sql databases create symphony --instance=symphony-db
gcloud sql users create symphony_user \
  --instance=symphony-db \
  --password=<STRONG_PASSWORD>
```

> **Connection string format for Cloud Run:**
> ```
> postgresql+psycopg2://symphony_user:<PW>@/symphony?host=/cloudsql/symphony-adaptive:asia-south1:symphony-db
> ```

### 3.4 — Store All Secrets in Secret Manager

```bash
# DATABASE_URL
echo -n "postgresql+psycopg2://symphony_user:<PW>@/symphony?host=/cloudsql/symphony-adaptive:asia-south1:symphony-db" \
  | gcloud secrets create DATABASE_URL --data-file=-

# Admin default password
echo -n "<STRONG_ADMIN_PW>" | gcloud secrets create ADMIN_DEFAULT_PASSWORD --data-file=-

# JWT secret (if used in admin.py)
echo -n "<RANDOM_64_CHAR_STRING>" | gcloud secrets create JWT_SECRET --data-file=-

# Frontend URL (fill in after Day 5)
echo -n "https://symphony-frontend-HASH-uc.a.run.app" \
  | gcloud secrets create FRONTEND_URL --data-file=-
```

### 3.5 — Grant Cloud Run Access to Cloud SQL + Secrets

```bash
# Cloud Run uses the default compute service account
PROJECT_NUMBER=$(gcloud projects describe symphony-adaptive --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Cloud SQL
gcloud projects add-iam-policy-binding symphony-adaptive \
  --member="serviceAccount:${SA}" --role="roles/cloudsql.client"

# Secret Manager
gcloud secrets add-iam-policy-binding DATABASE_URL \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding ADMIN_DEFAULT_PASSWORD \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding FRONTEND_URL \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
```

**End of Day 3 checkpoint:** `gcloud sql connect symphony-db --user=symphony_user` works.

---

## Day 4 — Deploy Backend Cloud Run Service

### 4.1 — Build & Push Backend Image

```bash
cd backend
docker build -t asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/backend:v1 .
docker push asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/backend:v1
```

### 4.2 — Deploy Backend to Cloud Run

```bash
gcloud run deploy symphony-backend \
  --image=asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/backend:v1 \
  --region=asia-south1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=60 \
  --add-cloudsql-instances=symphony-adaptive:asia-south1:symphony-db \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,ADMIN_DEFAULT_PASSWORD=ADMIN_DEFAULT_PASSWORD:latest,FRONTEND_URL=FRONTEND_URL:latest"
```

### 4.3 — Verify Backend

```bash
BACKEND_URL=$(gcloud run services describe symphony-backend \
  --region=asia-south1 --format='value(status.url)')

curl "$BACKEND_URL/health"
# → {"status": "ok"}

curl "$BACKEND_URL/docs"
# → FastAPI Swagger UI
```

> At this point, `Base.metadata.create_all(bind=engine)` runs on startup — this **auto-creates all 9 tables** in Cloud SQL (`skills`, `questions`, `q_matrix`, `answer_traps`, `question_dimensions`, `students`, `sessions`, `responses`, `bkt_state`).

### 4.4 — Import the Question Bank

Your XLSX-based importer needs to run once against the Cloud SQL database:

```bash
# Port-forward Cloud SQL locally via Cloud SQL Proxy, then:
cd backend
DATABASE_URL="postgresql+psycopg2://symphony_user:<PW>@localhost:5432/symphony" \
  python -m app.importer.import_data  # adjust to your actual importer entry point
```

**End of Day 4 checkpoint:** `GET $BACKEND_URL/docs` shows all routes. Question bank is loaded.

---

## Day 5 — Deploy Frontend Cloud Run Service

### 5.1 — Build & Push Frontend Image

```bash
cd frontend
docker build \
  --build-arg NEXT_PUBLIC_API_URL="$BACKEND_URL" \
  -t asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/frontend:v1 .
docker push asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/frontend:v1
```

### 5.2 — Deploy Frontend to Cloud Run

```bash
gcloud run deploy symphony-frontend \
  --image=asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/frontend:v1 \
  --region=asia-south1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5 \
  --set-env-vars="NEXT_PUBLIC_API_URL=$BACKEND_URL"
```

### 5.3 — Update FRONTEND_URL Secret

```bash
FRONTEND_URL=$(gcloud run services describe symphony-frontend \
  --region=asia-south1 --format='value(status.url)')

echo -n "$FRONTEND_URL" | gcloud secrets versions add FRONTEND_URL --data-file=-

# Redeploy backend to pick up updated FRONTEND_URL for CORS
gcloud run services update symphony-backend \
  --region=asia-south1 \
  --set-secrets="FRONTEND_URL=FRONTEND_URL:latest"
```

**End of Day 5 checkpoint:** Open `$FRONTEND_URL` in browser — the app loads and calls the backend successfully.

---

## Day 6 — CI/CD with Cloud Build + (Optional) Custom Domain

### 6.1 — `cloudbuild.yaml` at repo root

Create `cloudbuild.yaml`:

```yaml
steps:
  # --- Backend ---
  - name: 'gcr.io/cloud-builders/docker'

    args:
      - build
      - -t
      - 'asia-south1-docker.pkg.dev/$PROJECT_ID/symphony-repo/backend:$SHORT_SHA'
      - ./backend

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'asia-south1-docker.pkg.dev/$PROJECT_ID/symphony-repo/backend:$SHORT_SHA']

  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - run
      - deploy
      - symphony-backend
      - --image=asia-south1-docker.pkg.dev/$PROJECT_ID/symphony-repo/backend:$SHORT_SHA
      - --region=asia-south1
      - --platform=managed

  # --- Frontend ---
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - build
      - --build-arg
      - 'NEXT_PUBLIC_API_URL=https://symphony-backend-HASH-uc.a.run.app'
      - -t
      - 'asia-south1-docker.pkg.dev/$PROJECT_ID/symphony-repo/frontend:$SHORT_SHA'
      - ./frontend

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'asia-south1-docker.pkg.dev/$PROJECT_ID/symphony-repo/frontend:$SHORT_SHA']

  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - run
      - deploy
      - symphony-frontend
      - --image=asia-south1-docker.pkg.dev/$PROJECT_ID/symphony-repo/frontend:$SHORT_SHA
      - --region=asia-south1
      - --platform=managed

options:
  logging: CLOUD_LOGGING_ONLY
```

### 6.2 — Connect Cloud Build to GitHub

```bash
# In GCP Console: Cloud Build → Triggers → Connect Repository
# Select your GitHub repo → Branch: main → Build config: cloudbuild.yaml
```

Every `git push` to `main` now triggers a full build and deploy of both services.

### 6.3 — (Optional) Custom Domain

```bash
gcloud run domain-mappings create \
  --service=symphony-frontend \
  --domain=symphony.yourdomain.com \
  --region=asia-south1

# Add the CNAME/A records shown in the output to your DNS provider
```

**End of Day 6 checkpoint:** Push a test commit — both services redeploy automatically.

---

## Day 7 — Smoke Test + Go-Live Verification

### 7.1 — End-to-End Checklist

| Test | Expected Result |
|---|---|
| `GET $BACKEND_URL/health` | `{"status": "ok"}` |
| `GET $BACKEND_URL/docs` | Swagger UI, all routes visible |
| Open `$FRONTEND_URL` | App loads, no console CORS errors |
| Create a student + start a session | `/session/start` returns first question |
| Answer a question | `/session/respond` returns next question, BKT updates |
| Admin login at `/admin` | JWT issued, dashboard loads |
| CORS violation test from random origin | Request blocked (403) |
| Simulate 10 concurrent sessions | All respond within 3s (Cloud Run auto-scales) |

### 7.2 — Confirm Database State

```bash
gcloud sql connect symphony-db --user=symphony_user
\dt         -- lists all 9 tables
SELECT COUNT(*) FROM questions;   -- should match your XLSX import count
SELECT COUNT(*) FROM skills;
```

### 7.3 — Cost Estimate (at launch scale)

| Resource | Config | Est. Monthly Cost |
|---|---|---|
| Cloud Run – Backend | 1 vCPU, 1Gi, ~1000 req/day | ~$2–5 |
| Cloud Run – Frontend | 1 vCPU, 512Mi, ~1000 req/day | ~$1–3 |
| Cloud SQL | db-f1-micro, 10 GB SSD | ~$9 |
| Secret Manager | 5 secrets, <10k accesses | ~$0 |
| Artifact Registry | ~2 GB images | ~$0.20 |
| **Total** | | **~$12–17/month** |

---

## Critical Files to Create/Modify

| File | Action | Reason |
|---|---|---|
| `backend/Dockerfile` | **CREATE** | Containerize FastAPI |
| `frontend/Dockerfile` | **CREATE** | Containerize Next.js |
| `backend/.dockerignore` | **CREATE** | Exclude .db, .xlsx, venv |
| `frontend/.dockerignore` | **CREATE** | Exclude node_modules, .next |
| `backend/requirements.txt` | **MODIFY** | Add `psycopg2-binary` |
| `backend/app/main.py` | **MODIFY** | bcrypt, env-based CORS, env-based admin PW |
| `backend/app/database.py` | **READY** | Already env-driven ✅ |
| `frontend/next.config.js` | **MODIFY** | Add `output: 'standalone'` |
| `cloudbuild.yaml` | **CREATE** | CI/CD pipeline |

> [!CAUTION]
> Delete `render.yaml` from the repo root **before** pushing to GCP. The `symphony-db` free plan on Render expires after 90 days and will be a confusing dead reference once Cloud SQL is live.

> [!IMPORTANT]
> The `adaptive_math.db` SQLite file must **never** be committed or copied to Cloud Run. Cloud Run instances are ephemeral — any write to the local filesystem is lost on restart. All data must go through `DATABASE_URL` → Cloud SQL from Day 4 onward.
