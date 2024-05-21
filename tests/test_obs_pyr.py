# -*- coding: utf-8 -*-
""" Test Observatory of Pyrenees"""
# pylint: disable=import-error
import glob
import os
import unittest

import geopandas as gpd
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from eodag import EODataAccessGateway
from LookPyrenees.download import (
    check_old_files,
    cropzone,
    filter_img,
    process,
    search_data,
)
from LookPyrenees.manage_bucket import delete_blob, load_on_gcs

CURRENT_DIR = os.getcwd()
CREDS = os.environ.get("CREDS_PATH", "creds/")


class TestClassifBase(unittest.TestCase):
    """Setup class"""

    def setUp(self):
        self.path = f'{os.getenv("HOME")}/data/snow/output_img'

    def test_search_data(self):
        """Test to search data on provider"""
        dag = EODataAccessGateway()
        search_results = search_data(
            workspace=self.path, dag=dag, pref_provider="cop_dataspace", plot_res=False
        )
        print(f"search_results : {search_results}")
        return search_results

    def test_filter_img(self):
        """Test the filtering of Montcalm zone"""
        zone = "carlit"
        dag = EODataAccessGateway()
        search_results = search_data(
            workspace=self.path, dag=dag, pref_provider="cop_dataspace", plot_res=False
        )
        aoi_path = glob.glob(f"{os.getcwd()}/ressources/zone_4326.shp")
        crop_extent = gpd.read_file(aoi_path[0])

        crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME == zone])

        filtered_results = filter_img(
            search_results=search_results, dag=dag, new_crop=crop, outdir=self.path
        )
        print(f"filtered_results : {filtered_results}")

    def test_cropzone(self):
        """Test cropping of Montcalm zone"""
        zone = "montcalm"
        dag = EODataAccessGateway()
        search_results = search_data(
            workspace=self.path, dag=dag, pref_provider="cop_dataspace", plot_res=False
        )
        aoi_path = glob.glob(f"{os.getcwd()}/ressources/zone_4326.shp")
        crop_extent = gpd.read_file(aoi_path[0])
        crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME == zone])
        out_path = filter_img(search_results, dag, crop, self.path)

        file_path = cropzone(zone, crop, out_path)
        img = mpimg.imread(file_path)
        plt.imshow(img)
        plt.show()

    def test_check_old_files(self):
        """Test deleting old directories and files"""
        check_old_files(self.path)

    def test_process(self):
        """Test whole process for rulhe_nerassol zone"""
        zone = "rulhe_nerassol"
        file_path = process(
            zone=zone, outdir=self.path, pref_provider="cop_dataspace", plot_res=False
        )
        img = mpimg.imread(file_path)
        plt.imshow(img)
        plt.show()

    def test_upload_and_remove_on_gcs(self):
        """Test to upload an image on google cloud storage
        """
        print(f"CREDENTIALS PATH: {CREDS}")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDS

        file_to_upload = os.path.join(CURRENT_DIR, "tests", "examples", "T31TDH_20240421T103629_TCI_10m_orlu.tif")
        bucket_name = "pyrenees_images"
        destination_blob = "T31TDH_20240421T103629_TCI_10m_orlu.tif"

        load_on_gcs(bucket_name, file_to_upload, destination_blob)

        delete_blob(bucket_name, destination_blob)
