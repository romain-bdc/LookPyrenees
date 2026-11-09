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

## Map: search a place and see a recent Sentinel-2 image
Besides the predefined zones, the page `site/carte.html` lets you search a place in the Pyrenees (peak, pass, car park, village). The search goes through [Nominatim](https://nominatim.org/) (OpenStreetMap), restricted to the Pyrenees and triggered on validation (Enter / button). The page then shows, on top of an OSM map, the most recent usable Sentinel-2 image (cloud cover below the threshold) in a ~20 km x 20 km square around the place, with:
- a toggle between true colour and NDSI (snow index, `(B03 - B11) / (B03 + B11)`, clouds and shadows are masked);
- an opacity slider, a date selector (last 60 days, with cloud cover) and a download button.

### Architecture
```
Browser (Firebase Hosting, static site)
   ├─ Nominatim (place search)
   └─ /api/*  ──(Firebase Hosting rewrite)──▶ Cloud Run "scene-api" (FastAPI)
                                                ├─ STAC search + windowed COG reads
                                                └─ result cache: GCS bucket
```
The API (`src/scene_api/`, image built from `Dockerfile.scene-api`, deployed with `infra/deploy_scene_api.sh`) is separate from the daily job. Endpoints: `GET /api/dates?lat=..&lon=..` and `GET /api/scene?lat=..&lon=..&date=YYYY-MM-DD&layer=color|ndsi`. The requested centre is rounded to a 5 km grid so that nearby searches share the same cached image. See `SPEC_CARTE.md` for the details.

### Data sources and attributions
- Imagery: [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/) (`sentinel-2-l2a`); fallback on [Earth Search](https://earth-search.aws.element84.com/v1) (AWS).
- Contains modified Copernicus Sentinel-2 data.
- Map and search: (c) OpenStreetMap contributors, search by Nominatim (usage policy: 1 request/s, no autocompletion).

### Local development
```
uv sync --group scene-api
uv run --group scene-api uvicorn scene_api.main:app --reload --port 8080
uv run --group scene-api pytest tests/scene_api/
```
Serve the front with `cd site && python3 -m http.server 5000`, then open `http://localhost:5000/carte.html`. Add `?mock=1` to the URL to use fake data instead of the API (check `site/carte.html` / `site/carte.js` if the parameter has changed). To use the local API from the page, make it available under `/api` (e.g. with a reverse proxy) or adapt the base URL in the front.

### Cost limits
The target is at most 5 EUR/month. Cloud Run runs with `min-instances=0` and a small `max-instances`, the Firebase CDN caches API responses, images are cached in the bucket (objects under `scene/` deleted after 90 days), and the latitude/longitude must stay inside the Pyrenees bbox. Create the budget alert (50 %, 90 %, 100 % of 5 EUR) once with `./infra/setup_budget.sh --billing-account ID --email you@example.com` (add `--dry-run` to only print the commands). A budget only alerts, it does not stop spending.

## To be continued
- When a zone is exactly between two product it raises an error, the objective is to fix this by merging two products which cover the zone concerned.
- Add a super resolution algorithm in the workflow in order to imporve the spatial resolution
