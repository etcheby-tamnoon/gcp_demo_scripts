import os
import json
import argparse
import logging
import subprocess
from google.cloud import storage
from google.cloud import secretmanager
from google.api_core.exceptions import Conflict, PermissionDenied, Forbidden, NotFound

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def authenticate_gcp():
    """
    Prompts the user for authentication method and performs the required authentication.

    Returns:
        temp_key_path (str): Path to the temporary key file if created.
    """
    print("""
*****************************************************************************
*                             Authentication Options                         *
*****************************************************************************
* 1: GCP User OAuth authenticates and has permissions to directly create    *
*    the GCP Storage Bucket.                                                *
*                                                                           *
* 2: Separation of duties - GCP User OAuth authenticates to retrieve the    *
*    Secret Manager secret, and the script will use the service account     *
*    key JSON (secret) to create the storage bucket and its policy IAM      *
*    binding.                                                               *
*****************************************************************************
""")

    auth_method = input("Enter 1 or 2: ").strip()
    temp_key_path = None

    if auth_method == "1":
        logger.debug("Chosen authentication method: GCP User OAuth")
        try:
            subprocess.run(["gcloud", "auth", "application-default", "print-access-token"], check=True, stdout=subprocess.DEVNULL)
            logger.info("GCP User OAuth already authenticated.")
        except subprocess.CalledProcessError:
            run_gcloud_auth()
        logger.info("Using GCP User OAuth to directly create the GCP Storage Bucket.")

    elif auth_method == "2":
        logger.debug("Chosen authentication method: Service Account Key via Secret Manager")
        try:
            subprocess.run(["gcloud", "auth", "application-default", "print-access-token"], check=True, stdout=subprocess.DEVNULL)
            logger.info("GCP User OAuth authenticated to retrieve the secret.")
        except subprocess.CalledProcessError:
            run_gcloud_auth()

        secret_name = args.secret_name or input("Enter the name of your secret in Secret Manager: ").strip()
        logger.debug(f"Using secret name: {secret_name}")
        temp_key_path = get_service_account_key(secret_name, args.project_id)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_key_path
        logger.debug(f"GOOGLE_APPLICATION_CREDENTIALS set to: {temp_key_path}")
        logger.info("Using Service Account Credentials for bucket operations.")
    else:
        logger.error("Invalid authentication option. Exiting.")
        exit(1)

    return temp_key_path

def run_gcloud_auth():
    """Executes the 'gcloud auth application-default login' command to authenticate the user."""
    try:
        logger.info("Running GCP User OAuth Authentication...")
        subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)
        logger.info("Authentication completed successfully.")
    except FileNotFoundError:
        logger.error("'gcloud' CLI is not installed or not found in PATH.")
        exit(1)
    except subprocess.CalledProcessError:
        logger.error("Failed to authenticate using 'gcloud auth application-default login'.")
        exit(1)

def get_service_account_key(secret_name, project_id):
    """
    Retrieve the service account key from Secret Manager.

    Args:
        secret_name (str): The name of the secret storing the key.
        project_id (str): Your GCP project ID.

    Returns:
        str: Path to the temporary JSON key file.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": name})
        key_data = response.payload.data.decode("UTF-8")
        logger.debug(f"Secret {secret_name} retrieved successfully from project {project_id}.")
    except NotFound:
        logger.error(f"Secret '{secret_name}' does not exist in project '{project_id}'.")
        exit(1)
    except PermissionDenied:
        logger.error(f"Missing permissions to access the secret '{secret_name}'.")
        exit(1)

    temp_key_path = "temp_service_account_key.json"
    with open(temp_key_path, "w") as temp_key_file:
        temp_key_file.write(key_data)
        logger.debug(f"Service account key saved to temporary file: {temp_key_path}")

    return temp_key_path

def create_public_bucket(bucket_name, project_id):
    """
    Create a GCP Storage bucket with public read access.

    Args:
        bucket_name (str): Name of the bucket to be created.
        project_id (str): Your GCP project ID.
    """
    try:
        logger.debug(f"Initializing GCP Storage client for project {project_id}")
        client = storage.Client(project=project_id)

        logger.debug(f"Attempting to create bucket: {bucket_name}")
        bucket = client.bucket(bucket_name)
        new_bucket = client.create_bucket(bucket)
        logger.info(f"Bucket {new_bucket.name} created successfully.")

        try:
            policy = new_bucket.get_iam_policy()
            logger.debug(f"Current IAM policy: {json.dumps(policy.to_api_repr(), indent=2)}")
            policy.bindings.append({
                "role": "roles/storage.objectViewer",
                "members": {"allUsers"}
            })
            new_bucket.set_iam_policy(policy)
            logger.debug(f"Updated IAM policy: {json.dumps(policy.to_api_repr(), indent=2)}")
            logger.info(f"Public read access granted to bucket {bucket_name}.")
        except (PermissionDenied, Forbidden):
            logger.error(f"Missing permissions to set IAM policy on bucket {bucket_name}.")
            exit(1)

        bucket.make_public(recursive=True, future=True)
        logger.info(f"Bucket {bucket_name} is now publicly accessible at https://storage.googleapis.com/{bucket_name}/")

    except Conflict:
        logger.error(f"Bucket {bucket_name} already exists.")
    except (PermissionDenied, Forbidden):
        logger.error(f"Missing permissions to create bucket {bucket_name}.")
        exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a GCP Storage bucket with public access.")
    parser.add_argument("--bucket-name", type=str, help="Name of the GCP Storage bucket to create.")
    parser.add_argument("--project-id", type=str, help="GCP project ID where the bucket will be created.")
    parser.add_argument("--secret-name", type=str, help="Name of the Secret Manager secret containing service account key.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    bucket_name = args.bucket_name or input("Enter the desired bucket name: ").strip()
    logger.debug(f"Bucket name provided: {bucket_name}")

    project_id = args.project_id or input("Enter your GCP project ID: ").strip()
    logger.debug(f"Project ID provided: {project_id}")

    temp_key_path = authenticate_gcp()

    try:
        create_public_bucket(bucket_name, project_id)
    finally:
        if temp_key_path and os.path.exists(temp_key_path):
            os.remove(temp_key_path)
            logger.debug(f"Temporary key file {temp_key_path} deleted.")
