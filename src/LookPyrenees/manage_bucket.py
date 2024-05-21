"""This module allow to download, upload and delete data on google cloud storage"""

import logging
import os

from google.cloud import storage  # type: ignore

CREDS = os.environ.get("CREDS_PATH", "/creds/")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDS


def load_on_gcs(bucket_name, source_file, destination_blob):
    """
    Upload images to the bucket on Google Cloud Storage (GCS)
    """
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file = "local/path/to/file"
    # The ID of your GCS object
    # destination_blob = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request to upload is aborted if the object's
    # generation number does not match your precondition. For a destination
    # object that does not yet exist, set the if_generation_match precondition to 0.
    # If the destination object already exists in your bucket, set instead a
    # generation-match precondition using its generation number.
    generation_match_precondition = 0

    stats = blob.exists(storage_client)
    filename = source_file.split("/")[-1]
    if not stats:
        blob.upload_from_filename(source_file, if_generation_match=generation_match_precondition)
        logging.info("File %s uploaded to %s.", filename, destination_blob)
    else:
        logging.info("File %s already exists", destination_blob)


def delete_blob(bucket_name, blob_name):
    """Deletes a blob from the bucket."""

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    generation_match_precondition = None

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request to delete is aborted if the object's
    # generation number does not match your precondition.
    blob.reload()  # Fetch blob metadata to use in generation_match_precondition.
    generation_match_precondition = blob.generation

    stats = blob.exists(storage_client)
    if stats:
        blob.delete(if_generation_match=generation_match_precondition)
        logging.info("Blob %s deleted.", blob_name)
    else:
        logging.info("File %s does not exists", blob_name)
