"use strict";

const BUCKET_URL = "https://storage.googleapis.com/pyrenees_images/";
const PLAY_DELAY_MS = 700;

const app = document.getElementById("app");
const lightbox = document.getElementById("lightbox");
let manifest = null;
let timer = null;

const url = (path) => BUCKET_URL + path;
const label = (zone) => zone.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const fmtDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function preload(path) {
  new Image().src = url(path);
}

function openLightbox(image) {
  document.getElementById("lb-img").src = url(image.view);
  document.getElementById("lb-orig").href = url(image.orig);
  lightbox.hidden = false;
}
lightbox.addEventListener("click", (e) => { if (e.target !== document.getElementById("lb-orig")) lightbox.hidden = true; });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") lightbox.hidden = true; });

function renderHome() {
  const grid = el('<div class="grid"></div>');
  for (const [zone, images] of Object.entries(manifest.zones)) {
    const last = images[images.length - 1];
    grid.append(el(`<a class="card" href="#/zone/${encodeURIComponent(zone)}">
      <img loading="lazy" src="${url(last.thumb)}" alt="${label(zone)}">
      <div><strong>${label(zone)}</strong><span class="muted">${fmtDate(last.date)} · ${images.length} images</span></div>
    </a>`));
  }
  app.replaceChildren(grid);
}

function renderZone(zone, mode) {
  const images = manifest.zones[zone];
  if (!images) { app.textContent = "Zone inconnue."; return; }

  const tabs = el(`<div class="controls">
    <a href="#/">← Zones</a><h2 style="margin:0">${label(zone)}</h2>
    <button data-mode="time" class="${mode === "compare" ? "" : "on"}">Évolution</button>
    <button data-mode="compare" class="${mode === "compare" ? "on" : ""}">Avant / après</button>
  </div>`);
  tabs.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    location.hash = `#/zone/${encodeURIComponent(zone)}${b.dataset.mode === "compare" ? "/compare" : ""}`;
  }));
  app.replaceChildren(tabs, mode === "compare" ? compareView(images) : timeView(images));
}

function timeView(images) {
  let index = images.length - 1;
  const wrap = el("<div></div>");
  const frame = el('<div class="frame"><img alt=""></div>');
  const img = frame.firstElementChild;
  const slider = el(`<input type="range" min="0" max="${images.length - 1}" value="${index}" aria-label="Date">`);
  const dateLabel = el('<strong style="min-width:9em"></strong>');
  const play = el("<button>▶ Timelapse</button>");
  const strip = el('<div class="strip"></div>');

  const thumbs = images.map((image, i) => {
    const t = el(`<img loading="lazy" src="${url(image.thumb)}" alt="${fmtDate(image.date)}">`);
    t.addEventListener("click", () => show(i));
    strip.append(t);
    return t;
  });

  function show(i) {
    index = i;
    const image = images[i];
    img.style.opacity = ".5";
    img.onload = () => { img.style.opacity = ""; };
    img.src = url(image.view);
    img.alt = `${fmtDate(image.date)}`;
    img.onclick = () => openLightbox(image);
    slider.value = i;
    dateLabel.textContent = fmtDate(image.date);
    thumbs.forEach((t, j) => t.classList.toggle("sel", j === i));
    thumbs[i].scrollIntoView({ block: "nearest", inline: "center" });
    if (images[i + 1]) preload(images[i + 1].view);
  }

  function stop() { clearInterval(timer); timer = null; play.textContent = "▶ Timelapse"; }
  play.addEventListener("click", () => {
    if (timer) return stop();
    play.textContent = "⏸ Pause";
    timer = setInterval(() => show((index + 1) % images.length), PLAY_DELAY_MS);
  });
  slider.addEventListener("input", () => { stop(); show(+slider.value); });

  wrap.append(frame, el('<div class="controls"></div>'), strip);
  wrap.children[1].append(play, slider, dateLabel);
  show(index);
  return wrap;
}

function compareView(images) {
  const options = images.map((im, i) => `<option value="${i}">${fmtDate(im.date)}</option>`).join("");
  const wrap = el(`<div>
    <div class="controls">
      <label>Avant <select id="sel-a">${options}</select></label>
      <label>Après <select id="sel-b">${options}</select></label>
    </div>
    <div class="frame compare">
      <img id="img-b" alt="">
      <div class="top"><img id="img-a" alt=""></div>
      <div class="handle"></div>
      <span class="tag" id="tag-a" style="left:8px"></span>
      <span class="tag" id="tag-b" style="right:8px"></span>
      <input type="range" min="0" max="100" value="50" aria-label="Curseur de comparaison">
    </div></div>`);
  const $ = (s) => wrap.querySelector(s);
  const selA = $("#sel-a"), selB = $("#sel-b");
  selA.value = Math.max(0, images.length - 2);
  selB.value = images.length - 1;

  function update() {
    const a = images[selA.value], b = images[selB.value];
    $("#img-a").src = url(a.view);
    $("#img-b").src = url(b.view);
    $("#tag-a").textContent = fmtDate(a.date);
    $("#tag-b").textContent = fmtDate(b.date);
  }
  selA.addEventListener("change", update);
  selB.addEventListener("change", update);
  $("input[type=range]").addEventListener("input", (e) => {
    const v = e.target.value;
    $(".top").style.clipPath = `inset(0 ${100 - v}% 0 0)`;
    $(".handle").style.left = v + "%";
  });
  update();
  return wrap;
}

function route() {
  if (timer) { clearInterval(timer); timer = null; }
  if (!manifest) return;
  const [, kind, zone, mode] = location.hash.split("/");
  if (kind === "zone" && zone) renderZone(decodeURIComponent(zone), mode);
  else renderHome();
}

async function init() {
  try {
    const res = await fetch(url("manifest.json"));
    if (!res.ok) throw new Error(res.status);
    manifest = await res.json();
  } catch (err) {
    app.textContent = "Impossible de charger les images (" + err.message + ").";
    return;
  }
  document.getElementById("generated").textContent =
    "Mis à jour le " + new Date(manifest.generated).toLocaleDateString("fr-FR");
  route();
}

window.addEventListener("hashchange", route);
init();
