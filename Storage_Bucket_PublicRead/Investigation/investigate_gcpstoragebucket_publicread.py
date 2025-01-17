import csv
import json
import subprocess
import os
from google.cloud import storage
from google.cloud import secretmanager
from google.oauth2 import service_account


def run_gcloud_auth():
    try:
        subprocess.run(
            ["gcloud", "auth", "application-default", "login"], check=True)
        print("GCP User OAuth authentication successful.")
    except subprocess.CalledProcessError as e:
        print(f"Error during GCP User OAuth authentication: {e}")
        exit(1)

# Authentication function


def authenticate_gcp():
    print("\n" + "*" * 40)
    print("*          GCP Authentication           *")
    print("*" * 40 + "\n")
    print("Select your authentication method:")
    print("1. GCP User OAuth authentication")
    print("2. GCP OAuth + Service Account from Secret Manager")

    auth_method = input("Enter your choice (1 or 2): ").strip()
    temp_key_path = None

    if auth_method == "1":
        # Option 1: GCP User OAuth handles everything
        try:
            subprocess.run(["gcloud", "auth", "application-default",
                           "print-access-token"], check=True, stdout=subprocess.DEVNULL)
            print("GCP User OAuth already authenticated.")
            return None, None  # No credentials or temp key needed for this method
        except subprocess.CalledProcessError:
            run_gcloud_auth()
            return None, None  # Ensure successful re-authentication returns

    elif auth_method == "2":
        # Option 2: GCP OAuth + Service Account from Secret Manager
        try:
            secret_name = input(
                "Enter the name of your Secret Manager secret: ").strip()
            project_id = input(
                "Enter the project ID containing the secret: ").strip()

            secret_client = secretmanager.SecretManagerServiceClient()
            secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = secret_client.access_secret_version(name=secret_path)
            service_account_info = response.payload.data.decode("UTF-8")

            # Save the key to a temporary file
            temp_key_path = "temp_service_account_key.json"
            with open(temp_key_path, "w") as temp_key_file:
                temp_key_file.write(service_account_info)

            credentials = service_account.Credentials.from_service_account_file(
                temp_key_path)
            print(
                "\nAuthentication successful using Service Account from Secret Manager!")
            return credentials, temp_key_path
        except Exception as e:
            print(f"Error during Service Account retrieval: {e}")
            if temp_key_path and os.path.exists(temp_key_path):
                os.remove(temp_key_path)
            exit(1)

    else:
        print("Invalid choice. Exiting.")
        if temp_key_path and os.path.exists(temp_key_path):
            os.remove(temp_key_path)
        exit(1)

# Check overly permissive policies


def check_overly_permissive_policies(bucket_iam_policy):
    overly_permissive_roles = [
        {"role": "roles/storage.objectViewer",
            "members": ["allUsers", "allAuthenticatedUsers"]},
        {"role": "roles/storage.legacyBucketReader",
            "members": ["allUsers", "allAuthenticatedUsers"]},
        {"role": "roles/storage.legacyBucketWriter",
            "members": ["allUsers", "allAuthenticatedUsers"]},
    ]

    overly_permissive_bindings = []

    for binding in bucket_iam_policy.get("bindings", []):
        for overly_permissive_role in overly_permissive_roles:
            if binding["role"] == overly_permissive_role["role"] and any(
                member in binding["members"] for member in overly_permissive_role["members"]
            ):
                overly_permissive_bindings.append(binding)

    return overly_permissive_bindings

# Extract bucket metadata and IAM policies


def investigate_buckets(credentials, input_csv, output_json):
    # Initialize storage client
    storage_client = storage.Client(credentials=credentials)

    # Read input CSV
    projects = []
    with open(input_csv, mode="r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            projects.append(row["project_id"])

    # Initialize output data
    result = {}

    for project_id in projects:
        print(f"Investigating project: {project_id}")
        result[project_id] = []

        try:
            buckets = storage_client.list_buckets(project=project_id)

            for bucket in buckets:
                bucket_info = {
                    "bucket_name": bucket.name,
                    "location": bucket.location,
                }

                try:
                    policy = bucket.get_iam_policy()
                    overly_permissive_bindings = check_overly_permissive_policies(
                        policy)

                    if overly_permissive_bindings:
                        bucket_info["overly_permissive_bindings"] = overly_permissive_bindings
                    else:
                        bucket_info["overly_permissive_bindings"] = []

                except Exception as e:
                    if "403" in str(e) or "Access Denied" in str(e):
                        print(f"Access Denied for bucket {bucket.name}: {e}")
                        bucket_info["error"] = "Access Denied"
                    else:
                        print(
                            f"Error fetching IAM policy for bucket {bucket.name}: {e}")
                        bucket_info["error"] = str(e)

                result[project_id].append(bucket_info)

        except Exception as e:
            if "403" in str(e) or "Access Denied" in str(e):
                print(f"Access Denied for project {project_id}: {e}")
                result[project_id] = {"error": "Access Denied"}
            else:
                print(f"Error listing buckets for project {project_id}: {e}")
                result[project_id] = {"error": str(e)}

    # Write results to output JSON
    with open(output_json, "w") as json_file:
        json.dump(result, json_file, indent=4)

    print(f"Investigation results saved to {output_json}")


# Usage example
if __name__ == "__main__":
    print("\nWelcome to the GCP Storage Bucket Investigation Tool")

    credentials, temp_key_path = authenticate_gcp()

    try:
        input_csv = input("Enter the full path to your CSV file: ").strip()
        output_json = "public_bucket_read_investigation.json"

        investigate_buckets(credentials, input_csv, output_json)
    finally:
        if temp_key_path and os.path.exists(temp_key_path):
            os.remove(temp_key_path)
            print(f"Temporary file {temp_key_path} deleted.")
