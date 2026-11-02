"use strict";

// ---------------------------------------------------------------- configuration
const STYLES = {
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};

const PALETTES = {
  temp: ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#ffffbf", "#fee090", "#fdae61", "#f46d43", "#d73027", "#a50026"],
  humid: ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
  pressure: ["#762a83", "#af8dc3", "#e7d4e8", "#f7f7f7", "#d9f0d3", "#7fbf7b", "#1b7837"],
  wind: ["#ffffcc", "#c7e9b4", "#7fcdbb", "#41b6c4", "#2c7fb8", "#253494"],
  sun: ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
  rain: ["#e8f1fa", "#9ecae1", "#4292c6", "#2171b5", "#08306b"],
};

// src: stored variables the layer is computed from; range: colour scale limits (fixed, so colours stay comparable)
const LAYERS = {
  T2M: { label: "Temperature", unit: "°C", src: ["T2M"], range: [-20, 35], pal: "temp", digits: 1 },
  TD2M: { label: "Dew point", unit: "°C", src: ["TD2M"], range: [-25, 20], pal: "temp", digits: 1 },
  RH2M: { label: "Humidity", unit: "%", src: ["RH2M"], range: [0, 100], pal: "humid", digits: 0 },
  P0: { label: "Pressure (sea level)", unit: "hPa", src: ["P0"], range: [985, 1035], pal: "pressure", digits: 1 },
  WIND: { label: "Wind speed", unit: "m/s", src: ["UU", "VV"], range: [0, 20], pal: "wind", digits: 1 },
  GL: { label: "Sun (global radiation)", unit: "W/m²", src: ["GL"], range: [0, 1000], pal: "sun", digits: 0 },
  RR: { label: "Rain (per hour)", unit: "mm", src: ["RR"], range: [0, 10], pal: "rain", digits: 1, sqrt: true },
};

const EVENT_KINDS = {
  cold_front: { label: "Cold front passage", color: "#5e2ca5" },
  thunderstorm: { label: "Thunderstorm", color: "#e91e8c" },
  cold_drop: { label: "Cold drop", color: "#00838f" },
};

const PRESET_LABEL = { cold_front: "Cold front", thunderstorm: "Thunderstorms", calm: "Calm day" };
const PRESET_SETUP = {
  cold_front: { layer: "T2M", events: ["cold_front"] },
  thunderstorm: { layer: "RR", events: ["thunderstorm"] },
  calm: { layer: "T2M", events: [] },
};

// ---------------------------------------------------------------- state
const $ = (id) => document.getElementById(id);
let meta, flags = {}, share = {};
let map, geo, T0;
const cache = {}; // stored variable -> Uint8Array (time x point)
const luts = {};
const S = {
  t: 0, layer: "T2M", events: new Set(["cold_front"]), sel: null, playing: false, theme: "light", busy: false,
};

// ---------------------------------------------------------------- data
async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

// first row as stored, every later row as the int8 difference to the previous hour
async function getVariable(name) {
  if (cache[name]) return cache[name];
  const r = await fetch(`data/obs/${name}.bin`);
  if (!r.ok) throw new Error(`${name}: ${r.status}`);
  const buf = new Uint8Array(await r.arrayBuffer());
  const n = meta.n, nt = meta.nt;
  const out = new Uint8Array(nt * n);
  out.set(buf.subarray(0, n));
  const d = new Int8Array(buf.buffer, buf.byteOffset + n, (nt - 1) * n);
  for (let t = 1; t < nt; t++) {
    const o = t * n;
    for (let i = 0; i < n; i++) out[o + i] = out[o - n + i] + d[o - n + i];
  }
  cache[name] = out;
  return out;
}

function physical(name, q) {
  const s = meta.variables[name];
  const x = s.lo + q * s.step;
  return s.sqrt ? x * x : x;
}

function sample(layer, t, i) {
  const L = LAYERS[layer], k = t * meta.n + i;
  if (L.src.length === 2) return Math.hypot(physical(L.src[0], cache[L.src[0]][k]), physical(L.src[1], cache[L.src[1]][k]));
  return physical(L.src[0], cache[L.src[0]][k]);
}

function buildEvents(ev) {
  const n = meta.n, nt = meta.nt;
  for (const kind of Object.keys(EVENT_KINDS)) {
    const f = new Uint8Array(nt * n), c = new Float32Array(nt);
    const { t, p } = ev[kind];
    for (let k = 0; k < t.length; k++) { f[t[k] * n + p[k]] = 1; c[t[k]] += 1 / n; }
    flags[kind] = f;
    share[kind] = c;
  }
}

// ---------------------------------------------------------------- time
const fmtUtc = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC", weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const fmtVienna = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Vienna", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZoneName: "short",
});
const fmtDay = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "numeric", month: "short" });
const dateOf = (t) => new Date(T0 + t * 3600e3);
const indexOf = (iso) => Math.round((Date.parse(iso) - T0) / 3600e3);

// ---------------------------------------------------------------- colours
function makeLut(pal) {
  const stops = pal.map((h) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16)));
  return Array.from({ length: 256 }, (_, k) => {
    const x = (k / 255) * (stops.length - 1), a = Math.min(Math.floor(x), stops.length - 2), f = x - a;
    const c = stops[a].map((v, j) => Math.round(v + (stops[a + 1][j] - v) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  });
}

function colorIndex(L, v) {
  const [lo, hi] = L.range;
  let f = (v - lo) / (hi - lo);
  f = L.sqrt ? Math.sqrt(Math.max(0, f)) : f;
  return Math.max(0, Math.min(255, Math.round(f * 255)));
}

// ---------------------------------------------------------------- map
function radius(scale) {
  // half the grid spacing in pixels: spacing / 2 / (metres per pixel at 47.6 N) = 0.071 * 2^zoom for 15 km
  const k = 0.0710 * (meta.spacing_km / 15) * scale;
  return ["interpolate", ["exponential", 2], ["zoom"], 4, k * 16, 12, k * 4096];
}

function setupLayers() {
  map.addSource("pts", { type: "geojson", data: geo });
  map.addLayer({
    id: "pts", type: "circle", source: "pts",
    paint: { "circle-color": ["get", "c"], "circle-opacity": ["get", "o"], "circle-radius": radius(0.96) },
  });
  const empty = { type: "FeatureCollection", features: [] };
  map.addSource("rings", { type: "geojson", data: empty });
  map.addLayer({
    id: "rings-halo", type: "circle", source: "rings",
    paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": radius(0.72), "circle-stroke-color": "#ffffff", "circle-stroke-width": 4.5, "circle-stroke-opacity": 0.9 },
  });
  map.addLayer({
    id: "rings", type: "circle", source: "rings",
    paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": radius(0.72), "circle-stroke-color": ["get", "col"], "circle-stroke-width": 2.2 },
  });
  map.addSource("sel", { type: "geojson", data: empty });
  map.addLayer({
    id: "sel", type: "circle", source: "sel",
    paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": radius(1.15), "circle-stroke-color": S.theme === "dark" ? "#ffffff" : "#000000", "circle-stroke-width": 2.5 },
  });
  render();
}

function initMap() {
  map = new maplibregl.Map({
    container: "map", style: STYLES[S.theme], center: [13.35, 47.6], zoom: 6.2, minZoom: 4, maxZoom: 13,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.on("style.load", setupLayers);
  map.on("click", (e) => {
    if (!map.getLayer("pts")) return;
    const f = map.queryRenderedFeatures(e.point, { layers: ["pts"] })[0];
    select(f ? f.properties.i : null);
  });
  map.on("mousemove", (e) => {
    const f = map.getLayer("pts") ? map.queryRenderedFeatures(e.point, { layers: ["pts"] })[0] : null;
    const tip = $("tip");
    map.getCanvas().style.cursor = f ? "pointer" : "";
    if (!f || !cache[LAYERS[S.layer].src[0]]) { tip.hidden = true; return; }
    const L = LAYERS[S.layer], i = f.properties.i;
    tip.textContent = `${sample(S.layer, S.t, i).toFixed(L.digits)} ${L.unit} · ${meta.lat[i].toFixed(2)}°N ${meta.lon[i].toFixed(2)}°E`;
    tip.style.left = `${e.originalEvent.clientX + 14}px`;
    tip.style.top = `${e.originalEvent.clientY + 14}px`;
    tip.hidden = false;
  });
  map.on("mouseout", () => { $("tip").hidden = true; });
}

function fitAustria() {
  const wide = window.innerWidth > 760;
  map.fitBounds([[9.4, 46.3], [17.3, 49.1]], { padding: { top: 20, bottom: 20, left: wide ? 310 : 20, right: wide ? 60 : 20 }, duration: 0 });
}

// ---------------------------------------------------------------- render
let pending = false;
function render() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => { pending = false; draw(); });
}

function draw() {
  const L = LAYERS[S.layer], n = meta.n, t = S.t;
  if (!L.src.every((v) => cache[v])) return;
  const lut = luts[S.layer];
  const feats = geo.features;
  for (let i = 0; i < n; i++) {
    const v = sample(S.layer, t, i), p = feats[i].properties;
    p.c = lut[colorIndex(L, v)];
    p.o = L.sqrt && v < 0.05 ? 0.35 : 0.9;
  }
  const rings = [];
  for (const kind of S.events) {
    const f = flags[kind], col = EVENT_KINDS[kind].color;
    for (let i = 0; i < n; i++) {
      if (f[t * n + i]) rings.push({ type: "Feature", geometry: feats[i].geometry, properties: { col } });
    }
  }
  if (map.getSource("pts")) {
    map.getSource("pts").setData(geo);
    map.getSource("rings").setData({ type: "FeatureCollection", features: rings });
    map.getSource("sel").setData({
      type: "FeatureCollection", features: S.sel == null ? [] : [{ type: "Feature", geometry: feats[S.sel].geometry, properties: {} }],
    });
  }
  const d = dateOf(t);
  $("when").innerHTML = `${fmtUtc.format(d)} UTC <span>· ${fmtVienna.format(d)}</span>`;
  $("slider").value = t;
  drawTimeline();
  drawChart();
  writeHash();
}

// ---------------------------------------------------------------- timeline (year overview, click or drag to jump)
const TL = { w: 0, h: 0, cols: null };
function drawTimeline() {
  const cv = $("tl"), dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if (!w) return;
  if (TL.w !== w || TL.h !== h || !TL.cols) {
    cv.width = w * dpr; cv.height = h * dpr; TL.w = w; TL.h = h;
    TL.cols = {};
    for (const kind of ["cold_front", "thunderstorm"]) {
      const c = new Float32Array(w), s = share[kind];
      for (let x = 0; x < w; x++) {
        const a = Math.floor((x / w) * meta.nt), b = Math.max(a + 1, Math.floor(((x + 1) / w) * meta.nt));
        let m = 0;
        for (let k = a; k < b; k++) m = Math.max(m, s[k]);
        c[x] = m;
      }
      TL.cols[kind] = { c, max: Math.max(...c, 0.01) };
    }
  }
  const g = cv.getContext("2d"), css = getComputedStyle(document.documentElement);
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  const rows = [["cold_front", 0, 20], ["thunderstorm", 22, 14]];
  for (const [kind, y0, hh] of rows) {
    g.fillStyle = css.getPropertyValue("--line");
    g.fillRect(0, y0 + hh - 1, w, 1);
    g.fillStyle = EVENT_KINDS[kind].color;
    const { c, max } = TL.cols[kind];
    for (let x = 0; x < w; x++) {
      const bh = Math.ceil((c[x] / max) * (hh - 2));
      if (c[x] > 0.01 * max && bh > 0) g.fillRect(x, y0 + hh - 1 - bh, 1, bh);
    }
  }
  g.fillStyle = css.getPropertyValue("--muted");
  g.font = "10px system-ui, sans-serif";
  g.textBaseline = "top";
  for (let m = 0; m < 12; m++) {
    const d = new Date(Date.UTC(2025, 9 + m, 1)), t = (d.getTime() - T0) / 3600e3;
    if (t < 0 || t >= meta.nt) continue;
    const x = (t / meta.nt) * w;
    g.fillRect(x, 0, 1, h);
    g.fillText(d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" }), x + 3, 36 - 0);
  }
  g.fillStyle = css.getPropertyValue("--fg");
  g.fillRect(Math.round((S.t / meta.nt) * w) - 1, 0, 2, h);
}

function scrub(e) {
  const r = $("tl").getBoundingClientRect();
  setT(Math.max(0, Math.min(meta.nt - 1, Math.round(((e.clientX - r.left) / r.width) * (meta.nt - 1)))));
}

// ---------------------------------------------------------------- chart of the selected point
function drawChart() {
  const box = $("chart");
  if (S.sel == null) { box.hidden = true; return; }
  const L = LAYERS[S.layer], i = S.sel, n = meta.n;
  const a = Math.max(0, S.t - 72), b = Math.min(meta.nt - 1, S.t + 72);
  const vals = [];
  for (let t = a; t <= b; t++) vals.push(sample(S.layer, t, i));
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
  const W = 340, H = 150, ml = 34, mr = 6, mt = 8, mb = 20;
  const x = (t) => ml + ((t - a) / Math.max(1, b - a)) * (W - ml - mr);
  const y = (v) => mt + (1 - (v - lo) / (hi - lo)) * (H - mt - mb);
  let s = "";
  for (let k = 0; k <= 3; k++) {
    const v = lo + ((hi - lo) * k) / 3;
    s += `<line class="grid" x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}"/><text x="${ml - 4}" y="${y(v) + 3}" text-anchor="end">${v.toFixed(L.digits)}</text>`;
  }
  for (const kind of S.events) {
    s += `<g fill="${EVENT_KINDS[kind].color}" opacity=".28">`;
    for (let t = a; t <= b; t++) if (flags[kind][t * n + i]) s += `<rect x="${x(t) - 1.5}" y="${mt}" width="3" height="${H - mt - mb}"/>`;
    s += "</g>";
  }
  for (let t = a; t <= b; t++) {
    if (dateOf(t).getUTCHours() === 0) {
      s += `<line class="grid" x1="${x(t)}" x2="${x(t)}" y1="${mt}" y2="${H - mb}"/><text x="${x(t)}" y="${H - 6}" text-anchor="middle">${fmtDay.format(dateOf(t))}</text>`;
    }
  }
  s += `<polyline class="line" points="${vals.map((v, k) => `${x(a + k).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}"/>`;
  s += `<line class="now" x1="${x(S.t)}" x2="${x(S.t)}" y1="${mt}" y2="${H - mb}"/>`;
  $("csvg").innerHTML = s;
  $("ctitle").textContent = `${L.label} (${L.unit})`;
  $("csub").textContent = `Point ${meta.id[i]} · ${meta.lat[i].toFixed(2)}°N ${meta.lon[i].toFixed(2)}°E · 3 days before and after`;
  box.hidden = false;
}

function select(i) {
  S.sel = i == null || S.sel === Number(i) ? null : Number(i);
  render();
}

// ---------------------------------------------------------------- controls
function setT(t) { S.t = t; render(); }

async function setLayer(key) {
  S.layer = key;
  document.querySelectorAll("#vars .chip").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.key === key)));
  const L = LAYERS[key];
  $("legbar").style.background = `linear-gradient(90deg, ${PALETTES[L.pal].join(",")})`;
  $("lmin").textContent = L.range[0];
  $("lmax").textContent = L.range[1];
  $("lunit").textContent = L.unit;
  if (!L.src.every((v) => cache[v])) {
    document.body.style.cursor = "progress";
    try { await Promise.all(L.src.map(getVariable)); } finally { document.body.style.cursor = ""; }
  }
  render();
}

function syncEvents() {
  document.querySelectorAll("#evs input").forEach((c) => { c.checked = S.events.has(c.dataset.kind); });
}

function toggleEvent(kind, on) {
  if (on) S.events.add(kind); else S.events.delete(kind);
  syncEvents();
  render();
}

function togglePlay() {
  S.playing = !S.playing;
  $("play").textContent = S.playing ? "❚❚ Pause" : "▶ Play";
  const step = () => {
    if (!S.playing) return;
    setT((S.t + Number($("speed").value)) % meta.nt);
    setTimeout(step, 140);
  };
  if (S.playing) step();
}

function buildUi() {
  $("spacing").textContent = meta.spacing_km;
  const vars = $("vars");
  vars.className = "chips";
  for (const [key, L] of Object.entries(LAYERS)) {
    const b = document.createElement("button");
    b.className = "chip"; b.dataset.key = key; b.setAttribute("role", "radio"); b.textContent = L.label;
    b.onclick = () => setLayer(key);
    vars.append(b);
    luts[key] = makeLut(PALETTES[L.pal]);
  }
  for (const [kind, E] of Object.entries(EVENT_KINDS)) {
    const l = document.createElement("label");
    l.className = "ev";
    l.innerHTML = `<input type="checkbox" data-kind="${kind}"><span class="swatch" style="border-color:${E.color}"></span>${E.label}`;
    l.querySelector("input").onchange = (e) => toggleEvent(kind, e.target.checked);
    $("evs").append(l);
  }
  const fmt = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  for (const p of meta.presets) {
    const b = document.createElement("button");
    b.className = "jump";
    b.textContent = `${PRESET_LABEL[p.kind]} · ${fmt.format(new Date(Date.parse(p.time)))} UTC`;
    b.onclick = async () => {
      const setup = PRESET_SETUP[p.kind];
      S.events = new Set(setup.events);
      S.sel = null;
      syncEvents();
      S.t = indexOf(p.time);
      await setLayer(setup.layer);
    };
    $("jumps").append(b);
  }
  const slider = $("slider");
  slider.max = meta.nt - 1;
  slider.oninput = () => setT(Number(slider.value));
  $("prev").onclick = () => setT(Math.max(0, S.t - 1));
  $("next").onclick = () => setT(Math.min(meta.nt - 1, S.t + 1));
  $("play").onclick = togglePlay;
  $("cclose").onclick = () => select(null);
  let drag = false;
  $("tl").addEventListener("pointerdown", (e) => { drag = true; $("tl").setPointerCapture(e.pointerId); scrub(e); });
  $("tl").addEventListener("pointermove", (e) => { if (drag) scrub(e); });
  $("tl").addEventListener("pointerup", () => { drag = false; });
  $("theme").onclick = () => {
    S.theme = S.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = S.theme;
    TL.cols = null;
    map.setStyle(STYLES[S.theme]);
  };
  window.addEventListener("resize", () => { TL.cols = null; render(); });
}

// ---------------------------------------------------------------- shareable link: #v=T2M&t=4000&ev=cold_front&sel=12
function writeHash() {
  const h = `v=${S.layer}&t=${S.t}&ev=${[...S.events].join(",")}${S.sel == null ? "" : `&sel=${S.sel}`}&theme=${S.theme}`;
  history.replaceState(null, "", `#${h}`);
}

function readHash() {
  const q = new URLSearchParams(location.hash.slice(1));
  if (LAYERS[q.get("v")]) S.layer = q.get("v");
  if (q.has("t")) S.t = Math.max(0, Math.min(meta.nt - 1, Number(q.get("t")) || 0));
  if (q.has("ev")) S.events = new Set(q.get("ev").split(",").filter((k) => EVENT_KINDS[k]));
  if (q.has("sel") && Number(q.get("sel")) < meta.n) S.sel = Number(q.get("sel"));
  if (STYLES[q.get("theme")]) S.theme = q.get("theme");
}

// ---------------------------------------------------------------- start
async function main() {
  const [m, ev] = await Promise.all([fetchJson("data/meta.json"), fetchJson("data/events.json")]);
  meta = m; T0 = Date.parse(meta.t0);
  buildEvents(ev);
  geo = {
    type: "FeatureCollection",
    features: meta.lon.map((lon, i) => ({ type: "Feature", geometry: { type: "Point", coordinates: [lon, meta.lat[i]] }, properties: { i, c: "#999", o: 0.9 } })),
  };
  S.theme = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  const hasHash = location.hash.length > 1;
  if (!hasHash) {
    // open on the cold front that reaches the largest share of Austria
    const f = meta.presets.filter((p) => p.kind === "cold_front").sort((a, b) => b.share - a.share)[0];
    if (f) S.t = indexOf(f.time);
  }
  readHash();
  document.documentElement.dataset.theme = S.theme;
  buildUi();
  syncEvents();
  initMap();
  map.once("load", fitAustria);
  await setLayer(S.layer);
}

main().catch((err) => {
  document.body.insertAdjacentHTML("beforeend", `<p style="position:fixed;top:12px;left:12px;background:#fff;color:#b00;padding:8px;z-index:9">Could not load the data: ${err.message}</p>`);
  console.error(err);
});
