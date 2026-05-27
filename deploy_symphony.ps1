# Unified deployment and seeding script for Symphony (Day 3 + Day 4 Tasks)
# Run this AFTER linking a billing/payment account to your GCP project.

$ErrorActionPreference = "Stop"

Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "                   Symphony GCP Deployment & Seeding Tool                 " -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Green

Write-Host "`nChecking active gcloud configuration..." -ForegroundColor Cyan
$account = gcloud config get-value core/account
if (-not $account) {
    Write-Host "ERROR: Please log in to gcloud first by running: gcloud auth login" -ForegroundColor Red
    exit 1
}

Write-Host "`nChecking if GCP project 'symphony-adaptive' exists..." -ForegroundColor Cyan
$projectExists = $false
$check = gcloud projects list --filter="projectId=symphony-adaptive" --format="value(projectId)" 2>$null
if ($check -eq "symphony-adaptive") {
    $projectExists = $true
}

if (-not $projectExists) {
    Write-Host "Project 'symphony-adaptive' was not found in your GCP account." -ForegroundColor Yellow
    $createProj = Read-Host "Would you like this script to create it now? (y/n)"
    if ($createProj -eq 'y' -or $createProj -eq 'yes') {
        $orgId = Read-Host "Enter your GCP Organization ID (optional, press Enter to skip)"
        $folderId = ""
        if (-not $orgId) {
            $folderId = Read-Host "Enter your GCP Folder ID (optional, press Enter to skip)"
        }
        
        Write-Host "`nCreating project 'symphony-adaptive'..." -ForegroundColor Yellow
        if ($orgId) {
            gcloud projects create symphony-adaptive --name="Symphony Adaptive Math" --organization=$orgId
        } elseif ($folderId) {
            gcloud projects create symphony-adaptive --name="Symphony Adaptive Math" --folder=$folderId
        } else {
            gcloud projects create symphony-adaptive --name="Symphony Adaptive Math"
        }
        
        Write-Host "Setting active project to 'symphony-adaptive'..." -ForegroundColor Yellow
        gcloud config set project symphony-adaptive
        
        Write-Host "`n[IMPORTANT] You must link a billing account to the new project before proceeding." -ForegroundColor Cyan
        Write-Host "Please do the following:" -ForegroundColor Cyan
        Write-Host "1. Go to: https://console.cloud.google.com/billing" -ForegroundColor Cyan
        Write-Host "2. Link your billing account to the project 'symphony-adaptive'." -ForegroundColor Cyan
        Read-Host "Press Enter once the billing account is linked to continue..."
    } else {
        Write-Host "ERROR: Project 'symphony-adaptive' does not exist. Please create it or set it as active." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Project 'symphony-adaptive' found. Setting active project..." -ForegroundColor Green
    gcloud config set project symphony-adaptive
}

# --- STEP 1: Enable APIs ---
Write-Host "`nStep 1: Enabling required GCP APIs..." -ForegroundColor Cyan
try {
    gcloud services enable `
      run.googleapis.com `
      sqladmin.googleapis.com `
      secretmanager.googleapis.com `
      cloudbuild.googleapis.com `
      artifactregistry.googleapis.com
    Write-Host "   [SUCCESS] APIs enabled successfully." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to enable APIs. Make sure a billing/payment account is linked to the project 'symphony-adaptive'." -ForegroundColor Red
    exit 1
}

# --- STEP 2: Create Artifact Registry ---
Write-Host "`nStep 2: Creating Artifact Registry Docker repository..." -ForegroundColor Cyan
try {
    gcloud artifacts repositories create symphony-repo `
      --repository-format=docker `
      --location=asia-south1 `
      --description="Symphony container images"
    Write-Host "   [SUCCESS] Repository 'symphony-repo' created." -ForegroundColor Green
} catch {
    if ($_ -match "ALREADY_EXISTS") {
        Write-Host "   Repository 'symphony-repo' already exists." -ForegroundColor Yellow
    } else {
        throw $_
    }
}

# --- STEP 3: Create Cloud SQL PostgreSQL Instance ---
Write-Host "`nStep 3: Creating Cloud SQL (PostgreSQL) Database Instance..." -ForegroundColor Cyan
try {
    $inst = gcloud sql instances list --filter="name=symphony-db" --format="value(name)"
    if ($inst -eq "symphony-db") {
        Write-Host "   Cloud SQL instance 'symphony-db' already exists." -ForegroundColor Yellow
    } else {
        Write-Host "   Creating Cloud SQL instance 'symphony-db' (db-f1-micro, PostgreSQL 15)..." -ForegroundColor Yellow
        Write-Host "   (Note: This operation can take up to 5-10 minutes to complete)" -ForegroundColor DarkYellow
        gcloud sql instances create symphony-db `
          --database-version=POSTGRES_15 `
          --tier=db-f1-micro `
          --region=asia-south1 `
          --storage-type=SSD `
          --storage-size=10GB `
          --backup-start-time=02:00
        Write-Host "   [SUCCESS] Instance 'symphony-db' created." -ForegroundColor Green
    }
} catch {
    Write-Host "ERROR: Failed to create Cloud SQL instance." -ForegroundColor Red
    exit 1
}

# Create Postgres database 'symphony'
try {
    $db_exists = gcloud sql databases list --instance=symphony-db --filter="name=symphony" --format="value(name)"
    if ($db_exists -eq "symphony") {
        Write-Host "   Database 'symphony' already exists." -ForegroundColor Green
    } else {
        Write-Host "   Creating database 'symphony'..." -ForegroundColor Yellow
        gcloud sql databases create symphony --instance=symphony-db
        Write-Host "   [SUCCESS] Database 'symphony' created." -ForegroundColor Green
    }
} catch {
    Write-Host "ERROR: Failed to create database inside SQL instance." -ForegroundColor Red
    exit 1
}

# Prompt user for passwords
Write-Host ""
$db_pw = Read-Host "Enter a strong password for your Cloud SQL Database user (symphony_user)"
$admin_pw = Read-Host "Enter a strong default password for Admin Login"

# Create / configure database user
try {
    $user_exists = gcloud sql users list --instance=symphony-db --filter="name=symphony_user" --format="value(name)"
    if ($user_exists -eq "symphony_user") {
        Write-Host "   User 'symphony_user' already exists. Updating password..." -ForegroundColor Yellow
        gcloud sql users set-password symphony_user `
          --instance=symphony-db `
          --password=$db_pw
    } else {
        Write-Host "   Creating user 'symphony_user'..." -ForegroundColor Yellow
        gcloud sql users create symphony_user `
          --instance=symphony-db `
          --password=$db_pw
        Write-Host "   [SUCCESS] User 'symphony_user' created." -ForegroundColor Green
    }
} catch {
    Write-Host "ERROR: Failed to configure database user." -ForegroundColor Red
    exit 1
}

# --- STEP 4: Configure Secrets ---
Write-Host "`nStep 4: Creating Secrets in Secret Manager..." -ForegroundColor Cyan
$secrets = @("DATABASE_URL", "ADMIN_DEFAULT_PASSWORD", "JWT_SECRET", "FRONTEND_URL")
foreach ($sec in $secrets) {
    try {
        gcloud secrets describe $sec > $null 2>&1
        Write-Host "   Secret already exists: $sec" -ForegroundColor Green
    } catch {
        Write-Host "   Creating secret: $sec" -ForegroundColor Yellow
        gcloud secrets create $sec
    }
}

# Generate a random 64-character JWT secret key
$jwt_sec = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})

# Format database URL targeting Cloud SQL proxy socket inside Cloud Run container
$db_url = "postgresql+psycopg2://symphony_user:$db_pw@/symphony?host=/cloudsql/symphony-adaptive:asia-south1:symphony-db"

Write-Host "   Updating Secret versions..." -ForegroundColor Yellow
[System.IO.File]::WriteAllText("$env:TEMP\db_url.tmp", $db_url)
gcloud secrets versions add DATABASE_URL --data-file="$env:TEMP\db_url.tmp" | Out-Null
Remove-Item "$env:TEMP\db_url.tmp"

[System.IO.File]::WriteAllText("$env:TEMP\admin_pw.tmp", $admin_pw)
gcloud secrets versions add ADMIN_DEFAULT_PASSWORD --data-file="$env:TEMP\admin_pw.tmp" | Out-Null
Remove-Item "$env:TEMP\admin_pw.tmp"

[System.IO.File]::WriteAllText("$env:TEMP\jwt_sec.tmp", $jwt_sec)
gcloud secrets versions add JWT_SECRET --data-file="$env:TEMP\jwt_sec.tmp" | Out-Null
Remove-Item "$env:TEMP\jwt_sec.tmp"

# Temporary localhost frontend mapping (to be updated after Day 5)
[System.IO.File]::WriteAllText("$env:TEMP\fe_url.tmp", "http://localhost:3000")
gcloud secrets versions add FRONTEND_URL --data-file="$env:TEMP\fe_url.tmp" | Out-Null
Remove-Item "$env:TEMP\fe_url.tmp"

Write-Host "   [SUCCESS] Secrets configured with initial versions." -ForegroundColor Green

# --- STEP 5: Grant IAM Permissions ---
Write-Host "`nStep 5: Granting IAM permissions to Default Compute Service Account..." -ForegroundColor Cyan
$proj_num = gcloud projects describe symphony-adaptive --format="value(projectNumber)"
$sa = "$proj_num-compute@developer.gserviceaccount.com"

Write-Host "   Granting Cloud SQL Client role to: $sa" -ForegroundColor Yellow
gcloud projects add-iam-policy-binding symphony-adaptive `
  --member="serviceAccount:$sa" --role="roles/cloudsql.client" | Out-Null

Write-Host "   Granting Secret Manager Secret Accessor roles to service account..." -ForegroundColor Yellow
foreach ($sec in $secrets) {
    gcloud secrets add-iam-policy-binding $sec `
      --member="serviceAccount:$sa" --role="roles/secretmanager.secretAccessor" | Out-Null
}
Write-Host "   [SUCCESS] IAM bindings configured." -ForegroundColor Green

# --- STEP 6: Run Seeding & Data Migration ---
Write-Host "`nStep 6: Seeding Cloud SQL Database..." -ForegroundColor Cyan
$proxyPath = "$env:TEMP\cloud-sql-proxy.exe"

if (-not (Test-Path $proxyPath)) {
    Write-Host "   Downloading Cloud SQL Auth Proxy v2..." -ForegroundColor Yellow
    $url = "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.11.2/cloud-sql-proxy.x64.exe"
    Invoke-WebRequest -Uri $url -OutFile $proxyPath
    Write-Host "   [SUCCESS] Proxy downloaded." -ForegroundColor Green
}

# Launch Cloud SQL Proxy in the background
Write-Host "   Launching Cloud SQL Auth Proxy..." -ForegroundColor Yellow
$proxyProcess = Start-Process -FilePath $proxyPath -ArgumentList "symphony-adaptive:asia-south1:symphony-db" -NoNewWindow -PassThru

# Wait for proxy to establish connection listener
Start-Sleep -s 5

try {
    Write-Host "   Running database importer..." -ForegroundColor Yellow
    $env:DATABASE_URL = "postgresql+psycopg2://symphony_user:$db_pw@127.0.0.1:5432/symphony"
    
    # Run the seed python script to populate PostgreSQL instance
    python backend/seed_data.py
    Write-Host "   [SUCCESS] Cloud SQL PostgreSQL database seeded successfully!" -ForegroundColor Green
} catch {
    Write-Host "   [ERROR] Database seeding failed: $_" -ForegroundColor Red
} finally {
    Write-Host "   Shutting down Cloud SQL Auth Proxy..." -ForegroundColor Yellow
    Stop-Process -Id $proxyProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "   Proxy stopped." -ForegroundColor Green
}

Write-Host "`n==========================================================================" -ForegroundColor Green
Write-Host "[SUCCESS] All GCP Setup & Database Seeding Tasks are Complete!" -ForegroundColor Green
Write-Host "Please continue to Day 4 to build and push the backend docker container." -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Green
