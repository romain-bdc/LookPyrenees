"""This module allow to download, upload and delete data on google cloud storage"""

import datetime
import json
import logging
import os
import re
import tempfile
from pathlib import Path

from google.cloud import storage

os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

ORIG_PREFIX = "orig/"
THUMB_PREFIX = "thumb/"
VIEW_PREFIX = "view/"
MANIFEST_BLOB = "manifest.json"

IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
MANIFEST_CACHE = "public, max-age=300"

# T31TCH_20240511T103629_TCI_10m_rulhe_nerassol.png
IMAGE_NAME_RE = re.compile(r"^(?P<tile>T\w{5})_(?P<datetime>\d{8}T\d{6})_TCI_10m_(?P<zone>.+)\.png$")


def load_on_gcs(bucket_name, source_file, destination_blob, content_type=None, cache_control=None):
    """
    Upload images to the bucket on Google Cloud Storage (GCS)
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    if cache_control is not None:
        blob.cache_control = cache_control

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
        blob.upload_from_filename(
            source_file, content_type=content_type, if_generation_match=generation_match_precondition
        )
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

    # Originals live in orig/; legacy images (before the static site) sit at the bucket root
    blobs = [
        blob for blob in client.list_blobs(bucket)
        if blob.name.startswith(ORIG_PREFIX) or "/" not in blob.name
    ]

    date = name.split("_")[2].split("T")[0]
    tile = name.split("_")[5]

    matches = [date, tile, zone]
    # Check each blob name for the substring
    if len(blobs) > 0:
        for blob in blobs:
            if all(elem in blob.name for elem in matches):
                return True

    return False


def parse_image_name(filename):
    """Extract tile, datetime and zone from an image filename, None if it does not match"""
    match = IMAGE_NAME_RE.match(Path(filename).name)
    if match is None:
        return None
    return match.groupdict()


def build_manifest(bucket_name):
    """Write manifest.json listing every original image of the bucket, grouped by zone"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    zones = {}
    for blob in client.list_blobs(bucket, prefix=ORIG_PREFIX):
        name = blob.name[len(ORIG_PREFIX):]
        info = parse_image_name(name)
        if info is None:
            continue
        webp = Path(name).with_suffix(".webp").name
        date = info["datetime"]
        zones.setdefault(info["zone"], []).append({
            "date": f"{date[:4]}-{date[4:6]}-{date[6:8]}",
            "datetime": date,
            "tile": info["tile"],
            "thumb": f"{THUMB_PREFIX}{webp}",
            "view": f"{VIEW_PREFIX}{webp}",
            "orig": blob.name,
        })

    for images in zones.values():
        images.sort(key=lambda img: img["datetime"])

    manifest = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "zones": dict(sorted(zones.items())),
    }

    blob = bucket.blob(MANIFEST_BLOB)
    blob.cache_control = MANIFEST_CACHE
    blob.upload_from_string(json.dumps(manifest, indent=1), content_type="application/json")
    logging.info("Manifest written with %s images", sum(len(v) for v in zones.values()))
    return manifest


def upload_variants(bucket_name, png_path, variants):
    """Upload the original png and its webp variants ({'thumb': path, 'view': path}) to their prefixes"""
    png_name = Path(png_path).name
    load_on_gcs(bucket_name, str(png_path), f"{ORIG_PREFIX}{png_name}",
                content_type="image/png", cache_control=IMMUTABLE_CACHE)
    for prefix, key in ((THUMB_PREFIX, "thumb"), (VIEW_PREFIX, "view")):
        webp_path = variants[key]
        load_on_gcs(bucket_name, str(webp_path), f"{prefix}{Path(webp_path).name}",
                    content_type="image/webp", cache_control=IMMUTABLE_CACHE)


def backfill(bucket_name, make_variants):
    """Copy legacy root-level PNGs to orig/ (originals are kept) and generate their thumb/ and view/ variants"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    legacy = [b for b in client.list_blobs(bucket) if "/" not in b.name and parse_image_name(b.name)]
    logging.info("%s legacy images to backfill", len(legacy))

    with tempfile.TemporaryDirectory() as tmp:
        for blob in legacy:
            local = Path(tmp, blob.name)
            blob.download_to_filename(str(local))
            upload_variants(bucket_name, local, make_variants(local, tmp))
            local.unlink()
    build_manifest(bucket_name)
