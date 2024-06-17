# LookPyrenees 
This code allow you to download and visualize a zone of pyrenees to monitore snow cover in winter and summer season. You can use it if you want to see where is the snow limit when you do ski touring.

<img src="https://github.com/romain-bdc/LookPyrenees/assets/78345373/46617156-535c-438a-b70f-83d0334486b2" alt="drawing" width="300"/>

<img src="https://github.com/romain-bdc/LookPyrenees/assets/78345373/4e9a84a1-ba2a-47b0-82e7-41c0add707b5" alt="drawing" width="430"/>


[Visualize Pyrenees (Looker Studio report)](https://lookerstudio.google.com/embed/reporting/88692342-37da-4f11-aa67-e6bda7fb67a8/page/Uc62D)

Here is an overview of the global workfow of this project:
![workflow](https://github.com/romain-bdc/LookPyrenees/assets/78345373/b5ef312c-a5e4-48cd-afeb-a9d11823e980)



## Installation
You need to clone this repository, create an virtual environment `python3 -m venv NAME_OF_YOUR_ENVIRONMENT` and run the following commmand to install requires packages `pip install .` or `python3 setup.py install` 

This module use eodag which is an open source library to facilitate downloading earth observation products.

When installation of packages finished you need to add your credentials account of Peps : [peps](https://peps.cnes.fr/rocket/#/home) and copernicus data browser : [cop_dataspace](https://dataspace.copernicus.eu/browser/?zoom=3&lat=26&lng=0&themeId=DEFAULT-THEME&visualizationUrl=https%3A%2F%2Fsh.dataspace.copernicus.eu%2Fogc%2Fwms%2F28b654e7-8912-4e59-9e58-85b58d768b3a&datasetId=S2_L2A_CDAS&demSource3D=%22MAPZEN%22&cloudCoverage=30) in the eodag configuration file that you can find in $HOME/.config/eodag/eodag.yml

## Run command 

After installation, you can run this command to download a zone of Pyrenees, a compromise is computed between the most recent and the less cloudy image : `Lookpyrenees -z [ZONE] -o OUT_PATH`.

The list of current zone available (you can find shapefile in **ressources** folder) is : 3seigneurs, montcalm, rulhe_nerassol, carlit, orlu

Right here the command help :
```
usage: LookPyrenees [-h] [-z ZONE] [-o OUT_PATH] [-p PREF_PROVIDER] [-b BUCKET_NAME]
                    [-s PLOT_RESULTS] [--version] [-v] [-vv]

Workflow that download last images of Pyrenees

optional arguments:
  -h, --help            show this help message and exit
  -z ZONE, --zone ZONE  zone of Pyrenees to view, if no specified download all zones
  -o OUT_PATH, --out-path OUT_PATH
                        Output dirpath to store Pyrenees image
  -p PREF_PROVIDER, --pref-provider PREF_PROVIDER
                        Select preferred provider
  -b BUCKET_NAME, --bucket-name BUCKET_NAME
                        Select the bucket name
  -s PLOT_RESULTS, --show-results PLOT_RESULTS
                        Boolean to view or not search results
  --version             show program's version number and exit
  -v, --verbose         set loglevel to INFO
  -vv, --very-verbose   set loglevel to DEBUG
```

## To be continued
- When a zone is exactly between two product it raises an error, the objective is to fix this by merging two products which cover the zone concerned.
- Add a super resolution algorithm in the workflow in order to imporve the spatial resolution
