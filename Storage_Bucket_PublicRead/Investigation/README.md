# GCP Storage Bucket(s) Public Read Investigation Tool
![Tool Logo](images/Tamnoon.png)

## Overview
The **GCP Storage Bucket Public Read Investigation Tool** is a Python script designed to identify GCP storage buckets that have overly permissive IAM bindings allowing public/anonymous read access.
It provides a detailed investigation of storage buckets across multiple GCP projects and outputs the results in a JSON file.

## Features
- **GCP Authentication Options**:
  - GCP User OAuth authentication (using `gcloud` CLI).
  - Service Account JSON key retrieval from Google Secret Manager, with the ability to specify secret name and project ID via command-line arguments.

- **Script Flow**:
  - From Tamnoon Alerts CSV export, parses `Cloud Account ID (Project ID)` & `Cloud Asset Name (Storage Bucket Name)` column values.
  - Queries GCP storage buckets using the GCP API to retrieve metadata and IAM policies.
  - Identifies overly permissive IAM bindings (`roles/storage.objectViewer`, `roles/storage.legacyBucketReader`, etc.) granting access to `allUsers` or `allAuthenticatedUsers`.
  - Provides a JSON report summarizing findings per GCP project.
  - Includes additional project-level details like folder and organization hierarchy.
  - Handles exceptions such as permission errors and invalid configurations.
  - Securely manages temporary files for Service Account JSON keys.

## Prerequisites
1. **Python Environment**: Ensure Python 3.7 or higher is installed.
2. **Dependencies**: Install required Python libraries using the provided `requirements.txt` file:
   ```bash
   pip3 install -r requirements.txt
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
- The GCP user executing the script must also have permissions to access the secret in Secret Manager:
  - `secretmanager.secrets.access`
  - `secretmanager.versions.access`
  - `secretmanager.secrets.get`

### Additional Features
- **Project Hierarchy Retrieval**: Queries the GCP organizational hierarchy to include folder and organization details for each project.
- **Bucket Scanning**: The script lists buckets in each project specified in the input CSV file.
- **Policy Analysis**: Examines IAM bindings to detect public read access permissions.
- **Error Handling**: Logs errors related to permission issues or invalid configurations.

## Input
- **CSV File**: CSV export from Tamnoon's Alerts with `Cloud Account ID (Project ID)` & `Cloud Asset Name (Storage Bucket Name)` columns for the script to investigate.

## Output
- **JSON Report**: The script generates a JSON file (`public_bucket_read_investigation.json`) containing the following details:
  - **Project Details**:
    - `project_id`: The GCP project ID.
    - `folder_id`: The GCP folder ID, if applicable.
    - `organization_id`: The GCP organization ID, if applicable.
  - **Bucket Details**:
    - `bucket_name`: Name of the storage bucket.
    - `metadata`: Key storage bucket attributes, including:
      - `kind`, `selfLink`, `storageClass`, `uniformBucketLevelAccess`, `publicAccessPrevention`, `locationType`.
    - `iam_policy`: IAM bindings granting public access to `allUsers` or `allAuthenticatedUsers`.
    - `error` (if any): Describes permission or access issues.

## How to Run
1. Clone the repository and navigate to the script directory.
2. Prepare the input CSV file with `Cloud Account ID (Project ID)` and `Cloud Asset Name (Storage Bucket Name)` columns.
3. Run the script with one of the following options:

   - **Option 1**: Authenticate using `gcloud` CLI:
     ```bash
     python3 investigate_gcpstoragebucket_publicread.py --csv /path/to/csv_file.csv
     ```

   - **Option 2**: Authenticate using a Service Account JSON key retrieved from Secret Manager:
     ```bash
     python3 investigate_gcpstoragebucket_publicread.py --csv /path/to/csv_file.csv --secret-name my-secret --secret-project-id my-project-id
     ```

4. Follow the prompts for any additional input if required.
5. The results will be saved to `public_bucket_read_investigation.json`.

## Example JSON Output
```json
{
  "project-1": {
    "folder_id": "1234567890",
    "organization_id": "9876543210",
    "buckets": [
      {
        "bucket_name": "example-bucket-1",
        "metadata": {
          "kind": "storage#bucket",
          "selfLink": "https://www.googleapis.com/storage/v1/b/example-bucket-1",
          "storageClass": "STANDARD",
          "uniformBucketLevelAccess": true,
          "publicAccessPrevention": "enforced",
          "locationType": "multi-region"
        },
        "iam_policy": {
          "bindings": [
            {
              "role": "roles/storage.objectViewer",
              "members": ["allUsers"]
            }
          ]
        }
      }
    ]
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

