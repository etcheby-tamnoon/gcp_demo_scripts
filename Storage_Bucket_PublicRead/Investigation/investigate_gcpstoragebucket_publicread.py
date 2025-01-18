import csv
import json
import subprocess
import os
import argparse
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

# Extract specific metadata and IAM policy for a bucket


def extract_bucket_details(bucket):
    try:
        bucket.reload()  # Fetch the latest metadata
        raw_metadata = bucket._properties  # Full bucket metadata

        # Extract only required fields from metadata
        metadata = {
            "kind": raw_metadata.get("kind"),
            "selfLink": raw_metadata.get("selfLink"),
            "storageClass": raw_metadata.get("storageClass"),
            "uniformBucketLevelAccess": raw_metadata.get("iamConfiguration", {}).get("uniformBucketLevelAccess", {}).get("enabled"),
            "publicAccessPrevention": raw_metadata.get("iamConfiguration", {}).get("publicAccessPrevention"),
            "locationType": raw_metadata.get("locationType"),
        }
    except Exception as e:
        print(f"Error retrieving metadata for bucket {bucket.name}: {e}")
        metadata = {"error": f"Failed to fetch metadata: {str(e)}"}

    try:
        # Explicitly request IAM policy version 3
        iam_policy = bucket.get_iam_policy(requested_policy_version=3)
        iam_policy_dict = {
            "bindings": [
                {
                    "role": binding["role"],
                    "members": [
                        member for member in binding["members"] if member in {"allUsers", "allAuthenticatedUsers"}
                    ],
                }
                for binding in iam_policy.bindings
                if any(member in {"allUsers", "allAuthenticatedUsers"} for member in binding["members"])
            ]
        }
    except Exception as e:
        print(f"Error retrieving IAM policy for bucket {bucket.name}: {e}")
        iam_policy_dict = {"error": f"Failed to fetch IAM policy: {str(e)}"}

    return {"metadata": metadata, "iam_policy": iam_policy_dict}

# Validate CSV file


def validate_csv(input_csv):
    required_headers = {"Cloud Account ID", "Cloud Asset ID"}
    try:
        with open(input_csv, mode="r") as file:
            reader = csv.DictReader(file)
            headers = set(reader.fieldnames)
            if not required_headers.issubset(headers):
                raise ValueError(
                    f"CSV file must contain the following headers: {required_headers}")
    except Exception as e:
        print(f"Error validating CSV file: {e}")
        exit(1)

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
                bucket_details = extract_bucket_details(bucket)
                results[project_id].append({
                    "bucket_name": bucket_name,
                    "details": bucket_details,
                })

            except Exception as e:
                print(
                    f"Error processing bucket {bucket_name} in project {project_id}: {e}")
                results[project_id].append({
                    "bucket_name": bucket_name,
                    "error": str(e),
                })

    with open(output_json, "w") as json_file:
        json.dump(results, json_file, indent=4)

    print(f"Investigation results saved to {output_json}")


# Main execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GCP Storage Bucket Investigation Tool")
    parser.add_argument("--csv", type=str, required=True,
                        help="Path to the input CSV file containing Cloud Account ID and Cloud Asset ID columns.")
    args = parser.parse_args()

    validate_csv(args.csv)

    print("\nWelcome to the GCP Storage Bucket Investigation Tool")

    credentials, temp_key_path = authenticate_gcp()

    try:
        input_csv = args.csv
        output_json = "public_bucket_read_investigation.json"

        investigate_buckets(credentials, input_csv, output_json)
    finally:
        if temp_key_path and os.path.exists(temp_key_path):
            os.remove(temp_key_path)
            print(f"Temporary file {temp_key_path} deleted.")
