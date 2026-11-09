"use strict";

// Simulateur d'API pour développer carte.js sans backend : ouvrir carte.html?mock=1
// (chargé uniquement dans ce cas). Valeurs de ?mock= :
//   1 normal | nuages (toutes dates très nuageuses) | 404 | 429 | 500 | reseau (échec fetch)
// Les images sont dessinées dans un canvas (dégradé + grille) ; latence simulée ~1,5 s.

const BASE = new Date("2026-10-28T12:00:00");
const iso = (daysAgo) => new Date(BASE - daysAgo * 864e5).toISOString().slice(0, 10);

function dates(mode) {
  const rows = [[0, 4.2, 31, 98], [3, 35, 28, 95], [8, 62, 20, 90], [11, 12, 15, 42], [17, 8.5, 5, 97], [30, 90, 0, 100]];
  return rows.map(([d, c, s, p]) => ({
    date: iso(d), item: "S2B_MOCK_" + iso(d), data_pct: p, snow_pct: s,
    cloud_pct: mode === "nuages" ? Math.max(c, 45) : c,
  }));
}

function image(layer, label, type) {
  const c = document.createElement("canvas");
  c.width = c.height = 800;
  const g = c.getContext("2d");
  if (layer === "color") {
    const gr = g.createLinearGradient(0, 0, 800, 800);
    gr.addColorStop(0, "#3d5a2a"); gr.addColorStop(.5, "#8a7a5a"); gr.addColorStop(1, "#e8eef2");
    g.fillStyle = gr; g.fillRect(0, 0, 800, 800);
  } else {
    g.fillStyle = "#2f7fd8cc";   // NDSI : bleu sur fond transparent
    g.beginPath(); g.arc(400, 400, 220, 0, 7); g.fill();
  }
  g.strokeStyle = "#fff8"; g.lineWidth = 2;
  for (let i = 0; i <= 800; i += 100) { g.moveTo(i, 0); g.lineTo(i, 800); g.moveTo(0, i); g.lineTo(800, i); }
  g.stroke();
  g.fillStyle = "#000"; g.font = "32px sans-serif"; g.fillText(label, 20, 50);
  return new Promise((ok) => c.toBlob(ok, type));
}

window.mockApi = async function (path, mode) {
  await new Promise((r) => setTimeout(r, 1500));
  const u = new URL(path, location.href);
  const fail = { 404: 404, 429: 429, 500: 500 }[mode];
  if (mode === "reseau") throw new TypeError("mock: réseau");
  if (u.pathname === "/nominatim" || u.pathname.endsWith("/nominatim")) {
    const q = u.searchParams.get("q");
    return Response.json(q === "rien" ? [] : [
      { display_name: `${q}, Haute-Garonne, Occitanie, France`, lat: "42.78", lon: "1.32" },
      { display_name: `${q} (col), Hautes-Pyrénées, France`, lat: "42.91", lon: "0.14" },
    ]);
  }
  if (fail) return new Response("", { status: fail });
  const lat = +u.searchParams.get("lat"), lon = +u.searchParams.get("lon");
  const half = 0.0905, hx = half / Math.cos(lat * Math.PI / 180);   // ±10 km environ
  const bbox = [lon - hx, lat - half, lon + hx, lat + half];
  if (u.pathname.endsWith("/api/dates")) {
    const d = dates(mode);
    return Response.json({ center: [lat, lon], bbox, default: d[0].date, dates: d });
  }
  const png = u.searchParams.get("format") === "png";
  const blob = await image(u.searchParams.get("layer"), u.searchParams.get("date"), png ? "image/png" : "image/webp");
  return new Response(blob, { headers: { "X-Bbox": bbox.join(",") } });
};
