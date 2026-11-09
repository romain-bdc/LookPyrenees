"use strict";

// Emprise des Pyrénées (pyrenees.shp + marge) : [minlon, minlat, maxlon, maxlat].
const PYR_BBOX = [-2.0, 42.0, 3.2, 43.5];
const CLOUD_MAX = 20;   // % : seuil de la spec pour la date par défaut
const DATA_MIN = 50;    // % : couverture minimale
const QUICK_ITEMS = 8;    // scènes évaluées pour la première réponse rapide
const NOMINATIM_DELAY_MS = 1100;  // politique d'usage : 1 requête/s max

const $ = (id) => document.getElementById(id);
const statusBox = $("status"), panel = $("panel"), skeleton = $("skeleton");
const esc = (text) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const fmtDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
const pct = (v) => Math.round(v) + " %";

// Mode maquette (?mock=1) : on ne charge le simulateur que si demandé.
const MOCK = new URLSearchParams(location.search).get("mock");
let api = (path) => fetch(path);
if (MOCK) {
  api = (path) => window.mockApi(path, MOCK);
  document.title = "[maquette] " + document.title;
}

const map = L.map("map", { maxBounds: [[PYR_BBOX[1] - 1, PYR_BBOX[0] - 1], [PYR_BBOX[3] + 1, PYR_BBOX[2] + 1]] })
  .fitBounds([[PYR_BBOX[1], PYR_BBOX[0]], [PYR_BBOX[3], PYR_BBOX[2]]]);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 17, minZoom: 6,
  attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
}).addTo(map);
map.attributionControl.addAttribution('Images : Copernicus Sentinel-2 (modifiées) via Microsoft Planetary Computer ; lieux : <a href="https://nominatim.org/" target="_blank" rel="noopener">Nominatim</a>');

new ResizeObserver(() => map.invalidateSize()).observe($("map"));   // la barre de réglages change la hauteur de la carte

let marker = null, overlay = null;
let point = null, data = null, layer = "color";
let selection = 0;                 // identifie le point choisi (les dates complètes arrivent après coup)
let seq = 0;                       // invalide les réponses d'une sélection plus ancienne
const sceneUrls = new Map();       // "date|layer" -> URL objet (évite de re-télécharger)

function setStatus(html, kind) {
  statusBox.className = kind || "";
  statusBox.innerHTML = html;
}
function busy(on) { skeleton.hidden = !on; }
function inPyrenees(lat, lon) {
  return lon >= PYR_BBOX[0] && lon <= PYR_BBOX[2] && lat >= PYR_BBOX[1] && lat <= PYR_BBOX[3];
}

// --- Recherche Nominatim (à la validation uniquement) ---
let lastSearch = 0;
$("search").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("q").value.trim();
  if (!q) return;
  const btn = $("search-btn");
  btn.disabled = true;
  setStatus("Recherche en cours…");
  try {
    const wait = lastSearch + NOMINATIM_DELAY_MS - Date.now();
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
    lastSearch = Date.now();
    const [w, s, e2, n] = PYR_BBOX;
    const res = MOCK
      ? await window.mockApi("nominatim?q=" + encodeURIComponent(q), MOCK)
      : await fetch("https://nominatim.openstreetmap.org/search?" + new URLSearchParams({
        q, format: "jsonv2", limit: "6", "accept-language": "fr", bounded: "1", viewbox: `${w},${n},${e2},${s}`,
      }));
    if (!res.ok) throw new Error(res.status);
    showResults(await res.json());
  } catch (err) {
    setStatus("La recherche a échoué (réseau ou service indisponible). Réessayez dans un instant.", "error");
  } finally {
    btn.disabled = false;
  }
});

function showResults(items) {
  const list = $("results");
  list.replaceChildren();
  if (!items.length) {
    list.hidden = true;
    setStatus("Aucun lieu trouvé dans les Pyrénées pour cette recherche. Essayez un autre nom, ou cliquez sur la carte.");
    return;
  }
  setStatus(`${items.length} résultat${items.length > 1 ? "s" : ""} : choisissez un lieu.`);
  for (const it of items) {
    const li = document.createElement("li");
    li.innerHTML = `<button type="button">${esc(it.display_name)}</button>`;
    li.firstElementChild.addEventListener("click", () => {
      list.hidden = true;
      selectPoint(+it.lat, +it.lon);
    });
    list.append(li);
  }
  list.hidden = false;
  list.querySelector("button").focus();
}

map.on("click", (e) => { $("results").hidden = true; selectPoint(e.latlng.lat, e.latlng.lng); });

// --- Sélection d'un point et chargement des dates ---
async function selectPoint(lat, lon) {
  const id = ++seq;
  const sel = ++selection;
  point = { lat, lon };
  data = null;
  clearOverlay();
  panel.hidden = true;
  if (marker) marker.remove();
  marker = L.marker([lat, lon], { keyboard: false }).addTo(map);
  map.setView([lat, lon], Math.max(map.getZoom(), 10));

  if (!inPyrenees(lat, lon)) return outside();

  busy(true);
  setStatus("Recherche des images disponibles… (quelques secondes, jusqu'à 20 s la première fois)");
  const base = `/api/dates?lat=${lat.toFixed(5)}&lon=${lon.toFixed(5)}`;
  const fetchDates = async (query) => {
    const res = await api(base + query);
    if (id !== seq) return null;
    if (!res.ok) { failure(res.status, () => selectPoint(lat, lon)); return null; }
    const json = await res.json();
    return id === seq ? json : null;
  };
  try {
    // 1) réponse rapide sur les scènes les plus récentes ; 2) liste complète en arrière-plan
    data = await fetchDates(`&limit=${QUICK_ITEMS}`);
    if (!data) return;
    if (data.complete === false && !hasGoodDate(data)) {
      setStatus("Aucune image récente assez dégagée parmi les premières : analyse de toute la période…");
      data = await fetchDates("");
      if (!data) return;
    }
  } catch (err) {
    if (id === seq) failure(0, () => selectPoint(lat, lon));
    return;
  }
  if (!data.dates || !data.dates.length) return failure(404);
  fillDates();
  panel.hidden = false;
  const first = data.default || bestDate();
  const shown = showScene(first);
  if (data.complete === false) completeDates(sel, base);
  return shown;
}

// Complète la liste des dates sans toucher à l'image affichée.
async function completeDates(sel, base) {
  try {
    const res = await api(base);
    if (!res.ok || sel !== selection) return;
    const full = await res.json();
    if (sel !== selection) return;
    const current = $("date").value;   // l'utilisateur a pu changer de date entre-temps
    data = full;
    fillDates();
    markDate(current);
  } catch (err) { /* la liste partielle reste utilisable */ }
}

// Une date récente exploitable (peu de nuages, bonne couverture) suffit pour afficher sans attendre.
function hasGoodDate(d) {
  return d.dates.some((e) => e.cloud_pct < CLOUD_MAX && e.data_pct >= DATA_MIN);
}

function outside() {
  busy(false);
  setStatus("Ce lieu est hors des Pyrénées : choisissez un point dans la zone (Atlantique à la Méditerranée).", "error");
}

// Erreurs HTTP/réseau -> messages. 0 = erreur réseau.
function failure(code, retry) {
  busy(false);
  const again = retry ? ' <button type="button" id="retry">Réessayer</button>' : "";
  const msg = {
    0: "Impossible de joindre le serveur. Vérifiez votre connexion." + again,
    400: null,
    404: "Aucune image Sentinel-2 trouvée autour de ce lieu sur les 60 derniers jours. Essayez un autre point.",
    429: "Trop de demandes pour le moment. Patientez une minute puis réessayez." + again,
  }[code];
  if (code === 400) return outside();
  setStatus(msg || "Erreur du serveur (" + code + ")." + again, "error");
  if (retry && $("retry")) $("retry").addEventListener("click", retry);
}

// Sans date par défaut : la moins nuageuse (couverture suffisante de préférence).
function bestDate() {
  const ok = data.dates.filter((d) => d.data_pct >= DATA_MIN);
  const pool = ok.length ? ok : data.dates;
  return pool.reduce((a, b) => (b.cloud_pct < a.cloud_pct ? b : a)).date;
}

// Frise des dates, de la plus ancienne (gauche) à la plus récente : une barre empilée par date
// (nuages en haut, neige en bas, le reste = sol dégagé). Le <select> caché reste la valeur de référence.
function fillDates() {
  const sel = $("date"), strip = $("strip");
  sel.replaceChildren();
  strip.replaceChildren();
  let lastMonth = "";
  for (const d of [...data.dates].reverse()) {
    const o = document.createElement("option");
    o.value = d.date;
    o.textContent = fmtDate(d.date);
    sel.append(o);

    const when = new Date(d.date + "T12:00:00");
    const month = when.toLocaleDateString("fr-FR", { month: "short" }).replace(".", "");
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.date = d.date;
    b.className = "day" + (d.data_pct < DATA_MIN ? " partial" : "");
    b.title = `${fmtDate(d.date)} : nuages ${pct(d.cloud_pct)}, neige ${pct(d.snow_pct)}, couverture ${pct(d.data_pct)}` +
      (d.data_pct < DATA_MIN ? " (faible)" : "");
    b.innerHTML = `<span class="col"><i class="cl" style="height:${Math.min(d.cloud_pct, 100)}%"></i>` +
      `<i class="sn" style="height:${Math.min(d.snow_pct, 100)}%"></i></span>` +
      `<span class="lab">${when.getDate()}${month !== lastMonth ? `<small>${month}</small>` : ""}</span>`;
    lastMonth = month;
    b.addEventListener("click", () => showScene(d.date));
    strip.append(b);
  }
}

function markDate(date) {
  $("date").value = date;
  for (const b of $("strip").children) {
    const on = b.dataset.date === date;
    b.setAttribute("aria-pressed", on);
    if (on) b.scrollIntoView({ inline: "center", block: "nearest" });
  }
}

// --- Affichage de l'image ---
function clearOverlay() {
  if (overlay) { overlay.remove(); overlay = null; }
  for (const u of sceneUrls.values()) URL.revokeObjectURL(u);
  sceneUrls.clear();
}

async function showScene(date) {
  const id = ++seq;
  const entry = data.dates.find((d) => d.date === date);
  markDate(date);
  updateWarning(entry);
  const key = date + "|" + layer;
  let objUrl = sceneUrls.get(key);
  if (!objUrl) {
    busy(true);
    setStatus("Calcul de l'image… (5 à 15 s la première fois, instantané ensuite)");
    try {
      const res = await api(`/api/scene?lat=${point.lat.toFixed(5)}&lon=${point.lon.toFixed(5)}&date=${date}&layer=${layer}`);
      if (id !== seq) return;
      if (!res.ok) return failure(res.status, () => showScene(date));
      objUrl = URL.createObjectURL(await res.blob());
    } catch (err) {
      if (id === seq) failure(0, () => showScene(date));
      return;
    }
    if (id !== seq) { URL.revokeObjectURL(objUrl); return; }
    sceneUrls.set(key, objUrl);
  }
  busy(false);
  const [minlon, minlat, maxlon, maxlat] = data.bbox;
  const bounds = [[minlat, minlon], [maxlat, maxlon]];
  const opacity = $("opacity").value / 100;
  if (overlay) overlay.remove();
  overlay = L.imageOverlay(objUrl, bounds, { opacity, alt: `Image Sentinel-2 du ${fmtDate(date)}` }).addTo(map);
  map.fitBounds(bounds);
  setStatus(`Image du ${fmtDate(date)} (${layer === "ndsi" ? "neige NDSI" : "couleur"}).`);
}

function updateWarning(d) {
  const msgs = [];
  if (d.cloud_pct >= CLOUD_MAX) msgs.push(`Trop de nuages (${pct(d.cloud_pct)} de la zone) : l'image risque d'être peu lisible. Essayez une autre date.`);
  if (d.data_pct < DATA_MIN) msgs.push(`Couverture faible : l'image ne couvre que ${pct(d.data_pct)} de la zone.`);
  $("warn").textContent = msgs.join(" ");
  $("warn").hidden = !msgs.length;
}

// --- Contrôles ---
$("opacity").addEventListener("input", (e) => { if (overlay) overlay.setOpacity(e.target.value / 100); });
document.querySelectorAll("[data-layer]").forEach((b) => b.addEventListener("click", () => {
  layer = b.dataset.layer;
  document.querySelectorAll("[data-layer]").forEach((o) => {
    o.classList.toggle("on", o === b);
    o.setAttribute("aria-pressed", o === b);
  });
  $("legend").hidden = layer !== "ndsi";
  if (data) showScene($("date").value);
}));

// Le PNG est demandé à la volée (l'affichage utilise le format par défaut, plus léger).
$("download").addEventListener("click", async () => {
  const btn = $("download"), date = $("date").value;
  btn.disabled = true;
  try {
    const res = await api(`/api/scene?lat=${point.lat.toFixed(5)}&lon=${point.lon.toFixed(5)}&date=${date}&layer=${layer}&format=png`);
    if (!res.ok) throw new Error(res.status);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await res.blob());
    a.download = `sentinel2_${layer}_${date}_${point.lat.toFixed(3)}_${point.lon.toFixed(3)}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  } catch (err) {
    setStatus("Le téléchargement a échoué. Réessayez.", "error");
  } finally {
    btn.disabled = false;
  }
});
