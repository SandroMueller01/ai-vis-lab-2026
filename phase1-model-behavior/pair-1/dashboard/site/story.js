"use strict";
// Carlos's story (one-page dashboard): scrollytelling chapters (text steps on the left, a figure that stays in place
// and changes with each step), then the front explorer. Data: site/data/carlos/*.json (build_carlos_data.py).
// Uses h(), s(), tip, ramp(), byId() from common.js and legend() from charts.js.

const sgn = (v, d = 1) => `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(d)}`;
const at = (xs, ys, x) => ys[xs.indexOf(x)];
const RDBU = ramp(["#2166ac", "#4393c3", "#92c5de", "#e9e9e9", "#f4a582", "#d6604d", "#b2182b"]);
const INFERNO = ramp(["#000004", "#320a5e", "#781c6d", "#bc3754", "#ed6925", "#fbb61a", "#fcffa4"]);
const PLASMA = ramp(["#2a0f6e", "#6a00a8", "#b12a90", "#e16462", "#fca636", "#f0f921"]);
const C = { fc: "#6da7ec", band: "#3987e5", front: "#ff6b6b", grey: "#8b96a3", flag: "#ffa45c" };

async function loadJson(name) {
  const r = await fetch(`data/carlos/${name}.json?v=8`);
  if (!r.ok) throw new Error(`${name}.json: ${r.status}`);
  return r.json();
}

// ------------------------------------------------------------------------------------------- small svg helpers
function frame(W, H, aria) { return s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": aria }); }

// axes inside box {l, t, w, h}; returns the scales
function axes(svg, box, { x0, x1, y0, y1, xticks, yticks, xfmt = String, yfmt = String, xlabel, ylabel, grid = true }) {
  const X = (v) => box.l + ((v - x0) / (x1 - x0)) * box.w;
  const Y = (v) => box.t + box.h - ((v - y0) / (y1 - y0)) * box.h;
  for (const v of yticks || []) {
    if (grid) svg.append(s("line", { class: "gl", x1: box.l, x2: box.l + box.w, y1: Y(v), y2: Y(v) }));
    svg.append(s("text", { x: box.l - 7, y: Y(v) + 4, "text-anchor": "end", text: yfmt(v) }));
  }
  for (const v of xticks || []) {
    if (grid) svg.append(s("line", { class: "gl", x1: X(v), x2: X(v), y1: box.t, y2: box.t + box.h }));
    svg.append(s("text", { x: X(v), y: box.t + box.h + 15, "text-anchor": "middle", text: xfmt(v) }));
  }
  if (xlabel) svg.append(s("text", { x: box.l + box.w / 2, y: box.t + box.h + 32, "text-anchor": "middle", class: "axt", text: xlabel }));
  if (ylabel) svg.append(s("text", { x: box.l - 40, y: box.t + box.h / 2, "text-anchor": "middle", transform: `rotate(-90 ${box.l - 40} ${box.t + box.h / 2})`, class: "axt", text: ylabel }));
  return { X, Y };
}

const pts = (xs, ys, X, Y) => xs.map((x, i) => (ys[i] == null || !Number.isFinite(ys[i]) ? null : `${X(x).toFixed(1)},${Y(ys[i]).toFixed(1)}`)).filter(Boolean).join(" ");
const poly = (xs, ys, X, Y, attrs) => s("polyline", { points: pts(xs, ys, X, Y), fill: "none", "stroke-linejoin": "round", "stroke-linecap": "round", ...attrs });
const area = (xs, lo, hi, X, Y, attrs) => s("polygon", { points: `${pts(xs, hi, X, Y)} ${pts([...xs].reverse(), [...lo].reverse(), X, Y)}`, ...attrs });

// smooth path through points (Catmull-Rom)
function smooth(p) {
  if (p.length < 2) return "";
  let d = `M${p[0][0]},${p[0][1]}`;
  for (let i = 0; i < p.length - 1; i++) {
    const a = p[i - 1] || p[i], b = p[i], c = p[i + 1], e = p[i + 2] || c;
    d += ` C${b[0] + (c[0] - a[0]) / 6},${b[1] + (c[1] - a[1]) / 6} ${c[0] - (e[0] - b[0]) / 6},${c[1] - (e[1] - b[1]) / 6} ${c[0]},${c[1]}`;
  }
  return d;
}

// lon/lat -> box (equal scale, cos(lat) for longitude)
function geoBox(lon, lat, box) {
  const k = Math.cos((47.6 * Math.PI) / 180);
  const xs = lon.map((v) => v * k), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...lat), y1 = Math.max(...lat);
  const sc = Math.min(box.w / (x1 - x0), box.h / (y1 - y0));
  const ox = box.l + (box.w - (x1 - x0) * sc) / 2, oy = box.t + (box.h - (y1 - y0) * sc) / 2;
  return { x: (i) => ox + (lon[i] * k - x0) * sc, y: (i) => oy + (y1 - lat[i]) * sc };
}

function colorBar(svg, x, y, w, f, labels, title) {
  const id = `g${Math.random().toString(36).slice(2, 8)}`;
  const grad = s("linearGradient", { id });
  for (let k = 0; k <= 10; k++) grad.append(s("stop", { offset: `${k * 10}%`, "stop-color": f(k / 10) }));
  svg.append(s("defs", {}, grad), s("rect", { x, y, width: w, height: 8, rx: 2, fill: `url(#${id})` }));
  labels.forEach(([t, lab]) => svg.append(s("text", { x: x + t * w, y: y + 21, "text-anchor": "middle", text: lab })));
  if (title) svg.append(s("text", { x: x + w / 2, y: y - 6, "text-anchor": "middle", text: title }));
}

const isoZ = (t) => (/[zZ]$|[+-]\d\d:\d\d$/.test(t) ? t.replace(" ", "T") : `${t}Z`);

// ------------------------------------------------------------------------------------------- details on demand
function infoToggle(text) {
  const box = h("div", { class: "info", hidden: true, html: text });
  const btn = h("button", { type: "button", class: "infobtn", "aria-expanded": "false", title: "How to read this figure" }, "i");
  btn.onclick = () => { box.hidden = !box.hidden; btn.setAttribute("aria-expanded", String(!box.hidden)); };
  return [btn, box];
}

function moreToggle(html) {
  const more = h("p", { class: "more", hidden: true, html });
  const btn = h("button", { type: "button", class: "morebtn" }, "more");
  btn.onclick = () => { more.hidden = !more.hidden; btn.textContent = more.hidden ? "more" : "less"; };
  return [btn, more];
}

function drawer(title, body) {
  const d = h("aside", { class: "drawer", role: "dialog", "aria-label": title },
    h("div", { class: "dhead" }, h("b", {}, title), h("button", { type: "button", class: "dclose", "aria-label": "Close", onclick: () => d.classList.remove("open") }, "×")), body);
  document.body.append(d);
  return () => d.classList.toggle("open");  // the same button opens and closes it
}

// ------------------------------------------------------------------------------------------- sideways sections (wide screens)
// the story page has three sections; inside a section the page scroll moves the slides sideways (see .hs in story.css), after it down
const HS = document.body.dataset.page === "story" && matchMedia("(min-width: 900px)").matches && !/[?&]flow=vertical/.test(location.search);

// ------------------------------------------------------------------------------------------- scrollytelling frame
// steps: [{when, html, more, state, takeaway}]; draw(host, controls) returns update(state)
function scrolly({ id, kicker, question, sub, info, steps, draw, tall = false }) {
  const host = h("div", { class: "fig" });
  const controls = h("div", { class: "figctl" });
  const take = h("p", { class: "takeaway" });
  const [ib, ibox] = info ? infoToggle(info) : [null, null];
  const stepEls = steps.map((st) => {
    const [mb, more] = st.more ? moreToggle(st.more) : [null, null];
    return h("div", { class: "step" }, h("div", {}, st.when ? h("span", { class: "when" }, st.when) : null, h("span", { html: st.html }), mb, more));
  });
  const section = h("section", { class: "chapter", id },
    h("div", { class: "qnum" }, kicker),
    h("div", { class: "scrolly" },
      h("div", { class: tall ? "steps tall" : "steps" }, stepEls),
      h("div", { class: "sticky" }, h("div", { class: "viz" },
        h("div", { class: "qhead" }, h("h2", { class: "frame-q" }, question), ib), sub ? h("p", { class: "frame-sub" }, sub) : null, ibox, controls, host, take))));
  const update = draw(host, controls);
  let current = -1;
  const show = (i) => {
    if (i === current || i < 0) return;
    current = i;
    stepEls.forEach((el, k) => el.classList.toggle("active", k === i));
    if (!update.scrub) update(steps[i].state);
    take.textContent = steps[i].takeaway || "";
  };
  // ?ch=<id>&show=N sets that chapter to step N without scrolling (for screenshots)
  const q = new URLSearchParams(location.search);
  if (q.get("ch") === id) { show(Number(q.get("show") || 0)); return section; }
  const obs = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) show(stepEls.indexOf(e.target));
  }, { rootMargin: HS ? "0px -20% 0px -70%" : "-45% 0px -45% 0px" });  // sideways: the strip right of the figure
  stepEls.forEach((el) => obs.observe(el));
  show(0);
  if (update.scrub) {
    // the figure follows the scroll position continuously: f = 0 at the first step's centre, 1 at the second, ...
    let ticking = false;
    const onScroll = () => {
      ticking = false;
      const mid = HS ? innerWidth * 0.75 : innerHeight / 2, c = stepEls.map((el) => { const r = el.getBoundingClientRect(); return HS ? r.left + r.width / 2 : r.top + r.height / 2; });
      let f = 0;
      if (mid >= c[c.length - 1]) f = c.length - 1;
      else for (let k = 0; k < c.length - 1; k++) if (mid >= c[k] && mid < c[k + 1]) f = k + (mid - c[k]) / (c[k + 1] - c[k]);
      update.scrub(f);
    };
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  }
  return section;
}

// =========================================================================================== 1. the weather (Exp 7)
function chapterWeather(d) {
  const W = 1250, H = 560, n = d.x.length;
  const svg = frame(W, H, "Time curve of Austria's temperature map around the 25-26 March cold front");
  const box = { l: 30, t: 30, w: 850, h: 500 };
  const xr = [Math.min(...d.x), Math.max(...d.x)], yr = [Math.min(...d.y), Math.max(...d.y)];
  const sc = Math.min(box.w / (xr[1] - xr[0]), box.h / (yr[1] - yr[0]));
  const ox = box.l + (box.w - (xr[1] - xr[0]) * sc) / 2, oy = box.t + (box.h - (yr[1] - yr[0]) * sc) / 2;
  const P = d.x.map((x, i) => [ox + (x - xr[0]) * sc, oy + (yr[1] - d.y[i]) * sc]);
  const path = s("path", { d: smooth(P), fill: "none", stroke: "#5b6672", "stroke-width": 1.5 });
  svg.append(path);
  const dots = P.map(([x, y], i) => {
    const c = s("circle", { cx: x, cy: y, r: 5.2, fill: RDBU((d.mean[i] + d.clim) / (2 * d.clim)), stroke: d.passing[i] ? "#fff" : "none", "stroke-width": 2, class: "tdot" });
    c.addEventListener("pointermove", (ev) => tip.show(`<b>${d.label[i]}, ${d.hours[i].slice(8, 10)}.${d.hours[i].slice(5, 7)}.</b><br>Austria ${sgn(d.mean[i])} °C vs usual${d.passing[i] ? "<br>front passing" : ""}`, ev));
    c.addEventListener("pointerleave", () => tip.hide());
    svg.append(c);
    return c;
  });
  // day labels at 00h and 12h, beside the dots (offsets in px: right, down); Fri 00h left out (crowded)
  const LP = { "Tue 00h": [22, 30], "Tue 12h": [35, 25], "Wed 00h": [45, 25], "Wed 12h": [40, 0], "Thu 00h": [0, 45], "Thu 12h": [30, -20], "Fri 12h": [-25, 20], "Sat 00h": [0, 30], "Sat 12h": [35, -15] };
  const labels = [];
  d.label.forEach((lab, i) => {
    if (!LP[lab]) return;
    const t = s("text", { x: P[i][0] + LP[lab][0] * 0.8, y: P[i][1] + LP[lab][1] * 0.8 + 4, "text-anchor": "middle", class: "daylab", text: lab });
    svg.append(t);
    labels.push([i, t]);
  });
  const KP = { A: [-30, 0], B: [26, -22], C: [-34, 14] };
  const keyEls = Object.entries(d.keys).map(([k, v]) => {
    const [x, y] = P[v.i], [dx, dy] = KP[k];
    const g = s("g", {}, s("line", { x1: x, y1: y, x2: x + dx * 0.7, y2: y + dy * 0.7, stroke: "#fff", "stroke-width": 1.2 }),
      s("text", { x: x + dx, y: y + dy + 6, "text-anchor": "middle", class: "keylab", text: k }));
    svg.append(g);
    return [v.i, g];
  });
  // three snapshot maps
  const maps = Object.entries(d.keys).map(([k, v], r) => {
    const b = { l: 918, t: 30 + r * 166, w: 300, h: 128 };
    const geo = geoBox(d.points.lon, d.points.lat, b);
    const g = s("g", { class: "snap" });
    g.append(s("text", { x: b.l, y: b.t - 8, class: "title", text: `${k} · ${v.name} (${d.label[v.i]})` }));
    v.map.forEach((val, i) => g.append(s("circle", { cx: geo.x(i), cy: geo.y(i), r: 3, fill: RDBU((val + d.clim) / (2 * d.clim)) })));
    svg.append(g);
    return g;
  });
  colorBar(svg, 950, 534, 240, RDBU, [[0, `−${d.clim}`], [0.5, "0"], [1, `+${d.clim}`]], "°C vs the usual temperature");
  const iA = d.keys.A.i, iB = d.keys.B.i;
  const update = ({ upto, map }) => {
    const last = upto === "all" ? n - 1 : d.keys[upto].i;
    dots.forEach((c, i) => { c.style.opacity = i <= last ? 1 : 0.07; });
    labels.forEach(([i, t]) => { t.style.opacity = i <= last ? 1 : 0; });
    keyEls.forEach(([i, g]) => { g.style.opacity = i <= last ? 1 : 0; });
    path.setAttribute("d", smooth(P.slice(0, last + 1)));
    maps.forEach((g, r) => { g.style.opacity = r < map ? 0.5 : r === map ? 1 : 0.06; });
  };
  const steps = [
    { state: { upto: "A", map: 0 }, when: "Before the front",
      html: `Each dot is <b>one hour</b>: the whole temperature map of Austria. <b>Close dots = similar maps.</b> Warm air arrives first: ${sgn(d.mean[iA])} °C above usual (A).`,
      more: `Colour = Austria's average difference from the usual temperature for that month and hour. The layout comes from classical multidimensional scaling of the 120 hourly maps (378 points) and keeps ${Math.round(d.kept * 100)} % of their differences (time curves, Bach et al. 2015).` },
    { state: { upto: "B", map: 1 }, when: "The front passes",
      html: `White rings: the front crosses Austria. Within hours the curve <b>jumps</b> to a different map (B, ${sgn(d.mean[iB])} °C).` },
    { state: { upto: "all", map: 2 }, when: "After the front",
      html: "The cold stays (C). The curve wanders, but <b>never returns</b> to where it started.",
      takeaway: "A cold front changes the whole map within hours, and for days." },
  ];
  const draw = (host) => {
    host.append(svg);
    return update;
  };
  return scrolly({ id: "ch-weather", kicker: "Also tested", question: "How does a cold front change Austria's weather?",
    sub: "23–28 March 2026, one dot per hour.", steps, draw,
    info: "This figure is about the <b>data</b>, not the model: it shows what the model has to forecast in the next chapters." });
}

// =========================================================================================== 2. where it looks (Exp 10)
// full = false: the main story shows only normal days (heatmap + 32-hour pattern);
// full = true: the comparison with cold-front cases and the totals per day ("Also tested" section)
function chapterLooksFull(d) { return chapterLooks(d, true); }
function chapterLooks(d, full = false) {
  const W = 1250, H = 440;
  const svg = frame(W, H, "Occlusion: which hours of the history change the forecast");
  const [gn, gf] = d.groups;
  const all = [...gn.grid.flat(), ...gf.grid.flat()].sort((a, b) => a - b);
  const zmax = all[Math.floor(all.length * 0.98)];
  const heat = (g, left, w = 300) => {
    const b = { l: left, t: 40, w, h: 336 }, cw = b.w / 24, ch = b.h / 28;
    const grp = s("g");
    if (full) grp.append(s("text", { x: b.l + b.w / 2, y: 26, "text-anchor": "middle", class: "title", text: g.group === "normal day" ? `${g.n} random forecasts` : `Before a cold front (${g.n} cases)` }));
    g.grid.forEach((row, r) => row.forEach((v, c) => {
      const rect = s("rect", { x: b.l + c * cw, y: b.t + r * ch, width: cw + 0.3, height: ch + 0.3, fill: INFERNO(Math.min(v / zmax, 1)) });
      rect.addEventListener("pointermove", (ev) => tip.show(`<b>${r + 1} day${r ? "s" : ""} back, hour ${c + 1}</b><br>forecast changes by ${v.toFixed(3)} °C when this hour is hidden`, ev));
      rect.addEventListener("pointerleave", () => tip.hide());
      grp.append(rect);
    }));
    const pat = s("g", { class: "pattern" });
    d.pattern_32h.cells.forEach(([r, c]) => pat.append(s("rect", { x: b.l + c * cw + 0.5, y: b.t + r * ch + 0.5, width: cw - 1, height: ch - 1, fill: "none", stroke: "#4ee1ff", "stroke-width": 1.3 })));
    for (const r of [0, 6, 13, 20, 27]) grp.append(s("text", { x: b.l - 6, y: b.t + (r + 0.75) * ch, "text-anchor": "end", text: r + 1 }));
    for (const c of [0, 5, 11, 17, 23]) grp.append(s("text", { x: b.l + (c + 0.5) * cw, y: b.t + b.h + 14, "text-anchor": "middle", text: c + 1 }));
    grp.append(s("text", { x: b.l + b.w / 2, y: b.t + b.h + 32, "text-anchor": "middle", class: "axt", text: "hour of that day (1 = closest to the forecast)" }));
    svg.append(grp, pat);
    return { grp, pat };
  };
  svg.append(s("text", { x: 22, y: 208, "text-anchor": "middle", class: "axt", transform: "rotate(-90 22 208)", text: "days before the forecast" }));
  const N = full ? heat(gn, 52, 380) : heat(gn, 52, 560);
  const ratio = gf.per_day.reduce((a, b) => a + b) / gn.per_day.reduce((a, b) => a + b);
  const avg = d.pattern_32h.ratio_by_lag_mod_32;
  const patBtn = h("button", { type: "button", class: "toggle", "aria-pressed": "false" }, "Show the 32-hour pattern");
  if (!full) {
    colorBar(svg, 52, 420, 300, INFERNO, [[0, "0"], [1, `${zmax.toFixed(2)} °C or more`]], "");
    // side chart: zoom on 7-14 days back (5 spikes) as a line; guide lines every 32 hours
    const per = gn.grid.flat(), L0 = 168, L1 = 336;  // per[lag - 1] = change when that hour is hidden
    const sb = { l: 730, t: 40, w: 490, h: 336 };
    const ymax = Math.max(...per.slice(L0 - 1, L1)) * 1.1;
    const SX = (lag) => sb.l + ((lag - L0) / (L1 - L0)) * sb.w, SY = (v) => sb.t + sb.h - (v / ymax) * sb.h;
    const side = s("g");
    side.append(s("text", { x: sb.l + sb.w / 2, y: 26, "text-anchor": "middle", class: "title", text: "7 to 14 days back" }));
    for (const v of [0, 0.02, 0.04, 0.06, 0.08, 0.1].filter((v) => v < ymax)) side.append(s("line", { class: "gl", x1: sb.l, x2: sb.l + sb.w, y1: SY(v), y2: SY(v) }), s("text", { x: sb.l - 6, y: SY(v) + 4, "text-anchor": "end", text: v.toFixed(2) }));
    for (let lag = 33; lag <= L1; lag += 32) if (lag >= L0) side.append(s("line", { x1: SX(lag), x2: SX(lag), y1: sb.t, y2: sb.t + sb.h, stroke: "#4ee1ff", "stroke-opacity": 0.3, "stroke-dasharray": "2 3" }));
    const pts = [];
    for (let lag = L0; lag <= L1; lag++) pts.push(`${SX(lag).toFixed(1)},${SY(per[lag - 1]).toFixed(1)}`);
    side.append(s("polyline", { points: pts.join(" "), fill: "none", stroke: "#8b949e", "stroke-width": 1.2, "stroke-linejoin": "round" }));
    for (let lag = 33; lag < L1; lag += 32) if (lag >= L0) for (const l of [lag, lag + 1]) {
      const c = s("circle", { cx: SX(l), cy: SY(per[l - 1]), r: 2.6, fill: "#4ee1ff" });
      c.addEventListener("pointermove", (ev) => tip.show(`<b>${l} hours back</b><br>forecast changes by ${per[l - 1].toFixed(3)} °C`, ev));
      c.addEventListener("pointerleave", () => tip.hide());
      side.append(c);
    }
    for (const day of [8, 9, 10, 11, 12, 13, 14]) side.append(s("text", { x: SX(24 * day - 12), y: sb.t + sb.h + 14, "text-anchor": "middle", text: day }));
    side.append(s("text", { x: sb.l + sb.w / 2, y: sb.t + sb.h + 32, "text-anchor": "middle", class: "axt", text: "days before the forecast" }),
      s("text", { x: sb.l - 44, y: sb.t + sb.h / 2, "text-anchor": "middle", class: "axt", transform: `rotate(-90 ${sb.l - 44} ${sb.t + sb.h / 2})`, text: "forecast change (°C)" }));
    side.style.transition = "opacity .4s";
    svg.append(side);
    const setPat1 = (on) => { patBtn.setAttribute("aria-pressed", String(on)); N.pat.style.opacity = on ? 1 : 0; side.style.opacity = on ? 1 : 0.12; };
    patBtn.onclick = () => setPat1(patBtn.getAttribute("aria-pressed") !== "true");
    const steps1 = [
      { state: false, when: "One hour hidden",
        html: `We hide <b>one hour</b> of the 4-week history and measure how much the forecast changes. Bright = that hour matters. The last day matters most (${Math.round(gn.last_day_share * 100)} %), but <b>all four weeks</b> count.` },
      { state: true, when: "Look closer",
        html: `Bright pairs repeat every <b>32 hours</b>: one day down and 8 hours to the right. On the right, the same hours as a line: the spikes sit exactly every 32 hours, and there hiding an hour changes the forecast <b>${d.pattern_32h.ratio_normal[1].toFixed(1)}×</b> more than the average hour.`,
        more: "The 32-hour blocks explain <b>where</b> the bright cells are: the model probably reads its history in 32-hour blocks. <b>Why</b> those hours matter more is an open question for Phase II: do they weigh more, or does the model handle a gap at a block edge badly?" },
    ];
    const draw1 = (host) => { host.append(svg); return setPat1; };
    return scrolly({ id: "ch-looks", kicker: "How it reads its history", question: "Which part of its history does the model use?",
      sub: `${gn.n} random forecasts (random places and dates, not picked around a cold front); each of the 672 history hours hidden once.`, steps: steps1, draw: draw1,
      info: "Each cell is one hour of the history (rows = days back, columns = hours of that day). Colour = mean change of the 24-hour forecast when only this hour is hidden. Right: the same hours as a line, zoomed on 7 to 14 days back. Dashed lines every 32 hours; cyan dots = the two hours just after each line." });
  }
  const F = heat(gf, 472, 380);
  // totals per day back (same rows as the heatmaps)
  const lb = { l: 940, t: 40, w: 270, h: 336 };
  const mx = Math.ceil(Math.max(...gn.per_day, ...gf.per_day));
  const X = (v) => lb.l + (v / mx) * lb.w, Y = (day) => lb.t + ((day - 0.5) / 28) * lb.h;
  const lg = s("g");
  for (let v = 0; v <= mx; v++) lg.append(s("line", { class: "gl", x1: X(v), x2: X(v), y1: lb.t, y2: lb.t + lb.h }), s("text", { x: X(v), y: lb.t + lb.h + 14, "text-anchor": "middle", text: v }));
  const line = (vals, col) => s("polyline", { points: vals.map((v, i) => `${X(v)},${Y(i + 1)}`).join(" "), fill: "none", stroke: col, "stroke-width": 2.4, "stroke-linejoin": "round" });
  const ln = line(gn.per_day, C.grey), lf = line(gf.per_day, C.front);
  for (const day of [1, 7, 14, 21, 28]) lg.append(s("text", { x: lb.l - 6, y: Y(day) + 4, "text-anchor": "end", text: day }));
  lg.append(s("text", { x: lb.l - 30, y: lb.t + lb.h / 2, "text-anchor": "middle", transform: `rotate(-90 ${lb.l - 30} ${lb.t + lb.h / 2})`, class: "axt", text: "days back" }));
  lg.append(ln, lf, s("text", { x: lb.l + lb.w / 2, y: 26, "text-anchor": "middle", class: "title", text: "Total per day" }),
    s("text", { x: lb.l + lb.w / 2, y: lb.t + lb.h + 30, "text-anchor": "middle", class: "axt", text: "summed change (°C)" }));
  svg.append(lg);
  colorBar(svg, 52, 420, 300, INFERNO, [[0, "0"], [1, `${zmax.toFixed(2)} °C or more`]], "");
  const setPat = (on) => { patBtn.setAttribute("aria-pressed", String(on)); [N, F].forEach((p) => { p.pat.style.opacity = on ? 1 : 0; }); };
  patBtn.onclick = () => setPat(patBtn.getAttribute("aria-pressed") !== "true");
  const update = ({ front, pat }) => { F.grp.style.opacity = front ? 1 : 0.12; lf.style.opacity = front ? 1 : 0; setPat(pat); };
  const steps = [
    { state: { front: false, pat: false }, when: "Random forecasts",
      html: `We hide <b>one hour</b> of the 4-week history and measure how much the forecast changes. Bright = that hour matters. The last day matters most (${Math.round(gn.last_day_share * 100)} %), but <b>all four weeks</b> count.` },
    { state: { front: true, pat: false }, when: "Before a cold front",
      html: `Same shape, but every hour matters <b>${ratio.toFixed(1)}× more</b>, mostly 2–10 days back.` },
    { state: { front: true, pat: true }, when: "Look closer",
      html: `Bright pairs line up on a diagonal that repeats every <b>32 hours</b>: hiding the newest hours of each 32-hour block changes the forecast ${avg[1].toFixed(1)}× more than average.`,
      more: "The 32-hour blocks explain <b>where</b> the bright cells are: the model probably reads its history in 32-hour blocks. <b>Why</b> those hours matter more is an open question for Phase II: do they weigh more, or does the model handle a gap at a block edge badly?" },
  ];
  const draw = (host, ctl) => { host.append(legend([["random forecasts", C.grey], ["before a cold front", C.front]]), svg); ctl.append(patBtn); return update; };
  return scrolly({ id: "ch-looks-full", kicker: "Also tested", question: "Which part of its history does the model use, and does that change before a cold front?",
    sub: `${gn.n} random forecasts and ${gf.n} cold-front cases; each of the 672 history hours hidden once.`, steps, draw,
    info: "Each cell is one hour of the history (rows = days back, columns = hours of that day). Colour = mean change of the 24-hour forecast when only this hour is hidden." });
}

// =========================================================================================== 3. repeated patterns (Exp 1)
function chapterSundays(d) {
  const W = 1250, H = 400;
  const svgA = frame(W, 330, "Scores: does the forecast follow fixed Sundays");
  const rowsDef = [
    ["rep", "4 repeated Sundays", (g) => g.setup === "4 Sundays" && !g.flag, C.flag],
    ["single", "1 single Sunday", (g) => g.setup.startsWith("1 Sunday"), "#c9a77a"],
    ["flag", "4 Sundays + Sunday flag", (g) => g.setup === "4 Sundays" && g.flag, "#ff7f0e"],
  ];
  const vals = [10, 20, 50], pw = 320, gap = 40, left = 196, rowH = 70, top = 44;
  const rowEls = {};
  rowsDef.forEach(([key, label], r) => {
    const g = s("g", { class: "srow" });
    g.append(s("text", { x: left - 14, y: top + r * rowH + rowH / 2 + 4, "text-anchor": "end", class: "rowlab", text: label }));
    rowEls[key] = g;
    svgA.append(g);
  });
  vals.forEach((v, c) => {
    const x0 = left + c * (pw + gap), X = (p) => x0 + (p / 100) * pw;
    svgA.append(s("text", { x: x0 + pw / 2, y: 24, "text-anchor": "middle", class: "title", text: `Sundays set to ${v} °C` }));
    for (const p of [0, 50, 100]) svgA.append(s("line", { class: "gl", x1: X(p), x2: X(p), y1: top, y2: top + rowH * rowsDef.length }), s("text", { x: X(p), y: top + rowH * rowsDef.length + 16, "text-anchor": "middle", text: String(p) }));
    rowsDef.forEach(([key, , match, col], r) => {
      const sc = d.groups.filter((g) => g.value === v && match(g)).flatMap((g) => g.scores).filter((x) => x != null);
      const mean = sc.reduce((a, b) => a + b, 0) / sc.length;
      const cy = top + r * rowH + rowH / 2;
      let seed = 7 + r * 13 + c;
      const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
      const step = Math.max(1, Math.floor(sc.length / 800));
      for (let k = 0; k < sc.length; k += step) rowEls[key].append(s("circle", { cx: X(sc[k]), cy: cy + (rnd() - 0.5) * rowH * 0.62, r: 1.5, fill: col, "fill-opacity": 0.3 }));
      rowEls[key].append(s("line", { x1: X(mean), x2: X(mean), y1: cy - rowH * 0.36, y2: cy + rowH * 0.36, stroke: "#fff", "stroke-width": 2.5 }),
        s("text", { x: X(mean) + (mean > 80 ? -6 : 6), y: cy - rowH * 0.36 + 3, "text-anchor": mean > 80 ? "end" : "start", class: "val", text: `${Math.round(mean)} %` }));
    });
  });
  svgA.append(s("text", { x: left + (3 * pw + 2 * gap) / 2, y: top + rowH * rowsDef.length + 36, "text-anchor": "middle", class: "axt", text: "% of the way the forecast moved towards the fixed value (0 = ignored, 100 = copied) · white line = mean" }));

  // example pair (drawer, on demand)
  const exPanel = (e, kind) => {
    const svg = frame(560, 250, `Example: the model ${kind} the fixed Sundays`);
    const nh = e.history.length, xs = [...Array(nh).keys()].map((k) => k - nh), fx = [...Array(24).keys()];
    const allv = [...e.history, ...e.history_fixed, ...e.truth, ...e.original.q10, ...e.original.q90, ...e.fixed.q10, ...e.fixed.q90].filter((v) => v != null);
    const lo = Math.floor(Math.min(...allv)) - 1, up = Math.ceil(Math.max(...allv)) + 1;
    const b = { l: 46, t: 12, w: 500, h: 190 };
    const { X: x, Y: y } = axes(svg, b, { x0: -nh, x1: 24, y0: lo, y1: up, xticks: [-168, -120, -72, -24, 0, 24], yticks: [-5, 0, 5, 10, 15, 20, 25].filter((v) => v >= lo && v <= up), xfmt: (v) => (v ? `${v} h` : "0"), xlabel: "hours from the forecast start (Sunday 00 UTC)", ylabel: "°C" });
    e.sunday_hours.forEach((k) => svg.append(s("rect", { x: x(k - nh), y: b.t, width: x(1) - x(0), height: b.h, fill: "#ff7f0e", "fill-opacity": 0.07 })));
    svg.append(poly(xs, e.history, x, y, { stroke: C.fc, "stroke-width": 1.2 }), poly(xs, e.history_fixed, x, y, { stroke: "#ff7f0e", "stroke-width": 1.2 }),
      area(fx, e.original.q10, e.original.q90, x, y, { fill: C.band, "fill-opacity": 0.22 }), area(fx, e.fixed.q10, e.fixed.q90, x, y, { fill: "#ff7f0e", "fill-opacity": 0.2 }),
      poly(fx, e.original.q50, x, y, { stroke: C.fc, "stroke-width": 2.2 }), poly(fx, e.fixed.q50, x, y, { stroke: "#ff7f0e", "stroke-width": 2.2 }), poly(fx, e.truth, x, y, { stroke: "#fff", "stroke-width": 2 }));
    const season = ["Winter", "Spring", "Summer", "Autumn"][Math.floor((Number(e.sunday.slice(5, 7)) % 12) / 3)];  // Dec-Feb = winter, ...
    return h("div", { class: "expanel" }, h("p", { class: "exseason" }, season), h("p", { class: "exhead" }, h("b", {}, kind === "copies" ? "Copied" : "Ignored"), ` · point ${e.point}, Sunday ${e.sunday}, ${e.score} %`), svg);
  };
  const same = d.examples.copies.point === d.examples.ignores.point;
  const openEx = drawer("Two cases, Sundays fixed at 10 °C", h("div", {},
    legend([["real history and its forecast", C.fc], ["fixed Sundays and their forecast", "#ff7f0e"], ["what happened", "#fff"]]),
    exPanel(d.examples.copies, "copies"), exPanel(d.examples.ignores, "ignores"),
    same ? h("p", { class: "note" }, "The same place: copied in winter, ignored in spring, when the normal day-to-day swings are larger.") : null));

  const hostA = h("div", {}, svgA);
  const update = ({ rows }) => {
    rowsDef.forEach(([key]) => { rowEls[key].style.opacity = rows.includes(key) ? 1 : 0.06; });
  };
  const meanOf = (v, setup, flag) => Math.round(d.groups.find((g) => g.value === v && g.setup === setup && g.flag === flag).mean);
  const steps = [
    { state: { view: "rows", rows: ["rep"] }, when: "Repeated",
      html: `The last <b>4 Sundays</b> of the history are set to a fixed temperature; then we forecast the next Sunday. The model <b>copies</b> them: ${meanOf(10, "4 Sundays", false)} % of the way at 10 °C, ${meanOf(50, "4 Sundays", false)} % at 50 °C.`,
      more: `${d.n} cases: ${d.dates} Sundays over the year × 20 random places.` },
    { state: { view: "rows", rows: ["rep", "single"] }, when: "Once", html: "Only <b>one</b> Sunday fixed (1, 2 or 3 weeks back): <b>ignored</b>." },
    { state: { view: "rows", rows: ["rep", "single", "flag"] }, when: "With a Sunday flag", html: `Telling the model which hours are Sundays: it copies <b>more</b> (${meanOf(10, "4 Sundays", true)} % at 10 °C).` },
  ];
  const draw = (host, ctl) => { host.append(hostA); ctl.append(h("button", { type: "button", class: "toggle", onclick: openEx }, "See an example")); return update; };
  return scrolly({ id: "ch-sundays", kicker: "How it reads its history", question: "Does the model continue a pattern it has seen repeatedly, and ignore one it has seen once?",
    sub: "Forecasts for a Sunday after fixing Sundays in the 4-week history.", steps, draw,
    info: "40 forecast Sundays spread over the year, 20 random points each: 800 cases per setup, each with 4 weeks of history (so 4 Sundays). Each dot is one case (place and date). Score = how far the forecast moved from its normal value towards the fixed Sunday value, averaged over the 24 hours. The \"1 single Sunday\" row combines three setups: the Sunday 1, 2 or 3 weeks back (2,400 cases per panel; each alone about 2 %). Control, not shown: the same Sundays fixed, but forecasting the Wednesday of that week: hardly affected (1 to 6 %)." });
}

// the switch (Exp 1): score against the size of the change ("Also tested" section)
function chapterSundaySwitch(d) {
  // the switch: score against the size of the change (10 and 20 °C together)
  const W = 1250, H = 400;
  const svgB = frame(W, H, "Score against the size of the change");
  const bb = { l: 70, t: 24, w: 1130, h: 310 };
  const { X, Y } = axes(svgB, bb, { x0: 0, x1: 24, y0: 0, y1: 100, xticks: [0, 4, 8, 12, 16, 20, 24], yticks: [0, 25, 50, 75, 100], yfmt: (v) => `${v} %`, xlabel: "how different the fixed Sundays are from the real ones (°C)", ylabel: "copied" });
  const cross = [];
  d.score_vs_change.forEach((g) => {
    const col = g.flag ? "#ff7f0e" : C.grey;
    g.change.forEach((x, k) => { if (x <= 24 && g.score[k] != null) svgB.append(s("circle", { cx: X(x), cy: Y(g.score[k]), r: 1.4, fill: col, "fill-opacity": 0.13 })); });
    svgB.append(area(g.bins, g.q25, g.q75, X, Y, { fill: col, "fill-opacity": 0.16 }), poly(g.bins, g.median, X, Y, { stroke: col, "stroke-width": 3 }));
    for (let k = 1; k < g.bins.length; k++) {
      if (g.median[k - 1] < 50 && g.median[k] >= 50) {
        cross.push([g.flag, g.bins[k - 1] + ((50 - g.median[k - 1]) / (g.median[k] - g.median[k - 1])) * (g.bins[k] - g.bins[k - 1]), col]);
        break;
      }
    }
  });
  cross.forEach(([flag, xc, col], i) => svgB.append(s("line", { x1: X(xc), x2: X(xc), y1: bb.t, y2: bb.t + bb.h, stroke: col, "stroke-dasharray": "4 4" }),
    s("text", { x: X(xc) + (flag ? -6 : 6), y: bb.t + bb.h - 30 - i * 18, "text-anchor": flag ? "end" : "start", class: "val", text: `${flag ? "with flag" : "no flag"}: half copied at ${xc.toFixed(0)} °C` })));
  const hostB = h("div", {}, legend([["no time input", C.grey], ["with Sunday flag", "#ff7f0e"]]), svgB);

  const steps = [
    { state: null, when: "A switch", html: "Small changes are ignored, large ones copied: it works like a <b>switch</b>. The flag moves it about 2 °C earlier.",
      takeaway: "A repeated pattern is copied once it stands out by a few degrees." },
  ];
  const draw = (host) => { host.append(hostB); return () => {}; };
  return scrolly({ id: "ch-switch", kicker: "Also tested", question: "How different must the repeated Sundays be before the model copies them?",
    sub: "4 Sundays fixed at 10 or 20 °C; each dot is one case.", steps, draw,
    info: "Score = how far the forecast moved from its normal value towards the fixed Sunday value, averaged over the 24 hours. Lines = median, bands = middle half of the cases." });
}

// =========================================================================================== 4. a stranger history (Exp 6)
function chapterWeird(d) {
  const sl = d.slider, n = sl.sizes.length, W = 1250, H = 440;
  const svg = frame(W, H, "Inserting artificial cold drops into the history");
  const top = { l: 56, t: 24, w: 760, h: 110 }, bot = { l: 56, t: 196, w: 760, h: 196 }, side = { l: 900, t: 40, w: 270, h: 330 };
  const nh = sl.history[0].length, hx = [...Array(nh).keys()];
  const hall = sl.history.flat().filter((v) => v != null);
  const hlo = Math.floor(Math.min(...hall)) - 1, hup = Math.ceil(Math.max(...hall)) + 1;
  const A1 = axes(svg, top, { x0: 0, x1: nh, y0: hlo, y1: hup, xticks: [0, 336, 672, 1008, 1344, 1680], xfmt: (v) => (v === nh ? "now" : `−${(nh - v) / 168} wk`), yticks: [0, 10, 20, 30].filter((v) => v >= hlo && v <= hup), grid: false });
  svg.append(s("text", { x: top.l, y: top.t - 10, class: "title", text: "The 10-week history the model gets" }));
  const histLine = s("polyline", { fill: "none", stroke: "#9aa6b3", "stroke-width": 0.8 });
  const dropMarks = s("g");
  svg.append(dropMarks, histLine);
  const last = 24, bx = [...Array(last).keys()].map((k) => k - last), fx = [...Array(24).keys()];
  const ball = [...sl.history.map((hh) => hh.slice(-last)).flat(), ...sl.q10.flat(), ...sl.q90.flat(), ...sl.truth].filter((v) => v != null);
  const blo = Math.floor(Math.min(...ball)) - 1, bup = Math.ceil(Math.max(...ball)) + 1;
  const A2 = axes(svg, bot, { x0: -last, x1: 24, y0: blo, y1: bup, xticks: [-24, -12, 0, 12, 24], xfmt: (v) => (v ? `${v > 0 ? "+" : ""}${v} h` : "start"), yticks: [0, 5, 10, 15, 20, 25, 30].filter((v) => v >= blo && v <= bup), ylabel: "°C" });
  svg.append(s("text", { x: bot.l, y: bot.t - 10, class: "title", text: "Last day, the forecast and what happened" }));
  const recent = s("polyline", { fill: "none", stroke: "#9aa6b3", "stroke-width": 1.6 });
  const band = s("polygon", { fill: C.band, "fill-opacity": 0.3 });
  const med = s("polyline", { fill: "none", stroke: C.fc, "stroke-width": 2.6 });
  const widthTxt = s("text", { x: bot.l + bot.w, y: bot.t + bot.h + 38, "text-anchor": "end", class: "big" });
  svg.append(recent, band, med, poly(fx, sl.truth, A2.X, A2.Y, { stroke: "#fff", "stroke-width": 2.4 }), widthTxt);
  // side: change of the band width per forecast (with the drops minus without) against drop size; the cursor follows the slider
  const wv = d.lines.flatMap((l) => l.change_mean);
  const wlo = Math.floor(Math.min(...wv) * 2) / 2 - 0.1, wup = Math.ceil(Math.max(...wv) * 2) / 2 + 0.1;
  const A3 = axes(svg, side, { x0: 0, x1: 15, y0: wlo, y1: wup, xticks: [0, 5, 10, 15], yticks: [-1, -0.5, 0, 0.5, 1, 1.5, 2].filter((v) => v >= wlo && v <= wup), yfmt: (v) => (v > 0 ? `+${v}` : v < 0 ? `−${-v}` : "0"), xlabel: "size of each drop (°C)" });
  svg.append(s("text", { x: side.l + side.w / 2, y: side.t - 22, "text-anchor": "middle", class: "title", text: "How much wider the band gets (°C)" }),
    s("text", { x: side.l + side.w / 2, y: side.t - 7, "text-anchor": "middle", class: "val", text: `${d.n} forecasts, ${d.fronts} fronts` }),
    s("line", { x1: side.l, x2: side.l + side.w, y1: A3.Y(0), y2: A3.Y(0), stroke: "#8b96a3", "stroke-dasharray": "4 4" }),
    s("text", { x: side.l + 26, y: A3.Y(0) + 15, class: "val", text: "no drop inserted" }));
  const ends = d.lines.map((l) => [l.n_drops, A3.Y(l.change_mean[l.change_mean.length - 1])]).sort((a, b) => a[1] - b[1]);
  for (let k = 1; k < ends.length; k++) ends[k][1] = Math.max(ends[k][1], ends[k - 1][1] + 17);
  // 4 drops = the case on the left; the other lines stay in the background
  d.lines.forEach((l) => svg.append(poly(l.sizes, l.change_mean, A3.X, A3.Y, l.n_drops === 4 ? { stroke: "#6da7ec", "stroke-width": 3.4 } : { stroke: "#5b6672", "stroke-width": 1.6 })));
  ends.forEach(([nd, y]) => svg.append(s("text", { x: A3.X(15) + 5, y: y + 4, class: "val", style: `fill:${nd === 4 ? "#6da7ec" : "#8b96a3"}${nd === 4 ? ";font-weight:700" : ""}`, text: nd === 4 ? "4 drops" : `${nd} drop${nd > 1 ? "s" : ""}` })));
  const cursor = s("line", { y1: side.t, y2: side.t + side.h, stroke: "#fff", "stroke-dasharray": "3 3" });
  svg.append(cursor);
  const width = sl.q10.map((lo, k) => sl.q90[k].reduce((a, v, j) => a + v - lo[j], 0) / 24);
  const base = sl.history[0];
  const range = h("input", { type: "range", min: 0, max: n - 1, step: 1, value: 0, "aria-label": "Size of the inserted drops" });
  const out = h("output", {});
  let cur = 0;
  const render = (k) => {
    cur = k;
    const hh = sl.history[k];
    histLine.setAttribute("points", pts(hx, hh, A1.X, A1.Y));
    dropMarks.replaceChildren();
    let s0 = -1;
    hh.forEach((v, j) => {
      const on = Math.abs(v - base[j]) > 0.05;
      if (on && s0 < 0) s0 = j;
      if ((!on || j === nh - 1) && s0 >= 0) { dropMarks.append(s("rect", { x: A1.X(s0), y: top.t, width: Math.max(2, A1.X(j) - A1.X(s0)), height: top.h, fill: C.front, "fill-opacity": 0.25 })); s0 = -1; }
    });
    recent.setAttribute("points", pts(bx, hh.slice(-last), A2.X, A2.Y));
    band.setAttribute("points", `${pts(fx, sl.q90[k], A2.X, A2.Y)} ${pts([...fx].reverse(), [...sl.q10[k]].reverse(), A2.X, A2.Y)}`);
    med.setAttribute("points", pts(fx, sl.q50[k], A2.X, A2.Y));
    widthTxt.textContent = `band ${width[k].toFixed(1)} °C wide`;
    cursor.setAttribute("x1", A3.X(sl.sizes[k])); cursor.setAttribute("x2", A3.X(sl.sizes[k]));
    range.value = k;
    out.textContent = sl.sizes[k] === 0 ? "no drop inserted" : `4 drops of ${sl.sizes[k]} °C`;
  };
  range.oninput = () => { cancelAnimationFrame(anim); render(Number(range.value)); };
  let anim = null;
  const glide = (to) => {
    cancelAnimationFrame(anim);
    const from = cur, t0 = performance.now(), dur = Math.min(1400, 30 * Math.abs(to - from) + 250);
    const tick = (now) => {
      const f = Math.min(1, (now - t0) / dur), e = f < 0.5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2;
      render(Math.round(from + (to - from) * e));
      if (f < 1) anim = requestAnimationFrame(tick);
    };
    anim = requestAnimationFrame(tick);
  };
  // widest band over all forecasts (4 drops): the tested size with the largest average change
  const L4 = d.lines.find((l) => l.n_drops === 4), i4 = L4.change_mean.indexOf(Math.max(...L4.change_mean));
  const top4 = { size: L4.sizes[i4], change: L4.change_mean[i4] };
  const l12 = d.lines.find((l) => l.n_drops === 12), last12 = l12.sizes.length - 1;
  const split = { narrow: Math.round(l12.narrow_share[last12] * 100), widen: Math.round(l12.widen_share[last12] * 100) };
  const steps = [
    { state: 0, when: "No drop inserted", html: `A real cold-front case. With no drop inserted, the band is ${width[0].toFixed(1)} °C wide and misses the drop.` },
    { state: sl.sizes.indexOf(4), when: "Make it stranger", html: "We insert <b>4 artificial cold drops</b> into the history (red). The band <b>widens</b>." },
    { state: sl.sizes.indexOf(top4.size), when: "Widest", html: `Over all ${d.fronts} fronts, drops of <b>${top4.size} °C</b> widen the band the most: +${top4.change.toFixed(1)} °C on average (sizes tested: 3 to 15 °C).` },
    { state: n - 1, when: "Stranger still", html: `Bigger drops make it <b>narrower again</b>. With many big drops the effect splits: with 12 drops of 15 °C, ${split.narrow} % of the forecasts get narrower and ${split.widen} % wider.`,
      more: "Why the band narrows again is an open question for Phase II.", takeaway: "Strange history → wider band, but only up to a point." },
  ];
  const draw = (host, ctl) => {
    ctl.append(h("label", { class: "slider" }, "Inserted drops", range, out));
    host.append(svg);
    render(0);
    return (k) => { if (k != null) glide(k); };
  };
  return scrolly({ id: "ch-weird", kicker: "How it reads its history", question: "Does a stranger history make the model less sure?",
    sub: "", steps, draw,
    info: "Band = the 10–90 % range of the forecast: the model's own uncertainty. The inserted drops have the shape of an average cold front; the last 24 hours of the history are never changed." });
}

// =========================================================================================== 4b. where the strange part sits (Exp 6)
function chapterPosition(d) {
  const ex = d.example, n = ex.starts.length, W = 1250, H = 440, C0 = ex.history.length, L = ex.shape.length;
  const svg = frame(W, H, "One cold drop moved through the history");
  const top = { l: 56, t: 24, w: 760, h: 110 }, bot = { l: 56, t: 196, w: 760, h: 196 }, side = { l: 900, t: 40, w: 270, h: 330 };
  const hx = [...Array(C0).keys()], hist = ex.history;
  const hlo = Math.floor(Math.min(...hist) - d.size) - 1, hup = Math.ceil(Math.max(...hist)) + 1;
  const A1 = axes(svg, top, { x0: 0, x1: C0, y0: hlo, y1: hup, xticks: [0, 336, 672, 1008, 1344, 1680], xfmt: (v) => (v === C0 ? "now" : `−${(C0 - v) / 168} wk`), yticks: [0, 10, 20, 30].filter((v) => v >= hlo && v <= hup), grid: false });
  svg.append(s("text", { x: top.l, y: top.t - 10, class: "title", text: "The 10-week history the model gets" }));
  const histLine = s("polyline", { fill: "none", stroke: "#9aa6b3", "stroke-width": 0.8 });
  const dip = s("polyline", { fill: "none", stroke: C.front, "stroke-width": 2.2 });
  const dipBg = s("rect", { y: top.t, height: top.h, fill: C.front, "fill-opacity": 0.18 });
  svg.append(dipBg, histLine, dip);
  const bx = [...Array(24).keys()].map((k) => k - 24), fx = [...Array(24).keys()];
  const ball = [...hist.slice(-24), ...ex.q10.flat(), ...ex.q90.flat(), ...ex.truth].filter((v) => v != null);
  const blo = Math.floor(Math.min(...ball)) - 1, bup = Math.ceil(Math.max(...ball)) + 1;
  const A2 = axes(svg, bot, { x0: -24, x1: 24, y0: blo, y1: bup, xticks: [-24, -12, 0, 12, 24], xfmt: (v) => (v ? `${v > 0 ? "+" : ""}${v} h` : "start"), yticks: [0, 5, 10, 15, 20, 25, 30].filter((v) => v >= blo && v <= bup), ylabel: "°C" });
  svg.append(s("text", { x: bot.l, y: bot.t - 10, class: "title", text: "Last day, the forecast and what happened" }));
  const band = s("polygon", { fill: C.band, "fill-opacity": 0.3 });
  const med = s("polyline", { fill: "none", stroke: C.fc, "stroke-width": 2.6 });
  const widthTxt = s("text", { x: bot.l + bot.w, y: bot.t + bot.h + 38, "text-anchor": "end", class: "big" });
  svg.append(poly(bx, hist.slice(-24), A2.X, A2.Y, { stroke: "#9aa6b3", "stroke-width": 1.6 }), band, med, poly(fx, ex.truth, A2.X, A2.Y, { stroke: "#fff", "stroke-width": 2.4 }), widthTxt);
  // side: change of the band width per forecast (with the drop minus without), against the position (now on the right)
  const a = d.all, wv = [...a.change_q25, ...a.change_q75, 0];
  const wlo = Math.floor(Math.min(...wv) * 4) / 4 - 0.1, wup = Math.ceil(Math.max(...wv) * 4) / 4 + 0.1;
  const A3 = axes(svg, side, { x0: 70, x1: 0, y0: wlo, y1: wup, xticks: [70, 56, 42, 28, 14, 0], xfmt: (v) => (v ? `${v} d` : "now"), yticks: [0, 0.25, 0.5, 0.75, 1, 1.25].filter((v) => v >= wlo && v <= wup), yfmt: (v) => (v ? `+${v}` : "0"), xlabel: "the drop starts … days back" });
  svg.append(s("text", { x: side.l + side.w / 2, y: side.t - 22, "text-anchor": "middle", class: "title", text: "How much wider the band gets (°C)" }),
    s("text", { x: side.l + side.w / 2, y: side.t - 7, "text-anchor": "middle", class: "val", text: `${d.n} forecasts, ${d.fronts} fronts` }),
    area(a.days_back, a.change_q25, a.change_q75, A3.X, A3.Y, { fill: C.band, "fill-opacity": 0.22 }),
    s("line", { x1: side.l, x2: side.l + side.w, y1: A3.Y(0), y2: A3.Y(0), stroke: "#8b96a3", "stroke-dasharray": "4 4" }),
    s("text", { x: side.l + side.w - 2, y: A3.Y(0) + 15, "text-anchor": "end", class: "val", text: "no drop inserted" }),
    poly(a.days_back, a.change_mean, A3.X, A3.Y, { stroke: C.fc, "stroke-width": 3 }));
  const cursor = s("line", { y1: side.t, y2: side.t + side.h, stroke: "#fff", "stroke-dasharray": "3 3" });
  svg.append(cursor);
  const width = ex.q10.map((lo, k) => ex.q90[k].reduce((acc, v, j) => acc + v - lo[j], 0) / 24);
  const range = h("input", { type: "range", min: 0, max: n - 1, step: 1, value: 0, "aria-label": "Position of the inserted drop" });
  const out = h("output", {});
  let cur = 0, anim = null;
  const render = (k) => {
    cur = k;
    const st = ex.starts[k], hh = hist.map((v, j) => (j >= st && j < st + L ? v + d.size * ex.shape[j - st] : v));
    histLine.setAttribute("points", pts(hx, hh, A1.X, A1.Y));
    dip.setAttribute("points", pts(hx.slice(st, st + L), hh.slice(st, st + L), A1.X, A1.Y));
    dipBg.setAttribute("x", A1.X(st));
    dipBg.setAttribute("width", A1.X(st + L) - A1.X(st));
    band.setAttribute("points", `${pts(fx, ex.q90[k], A2.X, A2.Y)} ${pts([...fx].reverse(), [...ex.q10[k]].reverse(), A2.X, A2.Y)}`);
    med.setAttribute("points", pts(fx, ex.q50[k], A2.X, A2.Y));
    widthTxt.textContent = `band ${width[k].toFixed(1)} °C wide`;
    const back = (C0 - st) / 24;
    cursor.setAttribute("x1", A3.X(back));
    cursor.setAttribute("x2", A3.X(back));
    range.value = k;
    out.textContent = `starts ${back.toFixed(1)} days back`;
  };
  range.oninput = () => { cancelAnimationFrame(anim); render(Number(range.value)); };
  const glide = (to) => {
    cancelAnimationFrame(anim);
    const from = cur, t0 = performance.now(), dur = 1400;
    const tick = (now) => {
      const f = Math.min(1, (now - t0) / dur), e = f < 0.5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2;
      render(Math.round(from + (to - from) * e));
      if (f < 1) anim = requestAnimationFrame(tick);
    };
    anim = requestAnimationFrame(tick);
  };
  const near = (days) => {
    let best = 0;
    ex.starts.forEach((st, k) => { if (Math.abs((C0 - st) / 24 - days) < Math.abs((C0 - ex.starts[best]) / 24 - days)) best = k; });
    return best;
  };
  const steps = [
    { state: 0, when: "Far back", html: `One drop of ${d.size} °C, <b>10 weeks</b> back: the band does not change.` },
    { state: near(28), when: "Closer", html: "Four weeks back: still almost no effect." },
    { state: n - 1, when: "Close to now", html: `Only in the <b>last two weeks</b> does the band widen, most when the drop is a few days back: +${a.change_mean[a.change_mean.length - 1].toFixed(1)} °C on average, wider in ${Math.round(a.widen_share[a.widen_share.length - 1] * 100)} % of the forecasts.`,
      takeaway: "A strange part makes the model unsure only when it is recent." },
  ];
  const draw = (host, ctl) => {
    ctl.append(h("label", { class: "slider" }, `Inserted ${d.size} °C drop`, range, out));
    host.append(svg);
    render(0);
    const upd = (k) => glide(k);
    // scrolling between two steps moves the drop gradually from one step's position to the next
    upd.scrub = (f) => {
      const i = Math.min(Math.floor(f), steps.length - 2), t = f - i;
      cancelAnimationFrame(anim);
      render(Math.round(steps[i].state + t * (steps[i + 1].state - steps[i].state)));
    };
    return upd;
  };
  return scrolly({ id: "ch-position", tall: true, kicker: "Also tested", question: "Does it matter where the strange part sits?", sub: "", steps, draw,
    info: `The inserted drop is not a one-hour step: it copies the average cold front in our data (Experiment 5). The temperature falls by ${d.size} °C within about 5 hours, is still about ${(0.8 * d.size).toFixed(1)} °C lower after a day and ${(0.62 * d.size).toFixed(0)} °C lower after two, then returns to normal over a third day. It is added on top of the real history, so the day-night cycle stays. The last day before the forecast is never changed.` });
}

// =========================================================================================== 5. catching up (Exp 3 §6)
function chapterCatchingUp(d) {
  const T = (x) => at(d.truth.hours, d.truth.mean, x);
  const Sx = (off) => d.starts.find((st) => st.start === off);
  const F = (off, x) => at(Sx(off).hours, Sx(off).q50, x);
  const minT = Math.min(...d.truth.mean), minAt = d.truth.hours[d.truth.mean.indexOf(minT)];
  const W = 1250, H = 330, m = { l: 46, r: 8, t: 30, b: 40 }, gap = 10, nP = d.starts.length;
  const pw = (W - m.l - m.r - gap * (nP - 1)) / nP, x0 = -12, x1 = 35;
  const all = [...d.truth.mean, ...d.starts.flatMap((st) => [...st.q10, ...st.q90])];
  const y0 = Math.floor(Math.min(...all)) - 1, y1 = Math.ceil(Math.max(...all)) + 1;
  const Y = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);
  const svg = frame(W, H, "The average cold front seen from five forecast starts");
  for (let v = Math.ceil(y0 / 2) * 2; v <= y1; v += 2) svg.append(s("line", { class: "gl", x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }), s("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end", text: v ? sgn(v, 0) : "0" }));
  svg.append(s("text", { x: 12, y: (m.t + H - m.b) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${(m.t + H - m.b) / 2})`, class: "axt", text: "°C since the drop started" }));
  const panels = d.starts.map((st, i) => {
    const left = m.l + i * (pw + gap), X = (v) => left + ((v - x0) / (x1 - x0)) * pw;
    const line = (xs, ys) => xs.map((x, k) => (x >= x0 && x <= x1 ? `${X(x)},${Y(ys[k])}` : null)).filter(Boolean).join(" ");
    const g = s("g");
    const bg = s("rect", { class: "panel-bg", x: left, y: m.t, width: pw, height: H - m.t - m.b, rx: 4 });
    const title = s("text", { class: "ptitle", x: left + pw / 2, y: m.t - 10, "text-anchor": "middle", text: `start ${st.start > 0 ? "+" : st.start < 0 ? "−" : ""}${Math.abs(st.start)} h` });
    g.append(bg, s("rect", { class: "known", x: X(x0), y: m.t, width: X(st.start) - X(x0), height: H - m.t - m.b }), s("line", { class: "zero", x1: X(0), x2: X(0), y1: m.t, y2: H - m.b }));
    for (const t of [-12, 0, 12, 24]) g.append(s("text", { x: X(t), y: H - m.b + 15, "text-anchor": "middle", text: t > 0 ? `+${t}` : String(t) }));
    const band = s("polygon", { class: "fc", points: `${line(st.hours, st.q90)} ${line([...st.hours].reverse(), [...st.q10].reverse())}`, fill: C.band, "fill-opacity": 0.22 });
    const med = s("polyline", { class: "fc", points: line(st.hours, st.q50), fill: "none", stroke: C.fc, "stroke-width": 2.4, "stroke-linejoin": "round" });
    const pending = s("text", { class: "pending", x: left + pw * 0.72, y: (m.t + H - m.b) / 2, "text-anchor": "middle", text: "?" });
    g.append(band, s("polyline", { points: line(d.truth.hours, d.truth.mean), fill: "none", stroke: "#fff", "stroke-width": 2.2, "stroke-linejoin": "round" }), med, pending);
    const hit = s("rect", { class: "hit", x: left, y: m.t, width: pw, height: H - m.t - m.b });
    hit.addEventListener("pointermove", (ev) => {
      const r = svg.getBoundingClientRect(), hr = Math.round(x0 + ((((ev.clientX - r.left) / r.width) * W - left) / pw) * (x1 - x0));
      const tv = T(hr), k = st.hours.indexOf(hr);
      let html = `<b>start ${st.start > 0 ? "+" : ""}${st.start} h · hour ${hr > 0 ? "+" : ""}${hr}</b>`;
      if (tv != null) html += `<br><i style="background:#fff"></i>what happened: <b>${sgn(tv)} °C</b>`;
      if (k >= 0 && med.style.opacity !== "0") html += `<br><i style="background:${C.fc}"></i>forecast: <b>${sgn(st.q50[k])} °C</b>`;
      tip.show(html, ev);
    });
    hit.addEventListener("pointerleave", () => tip.hide());
    g.append(hit);
    svg.append(g);
    return { bg, title, band, med, pending, g };
  });
  panels.forEach((p) => svg.append(p.title));
  svg.append(s("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle", class: "axt", text: "hours from the drop start · grey = what the model has already seen" }));
  const update = ({ upto, focus }) => panels.forEach((p, i) => {
    const on = i <= upto;
    p.band.style.opacity = on ? 1 : 0; p.med.style.opacity = on ? 1 : 0; p.pending.style.opacity = on ? 0 : 1;
    p.bg.classList.toggle("active", i === focus); p.title.classList.toggle("active", i === focus);
    p.g.style.opacity = upto >= 0 && i > upto ? 0.55 : 1;
  });
  const steps = [
    { state: { upto: -1, focus: -1 }, html: `${d.n} front passages, aligned at the start of the drop (dotted line). In 6 hours the temperature falls <b>${Math.abs(T(6)).toFixed(1)} °C</b>, and keeps falling.` },
    { state: { upto: 0, focus: 0 }, when: "6 h before", html: "Nothing of the front seen yet: the forecast is <b>a normal evening</b>." },
    { state: { upto: 1, focus: 1 }, when: "At the drop start", html: `Still nothing seen. Six hours later it expects ${sgn(F(0, 6))} °C; reality: <b>${sgn(T(6))} °C</b>.` },
    { state: { upto: 2, focus: 2 }, when: "3 h in", html: "It has seen 3 hours of the fall and moves <b>part of the way</b>." },
    { state: { upto: 3, focus: 3 }, when: "6 h in", html: "With the drop in its history, it <b>adopts the cold level</b>." },
    { state: { upto: 4, focus: 4 }, when: "12 h in", html: `Reality keeps falling to ${sgn(minT)} °C; the forecast stays near ${sgn(F(12, minAt))} °C: it <b>never extends a fall</b> still going on.`,
      takeaway: "Missed before, adopted after, the ongoing fall not extended." },
  ];
  return scrolly({ id: "ch-catch", kicker: "Also tested", question: "Once the model sees the front, does it catch up?",
    sub: `Average of ${d.n} passages; forecasts started from 6 h before to 12 h after the drop start.`, steps,
    draw: (host) => { host.append(legend([["what happened", "#fff"], ["forecast", C.fc], ["forecast band (10–90 %)", C.band, "band"]]), svg); return update; },
    info: "All curves are the change since the drop started, averaged over the passages. Each panel is the same front, forecast from a different moment." });
}

// =========================================================================================== 6. does the cold last (Exp 5)
function chapterLasts(d) {
  const W = 1250, H = 360, b = { l: 64, t: 16, w: 1140, h: 290 };
  const svg = frame(W, H, "Does the model expect the cold to last");
  const all = [...d.truth.mean, ...d.starts.flatMap((st) => st.forecast)];
  const lo = Math.floor(Math.min(...all)) - 1, up = Math.ceil(Math.max(...all)) + 1;
  const { X, Y } = axes(svg, b, { x0: -12, x1: 71, y0: lo, y1: up, xticks: [-12, 0, 12, 24, 36, 48, 60], xfmt: (v) => (v > 0 ? `+${v} h` : v ? `${v} h` : "drop"), yticks: [-6, -4, -2, 0, 2].filter((v) => v > lo && v <= up), yfmt: (v) => (v ? sgn(v, 0) : "usual"), xlabel: "hours from the drop start", ylabel: "°C vs usual" });
  svg.append(s("line", { x1: b.l, x2: b.l + b.w, y1: Y(0), y2: Y(0), stroke: "#8b96a3", "stroke-width": 1.2 }), poly(d.truth.hours, d.truth.mean, X, Y, { stroke: "#fff", "stroke-width": 3 }));
  const SH = { 6: "#2171b5", 12: "#4292c6", 24: "#6baed6", 48: "#9ecae1" };
  const fl = d.starts.map((st) => {
    const g = s("g", {}, poly(st.hours, st.forecast, X, Y, { stroke: SH[st.start], "stroke-width": 2.6 }), s("circle", { cx: X(st.start), cy: Y(st.start_value), r: 5.5, fill: SH[st.start], stroke: "#fff", "stroke-width": 1.2 }),
      s("text", { x: X(st.start) + 2, y: Y(st.start_value) + 20, class: "val", text: `+${st.start} h` }));
    svg.append(g);
    return g;
  });
  const update = ({ show }) => fl.forEach((g, i) => { g.style.opacity = i < show ? 1 : 0; });
  const steps = [
    { state: { show: 0 }, html: "After the drop the air stays <b>colder than usual</b> for days (white)." },
    { state: { show: 2 }, when: "Just after the drop", html: "Forecasts started 6 or 12 h after the drop <b>keep the cold</b>." },
    { state: { show: 4 }, when: "1–2 days later", html: "No return to the usual pattern: once it has seen the cold, it expects it to last.",
      more: "How it adapts this well, instead of returning to the daily pattern of the weeks before, is a question for Phase II.", takeaway: "After the front, the model adapts." },
  ];
  return scrolly({ id: "ch-lasts", kicker: "Also tested", question: "Does the model expect the cold to last?",
    sub: `${d.n} passages; temperature minus the usual value for that place and hour.`, steps,
    draw: (host) => { host.append(legend([["what happened", "#fff"], ["forecasts started +6, +12, +24, +48 h after the drop", "#4292c6"]]), svg); return update; } });
}

// =========================================================================================== 7. is the band honest (Exp 11)
function chapterHonest(d) {
  const W = 1250, H = 250, b = { l: 180, t: 34, w: 1030, h: 180 };
  const svg = frame(W, H, "Below, inside or above the band");
  const X = (p) => b.l + (p / 100) * b.w, rh = b.h / 3;
  for (const p of [0, 25, 50, 75, 100]) svg.append(s("text", { x: X(p), y: b.t + b.h + 18, "text-anchor": "middle", text: `${p} %` }));
  const rows = d.rows.map((r, i) => {
    const y = b.t + i * rh + 8, hh = rh - 16, g = s("g");
    g.append(s("text", { x: b.l - 12, y: y + hh / 2 + 4, "text-anchor": "end", class: "rowlab", text: r.group }));
    let x = 0;
    for (const [k, col] of [["below", "#2166ac"], ["inside", "#d9d9d9"], ["above", "#b2182b"]]) {
      g.append(s("rect", { x: X(x), y, width: X(x + r[k]) - X(x), height: hh, fill: col }));
      if (r[k] >= 6) g.append(s("text", { x: X(x + r[k] / 2), y: y + hh / 2 + 5, "text-anchor": "middle", class: "barval", style: `fill:${k === "inside" ? "#12161b" : "#fff"}`, text: `${Math.round(r[k])} %` }));
      x += r[k];
    }
    svg.append(g);
    return g;
  });
  for (const p of [10, 90]) svg.append(s("line", { x1: X(p), x2: X(p), y1: b.t - 6, y2: b.t + b.h, stroke: "#fff", "stroke-dasharray": "4 4" }));
  svg.append(s("text", { x: X(50), y: b.t - 14, "text-anchor": "middle", class: "val", text: "honest: 10 % below · 80 % inside · 10 % above" }));
  const update = ({ show }) => rows.forEach((g, i) => { g.style.opacity = i < show ? 1 : 0.06; });
  const fr = d.rows[1];
  const steps = [
    { state: { show: 1 }, when: "Normal days", html: "An honest 10–90 % band holds reality <b>80 %</b> of the time. On normal days, it does." },
    { state: { show: 2 }, when: "A front coming", html: `With a front coming, <b>${Math.round(fr.below)} %</b> of the hours are colder than the whole band: confidently wrong, without warning.`, takeaway: "Before a front, the band is far too sure." },
    { state: { show: 3 }, when: "Just after the drop", html: "Once the drop has started, it is nearly honest again." },
  ];
  return scrolly({ id: "ch-honest", kicker: "Also tested", question: "Does the model know when it's unsure?",
    sub: "Share of forecast hours where reality fell below, inside or above the forecast band.", steps,
    draw: (host) => { host.append(legend([["reality colder than the band", "#2166ac"], ["inside the band", "#d9d9d9"], ["reality warmer", "#b2182b"]]), svg); return update; } });
}

// =========================================================================================== what did not help (Exp 2, 4)
function notHelping() {
  const tile = (big, label, more) => {
    const [b, m] = moreToggle(more);
    return h("div", { class: "tile" }, h("div", { class: "tbig" }, big), h("div", { class: "tlab", html: label }), b, m);
  };
  return h("section", { class: "chapter", id: "ch-nothelp" }, h("div", { class: "qnum" }, "Also tested"),
    h("h2", { class: "frame-q" }, "Does more information help?"),
    h("div", { class: "tiles" },
      tile("1.8 °C", "error with <b>2 to 10 weeks</b> of history: more history doesn't help", "1.85 °C with 1 week, about 1.8 °C from 2 to 10 weeks (2,400 forecasts: 50 places × 48 dates)."),
      tile("1.77 °C", "error when we tell it the <b>hour of day</b> or the <b>time of year</b>: unchanged", "Same as temperature alone; 52–53 % of the cases get better, a coin flip."),
      tile("≈ 21 %", "of the drop forecast with <b>pressure, humidity, wind</b> or <b>upwind temperatures</b>: the same as temperature alone", "Six combinations: levels or 3-hour changes of pressure, humidity and wind; temperature changes at points 40–240 km upwind; both; only their unusual part. Even a flag that marks the coming front did not help.")));
}

// =========================================================================================== 8. front explorer (Exp 3)
function frontExplorer(d) {
  const W = 1500, H = 480, mapB = { l: 10, t: 70, w: 760, h: 330 }, pb = { l: 900, t: 84, w: 560, h: 290 };
  const svg = frame(W, H, "Front explorer: drop captured at every point of one cold front");
  const geo = geoBox(d.points.lon, d.points.lat, mapB);
  const pidx = new Map(d.points.id.map((p, i) => [p, i]));
  const t0 = Date.parse("2025-10-01T00:00:00Z"), t1 = Date.parse("2026-10-01T00:00:00Z"), TX = (t) => 30 + ((t - t0) / (t1 - t0)) * 940;
  svg.append(s("line", { x1: 30, x2: 970, y1: 26, y2: 26, stroke: "#3a4450" }));
  ["Oct", "Dec", "Feb", "Apr", "Jun", "Aug"].forEach((mo, k) => svg.append(s("text", { x: TX(Date.UTC(2025, 9 + 2 * k, 1)), y: 52, "text-anchor": "middle", text: mo })));
  const base = s("g");
  d.points.lon.forEach((_, i) => base.append(s("circle", { cx: geo.x(i), cy: geo.y(i), r: 3.2, fill: "#2b333c" })));
  const layer = s("g"), lines = s("g"), hi = s("g"), panelAxes = s("g");
  const title = s("text", { x: pb.l - 40, y: pb.t - 14, class: "title" });
  const note = s("text", { x: mapB.l + 4, y: mapB.t + mapB.h + 24, class: "val" });
  // lines beyond the y-range (1-99 % of the values) are cut at the chart edges instead of running into the timeline
  const clip = s("clipPath", { id: "fx-clip" });
  clip.append(s("rect", { x: pb.l, y: pb.t, width: pb.w, height: pb.h }));
  const defs = s("defs");
  defs.append(clip);
  lines.setAttribute("clip-path", "url(#fx-clip)");
  hi.setAttribute("clip-path", "url(#fx-clip)");
  svg.append(defs, base, layer, panelAxes, lines, hi, title, note);
  colorBar(svg, 330, 452, 180, PLASMA, [[0, "0 %"], [0.5, "25 %"], [1, "50 %+"]], "unusual drop captured");
  svg.append(s("circle", { cx: 40, cy: 456, r: 4, fill: "none", stroke: "#8b96a3" }), s("text", { x: 50, y: 460, class: "val", text: "no clear drop at this point" }));
  const PX = (v) => pb.l + ((v + 6) / 23) * pb.w;
  let Y = null, cur = null;
  const highlight = (k) => {
    hi.replaceChildren();
    if (k == null || !cur) return;
    const i = pidx.get(cur.point[k]);
    hi.append(poly(d.hours, cur.truth[k], PX, Y, { stroke: "#fff", "stroke-width": 2.2 }), poly(d.hours, cur.forecast[k], PX, Y, { stroke: C.fc, "stroke-width": 2.2, "stroke-dasharray": "5 3" }),
      s("circle", { cx: geo.x(i), cy: geo.y(i), r: 7.5, fill: "none", stroke: "#fff", "stroke-width": 2 }));
  };
  const marks = d.fronts.map((f, i) => {
    const c = s("circle", { cx: TX(Date.parse(isoZ(f.front))), cy: 26, r: 4 + Math.sqrt(f.n) / 4, fill: f.doubtful ? "#12161b" : PLASMA(Math.min(f.captured_mean, 50) / 50), stroke: f.doubtful ? "#8b96a3" : "#12161b", "stroke-width": f.doubtful ? 1.5 : 2, class: "fmark" });
    c.addEventListener("click", () => pick(i));
    c.addEventListener("pointermove", (ev) => tip.show(`<b>${f.day}</b><br>${f.n} points · ${Math.round(f.captured_mean)} % captured on average${f.doubtful ? "<br>doubtful front (almost no drop)" : ""}<br><i>click to show</i>`, ev));
    c.addEventListener("pointerleave", () => tip.hide());
    svg.append(c);
    return c;
  });
  function pick(i) {
    const f = d.fronts[i];
    cur = f;
    marks.forEach((c, k) => c.classList.toggle("on", k === i));
    layer.replaceChildren(); lines.replaceChildren(); panelAxes.replaceChildren(); hi.replaceChildren();
    f.point.forEach((p, k) => {
      const j = pidx.get(p), cap = f.captured[k];
      const c = s("circle", { cx: geo.x(j), cy: geo.y(j), r: 4.4, fill: cap == null ? "none" : PLASMA(Math.min(cap, 50) / 50), stroke: cap == null ? "#8b96a3" : "none", "stroke-width": 1.2 });
      c.addEventListener("pointermove", (ev) => { highlight(k); tip.show(`<b>point ${p}</b><br>${cap == null ? "no clear unusual drop" : `unusual drop ${f.unusual_drop[k].toFixed(1)} °C, ${Math.round(cap)} % captured`}`, ev); });
      c.addEventListener("pointerleave", () => { highlight(null); tip.hide(); });
      layer.append(c);
    });
    const allv = [...f.truth.flat(), ...f.forecast.flat()].filter((v) => v != null).sort((a, b) => a - b);
    const lo = Math.floor(allv[Math.floor(allv.length * 0.01)]), up = Math.ceil(allv[Math.floor(allv.length * 0.99)]);
    const A = axes(panelAxes, pb, { x0: -6, x1: 17, y0: lo, y1: up, xticks: [-6, 0, 6, 12], xfmt: (v) => (v > 0 ? `+${v} h` : v ? `${v} h` : "drop"), yticks: [-12, -8, -4, 0, 4, 8].filter((v) => v >= lo && v <= up), yfmt: (v) => (v ? sgn(v, 0) : "0"), ylabel: "°C since the forecast start" });
    Y = A.Y;
    panelAxes.append(s("rect", { x: PX(0), y: pb.t, width: PX(6) - PX(0), height: pb.h, fill: C.band, "fill-opacity": 0.08 }));
    const mean = (arr) => d.hours.map((_, j) => { const v = arr.map((r) => r[j]).filter((x) => x != null); return v.reduce((a, b) => a + b, 0) / v.length; });
    f.truth.forEach((r) => lines.append(poly(d.hours, r, PX, Y, { stroke: "#8b96a3", "stroke-width": 0.8, "stroke-opacity": 0.16 })));
    lines.append(poly(d.hours, mean(f.truth), PX, Y, { stroke: "#fff", "stroke-width": 3 }), poly(d.hours, mean(f.forecast), PX, Y, { stroke: C.fc, "stroke-width": 3 }));
    title.textContent = `${f.day} · ${f.n} points · ${Math.round(f.captured_mean)} % of the unusual drop captured`;
    note.textContent = f.doubtful ? "Doubtful front: almost no drop at the labelled hour." : "";
  }
  const hit = s("rect", { class: "hit", x: pb.l, y: pb.t, width: pb.w, height: pb.h });
  hit.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect(), px = ((ev.clientX - r.left) / r.width) * W, py = ((ev.clientY - r.top) / r.height) * H;
    const j = Math.max(0, Math.min(d.hours.length - 1, Math.round(((px - pb.l) / pb.w) * 23)));
    let best = 0, bd = 1e9;
    cur.truth.forEach((row, k) => { if (row[j] == null) return; const dy = Math.abs(Y(row[j]) - py); if (dy < bd) { bd = dy; best = k; } });
    highlight(best);
    const cap = cur.captured[best];
    tip.show(`<b>point ${cur.point[best]}</b> (ringed on the map)<br>${cap == null ? "no clear unusual drop" : `${Math.round(cap)} % captured`}`, ev);
  });
  hit.addEventListener("pointerleave", () => { highlight(null); tip.hide(); });
  svg.append(hit);
  svg.append(s("text", { x: pb.l + pb.w, y: pb.t + pb.h + 34, "text-anchor": "end", class: "val", text: "grey: each point · white: mean · blue: mean forecast · shaded: drop window" }));
  const [ib, ibox] = infoToggle("Click a front on the timeline (size = number of points, colour = drop captured, hollow = doubtful front). <b>Map:</b> how much of the <b>unusual</b> drop (beyond normal evening cooling) the forecast showed, at each point, started 6 h before that point's drop. <b>Right:</b> change since the forecast start at every point. Hover a point or a line to link them.");
  pick(0);
  return h("section", { class: "chapter explorer", id: "ch-explore" }, h("div", { class: "qnum" }, "Explore it yourself"),
    h("div", { class: "viz" }, h("div", { class: "qhead" }, h("h2", { class: "frame-q" }, "Does the model miss every cold front, or only some? Where in Austria does it miss the most?"), ib),
      h("p", { class: "frame-sub" }, `${d.fronts.length} cold fronts, ${d.fronts.reduce((a, f) => a + f.n, 0).toLocaleString("en")} point passages. Click a front.`), ibox,
      svg));
}

// =========================================================================================== overview
// sketch of the setup with one real forecast from Sandro's runs (pages.js: loadRuns, runSeries)
async function overview() {
  if (!RUNS) await loadRuns();
  const geo = await getJson("data/meta.json");  // lon/lat of the 378 points (same order as the runs)
  const m = RUNS.meta, run = m.runs.findIndex((r) => r.label.includes("18 May 2026")), pt = m.places.Linz, v = runSeries(run, pt);
  const W = 1250, H = 300, mapB = { l: 0, t: 60, w: 190, h: 130 }, inB = { l: 262, t: 44, w: 330, h: 196 }, outB = { l: 880, t: 44, w: 230, h: 196 };
  const all = [...v.ctx, ...v.truth, ...v.q10, ...v.q90];
  const y0 = Math.floor(Math.min(...all)) - 1, y1 = Math.ceil(Math.max(...all)) + 1;
  const yticks = [];
  for (let t = Math.ceil(y0 / 4) * 4; t <= y1; t += 4) yticks.push(t);
  const svg = frame(W, H, "Sketch: the hourly temperature history goes into TiRex-2, which forecasts the next 24 hours with a 10 to 90 % band");
  const ctxX = Array.from({ length: m.ctx }, (_, i) => i - m.ctx + 1), hx = Array.from({ length: m.h }, (_, i) => i + 1);
  const A = axes(svg, inB, { x0: -m.ctx + 1, x1: 0, y0, y1, xticks: [-35, -24, -12, 0], yticks, xfmt: (x) => (x === -35 ? "−36" : x === 0 ? "0" : `−${-x}`), xlabel: "hours before the start (last 36 of 672)", ylabel: "temperature (°C)" });
  svg.append(poly(ctxX, v.ctx, A.X, A.Y, { stroke: C.grey, "stroke-width": 2.2 }),
    s("text", { x: inB.l + inB.w / 2, y: 24, "text-anchor": "middle", class: "title", text: "Input: 4 weeks of hourly temperature" }));
  const B = axes(svg, outB, { x0: 1, x1: m.h, y0, y1, xticks: [1, 6, 12, 18, 24], yticks, xlabel: "hours after the start" });
  svg.append(area(hx, v.q10, v.q90, B.X, B.Y, { fill: C.band, "fill-opacity": 0.3 }),
    poly(hx, v.truth, B.X, B.Y, { stroke: "#e7ebf0", "stroke-width": 1.6, "stroke-dasharray": "5 4" }),
    poly(hx, v.q50, B.X, B.Y, { stroke: C.fc, "stroke-width": 2.6 }),
    s("text", { x: outB.l + outB.w / 2, y: 24, "text-anchor": "middle", class: "title", text: "Output: the next 24 hours" }));
  // labels at the line ends, pushed apart so they don't overlap
  const L = m.h - 1, labs = [["10–90 % band", v.q90[L], C.band], ["forecast median (q50)", v.q50[L], C.fc], ["measured (truth)", v.truth[L], "#e7ebf0"]]
    .map(([t, y, c]) => ({ t, y: B.Y(y), c })).sort((a, b) => a.y - b.y);
  labs.forEach((l, i) => { if (i) l.y = Math.max(l.y, labs[i - 1].y + 17); });
  for (const l of labs) svg.append(s("text", { x: outB.l + outB.w + 10, y: l.y + 4, style: `fill:${l.c};font-size:13px;font-weight:600`, text: l.t }));
  // the model in the middle, with arrows
  const mx = 638, mw = 152, my = inB.t + inB.h / 2;
  svg.append(s("defs", {}, s("marker", { id: "ovarrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto" },
    s("path", { d: "M0,0 L10,5 L0,10 z", fill: "#9aa6b3" }))));
  svg.append(s("line", { x1: inB.l + inB.w + 12, x2: mx - 8, y1: my, y2: my, stroke: "#9aa6b3", "stroke-width": 2, "marker-end": "url(#ovarrow)" }),
    s("line", { x1: mx + mw + 8, x2: outB.l - 42, y1: my, y2: my, stroke: "#9aa6b3", "stroke-width": 2, "marker-end": "url(#ovarrow)" }),
    s("rect", { x: mx, y: my - 52, width: mw, height: 116, rx: 12, fill: "#1d242c", stroke: C.fc, "stroke-width": 1.5 }),
    s("image", { href: "tirex.svg", x: mx + 12, y: my - 42, width: 30, height: 36 }),  // TiRex logo (NX-AI, github.com/NX-AI/tirex-2)
    s("text", { x: mx + mw / 2 + 17, y: my - 14, "text-anchor": "middle", style: "font-size:22px;font-weight:700;fill:#e7ebf0", text: "TiRex-2" }),
    s("text", { x: mx + mw / 2, y: my + 14, "text-anchor": "middle", class: "axt", text: "zero-shot" }),
    s("text", { x: mx + mw / 2, y: my + 32, "text-anchor": "middle", text: "(not trained" }),
    s("text", { x: mx + mw / 2, y: my + 46, "text-anchor": "middle", text: "on this data)" }));
  // all points of Austria; the example point highlighted and linked to the input chart
  const G = geoBox(geo.lon, geo.lat, mapB);
  svg.append(s("text", { x: mapB.l + mapB.w / 2, y: 24, "text-anchor": "middle", class: "title", text: `All ${geo.lon.length} points` }));
  geo.lon.forEach((_, i) => { if (i !== pt) svg.append(s("circle", { cx: G.x(i), cy: G.y(i), r: 2, fill: "#5b6672" })); });
  svg.append(s("line", { x1: G.x(pt) + 6, y1: G.y(pt), x2: inB.l - 58, y2: my, stroke: C.grey, "stroke-width": 1.2, "stroke-dasharray": "3 3" }),
    s("circle", { cx: G.x(pt), cy: G.y(pt), r: 5, fill: "#e7ebf0" }),
    s("text", { x: G.x(pt), y: G.y(pt) - 9, "text-anchor": "middle", style: "fill:#e7ebf0;font-size:12px", text: "Linz" }),
    s("text", { x: mapB.l + mapB.w / 2, y: mapB.t + mapB.h + 30, "text-anchor": "middle", text: "one forecast per point," }),
    s("text", { x: mapB.l + mapB.w / 2, y: mapB.t + mapB.h + 46, "text-anchor": "middle", text: `repeated for all ${geo.lon.length}` }));
  return h("section", { class: "chapter overview", id: "overview" }, h("div", { class: "qnum" }, "Overview"),
    h("h1", { class: "q" }, "What does TiRex-2 react to, and when does it fail?"),
    h("p", { class: "ovdata" }, "Data: hourly weather analysis (INCA, GeoSphere Austria) at 378 points on a 15 km grid across Austria, October 2025 to September 2026."),
    h("div", { class: "ovfig" }, svg));
}

// ------------------------------------------------------------------------------------------- page
// story.html: overview, the main chapters, then Sandro's limits and errors, then a link to the second page.
// also-tested.html (data-page="more"): the other experiments, Sandro's other questions, the explorer.
const MAIN_PARTS = [[null, overview], ["where_it_looks", chapterLooks], ["fixed_sundays", chapterSundays], ["weird_history", chapterWeird]];
const MORE_PARTS = [[null, notHelping], ["where_it_looks", chapterLooksFull], ["fixed_sundays", chapterSundaySwitch], ["drop_position", chapterPosition],
  ["catching_up", chapterCatchingUp], ["cold_lasts", chapterLasts], ["band_honesty", chapterHonest], ["time_curve", chapterWeather]];
// the story page shows only what the talk uses of Sandro's sections; every other chart is on the second page
const MAIN_QUESTIONS = [4, 5], MORE_QUESTIONS = [1, 2, 3, 4, 5];
const TALK_CARDS = { 4: ["improvement"], 5: ["around-front"] };

const pageLink = (href, label, sub) => h("a", { class: "pagelink", href }, h("span", { class: "pl-label" }, label), sub ? h("span", { class: "pl-sub" }, sub) : null);

async function addParts(host, parts, only) {
  for (const [file, make] of parts) {
    if (only && !make.name.toLowerCase().includes(only)) continue;
    try {
      host.append(await make(file ? await loadJson(file) : null));
    } catch (err) {
      host.append(h("p", { class: "answer" }, `Could not load ${file || "a section"}: ${err.message}`));
      console.error(err);
    }
  }
}

async function addQuestions(main, nums, pick) {
  const questions = h("div", { id: "questions" });
  main.append(questions);
  try { await renderQuestions(questions, nums, pick); } catch (err) {
    questions.append(h("p", { class: "answer" }, `Could not load the question data: ${err.message}`));
    console.error(err);
  }
}

// ---- the three sideways sections of the story page
function ideaPanel() {
  const card = (title, ...body) => h("div", { class: "card2" }, h("h3", {}, title), ...body);
  return h("section", { class: "hs-idea", id: "idea" }, h("div", { class: "cols" },
    h("h1", {}, "What are we testing, and how?"),
    card("The model", h("p", {}, "TiRex-2 is a time-series forecasting model from JKU. It is used zero-shot: it was never trained on our data."),
      h("p", {}, "It gets the past temperature of one point and forecasts the next 24 hours, with a band from the 10th to the 90th percentile.")),
    card("The data", h("p", {}, "Hourly weather analysis (INCA, GeoSphere Austria), October 2025 to September 2026, at 378 points on a 15 km grid."),
      h("p", {}, "Events are labelled: cold fronts (found with a rule from the literature, 16 fronts), thunderstorms and cold drops.")),
    card("Our idea", h("p", {}, "Treat the model as a black box and ask where it fails."),
      h("ul", {}, h("li", {}, "Section 2: change what the model sees (which hours, repeated patterns, strange history) and watch what it does."),
        h("li", {}, "Section 3: 336 forecasts on all points, compared with a simple baseline, and how they go wrong at cold fronts.")))));
}

function hsection(id, number, title, sub, slides) {
  const track = h("div", { class: "hs-track" }, slides);
  const prog = h("i");
  const outer = h("section", { class: "hs", id }, h("div", { class: "hs-pin" },
    h("div", { class: "hs-bar" }, h("b", {}, `${number} · ${title}`), h("span", { class: "hs-sub" }, sub), h("span", { class: "hs-hint" }, "scroll down to move on →"), h("div", { class: "hs-prog" }, prog)),
    h("div", { class: "hs-view" }, track)));
  const view = outer.querySelector(".hs-view");
  outer._layout = () => {
    outer.style.setProperty("--vw", `${view.clientWidth}px`);
    const dx = Math.max(0, track.scrollWidth - view.clientWidth);
    outer.style.height = `${outer.querySelector(".hs-pin").offsetHeight + dx}px`;
  };
  outer._update = () => {
    const dx = Math.max(0, track.scrollWidth - view.clientWidth), navH = document.getElementById("nav")?.offsetHeight || 0;
    const room = outer.offsetHeight - outer.querySelector(".hs-pin").offsetHeight;
    const p = room > 0 ? Math.min(1, Math.max(0, (navH - outer.getBoundingClientRect().top) / room)) : 0;
    view.scrollLeft = p * dx;
    prog.style.width = `${p * 100}%`;
  };
  return outer;
}

async function startStoryHs(main) {
  const story = h("div", { id: "story" });
  main.append(story);
  const tmp = h("div");
  await addParts(tmp, [[null, overview], ["where_it_looks", chapterLooks], ["fixed_sundays", chapterSundays], ["weird_history", chapterWeird]]);
  const [ov, looks, sundays, weird] = [...tmp.children];
  const qhost = h("div");
  try { await renderQuestions(qhost, MAIN_QUESTIONS, { keep: TALK_CARDS }); } catch (err) { console.error(err); }
  const cards = [...qhost.querySelectorAll("section.viz")].map((c) => h("div", { class: "hs-slide" }, c));
  const explore = byId("explore");
  const end = h("div", { class: "hs-end" }, pageLink("also-tested.html", "Also tested →", "More experiments, our other charts and an explorer of all cold fronts"));
  const secs = [
    hsection("s-project", "1", "The project", "the model, the data and our idea", [explore, ov, ideaPanel()].filter(Boolean)),
    hsection("s-carlos", "2", "Carlos's experiments", "what TiRex-2 reacts to", [looks, sundays, weird].filter(Boolean)),
    hsection("s-sandro", "3", "Sandro's experiments", "limits and errors of 336 forecasts", [...cards, end]),
  ];
  story.append(...secs);
  const update = () => secs.forEach((s) => s._update());
  const layout = () => { secs.forEach((s) => s._layout()); update(); };
  addEventListener("resize", layout);
  addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
  new ResizeObserver(layout).observe(story);
  layout();
  setTimeout(() => { layout(); if (typeof map !== "undefined" && map?.resize) map.resize(); }, 600);
}

async function startStory() {
  const more = document.body.dataset.page === "more";
  const main = h("main", { id: "main", style: "max-width:none" });
  document.body.append(main);
  byId("tostory")?.addEventListener("click", () => byId("story").scrollIntoView({ behavior: "smooth" }));
  const story = h("section", { id: "story" });
  if (more) story.append(h("div", { class: "part-head" }, pageLink("story.html#story", "← Back to the story"), h("div", { class: "qnum" }, "Also tested"),
    h("h1", { class: "q" }, "More experiments"),
    h("p", {}, "Further tests of how TiRex-2 reads its history and how it handles cold fronts, Sandro's other questions, and an explorer of all cold fronts.")));
  main.append(story);
  // ?only=<part of a chapter function name> shows just that chapter (for screenshots while building)
  const only = new URLSearchParams(location.search).get("only");
  if (only) {
    byId("explore")?.style.setProperty("display", "none");
    return addParts(story, [...MAIN_PARTS, ...MORE_PARTS, ["front_explorer", frontExplorer]], only);
  }
  if (more) {
    await addParts(story, MORE_PARTS);
    await addQuestions(main, MORE_QUESTIONS, { drop: TALK_CARDS });
    await addParts(main, [["front_explorer", frontExplorer]]);
    main.append(h("div", { class: "pagelink-row" }, pageLink("story.html#story", "← Back to the story")));
    return;
  }
  if (HS) { main.removeChild(story); return startStoryHs(main); }
  await addParts(story, MAIN_PARTS);
  await addQuestions(main, MAIN_QUESTIONS, { keep: TALK_CARDS });
  main.append(h("div", { class: "pagelink-row" }, pageLink("also-tested.html", "Also tested →", "More experiments and an explorer of all cold fronts")));
}

startStory();
