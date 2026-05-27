# Symphony GCP Deployment Guide
## Manual Steps After Running the Setup Script

---

## Immediately After Running the Script

### 1. Save Your Passwords Somewhere Safe
- The `symphony_user` database password you entered
- The admin default password you entered
- The JWT secret is auto-generated and stored in Secret Manager *(you don't need it separately)*

---

## Day 4 — Build & Push Docker Container

### 2. Authenticate Docker with GCP
```bash
gcloud auth configure-docker asia-south1-docker.pkg.dev
```

### 3. Build Your Docker Image Locally
```bash
docker build -t asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/backend:latest ./backend
```

### 4. Push the Image to Artifact Registry
```bash
docker push asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/backend:latest
```

---

## Day 5 — Deploy & Go Live

### 5. Deploy to Cloud Run
```bash
gcloud run deploy symphony-backend \
  --image=asia-south1-docker.pkg.dev/symphony-adaptive/symphony-repo/backend:latest \
  --region=asia-south1 \
  --add-cloudsql-instances=symphony-adaptive:asia-south1:symphony-db \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,JWT_SECRET=JWT_SECRET:latest
```

### 6. Get Your Live Public URL
After deployment, Cloud Run gives you a URL like:
```
https://symphony-backend-xxxx-el.a.run.app
```
> **Note:** Save this URL — you will need it for the next step.

### 7. Update the FRONTEND_URL Secret
Replace the temporary `localhost` placeholder with your real frontend URL:
```bash
echo "https://your-real-frontend-url.com" | gcloud secrets versions add FRONTEND_URL --data-file=-
```

---

## Verify Everything Works

### 8. Test the Database Connection
Hit a health-check endpoint of your deployed Cloud Run service to confirm the database is reachable.

### 9. Test Admin Login
Use the admin password you set during the script to verify login works correctly.

### 10. Deploy Your Frontend
If your frontend is a separate app, deploy it and point it to the Cloud Run backend URL obtained in Step 6.

---

## Summary Checklist

| #  | Task                          | When         | Status |
|----|-------------------------------|--------------|--------|
| 1  | Save passwords                | Right now    | ⬜     |
| 2  | Authenticate Docker with GCP  | Day 4        | ⬜     |
| 3  | Build Docker image            | Day 4        | ⬜     |
| 4  | Push to Artifact Registry     | Day 4        | ⬜     |
| 5  | Deploy to Cloud Run           | Day 5        | ⬜     |
| 6  | Note the live public URL      | Day 5        | ⬜     |
| 7  | Update FRONTEND_URL secret    | Day 5        | ⬜     |
| 8  | Test database connection      | Day 5        | ⬜     |
| 9  | Test admin login              | Day 5        | ⬜     |
| 10 | Deploy frontend               | Day 5        | ⬜     |

---

## What the Setup Script Already Completed

| Task                        | Status |
|-----------------------------|--------|
| GCP APIs enabled            | ✅     |
| Artifact Registry created   | ✅     |
| Cloud SQL instance created  | ✅     |
| Database & user configured  | ✅     |
| Secrets stored              | ✅     |
| IAM permissions granted     | ✅     |
| Database seeded             | ✅     |

---

*Generated for Symphony GCP Deployment — asia-south1 (Mumbai) region*
