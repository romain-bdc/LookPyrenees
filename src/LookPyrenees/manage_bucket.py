"""This module allow to download, upload and delete data on google cloud storage"""

import logging
import os

from google.cloud import storage  # type: ignore

os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")


def load_on_gcs(bucket_name, source_file, destination_blob):
    """
    Upload images to the bucket on Google Cloud Storage (GCS)
    """
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
        logging.info("File %s uploaded to bucket %s.", filename, bucket_name)
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


def check_files_on_bucket(bucket_name, name, zone):
    """This function allow to check if an image already exists before download it"""
    # Create a client
    client = storage.Client()

    # Get the bucket
    bucket = client.bucket(bucket_name)

    # List all blobs in the bucket
    blobs = list(client.list_blobs(bucket))

    date = name.split("_")[2].split("T")[0]
    tile = name.split("_")[5]

    matches = [date, tile, zone]
    # Check each blob name for the substring
    if len(blobs) > 0:
        for blob in blobs:
            if all(elem in blob.name for elem in matches):
                return True

    return False
