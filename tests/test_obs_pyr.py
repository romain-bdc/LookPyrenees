# -*- coding: utf-8 -*-
""" Test Observatory of Pyrenees"""
# pylint: disable=import-error
import datetime
import glob
import logging
import os
import shutil
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
        os.environ.get("EODAG__COP_DATASPACE__AUTH__CREDENTIALS__USERNAME")
        os.environ.get("EODAG__COP_DATASPACE__AUTH__CREDENTIALS__PASSWORD")

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

        os.environ.get("EODAG__COP_DATASPACE__AUTH__CREDENTIALS__USERNAME")
        os.environ.get("EODAG__COP_DATASPACE__AUTH__CREDENTIALS__PASSWORD")

        zone = "montcalm"
        dag = EODataAccessGateway()
        search_results = search_data(
            workspace=self.path, dag=dag, pref_provider="cop_dataspace", plot_res=False
        )
        aoi_path = glob.glob(f"{os.getcwd()}/ressources/zone_4326.shp")
        crop_extent = gpd.read_file(aoi_path[0])
        crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME == zone])
        out_paths = filter_img(search_results, dag, crop, self.path)

        for out_path in out_paths:
            file_path = cropzone(zone, crop, out_path)
            img = mpimg.imread(file_path)
            plt.imshow(img)
            plt.show()
            plt.clf()

    def test_check_old_files(self):
        """Test deleting old directories and files"""

        # Get today date in format YYYYMMDD
        today = datetime.datetime.now().strftime("%Y%m%d")

        path_dir = os.path.join(CURRENT_DIR, "tests", "examples", "check_dates")
        if not os.path.exists(path_dir):
            os.mkdir(os.path.join(CURRENT_DIR, "tests", "examples", "check_dates"))

        # Build filename with today date
        filename_today = f"T31TCH_{today}T105031_TCI_10m_rulhe_nerassol.tif"
        full_path_today = os.path.join(path_dir, filename_today)
        file_now = open(full_path_today, "w")
        file_now.close()

        # Build filename with one month before date
        one_month = datetime.datetime.now() - datetime.timedelta(days=32)
        one_month_date = one_month.strftime("%Y%m%d")
        filename_month_earlier = f"T31TCH_{one_month_date}T105031_TCI_10m_rulhe_nerassol.tif"
        full_path_one_month = os.path.join(path_dir, filename_month_earlier)
        file_one_month = open(full_path_one_month, "w")
        file_one_month.close()

        check_old_files(path_dir)

        # Check that today file still exists
        assert os.path.exists(full_path_today)

        # Check that old files has been removed
        assert not os.path.exists(full_path_one_month)

        with os.scandir(path_dir) as entries:
            for entry in entries:
                if entry.is_file():
                    os.unlink(entry.path)
                else:
                    shutil.rmtree(entry.path)
        logging.info("All files and subdirectories deleted successfully.")

    def test_process(self):
        """Test whole process for rulhe_nerassol zone"""
        os.environ.get("EODAG__COP_DATASPACE__AUTH__CREDENTIALS__USERNAME")
        os.environ.get("EODAG__COP_DATASPACE__AUTH__CREDENTIALS__PASSWORD")
        zone = "rulhe_nerassol"
        files_path = process(
            zone=zone, outdir=self.path, pref_provider="cop_dataspace", plot_res=False
        )

        for file_path in files_path:
            img = mpimg.imread(file_path)
            plt.imshow(img)
            plt.show()
            plt.clf()

    def test_upload_and_remove_on_gcs(self):
        """Test to upload an image on google cloud storage
        """
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        file_to_upload = os.path.join(CURRENT_DIR, "tests", "examples", "T31TDH_20240421T103629_TCI_10m_orlu.tif")
        bucket_name = "pyrenees_images"
        destination_blob = "T31TDH_20240421T103629_TCI_10m_orlu.tif"

        load_on_gcs(bucket_name, file_to_upload, destination_blob)

        delete_blob(bucket_name, destination_blob)
