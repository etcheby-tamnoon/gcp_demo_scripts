import csv
import json
import subprocess
import os
from google.cloud import storage
from google.cloud import secretmanager
from google.oauth2 import service_account
from urllib.parse import urlparse


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
        try:
            subprocess.run(["gcloud", "auth", "application-default",
                           "print-access-token"], check=True, stdout=subprocess.DEVNULL)
            print("GCP User OAuth already authenticated.")
            return None, None
        except subprocess.CalledProcessError:
            run_gcloud_auth()
            return None, None

    elif auth_method == "2":
        try:
            secret_name = input(
                "Enter the name of your Secret Manager secret: ").strip()
            project_id = input(
                "Enter the project ID containing the secret: ").strip()

            secret_client = secretmanager.SecretManagerServiceClient()
            secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = secret_client.access_secret_version(name=secret_path)
            service_account_info = response.payload.data.decode("UTF-8")

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

# Normalize bucket name


def extract_bucket_name(asset_id):
    if asset_id.startswith("https://") or asset_id.startswith("gs://"):
        parsed = urlparse(asset_id)
        return parsed.netloc if parsed.netloc else parsed.path
    return asset_id

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
    storage_client = storage.Client(credentials=credentials)

    results = {}
    with open(input_csv, mode="r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            project_id = row.get("Cloud Account ID")
            asset_id = row.get("Cloud Asset ID")

            if not project_id or not asset_id:
                print(f"Skipping row with missing project or asset ID: {row}")
                continue

            bucket_name = extract_bucket_name(asset_id)
            if project_id not in results:
                results[project_id] = []

            try:
                bucket = storage_client.bucket(bucket_name)
                policy = bucket.get_iam_policy()
                overly_permissive_bindings = check_overly_permissive_policies(
                    policy)

                bucket_info = {
                    "bucket_name": bucket_name,
                    "overly_permissive_bindings": overly_permissive_bindings,
                }
                results[project_id].append(bucket_info)

            except Exception as e:
                print(
                    f"Error processing bucket {bucket_name} in project {project_id}: {e}")
                results[project_id].append(
                    {"bucket_name": bucket_name, "error": str(e)})

    with open(output_json, "w") as json_file:
        json.dump(results, json_file, indent=4)

    print(f"Investigation results saved to {output_json}")


# Main execution
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
