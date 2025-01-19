import csv
import json
import subprocess
import os
import argparse
import logging
from google.cloud import storage
from google.cloud import secretmanager
from google.cloud import resourcemanager_v3
from google.oauth2 import service_account
from urllib.parse import urlparse
import pandas as pd
from tabulate import tabulate

# Configure logging
DEFAULT_LOG_LEVEL = logging.INFO
logging.basicConfig(level=DEFAULT_LOG_LEVEL,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def run_gcloud_auth():
    try:
        logging.debug("Starting GCP OAuth authentication using gcloud CLI.")
        subprocess.run(
            ["gcloud", "auth", "application-default", "login"], check=True)
        logging.info("GCP User OAuth authentication successful.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during GCP User OAuth authentication: {e}")
        exit(1)


def authenticate_gcp(secret_name=None, secret_project_id=None):
    logging.debug("Starting authentication process.")
    logging.info("\n" + "*" * 40)
    logging.info("*          GCP Authentication           *")
    logging.info("*" * 40 + "\n")
    logging.info("Select your authentication method:")
    logging.info("1. GCP User OAuth authentication")
    logging.info("2. GCP OAuth + Service Account from Secret Manager")

    auth_method = input("Enter your choice (1 or 2): ").strip()
    temp_key_path = None

    if auth_method == "1":
        try:
            logging.debug("Checking existing GCP User OAuth authentication.")
            subprocess.run(["gcloud", "auth", "application-default",
                           "print-access-token"], check=True, stdout=subprocess.DEVNULL)
            logging.info("GCP User OAuth already authenticated.")
            return None, None
        except subprocess.CalledProcessError:
            logging.debug(
                "No existing OAuth authentication found. Starting new login.")
            run_gcloud_auth()
            return None, None

    elif auth_method == "2":
        try:
            logging.debug("Using Service Account from Secret Manager.")
            if not secret_name or not secret_project_id:
                secret_name = input(
                    "Enter the name of your Secret Manager secret: ").strip()
                secret_project_id = input(
                    "Enter the project ID containing the secret: ").strip()

            secret_client = secretmanager.SecretManagerServiceClient()
            secret_path = f"projects/{secret_project_id}/secrets/{secret_name}/versions/latest"
            response = secret_client.access_secret_version(name=secret_path)
            service_account_info = response.payload.data.decode("UTF-8")

            temp_key_path = "temp_service_account_key.json"
            with open(temp_key_path, "w") as temp_key_file:
                temp_key_file.write(service_account_info)

            credentials = service_account.Credentials.from_service_account_file(
                temp_key_path)
            logging.info(
                "\nAuthentication successful using Service Account from Secret Manager!")
            return credentials, temp_key_path
        except Exception as e:
            logging.error(f"Error during Service Account retrieval: {e}")
            if temp_key_path and os.path.exists(temp_key_path):
                os.remove(temp_key_path)
            exit(1)

    else:
        logging.error("Invalid choice. Exiting.")
        if temp_key_path and os.path.exists(temp_key_path):
            os.remove(temp_key_path)
        exit(1)


def extract_bucket_name(asset_id):
    logging.debug(f"Extracting bucket name from asset ID: {asset_id}")
    if asset_id.startswith("https://") or asset_id.startswith("gs://"):
        parsed = urlparse(asset_id)
        return parsed.netloc if parsed.netloc else parsed.path
    return asset_id


def get_project_hierarchy(project_id):
    try:
        logging.debug(
            f"Fetching project hierarchy for project ID: {project_id}")
        client = resourcemanager_v3.ProjectsClient()
        project = client.get_project(name=f"projects/{project_id}")
        folder_id = None
        organization_id = None

        parent = project.parent
        if parent.startswith("folders/"):
            folder_id = parent.split("/")[-1]
        elif parent.startswith("organizations/"):
            organization_id = parent.split("/")[-1]

        logging.info(
            f"Retrieved hierarchy for project {project_id}: folder_id={folder_id}, organization_id={organization_id}")
        return {
            "project_id": project_id,
            "folder_id": folder_id,
            "organization_id": organization_id,
        }
    except Exception as e:
        logging.error(
            f"Error retrieving hierarchy for project {project_id}: {e}")
        return {
            "project_id": project_id,
            "folder_id": None,
            "organization_id": None,
            "error": str(e),
        }


def extract_bucket_details(bucket):
    logging.debug(f"Extracting details for bucket: {bucket.name}")
    try:
        bucket.reload()
        raw_metadata = bucket._properties
        metadata = {
            "kind": raw_metadata.get("kind"),
            "selfLink": raw_metadata.get("selfLink"),
            "storageClass": raw_metadata.get("storageClass"),
            "uniformBucketLevelAccess": raw_metadata.get("iamConfiguration", {}).get("uniformBucketLevelAccess", {}).get("enabled"),
            "publicAccessPrevention": raw_metadata.get("iamConfiguration", {}).get("publicAccessPrevention"),
            "locationType": raw_metadata.get("locationType"),
        }
    except Exception as e:
        logging.error(
            f"Error retrieving metadata for bucket {bucket.name}: {e}")
        metadata = {"error": f"Failed to fetch metadata: {str(e)}"}

    try:
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
        logging.debug(
            f"IAM policy for bucket {bucket.name}: {iam_policy_dict}")
    except Exception as e:
        logging.error(
            f"Error retrieving IAM policy for bucket {bucket.name}: {e}")
        iam_policy_dict = {"error": f"Failed to fetch IAM policy: {str(e)}"}

    return {"metadata": metadata, "iam_policy": iam_policy_dict}


def validate_csv(input_csv):
    required_headers = {"Cloud Account ID", "Cloud Asset ID"}
    try:
        logging.debug("Validating input CSV file.")
        with open(input_csv, mode="r") as file:
            reader = csv.DictReader(file)
            headers = set(reader.fieldnames)
            if not required_headers.issubset(headers):
                raise ValueError(
                    f"CSV file must contain the following headers: {required_headers}")
    except Exception as e:
        logging.error(f"Error validating CSV file: {e}")
        exit(1)


def generate_summary_table(results, output_table_csv, display_in_terminal=False):
    summary_data = []

    for project_id, project_data in results.items():
        folder_id = project_data.get("folder_id", "N/A")
        for bucket in project_data.get("buckets", []):
            bucket_name = bucket.get("bucket_name", "Unknown")
            permissions = bucket.get("details", {}).get(
                "iam_policy", {}).get("bindings", [])
            metadata_permissions = [
                f"{binding['role']}: {', '.join(binding['members'])}"
                for binding in permissions
                if binding.get("members")
            ]
            overly_permissive_bindings = bucket.get("details", {}).get(
                "iam_policy", {}).get("bindings", [])
            exposure_match = "Yes" if overly_permissive_bindings else "No"
            if overly_permissive_bindings and not metadata_permissions:
                exposure_match = "Discrepancy"

            summary_data.append({
                "Folder Name/ID": folder_id,
                "Project Name/ID": project_id,
                "Bucket Name": bucket_name,
                "Permissions": "; ".join(metadata_permissions) if metadata_permissions else "None",
                "Exposure Match": exposure_match
            })

    df = pd.DataFrame(summary_data)
    df.to_csv(output_table_csv, index=False)
    logging.info(f"Summary table saved to {output_table_csv}")

    if display_in_terminal:
        print("\nSummary Table:\n")
        print(tabulate(summary_data, headers="keys", tablefmt="grid"))


def investigate_buckets(credentials, input_csv, output_json):
    logging.debug("Starting bucket investigation.")
    storage_client = storage.Client(credentials=credentials)

    results = {}
    with open(input_csv, mode="r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            project_id = row.get("Cloud Account ID")
            asset_id = row.get("Cloud Asset ID")

            if not project_id or not asset_id:
                logging.warning(
                    f"Skipping row with missing project or asset ID: {row}")
                continue

            hierarchy = get_project_hierarchy(project_id)
            folder_id = hierarchy.get("folder_id")
            organization_id = hierarchy.get("organization_id")

            if project_id not in results:
                results[project_id] = {
                    "folder_id": folder_id,
                    "organization_id": organization_id,
                    "buckets": [],
                }

            try:
                bucket_name = extract_bucket_name(asset_id)
                bucket = storage_client.bucket(bucket_name)
                bucket_details = extract_bucket_details(bucket)
                logging.info(
                    f"Successfully processed bucket: {bucket_name} in project: {project_id}")
                results[project_id]["buckets"].append({
                    "bucket_name": bucket_name,
                    "details": bucket_details,
                })

            except Exception as e:
                logging.error(
                    f"Error processing bucket {bucket_name} in project {project_id}: {e}")
                results[project_id]["buckets"].append({
                    "bucket_name": bucket_name,
                    "error": str(e),
                })

    with open(output_json, "w") as json_file:
        json.dump(results, json_file, indent=4)

    logging.info(f"Investigation results saved to {output_json}")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="GCP Storage Bucket Investigation Tool")
        parser.add_argument("--csv", type=str, required=True,
                            help="Path to the input CSV file containing Cloud Account ID and Cloud Asset ID columns.")
        parser.add_argument("--secret-name", type=str,
                            help="Name of the GCP Secret for Service Account authentication (optional).")
        parser.add_argument("--secret-project-id", type=str,
                            help="GCP Project ID where the secret is stored (optional).")
        parser.add_argument("--debug", action="store_true",
                            help="Enable debug-level logging.")

        args = parser.parse_args()

        # Set log level based on --debug flag
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

        validate_csv(args.csv)

        logging.info("\nWelcome to the GCP Storage Bucket Investigation Tool")

        credentials, temp_key_path = authenticate_gcp(
            secret_name=args.secret_name, secret_project_id=args.secret_project_id)

        try:
            input_csv = args.csv
            output_json = "public_bucket_read_investigation.json"
            output_table_csv = "summary_table.csv"

            investigate_buckets(credentials, input_csv, output_json)

            with open(output_json, "r") as json_file:
                results = json.load(json_file)
                generate_summary_table(
                    results, output_table_csv, display_in_terminal=True)
        finally:
            if temp_key_path and os.path.exists(temp_key_path):
                os.remove(temp_key_path)
                logging.info(f"Temporary file {temp_key_path} deleted.")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        raise
