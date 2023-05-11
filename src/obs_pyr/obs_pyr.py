from eodag import EODataAccessGateway, setup_logging
from eodag.crunch import FilterOverlap
from shapely.geometry import mapping

import datetime
import os
import glob
import logging
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import rasterio as rio
import rioxarray as rxr
import geopandas as gpd


setup_logging(3)  # 0: nothing, 1: only progress bars, 2: INFO, 3: DEBUG


def write_raster(path, raster, crs, transform, nodata, driver='GTiff'):
    """Write a raster to a file."""
    
    with rio.open(path, 'w', driver=driver, height=raster.shape[0], width=raster.shape[1],
                       count=1, dtype=raster.dtype, crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(raster, 1)

def search_data(workspace, dag, pref_provider):
    geom={'lonmin':1, 'latmin' : 43 , 'lonmax' :3,'latmax':44}
    end=datetime.date.today()
    last_month = end - datetime.timedelta(days=30)

    if pref_provider=='peps':
        default_search_criteria = {"productType":"S2_MSI_L1C",
            "start":last_month,
            "end":end,
            "cloudCover":100,
            "tileIdentifier":'31TCH',
        }
    else:
        default_search_criteria = {"productType":"S2_MSI_L2A",
            "start":last_month,
            "end":end,
            "cloudCover":100,
            "geom":geom,
        }

    dag.set_preferred_provider(pref_provider)
    search_results, total_count = dag.search(**default_search_criteria)

    if total_count==0:
        raise ValueError("No products found")
    
    logging.info(f"Number of products found : {total_count}")
    
    if 'quicklook' in search_results[0].properties.keys():
        quicklooks_dir = os.path.join(workspace, "quicklooks")
        if not os.path.isdir(quicklooks_dir):
            os.mkdir(quicklooks_dir)

        fig = plt.figure(figsize=(10, 8))
        for i, product in enumerate(search_results, start=1):
            
            # This line takes care of downloading the quicklook
            quicklook_path = product.get_quicklook(base_dir=quicklooks_dir)
            #download_prod = dag.download(product)
            img = mpimg.imread(quicklook_path)
            x=round(total_count/3)
            ax = fig.add_subplot(x, 3, i)
            date=product.properties['modificationDate'].split('T')[0]
            ax.set_title(f"{date} and CC : {round(product.properties['cloudCover'])}")
            plt.imshow(img)
        plt.tight_layout()
        plt.show()

    return search_results

def filter_img(search_results, dag, search_geometry):
    #filter_results=search_results.filter_property(operator="eq", relativeOrbitNumber=51)
    filter_results=search_results.crunch(FilterOverlap(dict(minimum_overlap=95)), geometry=search_geometry)
    
    print(f'filter results overlapped are : {filter_results} with size of {len(filter_results)}')
    cc=100
    for img in filter_results:
        if img.properties['cloudCover']<cc:
            final_img=img
            cc=img.properties['cloudCover']

    print(f"Final product selected : {final_img}")
    out_path=dag.download(final_img)

    return out_path


def cropzone(zone, out_dir, pref_provider='cop_dataspace'):

    #aoi='/'.join(out_dir.split('/')[:-3])
    aoi_path=glob.glob(f"{out_dir}/zones/*.shp")
    
    crop_extent = gpd.read_file(aoi_path[0])
    new_crop = gpd.read_file(aoi_path[0], mask=crop_extent[crop_extent.NAME==zone])
    
    search_geometry=new_crop["geometry"][0]
    dag=EODataAccessGateway()
    workspace=f"{os.getenv('HOME')}/data/snow"

    search_results = search_data(workspace, dag, pref_provider)
    out_path=filter_img(search_results, dag, search_geometry)
    img_path=glob.glob(f"{out_path}/GRANULE/*/IMG_DATA/*_TCI.jp2", recursive=True)[0]

    raster = rxr.open_rasterio(img_path,
                                masked=True).squeeze()
    logging.info('crop extent crs: ', new_crop.crs)
    logging.info('raster crs: ', raster.rio.crs)

    raster_clipped = raster.rio.clip(new_crop.geometry.apply(mapping),
                                        new_crop.crs)
    
    tif_file=img_path.split('/')[-1].split('.')[0]
    path_to_tif_file=os.path.join(out_dir,tif_file+f'_{zone}.tif')
    # Write the data to a new geotiff file
    raster_clipped.rio.to_raster(path_to_tif_file)



# search_results=search_data(workspace=f"{os.getenv('HOME')}/data/snow/",
#                            start=last_month,
#                            end=end,
#                            geom='31TCH',
#                            pref_provider='peps')

# out_path=f"{os.getenv('HOME')}/data/snow/S2B_MSIL1C_20230420T104619_N0509_R051_T31TCH_20230420T125145/S2B_MSIL1C_20230420T104619_N0509_R051_T31TCH_20230420T125145.SAFE/"
# print(f"final path : {out_path}")
# img_path=glob.glob(f"{out_path}/GRANULE/*/IMG_DATA/*_TCI.jp2", recursive=True)
# print(f"IMG PATH {img_path}")
out_path=f"{os.getenv('HOME')}/data/snow/"
cropzone('montcalm',out_path, pref_provider='peps')
