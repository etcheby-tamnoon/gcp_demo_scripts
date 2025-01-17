# GCP Storage Bucket Public Read Investigation Tool

## Overview
The **GCP Storage Bucket Public Read Investigation Tool** is a Python script designed to identify GCP storage buckets that have overly permissive IAM bindings allowing public read access. It provides a detailed investigation of storage buckets across multiple GCP projects and outputs the results in a JSON file.

## Features
- **Authentication Options**:
  - GCP User OAuth authentication (using `gcloud` CLI).
  - Service Account JSON key retrieval from Google Secret Manager.
- Detects IAM bindings granting public read access (`roles/storage.objectViewer`, `roles/storage.legacyBucketReader`, etc.) to `allUsers` or `allAuthenticatedUsers`.
- Provides a JSON report summarizing findings per GCP project.
- Handles exceptions such as permission errors and invalid configurations.
- Securely handles temporary files for Service Account JSON keys.

## Prerequisites
1. **Python Environment**: Ensure Python 3.7 or higher is installed.
2. **Dependencies**: Install required Python libraries using the provided `requirements.txt` file:
   ```bash
   pip install -r requirements.txt
   ```
3. **gcloud CLI**: Install and configure the Google Cloud SDK (`gcloud`) for OAuth authentication.
4. **Service Account**: For authentication via Secret Manager, ensure a Service Account with the necessary permissions is created and stored in Secret Manager.

## Permissions Required

### Authentication Methods
#### Option 1: GCP User OAuth Authentication
- Requires the user to be authenticated via the `gcloud` CLI.
- The user must have the following permissions:
  - `storage.buckets.get`
  - `storage.buckets.getIamPolicy`
  - `resourcemanager.projects.get`

#### Option 2: Service Account from Secret Manager
- The Service Account must have:
  - `storage.buckets.get`
  - `storage.buckets.getIamPolicy`
  - `resourcemanager.projects.get`
- The user executing the script must have permissions to access the secret in Secret Manager:
  - `secretmanager.secrets.access`
  - `secretmanager.versions.access`
  - `secretmanager.secrets.get`

### Script Features
- **Bucket Scanning**: The script lists buckets in each project specified in the input CSV file.
- **Policy Analysis**: Examines IAM bindings to detect public read access permissions.
- **Error Handling**: Logs errors related to permission issues or invalid configurations.

## Input
- **CSV File**: A CSV file containing a `project_id` column with GCP project IDs to investigate.

## Output
- **JSON Report**: The script generates a JSON file (`public_bucket_read_investigation.json`) containing the following details:
  - **Project ID**: The GCP project ID.
  - **Bucket Details**:
    - `bucket_name`: Name of the storage bucket.
    - `location`: Location of the storage bucket.
    - `overly_permissive_bindings`: A list of IAM bindings granting public read access.
    - `error` (if any): Describes permission or access issues.

## How to Run
1. Clone the repository and navigate to the script directory.
2. Prepare the input CSV file with a `project_id` column.
3. Run the script:
   ```bash
   python investigate_gcpstoragebucket_publicread.py
   ```
4. Follow the prompts to select your authentication method:
   - **Option 1**: Authenticate using `gcloud` CLI.
   - **Option 2**: Authenticate using a Service Account JSON key retrieved from Secret Manager.
5. Provide the path to the input CSV file.
6. The results will be saved to `public_bucket_read_investigation.json`.

## Example JSON Output
```json
{
  "project-1": [
    {
      "bucket_name": "example-bucket-1",
      "location": "US",
      "overly_permissive_bindings": [
        {
          "role": "roles/storage.objectViewer",
          "members": ["allUsers"]
        }
      ]
    },
    {
      "bucket_name": "example-bucket-2",
      "location": "EU",
      "overly_permissive_bindings": []
    }
  ],
  "project-2": {
    "error": "Access Denied"
  }
}
```

## Security Considerations
- **Temporary Files**: The script securely handles temporary files for Service Account JSON keys and deletes them immediately after use.
- **Access Control**: Ensure the executing user or Service Account has only the necessary permissions to minimize security risks.

## Troubleshooting
1. **Error: Access Denied**
   - Verify that the user or Service Account has the required permissions.
2. **Error: Secret Manager Access Denied**
   - Ensure the user has `secretmanager.secrets.access`, `secretmanager.versions.access`, and `secretmanager.secrets.get` permissions.
3. **OAuth Authentication Issues**
   - Run `gcloud auth application-default login` manually to reauthenticate.


