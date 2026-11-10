# Spec : recherche d'un lieu et image Sentinel-2 récente autour

Statut : brouillon à valider. Phase 0 (prototype de latence) faite, voir §12. Les points marqués ⚠️ restent à vérifier.

## 1. Objectif

Depuis le site, l'utilisateur cherche un lieu (pic, col, parking, village) via OpenStreetMap et voit l'image Sentinel-2 **la plus récente et exploitable** autour de ce lieu, en **couleur vraie** et en **NDSI** (neige). Zone = carré centré sur le lieu, environ 20 km × 20 km (±10 km).

Contraintes :
- Pyrénées uniquement.
- Coût max **5 €/mois** (Cloud Run + bucket).
- Les zones prédéfinies et le pipeline actuel restent en place pour l'instant, puis seront retirés.

## 2. Parcours utilisateur

1. Champ de recherche au-dessus d'une carte OSM (Leaflet). La recherche appelle Nominatim, limitée à la bbox des Pyrénées, **déclenchée à la validation** (Entrée / bouton), pas à la frappe (politique d'usage de Nominatim : 1 req/s, pas d'autocomplétion, User-Agent/Referer identifiable, attribution ©OpenStreetMap).
2. L'utilisateur choisit un résultat (ou clique sur la carte). La carte se centre sur le point.
3. Le front appelle le backend, qui renvoie la liste des dates disponibles (60 derniers jours) avec le % de nuages **dans la fenêtre**, et la date présélectionnée (la plus récente sous le seuil de nuages).
4. L'image s'affiche en superposition (`ImageOverlay`) sur la carte OSM, avec :
   - bascule Couleur / NDSI ;
   - curseur d'opacité ;
   - sélecteur de date (liste du point 3) ;
   - bouton de téléchargement (PNG de l'image affichée).
5. Si aucune date n'est sous le seuil de nuages, afficher la moins nuageuse avec un avertissement clair.

## 3. Architecture

```
Navigateur (Firebase Hosting, site statique)
   ├─ Nominatim (recherche de lieu)
   └─ /api/*  ──(rewrite Firebase Hosting)──▶ Cloud Run "scene-api" (FastAPI)
                                                 ├─ STAC (Planetary Computer) : recherche des scènes
                                                 ├─ lecture fenêtrée des COG (rasterio, requêtes Range)
                                                 └─ cache résultats : bucket GCS (public, lecture seule)
```

- Le service est **séparé** du job quotidien existant (autre image, autre déploiement). Le job existant n'est pas modifié.
- Le rewrite Firebase Hosting → Cloud Run met un CDN devant l'API (en-têtes `Cache-Control`), ce qui réduit les appels et l'egress.
- **Source des données (décision phase 0)** : Planetary Computer (`sentinel-2-l2a`, Azure Europe de l'Ouest). STAC : `https://planetarycomputer.microsoft.com/api/stac/v1`. Les COG se lisent en HTTP Range avec un jeton SAS gratuit, obtenu sans authentification sur `https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a` et à mettre en cache jusqu'à son expiration. Mesuré 2 à 3 fois plus rapide qu'Earth Search (§12).
- **Secours** : Earth Search (`https://earth-search.aws.element84.com/v1`, COG publics sans authentification). L'interface STAC est la même, seuls les noms d'assets et les ids d'items changent. La source est donc isolée derrière une petite couche de configuration.
- ⚠️ Mesures faites depuis WSL, pas depuis Cloud Run `europe-west1` : à reconfirmer au déploiement (étape 3).
- **Pas d'eodag dans ce service.** La recherche se fait en STAC (`pystac-client`) et la lecture en fenêtres (`rasterio`). eodag télécharge des produits entiers (1 Go), alourdit les démarrages à froid et sert surtout à gérer les identifiants des fournisseurs, inutiles ici. eodag reste utilisé uniquement par le job quotidien existant.

## 4. API

### `GET /api/dates?lat=..&lon=..`
Renvoie les scènes des 60 derniers jours couvrant la fenêtre.
```json
{ "center": [42.78, 1.32],
  "bbox": [minlon, minlat, maxlon, maxlat],
  "default": "2026-10-28",
  "dates": [{ "date": "2026-10-28", "item": "S2B_...", "cloud_pct": 4.2, "snow_pct": 31.0, "data_pct": 98.0 }] }
```
`cloud_pct` est calculé **sur la fenêtre** via la couche SCL (classes 3, 8, 9, 10), pas via le `eo:cloud_cover` de toute la tuile : l'écart est grand (mesuré : tuile 26 % contre 59,7 % dans la fenêtre à Canigou). Ce `eo:cloud_cover` (propriété de l'item STAC) sert seulement de pré-filtre bon marché : on écarte les scènes à plus de 90 % de nuages avant de lire le moindre pixel. Chaque entrée de `dates` contient aussi `data_pct` (voir §5).

### `GET /api/scene?lat=..&lon=..&date=YYYY-MM-DD&layer=color|ndsi`
Renvoie une image WebP (`format=png` : PNG sans perte ; `format=tif` : GeoTIFF géoréférencé, EPSG:4326, pour QGIS), toutes à la résolution native de 10 m avec en-tête `X-Bbox`. Erreurs : 400 hors Pyrénées ou paramètre invalide, 404 aucune scène, 429 limite atteinte.

## 5. Traitement

- **Grille** : le centre demandé est arrondi à une grille de 5 km (en UTM 31N, EPSG:32631). La fenêtre est ensuite un carré de 20 km autour du centre arrondi. Les recherches voisines tombent sur la même fenêtre, ce qui améliore fortement le taux de cache. Le point recherché reste toujours dans l'image (marge ≥ 7,5 km).
- **Couleur** : bande `visual` (TCI, 10 m), lecture de la fenêtre, 2000 × 2000 px au maximum, redimensionnée à 1600 px côté max pour l'affichage.
- **Données utilisées (assets Planetary Computer)** : `visual` (couleur), `B03` (10 m), `B11` (20 m) et `SCL` (classification, 20 m). Chez Earth Search (secours) les noms sont `visual`, `green`, `swir16` et `scl`. Il n'existe pas d'asset NDSI : il est calculé. Les assets `cloud` et `snow` d'Earth Search (probabilités Sen2Cor) ne sont pas utilisés : leurs `href` pointent vers des `.jp2` en `s3://sentinel-s2-l2a`, pas vers des COG publics.
- **NDSI** : `(B03 − B11) / (B03 + B11)`, avec B11 (20 m) rééchantillonnée à 10 m. Neige si NDSI > 0,4 (seuil à valider sur des cas réels). Les pixels nuage/ombre (SCL 3, 8, 9, 10) sont masqués en transparent pour éviter la confusion neige/nuage. Palette : transparent hors neige, dégradé bleu pour la neige.
- **Couverture (nodata)** : la fenêtre déborde souvent de la tuile ou de la fauchée orbitale (mesuré : 58 à 96 % de nodata à Canigou, 75 % sur une scène du Pic du Midi). On calcule donc `data_pct` (pixels SCL ≠ 0) et `cloud_pct` / `snow_pct` **uniquement sur les pixels valides**. Une scène dont `data_pct` est < 50 % est écartée de la présélection et signalée dans la liste.
- **Choix de la date par défaut** : la plus récente avec `cloud_pct` < 20 % et `data_pct` ≥ 50 %. Pas de mosaïque pour l'instant : si plusieurs tuiles se chevauchent à la même date, on prend celle de plus grande `data_pct`. ⚠️ Pour certains lieux (Canigou) aucune tuile ne couvre bien la fenêtre : la mosaïque de deux tuiles (§9) est alors à prioriser.
- **Coût de `/api/dates`** : il faut lire SCL pour chaque scène des 60 jours (30 à 50 items, environ 1 à 2 s chacune). Lecture de SCL à résolution réduite (overviews, par ex. 100 m), parallélisée, et résultat par item et fenêtre mis en cache (§6).
- **Limites** : lat/lon obligatoirement dans la bbox des Pyrénées (déduite de `ressources/pyrenees.shp`, avec marge).

## 6. Cache

- Clé : `scene/v2/<item_id>/<layer>/<cx>_<cy>.<webp|png|tif>` (`v2` = version du rendu : pleine résolution, à incrémenter si le rendu change) ; les statistiques par item et fenêtre (`cloud_pct`, `snow_pct`, `data_pct`) sont mises en cache en JSON sous `stats/<item_id>/<cx>_<cy>.json` (cx, cy = centre arrondi en mètres UTM).
- Avant tout calcul, vérification de l'existence dans le bucket. Sinon calcul, écriture, réponse.
- En-têtes : `Cache-Control: public, max-age=31536000, immutable` pour les images (un item Sentinel-2 ne change pas), 1 h pour `/api/dates`.
- Règle de cycle de vie du bucket : suppression des objets `scene/` après 90 jours.

## 7. Coût (estimation à confirmer au prototype)

- Cloud Run : `min-instances=0`, `max-instances=2`, 1 vCPU, 1 Go. Le quota gratuit (≈ 180 000 vCPU-s/mois) couvre des dizaines de milliers de requêtes de quelques secondes.
- Bucket : quelques centaines de Ko par image, soit quelques Go au pire = quelques centimes.
- Principal risque de coût : l'egress de masse. Mesures : CDN Firebase devant l'API, `max-instances`, limitation de débit par IP, alerte de budget à 5 € (déjà prévue dans `TASKS.md`).

## 8. Front

- Reste sans framework dans `site/`, avec Leaflet (CDN) en plus. Nouvelle page (ex. `site/carte.html`) pour ne pas casser l'existant ; lien depuis l'accueil.
- États à gérer : chargement (squelette + indication de durée), erreur réseau, aucune scène, lieu hors Pyrénées, trop de nuages.
- Attributions affichées : ©OpenStreetMap, Copernicus Sentinel-2.

## 9. Hors périmètre / évolutions

- Mosaïque de plusieurs tuiles et fusion multi-dates en retirant les nuages.
- Suppression des zones prédéfinies et du job quotidien actuel (une fois la carte validée).
- Emprise ajustable, tuiles XYZ pour naviguer librement, fond de carte avec relief (IGN / OpenTopoMap).
- Historique de la fonte (curseur de dates avec comparaison avant/après).

## 10. Plan

0. ✅ **Prototype de latence** (fait, voir §12) : go, source Planetary Computer.
1. Service FastAPI `scene-api` : `/api/dates` et `/api/scene`, tests unitaires sur le calcul NDSI/masque et sur l'arrondi de grille (avec des COG de test locaux).
2. Cache GCS + en-têtes + limites (`max-instances`, bbox, rate limit).
3. Dockerfile + déploiement Cloud Run + rewrite `firebase.json` (`/api/**`).
4. Front : recherche Nominatim, carte Leaflet, overlay, bascule Couleur/NDSI, sélecteur de dates, téléchargement.
5. Alerte de budget 5 €, documentation dans le README.

## 11. Questions ouvertes

- Seuil de nuages par défaut (20 % proposé) et seuil NDSI (0,4 proposé) : à calibrer sur de vraies images d'hiver.
- Taille du carré : ±10 km donne 2000 × 2000 px à 10 m. Une version plus petite serait plus rapide ; la taille est à valider avec la latence mesurée.
- Faut-il garder les images des lieux déjà recherchés plus de 90 jours ?

## 12. Résultats de la phase 0 (prototype de latence)

Script hors repo, 3 lieux (Aneto, Pic du Midi, Canigou), 3 scènes récentes par lieu, fenêtre ±10 km à 2000 × 2000 px, 1er novembre 2026, depuis WSL.

| | Earth Search (AWS us-west-2) | Planetary Computer (Azure Europe de l'Ouest) |
|---|---|---|
| Recherche STAC | 2,7 à 3,1 s | 0,5 à 0,9 s |
| `visual` par scène | 0,7 à 4,0 s | 0,3 à 1,8 s |
| B03 + B11 + SCL par scène | 2,2 à 4,3 s | 0,6 à 1,9 s |
| Total par scène | 3 à 8 s | 1 à 3,5 s |

Décisions : go ; source Planetary Computer, Earth Search en secours ; `cloud_pct` calculé sur pixels valides ; prise en compte de `data_pct` (§5) ; mosaïque à prioriser (§9). Le seuil NDSI (0,4) n'a pas pu être calibré : fin octobre la neige ne couvre que 0 à 8 % des fenêtres, à refaire sur des images d'hiver.
