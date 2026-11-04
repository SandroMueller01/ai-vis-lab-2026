"use strict";
// Chart components (SVG, no libraries): line chart with band, horizontal bars, heatmap, point map and a colour scale bar.
// Every chart puts a table view under itself and shows values on hover.

function niceTicks(lo, hi, n = 5) {
  const span = hi - lo || 1, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((v) => v >= step0);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

function legend(items) {
  return h("div", { class: "legend" }, items.map(([label, color, kind]) =>
    h("span", {}, h("i", { class: kind === "band" ? "sw" : "", style: `background:${color}` }), label)));
}

// cfg: series [{name, color, xs, ys, width, dash}], band {xs, lo, hi, color, name}, xlim, ylim, xticks, xlabel, ylabel,
//      yfmt, xfmt, refs [{y, label}], vmarks [{x, label, color}], height, aria
function lineChart(host, cfg) {
  const W = cfg.width || 820, H = cfg.height || 300, m = { l: 54, r: 18, t: 16, b: 42 };
  const ytick = cfg.ytickfmt || ((v) => String(+v.toFixed(2)));
  const yfmt = cfg.yfmt || ((v) => fmt(v, 1)), xfmt = cfg.xfmt || ((v) => String(v));
  const xs = [], ys = [];
  for (const se of cfg.series) { xs.push(...se.xs); ys.push(...se.ys.filter(Number.isFinite)); }
  if (cfg.band) { xs.push(...cfg.band.xs); ys.push(...cfg.band.lo, ...cfg.band.hi); }
  for (const r of cfg.refs || []) ys.push(r.y);
  const [x0, x1] = cfg.xlim || [Math.min(...xs), Math.max(...xs)];
  let [y0, y1] = cfg.ylim || [Math.min(...ys), Math.max(...ys)];
  if (!cfg.ylim) { const pad = (y1 - y0) * 0.08 || 1; y0 -= pad; y1 += pad; }
  const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
  const Y = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);

  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": cfg.aria || cfg.ylabel || "chart" });
  for (const v of niceTicks(y0, y1, 5)) {
    svg.append(s("line", { class: "gl", x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }), s("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end", text: ytick(v) }));
  }
  svg.append(s("line", { class: "axis", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  for (const v of cfg.xticks || niceTicks(x0, x1, 6)) {
    svg.append(s("line", { class: "gl", x1: X(v), x2: X(v), y1: m.t, y2: H - m.b }), s("text", { x: X(v), y: H - m.b + 16, "text-anchor": "middle", text: (cfg.xtickfmt || String)(v) }));
  }
  if (cfg.xlabel) svg.append(s("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle", text: cfg.xlabel }));
  if (cfg.ylabel) svg.append(s("text", { x: 12, y: (m.t + H - m.b) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${(m.t + H - m.b) / 2})`, text: cfg.ylabel }));
  if (cfg.band) {
    const b = cfg.band, up = b.xs.map((x, i) => `${X(x)},${Y(b.hi[i])}`), down = b.xs.map((x, i) => `${X(x)},${Y(b.lo[i])}`).reverse();
    svg.append(s("polygon", { points: [...up, ...down].join(" "), fill: b.color || COL.blue, "fill-opacity": 0.25 }));
  }
  for (const r of cfg.refs || []) {
    svg.append(s("line", { class: "ref", x1: m.l, x2: W - m.r, y1: Y(r.y), y2: Y(r.y) }),
      s("text", { class: "ref-label", x: W - m.r, y: Y(r.y) - 5, "text-anchor": "end", text: r.label }));
  }
  for (const v of cfg.vmarks || []) {
    svg.append(s("line", { x1: X(v.x), x2: X(v.x), y1: m.t, y2: H - m.b, stroke: v.color || COL.orange, "stroke-width": 1.4 }),
      s("text", { x: X(v.x) + 4, y: m.t + 10, fill: v.color || COL.orange, style: `fill:${v.color || COL.orange}`, text: v.label }));
  }
  for (const se of cfg.series) {
    const pts = se.xs.map((x, i) => (Number.isFinite(se.ys[i]) ? `${X(x)},${Y(se.ys[i])}` : null)).filter(Boolean);
    svg.append(s("polyline", { points: pts.join(" "), fill: "none", stroke: se.color, "stroke-width": se.width || 2.2, "stroke-dasharray": se.dash, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    se.map = new Map(se.xs.map((x, i) => [x, se.ys[i]]));
  }
  const grid = [...new Set(xs)].sort((p, q) => p - q);
  const bandAt = cfg.band ? new Map(cfg.band.xs.map((x, i) => [x, [cfg.band.lo[i], cfg.band.hi[i]]])) : null;
  const cross = s("line", { y1: m.t, y2: H - m.b, stroke: COL.sec, "stroke-width": 1, visibility: "hidden" });
  const dots = cfg.series.map((se) => s("circle", { r: 4, fill: se.color, stroke: "#12161b", "stroke-width": 2, visibility: "hidden" }));
  const hit = s("rect", { class: "hit", x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b });
  svg.append(cross, ...dots, hit);
  hit.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect(), px = ((ev.clientX - r.left) / r.width) * W;
    const xv = x0 + ((px - m.l) / (W - m.l - m.r)) * (x1 - x0);
    const x = grid.reduce((best, g) => (Math.abs(g - xv) < Math.abs(best - xv) ? g : best), grid[0]);
    cross.setAttribute("x1", X(x)); cross.setAttribute("x2", X(x)); cross.setAttribute("visibility", "visible");
    let html = `<b>${xfmt(x)}</b>`;
    cfg.series.forEach((se, i) => {
      const v = se.map.get(x);
      if (v == null || !Number.isFinite(v)) { dots[i].setAttribute("visibility", "hidden"); return; }
      dots[i].setAttribute("cx", X(x)); dots[i].setAttribute("cy", Y(v)); dots[i].setAttribute("visibility", "visible");
      html += `<br><i style="background:${se.color}"></i>${se.name}: <b>${yfmt(v)}</b>`;
    });
    if (bandAt && bandAt.has(x)) html += `<br><i style="background:${cfg.band.color || COL.blue};opacity:.5"></i>${cfg.band.name}: ${yfmt(bandAt.get(x)[0])} to ${yfmt(bandAt.get(x)[1])}`;
    tip.show(html, ev);
  });
  hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); dots.forEach((d) => d.setAttribute("visibility", "hidden")); tip.hide(); });

  host.replaceChildren();
  const items = cfg.series.filter((se) => se.name).map((se) => [se.name, se.color]);
  if (cfg.band && cfg.band.name) items.push([cfg.band.name, cfg.band.color || COL.blue, "band"]);
  if (items.length > 1 || cfg.forceLegend) host.append(legend(items));
  host.append(svg);
  const headers = [cfg.xlabel || "x", ...cfg.series.map((se) => se.name), ...(cfg.band ? [`${cfg.band.name} (low)`, `${cfg.band.name} (high)`] : [])];
  const rows = grid.map((x) => [xfmt(x), ...cfg.series.map((se) => (se.map.has(x) && Number.isFinite(se.map.get(x)) ? yfmt(se.map.get(x)) : "")),
    ...(bandAt ? (bandAt.has(x) ? bandAt.get(x).map(yfmt) : ["", ""]) : [])]);
  tableView(host, { headers, rows });
}

// cfg: rows [{label, group, value, n, tip}], max, unit, ref {value, label}, color, valueLabel, labelWidth
function barChart(host, cfg) {
  const W = 720, lw = cfg.labelWidth || 270, rightPad = 54, top = 14, rowH = 26, grpH = 24;
  const x0 = lw + 12, x1 = W - rightPad, max = cfg.max, X = (v) => x0 + (v / max) * (x1 - x0);
  let y = top;
  const placed = cfg.rows.map((r, i) => {
    const newGroup = r.group && (i === 0 || cfg.rows[i - 1].group !== r.group);
    if (newGroup) y += i === 0 ? grpH - 8 : grpH;
    const out = { ...r, y, newGroup };
    y += rowH;
    return out;
  });
  const H = y + 30;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": cfg.aria || cfg.valueLabel });
  for (const v of niceTicks(0, max, 5)) {
    svg.append(s("line", { class: "gl", x1: X(v), x2: X(v), y1: top, y2: H - 28 }), s("text", { x: X(v), y: H - 12, "text-anchor": "middle", text: `${v}${cfg.unit || ""}` }));
  }
  const fv = cfg.fmt || ((v) => `${Math.round(v)}`);
  for (const p of placed) {
    if (p.newGroup) svg.append(s("text", { class: "grp", x: lw, y: p.y - 6, "text-anchor": "end", text: p.group.toUpperCase() }));
    svg.append(s("text", { class: "rowlab", x: lw, y: p.y + 14, "text-anchor": "end", text: p.label }));
    svg.append(s("rect", { x: x0, y: p.y + 2, width: Math.max(1, X(p.value) - x0), height: 15, rx: 2, fill: cfg.color || COL.blue }));
    svg.append(s("text", { class: "val", x: X(p.value) + 6, y: p.y + 14, text: fv(p.value) }));
    const hit = s("rect", { class: "hit", x: 0, y: p.y - 2, width: W, height: rowH, style: "cursor:default" });
    hit.addEventListener("pointermove", (ev) => tip.show(p.tip || `<b>${p.label}</b><br>${cfg.valueLabel}: <b>${fv(p.value)}${cfg.unit || ""}</b>${p.n ? `<br>${p.n.toLocaleString("en-GB")} cases` : ""}`, ev));
    hit.addEventListener("pointerleave", () => tip.hide());
    svg.append(hit);
  }
  if (cfg.ref) {
    svg.append(s("line", { x1: X(cfg.ref.value), x2: X(cfg.ref.value), y1: top, y2: H - 28, stroke: COL.orange, "stroke-width": 1.5 }),
      s("text", { x: X(cfg.ref.value) - 4, y: H - 32, "text-anchor": "end", style: `fill:${COL.orange}`, text: cfg.ref.label }));
  }
  host.replaceChildren(svg);
  tableView(host, {
    headers: ["Group", "Row", cfg.valueLabel, ...(cfg.rows.some((r) => r.n) ? ["Cases"] : [])],
    rows: cfg.rows.map((r) => [r.group || "", r.label, `${fv(r.value)}${cfg.unit || ""}`, ...(cfg.rows.some((q) => q.n) ? [r.n ? r.n.toLocaleString("en-GB") : ""] : [])]),
  });
}

// cfg: cols, rows (labels), z [row][col] (null = no value), color(v), colTickEvery, rowTickEvery, xlabel, ylabel, flipY, tip(ri, ci), height
function heatmap(host, cfg) {
  const W = 640, H = cfg.height || 320, m = { l: 62, r: 10, t: 10, b: 44 };
  const nc = cfg.cols.length, nr = cfg.rows.length, cw = (W - m.l - m.r) / nc, ch = (H - m.t - m.b) / nr;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": cfg.aria || cfg.ylabel });
  const yAt = (ri) => m.t + (cfg.flipY ? nr - 1 - ri : ri) * ch;
  for (let ri = 0; ri < nr; ri++) {
    for (let ci = 0; ci < nc; ci++) {
      const v = cfg.z[ri][ci];
      const rect = s("rect", { x: m.l + ci * cw, y: yAt(ri), width: cw + 0.6, height: ch + 0.6, fill: v == null ? "#1d242c" : cfg.color(v), "shape-rendering": "crispEdges" });
      rect.addEventListener("pointermove", (ev) => tip.show(cfg.tip(ri, ci), ev));
      rect.addEventListener("pointerleave", () => tip.hide());
      svg.append(rect);
    }
  }
  for (let ri = 0; ri < nr; ri += cfg.rowTickEvery || 1) svg.append(s("text", { x: m.l - 8, y: yAt(ri) + ch / 2 + 4, "text-anchor": "end", text: cfg.rows[ri] }));
  for (let ci = 0; ci < nc; ci += cfg.colTickEvery || 1) svg.append(s("text", { x: m.l + ci * cw + cw / 2, y: H - m.b + 16, "text-anchor": "middle", text: cfg.cols[ci] }));
  if (cfg.xlabel) svg.append(s("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle", text: cfg.xlabel }));
  if (cfg.ylabel) svg.append(s("text", { x: 12, y: (m.t + H - m.b) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${(m.t + H - m.b) / 2})`, text: cfg.ylabel }));
  host.replaceChildren(svg);
  tableView(host, { headers: [cfg.ylabel || "", ...cfg.cols.map(String)], rows: cfg.rows.map((r, ri) => [r, ...cfg.z[ri].map((v) => (v == null ? "" : cfg.tableFmt ? cfg.tableFmt(v) : fmt(v, 2)))]) });
}

// colour scale bar: stops (hex list), min, max, label
function scaleBar({ stops, min, max, label, mid }) {
  return h("div", { class: "scale" }, h("span", {}, `${min}`), h("div", { class: "bar", style: `background:${cssGradient(stops)}` }),
    h("span", {}, `${max}`), mid != null ? h("span", {}, `(middle: ${mid})`) : null, h("span", {}, label));
}

// points on a map without a base map. cfg: lon, lat, fill(i), tip(i), onClick(i), arrow {deg, text}, height
function scatterMap(host, cfg) {
  const W = 640, pad = 8, kx = Math.cos((47.6 * Math.PI) / 180), lon0 = 9.3, lat1 = 49.4;
  const scale = (W - 2 * pad) / ((17.3 - lon0) * kx), H = Math.round((49.4 - 46.0) * scale + 2 * pad);
  const px = (lo) => pad + (lo - lon0) * kx * scale, py = (la) => pad + (lat1 - la) * scale;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": cfg.aria || "map of the points" });
  const r = 0.5 * 0.2 * kx * scale * 0.98;
  const dots = cfg.lon.map((lo, i) => {
    const c = s("circle", { cx: px(lo), cy: py(cfg.lat[i]), r, fill: cfg.fill(i), style: cfg.onClick ? "cursor:pointer" : "" });
    c.addEventListener("pointermove", (ev) => tip.show(cfg.tip(i), ev));
    c.addEventListener("pointerleave", () => tip.hide());
    if (cfg.onClick) c.addEventListener("click", () => cfg.onClick(i));
    svg.append(c);
    return c;
  });
  const ring = s("circle", { r: r + 2.5, fill: "none", stroke: "#ffffff", "stroke-width": 2, visibility: "hidden", "pointer-events": "none" });
  svg.append(ring);
  if (cfg.arrow) {
    const b = (cfg.arrow.deg * Math.PI) / 180, x = pad + 20, y = pad + 28, len = 54;
    svg.append(s("defs", {}, s("marker", { id: "ah", viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" }, s("path", { d: "M0,0 L10,5 L0,10 z", fill: COL.text }))),
      s("line", { x1: x, y1: y, x2: x + Math.sin(b) * len, y2: y - Math.cos(b) * len, stroke: COL.text, "stroke-width": 2, "marker-end": "url(#ah)" }),
      s("text", { x: x + 8, y: y - 12, text: cfg.arrow.text }));
  }
  host.replaceChildren(svg);
  return {
    recolor() { dots.forEach((c, i) => c.setAttribute("fill", cfg.fill(i))); },
    select(i) {
      if (i == null) { ring.setAttribute("visibility", "hidden"); return; }
      ring.setAttribute("cx", dots[i].getAttribute("cx")); ring.setAttribute("cy", dots[i].getAttribute("cy")); ring.setAttribute("visibility", "visible");
    },
  };
}
