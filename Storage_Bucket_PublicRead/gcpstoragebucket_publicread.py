import os
import json
import subprocess
from google.cloud import storage
from google.cloud import secretmanager
from google.api_core.exceptions import Conflict, PermissionDenied, Forbidden, NotFound

# Authentication method prompt
print("""
*****************************************************************************
*                             Authentication Options                         *
*****************************************************************************
* 1: GCP User OAuth authenticates and has permissions to directly create    *
*    the GCP Storage Bucket.                                                *
*                                                                           *
* 2: Separation of duties - GCP User OAuth authenticates to retrieve the    *
*    Secret Manager secret, and the script will use the service account     *
*    entitlements to create the storage bucket and its policy IAM      *
*    binding.                                                               *
*****************************************************************************
""")

# Get authentication method input from user


def authenticate_gcp():
    auth_method = input("Enter 1 or 2: ").strip()
    temp_key_path = None

    if auth_method == "1":
        # Option 1: GCP User OAuth handles everything
        try:
            subprocess.run(["gcloud", "auth", "application-default",
                           "print-access-token"], check=True, stdout=subprocess.DEVNULL)
            print("GCP User OAuth already authenticated.")
        except subprocess.CalledProcessError:
            run_gcloud_auth()
        print("Using GCP User OAuth to directly create the GCP Storage Bucket.")

    elif auth_method == "2":
        # Option 2: Separation of duties
        try:
            subprocess.run(["gcloud", "auth", "application-default",
                           "print-access-token"], check=True, stdout=subprocess.DEVNULL)
            print("GCP User OAuth already authenticated to retrieve the secret.")
        except subprocess.CalledProcessError:
            run_gcloud_auth()

        # Prompt for the secret name
        secret_name = input(
            "Enter the name of your secret in Secret Manager (mapped to the service account key JSON file): ").strip()
        temp_key_path = get_service_account_key(secret_name, PROJECT_ID)

        # Use the retrieved service account key for further actions
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_key_path
        print("Using Service Account Credentials for bucket operations.")
    else:
        print("Invalid option. Exiting.")
        exit(1)

    return temp_key_path

# Function to run GCP User OAuth authentication


def run_gcloud_auth():
    """
    Executes the 'gcloud auth application-default login' command to authenticate the user.
    """
    try:
        print("Running GCP User OAuth Authentication...")
        subprocess.run(
            ["gcloud", "auth", "application-default", "login"], check=True)
        print("Authentication completed successfully.")
    except FileNotFoundError:
        print("Error: 'gcloud' CLI is not installed or not found in PATH.")
        exit(1)
    except subprocess.CalledProcessError:
        print(
            "Error: Failed to authenticate using 'gcloud auth application-default login'.")
        exit(1)

# Function to retrieve the service account key from Secret Manager


def get_service_account_key(secret_name, project_id):
    """
    Retrieve the service account key from Secret Manager.

    :param secret_name: The name of the secret storing the key.
    :param project_id: Your GCP project ID.
    :return: Path to the temporary JSON key file.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": name})
    except NotFound:
        print(
            f"Error: The secret '{secret_name}' does not exist in the project '{project_id}'.")
        exit(1)
    except PermissionDenied:
        print(
            f"Error: Missing permissions to access the secret {secret_name}. Ensure you have 'roles/secretmanager.secretAccessor'.")
        exit(1)

    key_data = response.payload.data.decode("UTF-8")

    # Save the key to a temporary file
    temp_key_path = "temp_service_account_key.json"
    with open(temp_key_path, "w") as temp_key_file:
        temp_key_file.write(key_data)

    return temp_key_path

# Function to create a public storage bucket


def create_public_bucket(bucket_name, project_id):
    """
    Create a GCP Storage bucket with public read access.

    :param bucket_name: Name of the bucket to be created.
    :param project_id: Your GCP project ID.
    """
    try:
        # Initialize the GCP storage client
        client = storage.Client(project=project_id)

        # Create the bucket
        bucket = client.bucket(bucket_name)
        new_bucket = client.create_bucket(bucket)

        print(f"Bucket {new_bucket.name} created.")

        try:
            # Add public read access IAM binding
            policy = new_bucket.get_iam_policy()
            policy.bindings.append({
                "role": "roles/storage.objectViewer",
                "members": {"allUsers"}
            })
            new_bucket.set_iam_policy(policy)

            print(f"Public read access granted to bucket {bucket_name}.")
        except PermissionDenied:
            print(
                f"Error: Missing permissions to set IAM policy on the bucket {bucket_name}. Ensure you have 'roles/storage.admin' or appropriate permissions.")
            exit(1)
        except Forbidden:
            print(
                f"Error: Forbidden from modifying IAM policies on the bucket {bucket_name}. Check your permissions.")
            exit(1)

        # Set bucket to be publicly readable
        bucket.make_public(recursive=True, future=True)

        print(f"Bucket {bucket_name} is now publicly accessible.")
        print(f"Public URL: https://storage.googleapis.com/{bucket_name}/")

    except Conflict:
        print(f"Bucket {bucket_name} already exists.")
    except PermissionDenied:
        print(
            f"Error: Missing permissions to create the bucket {bucket_name}. Ensure you have 'roles/storage.admin' or appropriate permissions.")
        exit(1)
    except Forbidden:
        print(
            f"Error: Forbidden from creating the bucket {bucket_name}. Check your permissions.")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        exit(1)


if __name__ == "__main__":
    # Prompt for bucket name and project ID
    BUCKET_NAME = input("Enter the desired bucket name: ").strip()
    PROJECT_ID = input("Enter your GCP project ID: ").strip()

    # Authenticate and possibly retrieve a temporary key
    temp_key_path = authenticate_gcp()

    try:
        create_public_bucket(BUCKET_NAME, PROJECT_ID)
    finally:
        # Clean up the temporary key file
        if temp_key_path and os.path.exists(temp_key_path):
            os.remove(temp_key_path)
            print(f"Temporary key file {temp_key_path} deleted.")
