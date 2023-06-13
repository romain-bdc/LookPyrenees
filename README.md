# LookPyrenees 
This code allow you to download and visualize a zone of pyrenees to prevent snow in winter and summer season.

## Installation
You need to clone this repository, create an virtual environment `python3 -m venv NAME_OF_YOUR_ENVIRONMENT` and run the following commmand to install requires packages `pip install .` or `python3 setup.py install` 

This module use eodag which is an open source library to facilitate downloading earth observation products.

When installation of packages finished you need to add your credentials account of Peps : [peps](https://peps.cnes.fr/rocket/#/home) and copernicus data browser : [cop_dataspace](https://dataspace.copernicus.eu/browser/?zoom=3&lat=26&lng=0&themeId=DEFAULT-THEME&visualizationUrl=https%3A%2F%2Fsh.dataspace.copernicus.eu%2Fogc%2Fwms%2F28b654e7-8912-4e59-9e58-85b58d768b3a&datasetId=S2_L2A_CDAS&demSource3D=%22MAPZEN%22&cloudCoverage=30) in the eodag configuration file that you can find in $HOME/.config/eodageodag.yml

## Run command 

After installation, you can run this command to download a zone of Pyrenees, a compromise is computed between the most recent and the less cloudy image : `python3 src/lookpyrenees/cli.py ZONE OUT_PATH`.

The list of current zone available (you can find shapefile in **ressources** folder) is : 3seigneurs, montcalm, rulhe_nerassol, carlit, orlu

Right here the command help :
```
usage: cli.py [-h] [-p PREF_PROVIDER] [-s PLOT_RESULTS] [--version] [-v] [-vv] zone out_path

Workflow that download last images of Pyrenees

positional arguments:
  zone                  zone of Pyrenees to view
  out_path              Output dirpath to store Pyrenees image

optional arguments:
  -h, --help            show this help message and exit
  -p PREF_PROVIDER, --pref-provider PREF_PROVIDER
                        Select preferred provider
  -s PLOT_RESULTS, --show-results PLOT_RESULTS
                        Boolean to view or not search results
  --version             show program's version number and exit
  -v, --verbose         set loglevel to INFO
  -vv, --very-verbose   set loglevel to DEBUG
```

## To be continued
- When a zone is exactly between two product it raises an error, the objective is to fix this by merging two products which cover the zone concerned.
- Create a real cli command : replace `python3 src/lookpyrenees/cli.py [ARGS]` by `LookPyrenees [ARGS]`
- Add scrip to process L1C image to L2A images (for peps provider for example)

