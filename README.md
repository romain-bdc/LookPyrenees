# LookPyrenees 
This code allow you to download and visualize a zone of pyrenees to monitore snow cover in winter and summer season. You can use it if you want to see where is the snow limit when you do ski touring.

Here is an image of Montcalm zone on 05-06-2024
<p align="left">
<img src="https://github.com/romain-bdc/LookPyrenees/assets/78345373/46617156-535c-438a-b70f-83d0334486b2" width="300">
</p>

Here is an image of Orlu zone on 11-05-2024
<p align="left">
<img src="https://github.com/romain-bdc/LookPyrenees/assets/78345373/4e9a84a1-ba2a-47b0-82e7-41c0add707b5" width="400">
</p>



Browse all zones, their evolution over time and a before/after comparison on the website: https://lookpyrenees.web.app

Here is an overview of the global workfow of this project:
![workflow](https://github.com/romain-bdc/LookPyrenees/assets/78345373/b5ef312c-a5e4-48cd-afeb-a9d11823e980)



## Installation
You need [uv](https://docs.astral.sh/uv/) and Python 3.14. Clone this repository and run `uv sync` to create the virtual environment (`.venv`) and install the dependencies, then run the CLI with `uv run LookPyrenees ...`.

This module uses [eodag](https://eodag.readthedocs.io/en/stable/) which is an open source library to facilitate downloading earth observation products from different providers.

When installation of packages finished you need to add your credentials account of the copernicus data browser : [cop_dataspace](https://dataspace.copernicus.eu/browser/?zoom=3&lat=26&lng=0&themeId=DEFAULT-THEME&visualizationUrl=https%3A%2F%2Fsh.dataspace.copernicus.eu%2Fogc%2Fwms%2F28b654e7-8912-4e59-9e58-85b58d768b3a&datasetId=S2_L2A_CDAS&demSource3D=%22MAPZEN%22&cloudCoverage=30) in the eodag configuration file that you can find in $HOME/.config/eodag/eodag.yml

## Run command 

After installation, you can run this command to download a zone of Pyrenees, a compromise is computed between the most recent and the less cloudy image : `uv run LookPyrenees -z [ZONE] -o OUT_PATH`.

The list of current zone available (you can find shapefile in **ressources** folder) is : 3seigneurs, montcalm, rulhe_nerassol, carlit, orlu

Right here the command help :
```
usage: LookPyrenees [-h] [-z ZONE] [-o OUT_PATH] [-p PREF_PROVIDER] [-b BUCKET_NAME]
                    [-s PLOT_RESULTS] [--backfill] [--version] [-v] [-vv]

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
  --backfill            copy legacy root-level PNGs of the bucket to orig/, generate
                        thumb/ and view/, rebuild the manifest
  --version             show program's version number and exit
  -v, --verbose         set loglevel to INFO
  -vv, --very-verbose   set loglevel to DEBUG
```

## Architecture of the website
The daily Cloud Run job downloads the images and, when `-b BUCKET` is given, writes in the bucket:

| Path | Content |
| --- | --- |
| `thumb/<name>.webp` | thumbnail (~400 px), used in grids |
| `view/<name>.webp` | display version (~1600 px) |
| `orig/<name>.png` | original image, for download |
| `manifest.json` | list of zones / dates / tiles / paths, rebuilt at the end of each run |

Images are cached for one year (`immutable`), the manifest for 5 minutes. The static site in `site/` is served by Firebase Hosting and reads `manifest.json` and the images straight from the public bucket.

### One-time setup
- `uv run LookPyrenees -b pyrenees_images --backfill` converts images that were uploaded before the website existed (legacy PNGs at the bucket root are kept, delete them when you want).
- `./infra/setup_bucket.sh` makes the bucket publicly readable and applies `infra/cors.json` (allowed origins: the Firebase domains).
- `firebase deploy --only hosting` deploys `site/`. The workflow `deploy-site.yml` does it on each push to `main` touching `site/`; it needs the `FIREBASE_SERVICE_ACCOUNT_LOOKPYRENEES_6E7E4` GitHub secret (created by `firebase init hosting:github`).
- To preview locally: `cd site && python3 -m http.server 5000` (port 5000 is allowed by the CORS config).

## To be continued
- When a zone is exactly between two product it raises an error, the objective is to fix this by merging two products which cover the zone concerned.
- Add a super resolution algorithm in the workflow in order to imporve the spatial resolution
