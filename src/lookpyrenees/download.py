"""This module allow to search, crop and download zone of PYrenees"""
import datetime
import os
import glob
import logging

from eodag import EODataAccessGateway, setup_logging
from eodag.crunch import FilterOverlap, FilterDate
from shapely.geometry import mapping

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import rasterio as rio
import rioxarray as rxr
import geopandas as gpd
#import numpy
#print(numpy.__version__)
#print(numpy.__path__)

setup_logging(2)  # 0: nothing, 1: only progress bars, 2: INFO, 3: DEBUG
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

def write_raster(path, raster, crs, transform, nodata):
    """
    Write a raster to a tif file
    """
    with rio.open(path, 'w', driver='GTiff', height=raster.shape[0], width=raster.shape[1],
                  count=1, dtype=raster.dtype, crs=crs, transform=transform,
                  nodata=nodata) as dst:
        dst.write(raster, 1)

def search_data(workspace, dag, pref_provider, plot_res):
    """
    Process the search of EOproducts for Ariege zone
    """
    geom = {'lonmin' : 1, 'latmin' : 43, 'lonmax' : 3, 'latmax' : 44}
    end = datetime.date.today()
    last_month = end - datetime.timedelta(days=30)

    if pref_provider == 'peps':
        default_search_criteria = {"productType":"S2_MSI_L1C",
                                   "start":last_month,
                                   "end":end,
                                   "cloudCover":100,
                                   "tileIdentifier":'31TCH'}
    else:
        default_search_criteria = {"productType":"S2_MSI_L2A",
                                   "start" : last_month,
                                   "end" : end,
                                   "cloudCover" : 100,
                                   "geom" : geom}

    dag.set_preferred_provider(pref_provider)
    search_results, total_count = dag.search(**default_search_criteria)

    if total_count == 0:
        raise ValueError("No products found")

    logging.info("Number of products found : %s", total_count)

    if 'quicklook' in search_results[0].properties.keys() and plot_res:
        quicklooks_dir = os.path.join(workspace, "quicklooks")
        if not os.path.isdir(quicklooks_dir):
            os.mkdir(quicklooks_dir)

        fig = plt.figure(figsize=(10, 8))
        for i, product in enumerate(search_results, start=1):

            # This line takes care of downloading the quicklook
            quicklook_path = product.get_quicklook(base_dir=quicklooks_dir)
            #download_prod = dag.download(product)
            img = mpimg.imread(quicklook_path)
            size_x = round(total_count/3)
            axe_x = fig.add_subplot(size_x, 3, i)
            date = product.properties['modificationDate'].split('T')[0]
            axe_x.set_title(f"{date} and CC : {round(product.properties['cloudCover'])}")
            plt.imshow(img)
        plt.tight_layout()
        plt.show()

    return search_results

def lim_cloudcover(filtered_img):
    """
    Return the minimum cloudcover on EOproducts list
    """
    cloud_cover = 100
    too_cloudy = False
    for img in filtered_img:
        if img.properties['cloudCover'] < cloud_cover:
            final_img = img
            cloud_cover = img.properties['cloudCover']
    if cloud_cover > 30:
        too_cloudy = True

    return final_img, too_cloudy

def filter_img(search_results, dag, new_crop):
    """
    Filter images based on overlapped parameters, date and cloudcover
    """
    search_geometry = new_crop["geometry"][0]

    filter_results = search_results.crunch(
        FilterOverlap(dict(minimum_overlap=100)), geometry=search_geometry)
    logging.info('filter results overlapped are : %s with size of %s',
                 filter_results,
                 len(filter_results))

    recent = max([eo.properties['modificationDate'] for eo in filter_results]).split('T')[0]

    middle = datetime.datetime.strptime(recent, '%Y-%m-%d').date() - datetime.timedelta(days=10)
    filter_results_date = filter_results.crunch(
        FilterDate(dict(start=str(middle), end=str(recent))))
    final_img, too_cloudy = lim_cloudcover(filter_results_date)

    if not too_cloudy:
        out_path = dag.download(final_img)
    else:
        final_img, _ = lim_cloudcover(filter_results)
        out_path = dag.download(final_img)

    final_date = final_img.properties['modificationDate']
    final_cc = round(final_img.properties['cloudCover'], ndigits=2)

    logging.info("Final product at date %s with cloudcover of %s", final_date, final_cc)

    return out_path


def cropzone(zone, new_crop, out_path):
    """
    Crop the selected zone on image and create a tif file
    """
    img_path = glob.glob(f"{out_path}/GRANULE/*/IMG_DATA/*_TCI.jp2", recursive=True)[0]

    raster = rxr.open_rasterio(img_path,
                               masked=True).squeeze()
    logging.info('crop extent crs: %s', new_crop.crs)
    logging.info('raster crs: %s', raster.rio.crs)

    raster_clipped = raster.rio.clip(new_crop.geometry.apply(mapping),
                                     new_crop.crs)

    tif_file = img_path.split('/')[-1].split('.')[0]
    path_to_tif_file = os.path.join(out_path, tif_file+f'_{zone}.tif')
    # Write the data to a new geotiff file
    raster_clipped.rio.to_raster(path_to_tif_file)

    return path_to_tif_file

def process(zone, outdir, pref_provider, plot_res):
    """
    Process search, filter and crop final EO product
    """
    dag = EODataAccessGateway()
    search_results = search_data(outdir, dag, pref_provider, plot_res)

    aoi_path = glob.glob(f"{os.getcwd()}/ressources/zones/*.shp")
    crop_extent = gpd.read_file(aoi_path[0])
    new_crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME == zone])
    out_path = filter_img(search_results, dag, new_crop)

    file_path = cropzone(zone, new_crop, out_path)

    return file_path
