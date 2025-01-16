# GCP Storage Bucket Management Script

This Python script allows you to create a publicly accessible Google Cloud Platform (GCP) Storage Bucket with two modes of operation:

1. **Direct Creation via GCP User OAuth**
2. **Separation of Duties**: 
GCP User retrieves Service Account key JSON from Secret Manager, and code uses it to perform bucket operations.

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
If needed, [download and install Python]
(https://www.python.org/downloads/).

### Configure GCP Authentication
- **For GCP User OAuth**: 
Ensure the `gcloud` CLI is installed and configured.
  ```bash
  gcloud auth application-default login
  ```
- **Separation of Duties**: 
Ensure Service Account JSON key stored securely in [GCP Secret Manager]
(https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets).

### Required IAM Permissions
- **For GCP User OAuth**:
  - `roles/storage.admin` to create buckets and manage their IAM policies.
  - `roles/secretmanager.secretAccessor` to access secrets from Secret Manager (if using Option 2).

- **For Service Account**:
  - `roles/storage.admin` to create buckets and manage IAM policies.

-------

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
- **Permissions**: 
Detects missing IAM roles (e.g., `roles/storage.admin`, `roles/secretmanager.secretAccessor`).
- **Authentication**: 
Prompts for `gcloud` authentication if necessary.
- **Conflict**: 
Handles bucket name conflicts gracefully.

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
Ensure the user or service account has the necessary permissions listed in the [Prerequisites](#prerequisites) section.

---

