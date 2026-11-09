# Plan : remplacer Looker Studio par un site statique

Objectif : un site statique (Firebase Hosting) qui affiche les images Sentinel-2 des zones des Pyrénées et leur évolution dans le temps. Les images restent dans le bucket GCS (public en lecture seule). Le job quotidien produit les images optimisées et un `manifest.json`.

Légende : 🤖 = faisable par Claude, 👤 = action manuelle de l'utilisateur.

## Architecture cible

```
Cloud Run job (quotidien)
   └─ télécharge, recadre, convertit
   └─ écrit dans le bucket :
        thumb/<nom>.webp   (~400 px, grille)
        view/<nom>.webp    (~1600 px, affichage)
        orig/<nom>.png     (original, téléchargement)
        manifest.json      (liste zone / date / tuile / chemins)
Firebase Hosting (site/)
   └─ HTML/JS statique qui lit manifest.json et affiche les images du bucket
```

Nom de fichier actuel : `T31TCH_20240511T103629_TCI_10m_rulhe_nerassol.png` (tuile, date, zone déjà dans le nom).

Images en cache longue durée : `Cache-Control: public, max-age=31536000, immutable`. Le manifest a un cache court (~5 min).

## A. Job Python

### 1. Variantes d'image 🤖
Dans `src/LookPyrenees/download.py`, ajouter une fonction qui produit, à partir du PNG, une miniature (~400 px, WebP) et une version d'affichage (~1600 px, WebP). Test unitaire sur les tailles et le format.

### 2. Upload structuré 🤖
Dans `src/LookPyrenees/manage_bucket.py`, étendre `load_on_gcs` pour définir `content_type` et `Cache-Control`. Ranger les fichiers dans `thumb/`, `view/`, `orig/`. Adapter `process()` pour envoyer les 3 variantes.

Attention : `check_files_on_bucket` cherche par sous-chaîne dans tous les blobs. Vérifier qu'il fonctionne toujours avec les préfixes (ou le restreindre à `orig/`).

### 3. Manifest 🤖
Dans `manage_bucket.py`, `build_manifest(bucket)` : liste les blobs de `orig/`, extrait zone / date / tuile depuis le nom, écrit `manifest.json` (cache court). L'appeler à la fin de `main()` dans `cli.py`.

### 4. Rattrapage de l'existant 🤖
Option CLI `--backfill` : pour chaque PNG déjà présent à la racine du bucket, générer `thumb/` et `view/`, copier vers `orig/`, puis régénérer le manifest.

👤 L'exécuter une fois avec tes identifiants GCP (le bucket est chez toi) : `uv run LookPyrenees -b pyrenees_images --backfill`. Les anciens PNG de la racine peuvent ensuite être supprimés, à ta décision.

## B. Infra GCP

### 5. Bucket public en lecture seule + CORS 🤖/👤
🤖 Écrire un script `infra/setup_bucket.sh` (commandes `gcloud storage` ou `gsutil`) qui :
- donne `roles/storage.objectViewer` à `allUsers` ;
- applique un `cors.json` limité au domaine Firebase.

👤 Exécuter le script une fois (droits propriétaire du projet requis).

### 6. Alerte de budget 👤
Console GCP > Billing > Budgets & alerts : budget de 5 €/mois avec alerte. Non automatisable sans droits de facturation, et il suffit de 2 minutes.

## C. Front statique (`site/`)

### 7. Squelette 🤖
`index.html`, JS et CSS sans framework (ou très léger). Charge `manifest.json` et affiche une grille des zones avec la dernière image en miniature.

### 8. Vue par zone 🤖
Slider temporel pour naviguer entre les dates, préchargement de l'image suivante, `loading="lazy"`, placeholder pendant le chargement.

### 9. Comparaison avant/après 🤖
Curseur glissant entre deux dates choisies.

### 10. Ouverture en grand 🤖
Clic sur une image : charge la version `view/`, avec un lien vers `orig/`.

### 11. Finitions 🤖
Responsive, mode sombre, timelapse (lecture automatique) en option.

## D. Déploiement

### 12. Firebase Hosting 🤖/👤
🤖 Ajouter `firebase.json` (dossier `site/`) et `.firebaserc`.

👤 Étapes manuelles uniques :
- `npm i -g firebase-tools` puis `firebase login` ;
- `firebase projects:addfirebase <ID_PROJET_GCP>` (ou via la console Firebase) pour activer Firebase sur le projet existant ;
- me donner l'ID du projet et le nom du bucket.

Le premier déploiement (`firebase deploy --only hosting`) peut être lancé par Claude une fois connecté.

### 13. GitHub Actions 🤖/👤
🤖 Workflow `.github/workflows/deploy-site.yml` qui déploie `site/` à chaque push sur `main` (filtre sur `site/**`).

👤 Créer un compte de service Firebase Hosting et ajouter son JSON en secret GitHub. Le plus simple : `firebase init hosting:github` (assistant interactif, configure tout en une fois).

### 14. README 🤖
Remplacer le lien Looker Studio par le nouveau site et documenter l'architecture et les commandes (`--backfill`, setup du bucket).

## Ordre conseillé

1 → 2 → 3 → 4 (job complet, testable seul) → 5 → 7 → 8 → 12 → 13 → 9, 10, 11 → 14. La tâche 6 peut se faire à tout moment.

## Récapitulatif des actions manuelles (minimum)

1. Lancer `--backfill` une fois (tâche 4).
2. Lancer `infra/setup_bucket.sh` une fois (tâche 5).
3. Créer l'alerte de budget (tâche 6).
4. `firebase login` et activer Firebase sur le projet GCP, puis `firebase init hosting:github` (tâches 12 et 13).
5. Fournir l'ID du projet GCP et le nom du bucket.

---

# Plan : recherche d'un lieu et image Sentinel-2 (carte)

Détails dans `SPEC_CARTE.md` (§10). Légende : 🤖 = Claude, 👤 = action manuelle.

## Phases

| Phase | Contenu | Statut |
| --- | --- | --- |
| 0 | Prototype de latence (source Planetary Computer) | fait |
| 1 | Service FastAPI `src/scene_api/` (`/api/dates`, `/api/scene`) et tests | en cours d'implémentation |
| 2 | Cache GCS, en-têtes, limites (bbox, `max-instances`) | en cours d'implémentation |
| 3 | `Dockerfile.scene-api`, `infra/deploy_scene_api.sh`, rewrite `firebase.json` | en cours d'implémentation |
| 4 | Front `site/carte.html` (Nominatim, Leaflet, overlay, dates) | en cours d'implémentation |
| 5 | Alerte de budget (`infra/setup_budget.sh`) et README | écrit, non exécuté |

## Actions manuelles restantes 👤

- [ ] Déployer le service sur Cloud Run avec `infra/deploy_scene_api.sh` (droits sur le projet GCP requis), puis reconfirmer la latence depuis `europe-west1`.
- [ ] Appliquer la règle de cycle de vie du bucket pour `scene/` (90 jours), si le script de déploiement ne le fait pas.
- [ ] Déployer le rewrite `/api/**` vers Cloud Run : `firebase deploy --only hosting` (après revue de `firebase.json`).
- [ ] Exécuter une fois `./infra/setup_budget.sh --billing-account <ID> --email <adresse>` (essayer d'abord avec `--dry-run`). Nécessite les droits de facturation.
- [ ] Vérifier / ajouter les secrets GitHub nécessaires aux workflows (`FIREBASE_SERVICE_ACCOUNT_LOOKPYRENEES_6E7E4` existe déjà pour le site ; le reste dépend du workflow de déploiement de l'API, s'il y en a un).
- [ ] Calibrer les seuils (nuages 20 %, NDSI 0,4) sur des images d'hiver.
