# GCP Storage Bucket - Public Read Deployment Script

This Python script allows you to create a publicly accessible Google Cloud Platform (GCP) Storage Bucket with two modes of operation:

1. **Direct Creation via GCP User OAuth**
2. **Separation of Duties**: GCP User retrieves Service Account key JSON from Secret Manager, and code uses it to perform bucket operations.

---

## Prerequisites

### Install Required Libraries
Ensure the following Python libraries are installed:
```bash
pip3 install -r requirements.txt
```

### Python Version
This script requires **Python 3.9 or higher**. Check your Python version with:
```bash
python3 --version
```
If needed, [download and install Python](https://www.python.org/downloads/).

### Configure GCP Authentication
- **For GCP User OAuth**: 
Ensure the `gcloud` CLI is installed and configured.
  ```bash
  gcloud auth application-default login
  ```
- **Separation of Duties**: 
Ensure Service Account JSON key is stored securely in [GCP Secret Manager](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets).

### Required IAM Permissions

#### **Option 1: Direct Creation via GCP User OAuth**
The user account must have the following granular permissions:
- **Storage Bucket Permissions**:
  - `storage.buckets.create`: To create buckets.
  - `storage.buckets.get`: To check bucket existence.
  - `storage.buckets.getIamPolicy`: To fetch bucket IAM policies.
  - `storage.buckets.setIamPolicy`: To set bucket IAM policies.
- **Recommended Predefined Role**: Assign `roles/storage.admin`.

If accessing secrets from Secret Manager:
- **Secret Manager Permissions**:
  - `secretmanager.secrets.get`: To access the secret.
  - `secretmanager.versions.access`: To retrieve the secret version.
- **Recommended Predefined Role**: Assign `roles/secretmanager.secretAccessor`.

#### **Option 2: Separation of Duties**
- **For GCP User (to access Secret Manager)**:
  - `secretmanager.secrets.get`: To access the secret.
  - `secretmanager.versions.access`: To retrieve the secret version.
  - **Recommended Predefined Role**: Assign `roles/secretmanager.secretAccessor`.

- **For Service Account (to manage Storage Bucket)**:
  - `storage.buckets.create`: To create buckets.
  - `storage.buckets.get`: To check bucket existence.
  - `storage.buckets.getIamPolicy`: To fetch bucket IAM policies.
  - `storage.buckets.setIamPolicy`: To set bucket IAM policies.
  - **Recommended Predefined Role**: Assign `roles/storage.admin`.

---

## Usage Instructions

### Step 1: Clone or Download the Script
Save the script to a local directory.

### Step 2: Execute the Script
Run the script using Python:
```bash
python3 <script_name>.py
```

### Step 3: Follow the Prompts
The script will prompt you to choose one of the following options:

#### **Option 1: Direct Bucket Creation via GCP User OAuth**
1. Select option `1`.
2. Enter the desired bucket name and project ID.
3. The script will directly use your GCP User OAuth credentials to create the bucket and set its IAM policy.

#### **Option 2: Separation of Duties**
1. Select option `2`.
2. Enter the name of the secret in Secret Manager that stores the Service Account key JSON.
3. The script will:
   - Use GCP User OAuth to fetch the secret.
   - Use the retrieved Service Account key JSON to create the bucket and set its IAM policy.

---

## Script Features

### Error Handling
- **Permissions**: Detects missing IAM roles (e.g., `roles/storage.admin`, `roles/secretmanager.secretAccessor`) and provides actionable error messages.
- **Authentication**: Prompts for `gcloud` authentication if necessary.
- **Conflict**: Handles bucket name conflicts gracefully.

### Cleanup
- Deletes temporary files (e.g., Service Account key JSON) after execution.

---

## Example Output

**Execution Example:**
```text
Select your Google Cloud authentication method:
1. GCP User OAuth authenticates and has permissions to directly create the GCP Storage Bucket.
2. Separation of duties - GCP User OAuth authenticates to retrieve the Secret Manager secret, and the script will use the service account key JSON (secret) to create the storage bucket and its policy IAM binding.
Enter 1 or 2: 1

Enter the desired bucket name: my-public-bucket
Enter your GCP project ID: my-gcp-project
Bucket my-public-bucket created.
Public read access granted to bucket my-public-bucket.
Bucket my-public-bucket is now publicly accessible.
Public URL: https://storage.googleapis.com/my-public-bucket/
```

---

## Notes
- **Security**: Avoid hardcoding secrets. Use GCP Secret Manager for secure secret storage.
- **IAM Best Practices**: Assign minimal permissions necessary for each role.

---

## Troubleshooting

### Missing `gcloud` CLI
If you encounter an error related to `gcloud`, install it:
```bash
https://cloud.google.com/sdk/docs/install
```

### Permission Errors
If you encounter permission errors, ensure the user or service account has the necessary permissions listed in the [Prerequisites](#prerequisites) section. Check the assigned roles and policies using:
```bash
gcloud projects get-iam-policy <PROJECT_ID>
```

---
