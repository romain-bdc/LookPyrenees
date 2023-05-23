# -*- coding: utf-8 -*-
""" Test Observatory of Pyrenees"""
# pylint: disable=import-error
import os
import unittest
import glob

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import geopandas as gpd

from eodag import EODataAccessGateway
from src.lookpyrenees.download import (search_data,
                                       filter_img,
                                       cropzone,
                                       process,
                                       )

class TestClassifBase(unittest.TestCase):
    """Setup class"""
    def setUp(self):
        self.path = f'{os.getenv("HOME")}/data/snow/output_img'

    def test_search_data(self):
        """ Test to search data on provider
        """
        dag = EODataAccessGateway()
        search_results = search_data(workspace=self.path,
                                     dag=dag,
                                     pref_provider='peps',
                                     plot_res=False)
        print(f'search_results : {search_results}')
        return search_results

    def test_filter_img(self):
        """ Test the filtering of Montcalm zone
        """
        zone = 'montcalm'
        dag = EODataAccessGateway()
        search_results = search_data(workspace=self.path,
                                     dag=dag,
                                     pref_provider='cop_dataspace',
                                     plot_res=False)
        aoi_path = glob.glob(f"{os.getcwd()}/ressources/new_zone.shp")
        crop_extent = gpd.read_file(aoi_path[0])

        crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME == zone])

        filtered_results = filter_img(search_results=search_results,
                                      dag=dag,
                                      new_crop=crop,
                                      outdir=self.path)
        print(f"filtered_results : {filtered_results}")

    def test_cropzone(self):
        """ Test cropping of Montcalm zone
        """
        zone = 'montcalm'
        dag = EODataAccessGateway()
        search_results = search_data(workspace=self.path,
                                     dag=dag,
                                     pref_provider='peps',
                                     plot_res=False)
        aoi_path = glob.glob(f"{os.getcwd()}/ressources/zones/*.shp")
        crop_extent = gpd.read_file(aoi_path[0])
        crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME == zone])
        out_path = filter_img(search_results, dag, crop, self.path)

        file_path = cropzone(zone, crop, out_path)
        img = mpimg.imread(file_path)
        plt.imshow(img)
        plt.show()

    def test_process(self):
        """ Test whole process for rulhe_nerassol zone
        """
        zone = 'rulhe_nerassol'
        file_path = process(zone=zone,
                            outdir=self.path,
                            pref_provider='peps',
                            plot_res=False)
        img = mpimg.imread(file_path)
        plt.imshow(img)
        plt.show()
