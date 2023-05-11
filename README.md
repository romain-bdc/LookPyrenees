# LookPyrenees 
This code allow you to download and visualize a zone of pyrenees to prevent snow in winter and summer season.

## Installation
You need to clone this repository, create an virtual environment `python3 -m venv NAME_OF_YOUR_ENVIRONMENT` and run the following commmand to install requires packages `pip install .`

This module use eodag which is an open source library to facilitate downloading earth observation products.

When installation of packages finished you need to add your credentials account of Peps : https://peps.cnes.fr/rocket/#/home and copernicus data browser : https://dataspace.copernicus.eu/browser/?zoom=3&lat=26&lng=0&themeId=DEFAULT-THEME&visualizationUrl=https%3A%2F%2Fsh.dataspace.copernicus.eu%2Fogc%2Fwms%2F28b654e7-8912-4e59-9e58-85b58d768b3a&datasetId=S2_L2A_CDAS&demSource3D=%22MAPZEN%22&cloudCoverage=30 in the eodag configuration file that you can find in $HOME/.config/eodageodag.yml


