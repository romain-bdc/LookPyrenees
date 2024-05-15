"""This module allow to search, crop and download zone of Pyrenees"""
# pylint: disable=import-error
import datetime
import glob
import logging
import os
import shutil
from pathlib import Path

import folium
import geopandas as gpd
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import rasterio as rio
import rioxarray as rxr
from eodag.api.search_result import SearchResult
from eodag.crunch import FilterDate, FilterOverlap, FilterProperty
from shapely.geometry import mapping

from eodag import EODataAccessGateway, setup_logging

setup_logging(2)  # 0: nothing, 1: only progress bars, 2: INFO, 3: DEBUG
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


def create_search_result_map(search_results, extent):
    """Small utility to create an interactive map with folium
    that displays an extent in red and EO Producs in blue"""
    fmap = folium.Map([46, 3], zoom_start=6)
    folium.GeoJson(extent, style_function=lambda x: {"color": "red"}).add_to(fmap)
    folium.GeoJson(search_results).add_to(fmap)

    return fmap


def check_coverage(search_results, polygon_geometry):
    """ "Check if results searched contains the zone geometry"""
    contains = []
    for img in search_results:
        if img.geometry.contains(polygon_geometry):
            contains.append(True)
        else:
            contains.append(False)

    return contains


def write_raster(path, raster, crs, transform, nodata):
    """
    Write a raster to a tif file
    """
    with rio.open(
            path,
            "w",
            driver="GTiff",
            height=raster.shape[0],
            width=raster.shape[1],
            count=1,
            dtype=raster.dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
    ) as dst:
        dst.write(raster, 1)


def search_data(workspace, dag, pref_provider, plot_res):
    """
    Process the search of EOproducts for Ariege zone
    """
    end = datetime.date.today()
    last_month = end - datetime.timedelta(days=30)
    geom_path = glob.glob(f"{os.getcwd()}/ressources/pyrenees.shp")[0]
    geom = gpd.read_file(geom_path).geometry

    if pref_provider == "peps":
        default_search_criteria = {
            "productType": "S2_MSI_L1C",
            "start": last_month,
            "end": end,
            "cloudCover": 100,
            "geom": geom[0],
        }
    else:
        default_search_criteria = {
            "productType": "S2_MSI_L2A",
            "start": str(last_month),
            "end": str(end),
            "cloudCover": 100,
            "geom": geom[0],
        }

    dag.set_preferred_provider(pref_provider)
    search_results = dag.search_all(**default_search_criteria)

    if len(search_results) == 0:
        raise ValueError("No products found")

    logging.info("Number of products found : %s", len(search_results))

    if "quicklook" in search_results[0].properties.keys() and plot_res:
        quicklook_img(workspace, search_results, len(search_results))

    return search_results


def quicklook_img(workspace, search_results, total_count):
    """Function to plot overview of products if needed"""
    quicklooks_dir = os.path.join(workspace, "quicklooks")
    if not os.path.isdir(quicklooks_dir):
        os.mkdir(quicklooks_dir)

    fig = plt.figure(figsize=(10, 8))
    for i, product in enumerate(search_results, start=1):
        # This line takes care of downloading the quicklook
        quicklook_path = product.get_quicklook(base_dir=quicklooks_dir)
        # download_prod = dag.download(product)
        img = mpimg.imread(quicklook_path)
        size_x = int(np.ceil(total_count / 3))

        axe_x = fig.add_subplot(size_x, 3, i)
        date = product.properties["modificationDate"].split("T")[0]
        axe_x.set_title(f'{date} and CC : {round(product.properties["cloudCover"])}')
        plt.imshow(img)
    plt.tight_layout()
    plt.show()


def lim_cloudcover(filtered_img, lim_cloudcover: float = 20.0):
    """
    Return the minimum cloudcover on EOproducts list
    """
    too_cloudy = False
    finals_img = filtered_img.crunch(FilterProperty(dict(cloudCover=lim_cloudcover, operator="lt")))

    if len(finals_img) == 0:
        too_cloudy = True

    return finals_img, too_cloudy


def filter_img(search_results, dag, new_crop, outdir):
    """
    Filter images based on overlapped parameters, date and cloudcover
    """
    search_geometry = new_crop["geometry"][0]
    contains = check_coverage(search_results, search_geometry)

    if any(contains):
        logging.info("The search geometry is contained in one product")
        filter_results = search_results.crunch(
            FilterOverlap({"contains": True}), geometry=search_geometry
        )
    else:
        logging.warning("The search geometry is not totally contained in one product")
        area_zone = search_geometry.area
        product_to_keep = []
        for product in search_results:
            coverage_zone = (
                100 * product.geometry.intersection(search_geometry).area / area_zone
            )

            if coverage_zone > 95:
                product_to_keep.append(product)

        filter_results = SearchResult(products=product_to_keep)

        logging.info(
            "Filter results overlapped are : %s with size of %s",
            filter_results,
            len(filter_results),
        )
        logging.info(
            "There was %s products before filtering overlapping there are %s now",
            len(search_results),
            len(filter_results),
        )

    recent = max([eo.properties["modificationDate"] for eo in filter_results]).split(
        "T"
    )[0]

    recent_up = datetime.datetime.strptime(recent, "%Y-%m-%d").date() + datetime.timedelta(
        days=1
    )

    middle = datetime.datetime.strptime(recent, "%Y-%m-%d").date() - datetime.timedelta(
        days=10
    )
    filter_results_date = filter_results.crunch(
        FilterDate({"start": str(middle), "end": str(recent_up)})
    )

    # Display cloudcover of images of the last month
    for eoprod in filter_results:
        logging.info(
            "Filter product id %s with cloudcover of %s",
            eoprod.properties["id"],
            eoprod.properties["cloudCover"],
        )

    finals_img, too_cloudy = lim_cloudcover(filter_results_date)

    if not too_cloudy:
        out_paths = dag.download_all(search_result=finals_img, outputs_prefix=outdir)
    else:
        finals_img, _ = lim_cloudcover(filter_results)
        out_paths = dag.download_all(search_result=finals_img, outputs_prefix=outdir)

    for img in finals_img:
        if "quicklook" in img.properties.keys():
            quicklook_img(outdir, [img], 1)

        final_date = img.properties["modificationDate"]
        final_cc = round(img.properties["cloudCover"], ndigits=2)

        logging.info("Final product at date %s with cloudcover of %s", final_date, final_cc)

    return out_paths


def cropzone(zone, new_crop, out_path):
    """
    Crop the selected zone on image and create a tif file
    """
    img_type = out_path.split("/")[-1].split("_")[1]
    if "L2A" in img_type:
        img_path = glob.glob(
            f"{out_path}/GRANULE/*/IMG_DATA/R10m/*_TCI_10m.jp2", recursive=True
        )[0]
    else:
        img_path = glob.glob(
            f"{out_path}/GRANULE/*/IMG_DATA/*_TCI*jp2", recursive=True
        )[0]

    raster = rxr.open_rasterio(img_path, masked=True).squeeze()
    logging.info("crop extent crs: %s", new_crop.crs)
    logging.info("raster crs: %s", raster.rio.crs)

    raster_clipped = raster.rio.clip(new_crop.geometry.apply(mapping), new_crop.crs)

    tif_file = img_path.split("/")[-1].split(".")[0]
    output_img = "/".join(out_path.split("/")[:-2])
    path_to_tif_file = os.path.join(output_img, tif_file + f"_{zone}.tif")
    # Write the data to a new geotiff file
    raster_clipped.rio.to_raster(path_to_tif_file)

    return path_to_tif_file


def check_old_files(outdir):
    """
    Check the date of images downloaded and delete too old files
    """

    min_date = datetime.date.today() - datetime.timedelta(days=31)
    files_list = os.listdir(outdir)
    logging.info(f"la taille des fichiers {len(files_list)} et elle vaut {files_list}")
    if len(files_list) != 0:
        for obj in files_list:
            path_obj = Path(outdir, obj)

            if os.path.isfile(str(path_obj)) and obj.endswith('.tif'):
                date_file = obj.split('_')[1].split('T')[0]
                if datetime.datetime.strptime(date_file, "%Y%m%d").date() < min_date:
                    os.remove(path_obj)
            elif os.path.isdir(str(path_obj)) and obj.startswith("S2"):
                date_dir = obj.split('_')[2].split('T')[0]
                if datetime.datetime.strptime(date_dir, "%Y%m%d").date() < min_date:
                    shutil.rmtree(path_obj)


def process(zone, outdir, pref_provider, plot_res):
    """
    Process search, filter and crop final EO product
    """
    dag = EODataAccessGateway()
    search_results = search_data(outdir, dag, pref_provider, plot_res)
    aoi_path = glob.glob(f"{os.getcwd()}/ressources/zone_4326.shp")

    logging.info("AOI PATH : %s", aoi_path)
    crop_extent = gpd.read_file(aoi_path[0])

    list_zone = crop_extent.NAME.to_list()
    if zone not in list_zone:
        raise ValueError(f"This zone {zone} does not exist")

    new_crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME == zone])

    # logging.INFO(f"There are {len(search_results)} products")

    out_paths = filter_img(search_results, dag, new_crop, outdir)

    check_old_files(outdir)

    file_path = [cropzone(zone, new_crop, out_path) for out_path in out_paths]

    return file_path
