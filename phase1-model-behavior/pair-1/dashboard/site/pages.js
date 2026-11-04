"use strict";
// The five question pages. Every visualisation names the questions it answers (chips under its title).

let R = null, RUNS = null; // results.json and the forecast runs
const f0 = (x) => Math.round(x);
const f1 = (x) => Number(x).toFixed(1);

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function loadRuns() {
  const [meta, buf] = await Promise.all([getJson("data/forecast_runs.json"), fetch("data/forecast_runs.bin").then((r) => r.arrayBuffer())]);
  RUNS = { meta, data: new Int16Array(buf) };
}

// values of one run at one point: 36 h before the start, 24 h measured, quantiles q10, q50, q90
function runSeries(run, pt) {
  const m = RUNS.meta, base = (run * m.n + pt) * m.stride;
  const take = (o, len) => Array.from(RUNS.data.subarray(base + o, base + o + len), (v) => v / m.scale);
  return { ctx: take(0, m.ctx), truth: take(m.ctx, m.h), q10: take(m.ctx + m.h, m.h), q50: take(m.ctx + 2 * m.h, m.h), q90: take(m.ctx + 3 * m.h, m.h) };
}

const compass = (deg) => ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][Math.round(deg / 45) % 8];
const dateLabel = (iso) => new Date(iso).toLocaleString("en-GB", { timeZone: "UTC", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }) + " UTC";
const pointLabel = (i) => {
  const near = Object.entries(RUNS ? RUNS.meta.places : {}).find(([, p]) => p === i);
  return `${near ? `${near[0]} area · ` : ""}${R.points.lat[i].toFixed(2)}°N ${R.points.lon[i].toFixed(2)}°E`;
};

function head(n) { return [h("div", { class: "qnum" }, `Question ${n}`), h("h1", { class: "q" }, QUESTIONS[n].long)]; }
const answer = (html) => h("p", { class: "answer", html });
const named = (label) => R.situations.find((x) => x.label.startsWith(label));

// ------------------------------------------------------------------------------------------------ forecast in detail
function drawFan(host, run, pt, height = 300, width = 820) {
  const m = RUNS.meta, info = m.runs[run], v = runSeries(run, pt);
  const ctxX = Array.from({ length: m.ctx }, (_, i) => i - m.ctx), hx = Array.from({ length: m.h }, (_, i) => i);
  const arr = info.arrival ? info.arrival[pt] : 99;
  lineChart(host, {
    series: [
      { name: "Before the start", color: COL.sec, xs: ctxX, ys: v.ctx, width: 1.6 },
      { name: "Measured", color: COL.text, xs: hx, ys: v.truth, width: 2.2 },
      { name: "TiRex-2 forecast", color: COL.blue, xs: hx, ys: v.q50, width: 2.4 },
    ],
    band: { xs: hx, lo: v.q10, hi: v.q90, color: COL.blue, name: "10–90 % band" },
    vmarks: arr !== 99 && arr >= 0 && arr < m.h ? [{ x: arr, label: "front arrives" }] : [],
    xlim: [-m.ctx, m.h - 1], xticks: [-36, -24, -12, 0, 12, 23], xlabel: "hours from the forecast start", ylabel: "temperature (°C)",
    xfmt: (x) => (x < 0 ? `${-x} h before the start` : `${x} h after the start`), height, width, aria: "Measured temperature, forecast and band",
  });
}

function runSelect(value, onChange) {
  const sel = h("select", { "aria-label": "Forecast to show", onchange: () => onChange(Number(sel.value)) });
  const groups = { front: "Cold fronts", calm: "Calm day", storm: "Thunderstorm day", normal: "Normal days" };
  for (const [kind, label] of Object.entries(groups)) {
    const og = h("optgroup", { label });
    RUNS.meta.runs.forEach((r, i) => { if (r.kind === kind) og.append(h("option", { value: i, selected: i === value }, r.label)); });
    if (og.children.length) sel.append(og);
  }
  return sel;
}

function placeSelect(value, onChange) {
  const sel = h("select", { "aria-label": "Place", onchange: () => onChange(Number(sel.value)) });
  for (const [name, i] of Object.entries(RUNS.meta.places)) sel.append(h("option", { value: i, selected: i === value }, name));
  if (!Object.values(RUNS.meta.places).includes(value)) sel.append(h("option", { value, selected: true }, pointLabel(value)));
  return sel;
}

const findRun = (kind, text) => Math.max(0, RUNS.meta.runs.findIndex((r) => r.kind === kind && (!text || r.label.includes(text))));

// ------------------------------------------------------------------------------------------------ Q1
function pageQ1(main) {
  const S = R.summary, L = R.lead;
  main.append(...head(1), answer(
    `TiRex-2 is wrong by more than 2 °C in <b>${f0(S.wrong12)} %</b> of the forecasts up to 12 hours ahead (average error ${f1(S.mae12)} °C) and in <b>${f0(S.wrong24)} %</b> of the forecasts 13 to 24 hours ahead. ` +
    `It beats the two simple forecasts, but its lead over "same as yesterday" shrinks from ${f0(S.improve12)} % at 12 hours to ${f0(S.improve24)} % at 24 hours. ` +
    `Its uncertainty band holds the true value ${f0(S.cover)} % of the time, close to the 80 % it should hold.`));

  const host1 = h("div");
  const names = { tirex: ["TiRex-2", COL.blue], last_hour: ["Same as 1 hour ago", COL.aqua], yesterday: ["Same as yesterday", COL.orange] };
  const draw1 = (metric) => {
    const common = { xlim: [1, 24], xticks: [1, 6, 12, 18, 24], xlabel: "hours ahead", xfmt: (x) => `${x} h ahead`, height: 320 };
    if (metric === "cover") {
      lineChart(host1, { ...common, series: [{ name: "TiRex-2", color: COL.blue, xs: L.leads, ys: L.cover }], ylim: [60, 100], ylabel: "true value inside the band (%)", yfmt: (v) => `${f1(v)} %`, refs: [{ y: 80, label: "should be 80 %" }], aria: "Share of true values inside the band by hours ahead" });
      return;
    }
    const data = metric === "mae" ? L.mae : L.wrong;
    lineChart(host1, {
      ...common, series: Object.entries(names).map(([k, [name, color]]) => ({ name, color, xs: L.leads, ys: data[k] })),
      ylim: metric === "mae" ? [0, 5.4] : [0, 100], ylabel: metric === "mae" ? "average error (°C)" : "wrong by more than 2 °C (%)",
      yfmt: metric === "mae" ? (v) => `${fmt(v, 2)} °C` : (v) => `${f1(v)} %`, aria: "Error by hours ahead",
    });
  };
  draw1("mae");
  main.append(card({
    id: "by-lead", title: "Error by hours ahead", questions: [1, 4], related: [9],
    desc: "How far the forecast is from the measured value, compared with two simple forecasts. Lower is better. A forecast counts as a mistake when it is more than 2 °C off.",
    controls: [segmented([["mae", "Average error"], ["wrong", "Share wrong by more than 2 °C"], ["cover", "Inside the 10–90 % band"]], "mae", draw1)],
    body: host1, note: `${S.n_spread} start times spread over the year, ${S.n_points} points, forecasts 1 to 24 hours ahead. Hover the chart for the values.`,
  }));

  // one forecast in detail, with a small map to pick the point
  const st = { run: findRun("front", "25 Mar"), pt: RUNS.meta.places.Innsbruck };
  const fanHost = h("div"), mapHost = h("div"), name = h("p", { class: "note" });
  let map;
  const redraw = () => { drawFan(fanHost, st.run, st.pt, 330, 660); map.select(st.pt); name.textContent = `Shown: ${pointLabel(st.pt)}. Click a dot on the map to choose another point.`; };
  const body = h("div", { class: "cols wide-left" }, h("div", {}, fanHost), h("div", {}, mapHost, name));
  main.append(card({
    id: "detail", title: "One forecast in detail", questions: [1, 2], related: [4],
    desc: "The measured temperature, the TiRex-2 forecast and its 10–90 % band for one place and one start time. Pick a cold front to see what happens when the weather changes suddenly.",
    controls: [h("label", {}, "Forecast ", runSelect(st.run, (v) => { st.run = v; redraw(); })), h("label", {}, "Place ", placeSelect(st.pt, (v) => { st.pt = v; redraw(); }))],
    body, note: "Grey: the 36 hours before the start (the model sees these). White: what was measured. Blue: the forecast and its band.",
  }));
  map = scatterMap(mapHost, { lon: R.points.lon, lat: R.points.lat, fill: () => "#4a5560", tip: (i) => pointLabel(i), onClick: (i) => { st.pt = i; byId("detail").querySelector("select[aria-label=Place]")?.replaceWith(placeSelect(i, (v) => { st.pt = v; redraw(); })); redraw(); } });
  redraw();
  main.append(sources([
    'Bureau of Meteorology, <a href="https://www.bom.gov.au/news-and-media/understanding-forecast-accuracy-and-verification">Understanding forecast accuracy and verification</a> and IPMA, <a href="https://www.ipma.pt/opencms/en/otempo/prev.localidade.hora/prev.verificacao/forecast-verification.jsp">Forecast verification</a>: a forecast counts as correct within 2 °C.',
    "Murphy, A. H. (1993): What is a good forecast? Weather and Forecasting 8, 281–293. Wilks, D. S. (2019): Statistical Methods in the Atmospheric Sciences, 4th ed.",
    "Gneiting, T., Balabdaoui, F., Raftery, A. E. (2007): Probabilistic forecasts, calibration and sharpness. J. R. Stat. Soc. B 69, 243–268.",
    'Auer, A. et al. (2025): <a href="https://arxiv.org/abs/2505.23719">TiRex: Zero-Shot Forecasting Across Long and Short Horizons with Enhanced In-Context Learning</a>. NeurIPS 2025.',
  ]));
}

// ------------------------------------------------------------------------------------------------ Q2
function situationBars(host, metric, extra = {}) {
  const rows = R.situations.map((x) => ({ group: x.group, label: x.label, value: metric === "wrong" ? x.wrong : x.cover, n: x.n }));
  barChart(host, {
    rows, max: 100, unit: " %", valueLabel: metric === "wrong" ? "Wrong by more than 2 °C" : "True value inside the 10–90 % band",
    ref: metric === "cover" ? { value: 80, label: "should be 80 %" } : null, color: metric === "wrong" ? COL.blue : COL.aqua, ...extra,
  });
}

function pageQ2(main) {
  const like = named("like yesterday"), far = named("5 °C or more"), day = named("daytime"), night = named("night");
  const cf = named("during a cold front"), ts = named("during a thunderstorm"), rainy = named("rainy"), dry = named("dry");
  main.append(...head(2), answer(
    `The most important factor is how much the weather changes. On days like yesterday TiRex-2 is wrong in <b>${f0(like.wrong)} %</b> of the forecasts; on days that are 5 °C or more different it is wrong in <b>${f0(far.wrong)} %</b>. ` +
    `It is also worse in the daytime (${f0(day.wrong)} % against ${f0(night.wrong)} % at night) and in rain (${f0(rainy.wrong)} % against ${f0(dry.wrong)} % when dry). ` +
    `It is worst during weather events: wrong in ${f0(cf.wrong)} % of the hours of a cold front and ${f0(ts.wrong)} % of a thunderstorm. There the uncertainty band holds the true value only ${f0(cf.cover)} % and ${f0(ts.cover)} % of the time, instead of 80 %.`));

  const host = h("div");
  const draw = (metric) => situationBars(host, metric);
  draw("wrong");
  main.append(card({
    id: "situations", title: "Right and wrong by weather situation", questions: [2, 4], related: [9],
    desc: "The same forecasts, split by the weather at the time. Left view: how often a forecast is wrong by more than 2 °C. Right view: whether the uncertainty band is honest (it should hold the true value 80 % of the time).",
    controls: [segmented([["wrong", "Wrong by more than 2 °C"], ["cover", "Inside the 10–90 % band"]], "wrong", draw)], body: host,
    note: `Forecasts 1 to 12 hours ahead. The event rows use all forecasts, including the ${R.summary.n_front_runs} extra runs started 6 and 12 hours before each front. A case is one start time and one point.`,
  }));

  const st = { a: findRun("calm"), b: findRun("front", "25 Mar"), pt: RUNS.meta.places.Innsbruck };
  const hostA = h("div"), hostB = h("div");
  const redraw = () => { drawFan(hostA, st.a, st.pt, 300, 500); drawFan(hostB, st.b, st.pt, 300, 500); };
  redraw();
  main.append(card({
    id: "compare", title: "A calm day against a front day", questions: [2, 1], related: [4],
    desc: "The same place on two different days. On a calm day the forecast follows the measurement. When a front arrives, the measured temperature falls but the forecast does not, and the band does not warn about it.",
    controls: [h("label", {}, "Place ", placeSelect(st.pt, (v) => { st.pt = v; redraw(); })),
      h("label", {}, "Left ", runSelect(st.a, (v) => { st.a = v; redraw(); })), h("label", {}, "Right ", runSelect(st.b, (v) => { st.b = v; redraw(); }))],
    body: h("div", { class: "cols" }, hostA, hostB),
  }));
  main.append(sources([
    "Wilks, D. S. (2019): Statistical Methods in the Atmospheric Sciences, 4th ed. (verification split by situation).",
    "Gneiting, T., Balabdaoui, F., Raftery, A. E. (2007): Probabilistic forecasts, calibration and sharpness. J. R. Stat. Soc. B 69, 243–268.",
    'Auer, A. et al. (2025): <a href="https://arxiv.org/abs/2505.23719">TiRex</a>. The model forecasts from the history of one series only.',
    'Skok, G., Lledó, L. (2024): <a href="https://arxiv.org/abs/2407.20624">Quantifying double-penalty effects</a> (a timing error is punished twice).',
  ]));
}

// ------------------------------------------------------------------------------------------------ Q3
function pageQ3(main) {
  const F = R.fronts, acc = F.filter((f) => f.accepted);
  main.append(...head(3), answer(
    `There is no official list of cold fronts for Austria, so we use methods from research. We call it a cold front when two things hold. <b>At one point</b> the temperature falls by at least 3 °C within 3 hours and the pressure rises by at least 2 hPa, compared with what is normal for that place and hour. ` +
    `<b>In the country</b> at least half of the points must have such a passage within 24 hours, and the times must form a line that moves across Austria from the west or north. This finds <b>${acc.length} cold fronts</b> in one year, from ${F.length} candidates.`));

  main.append(card({
    id: "rule", title: "The rule in four steps", questions: [3],
    body: h("ol", { style: "line-height:1.7;margin:6px 0 0 20px;padding:0" },
      h("li", { html: "<b>Compare with normal.</b> The 3-hour temperature change and the 6-hour pressure change are compared with the usual change at that place, month and hour, so the daily rhythm does not count." }),
      h("li", { html: "<b>Find passages.</b> A point has a passage when it cools by at least 3 °C and the pressure rises by at least 2 hPa." }),
      h("li", { html: "<b>Look for a country-wide event.</b> At least half of the points must have a passage within 24 hours." }),
      h("li", { html: "<b>Check that it moves.</b> The passage times must fit a line that moves across Austria: R² of at least 0.3, a speed of 1 to 30 m/s, coming from the west or north. A thunderstorm cools fast too, but only in one place." })),
    note: "The thresholds are options of the event script, so the team can change them in one place.",
  }));

  const st = { i: F.findIndex((f) => f.peak.startsWith("2026-05-11")), only: false };
  const tbody = h("tbody"), mapHost = h("div"), mapScale = h("div"), hovHost = h("div"), hovScale = h("div"), selLabel = h("span");
  const rowsOf = () => F.map((f, i) => [f, i]).filter(([f]) => !st.only || f.accepted);
  const drawTable = () => {
    tbody.replaceChildren(...rowsOf().map(([f, i]) => h("tr", { "aria-selected": String(i === st.i), onclick: () => { st.i = i; drawTable(); drawFront(); } },
      h("td", {}, dateLabel(f.peak)), h("td", {}, `${f0(f.share * 100)} %`), h("td", {}, f.r2.toFixed(2)), h("td", {}, `${f0(f.speed_kmh)} km/h`), h("td", {}, compass(f.direction)),
      h("td", {}, h("span", { class: `tag ${f.accepted ? "yes" : "no"}` }, f.accepted ? "cold front" : "not a front"), " ", f.accepted ? "" : f.why))));
  };
  main.append(card({
    id: "candidates", title: "All candidate fronts", questions: [3],
    desc: "Days on which many points had a passage. Click a row to see it on the map and in the time diagram below. Rejected candidates show why they are not cold fronts.",
    controls: [segmented([["all", `All ${F.length} candidates`], ["acc", `Only the ${acc.length} cold fronts`]], "all", (v) => { st.only = v === "acc"; if (st.only && !F[st.i].accepted) st.i = F.indexOf(acc[0]); drawTable(); drawFront(); })],
    body: h("div", { style: "max-height:380px;overflow:auto;border:1px solid var(--line);border-radius:8px" },
      h("table", { class: "pick" }, h("thead", {}, h("tr", {}, ["Peak (UTC)", "Points with a passage", "Fit of the moving line (R²)", "Speed", "Moves towards", "Verdict"].map((x) => h("th", {}, x)))), tbody)),
    note: "Passage times are the hour in which the cooling and pressure rise starts. Speed and direction come from a plane fitted to the passage times of all points, so they are an average over Austria.",
  }));

  const drawFront = () => {
    const f = F[st.i];
    selLabel.textContent = `${dateLabel(f.peak)} · ${f.accepted ? "cold front" : "not a front"}`;
    scatterMap(mapHost, {
      lon: R.points.lon, lat: R.points.lat, arrow: { deg: f.direction, text: `fitted line moves ${compass(f.direction)}, about ${f0(f.speed_kmh)} km/h` },
      fill: (i) => (f.arrival[i] === 99 ? "#383835" : DIV(Math.max(-8, Math.min(8, f.arrival[i])) / 16 + 0.5)),
      tip: (i) => `<b>${pointLabel(i)}</b><br>${f.arrival[i] === 99 ? "no passage found" : f.arrival[i] === 0 ? "at the middle of the passage times" : `${Math.abs(f.arrival[i])} h ${f.arrival[i] < 0 ? "earlier" : "later"} than the middle point`}`,
    });
    mapScale.replaceChildren(scaleBar({ stops: DIV_STOPS, min: "8 h earlier", max: "8 h later", label: "than the middle point (grey dot: no passage found)" }));
    const lons = R.lon_edges.slice(0, -1).map((e) => e + 0.125);
    heatmap(hovHost, {
      cols: lons.map((v) => v.toFixed(1)), rows: R.time_rows.map(String), z: R.time_rows.map((_, ri) => f.z[ri].map((v) => (v === 99 ? null : v))),
      color: (v) => DIV(Math.max(-6, Math.min(6, v)) / 12 + 0.5), colTickEvery: 4, rowTickEvery: 6, flipY: true, xlabel: "longitude (°E), west to east", ylabel: "hours from the peak", height: 340,
      tip: (ri, ci) => `<b>${lons[ci].toFixed(2)}°E, ${R.time_rows[ri]} h from the peak</b><br>${f.z[ri][ci] === 99 ? "no value" : `${f1(f.z[ri][ci])} °C change over 3 h compared with normal`}`,
      tableFmt: (v) => fmt(v, 1), aria: "Time against longitude",
    });
    hovScale.replaceChildren(scaleBar({ stops: DIV_STOPS, min: "−6 °C", max: "+6 °C", label: "temperature change over 3 hours compared with normal" }));
  };
  drawTable();

  main.append(card({
    id: "arrival", title: "When the front reaches each point", questions: [3],
    desc: "Each dot is a 15 km point, coloured by when the passage starts there. For a real front the west and north are blue (early) and the south-east is red (late): the cooling moves across the country as a line.",
    controls: [h("span", { class: "note" }, "Selected: ", selLabel)], body: h("div", {}, mapHost, mapScale),
  }));
  main.append(card({
    id: "hovmoeller", title: "The front as a diagonal", questions: [3],
    desc: "Time (up) against longitude (right), colour = temperature change over 3 hours compared with normal. A cold front is a blue diagonal stripe from the lower left to the upper right: it reaches the west first. A blue band about 10 to 14 hours after the peak is the missing morning warming on a cold day, not a second front.",
    body: h("div", {}, hovHost, hovScale),
  }));
  drawFront();

  const fc = R.front_check, mini = (title, ys, ylabel, extra = {}) => {
    const host = h("div");
    lineChart(host, { series: [{ name: title, color: COL.blue, xs: fc.rel, ys }], vmarks: [{ x: 0, label: "passage" }], xlim: [-12, 12], xticks: [-12, -6, 0, 6, 12], xlabel: "hours from the front passage", ylabel, height: 250, width: 500, xfmt: (x) => `${x} h`, forceLegend: false, ...extra });
    return h("div", {}, h("div", { class: "note", style: "margin:0 0 4px" }, title), host);
  };
  main.append(card({
    id: "check", title: "What a detected front looks like", questions: [3],
    desc: `The average of ${fc.n.toLocaleString("en-GB")} point passages in ${acc.length} fronts. Temperature and pressure are part of the rule. Wind and rain are not, so they are an independent check: the wind turns from south to north and it rains at the passage, as in a textbook cold front.`,
    body: h("div", { class: "cols" },
      mini("Temperature, change since 12 h before", fc.dT, "°C", { yfmt: (v) => `${f1(v)} °C` }),
      mini("Pressure, change since 12 h before", fc.dP, "hPa", { yfmt: (v) => `${f1(v)} hPa` }),
      mini("North–south wind (positive = from the south)", fc.v, "m/s", { refs: [{ y: fc.base_v, label: "all hours" }], yfmt: (v) => `${fmt(v, 2)} m/s` }),
      mini("Hours with rain of 0.5 mm or more", fc.rain, "%", { refs: [{ y: fc.base_rain, label: "all hours" }], yfmt: (v) => `${f1(v)} %` })),
  }));
  main.append(sources([
    "Hewson, T. D. (1998): Objective fronts. Meteorological Applications 5, 37–65. Renard, R. J., Clarke, L. C. (1965): Experiments in numerical objective frontal analysis. Mon. Wea. Rev. 93, 547–556.",
    'Jenkner, J. et al. (2010): <a href="https://www.research-collection.ethz.ch/handle/20.500.11850/16922">Detection and climatology of fronts in a high-resolution model reanalysis over the Alps</a>. Meteorol. Appl. 17, 1–18.',
    "Simmonds, I., Keay, K., Bye, J. A. T. (2012): Identification and climatology of Southern Hemisphere mobile fronts in a modern reanalysis. J. Climate 25, 1945–1962.",
    'Schemm, S., Rudeva, I., Simmonds, I. (2015): <a href="https://boris.unibe.ch/71843">Extratropical fronts in the lower troposphere – global perspectives obtained from two automated methods</a>. Q. J. R. Meteorol. Soc. 141, 1686–1698.',
    'Our definition, thresholds, checks and limits: <a href="https://github.com/SandroMueller01/ai-vis-lab-2026/blob/main/data_acquisition/events/README.md">data_acquisition/events/README.md</a>. We find almost no fronts in winter, because cold air in the valleys hides them at the ground.',
  ]));
}

// ------------------------------------------------------------------------------------------------ Q4
function pageQ4(main) {
  const S = R.summary, E = R.lead_events, cf = named("during a cold front"), far = named("5 °C or more"), like = named("like yesterday");
  const at6 = (k) => E[k][5], bandFront = cf.cover;
  main.append(...head(4), answer(
    `TiRex-2 is a general forecasting model that sees only the past temperature of one point. It is good in normal weather but cannot know about a change that is coming. Its lead over "same as yesterday" shrinks from ${f0(S.improve12)} % at 12 hours to ${f0(S.improve24)} % at 24 hours. ` +
    `During a cold front the error 6 hours ahead is ${f1(at6("cold_front"))} °C instead of ${f1(E.all[5])} °C, and the uncertainty band holds the true value only ${f0(bandFront)} % of the time instead of 80 %.`));

  main.append(card({
    id: "limits", title: "What the model does not see, and what we cannot check", questions: [4], related: [5],
    body: h("ul", {},
      h("li", { html: "<b>One point, one variable.</b> The model got only the past temperature of one point (28 days). Wind, pressure, humidity and neighbouring points were not given." }),
      h("li", { html: "<b>Extra past information was ignored.</b> In our first test with extra past inputs (PR #8, smoke test) the forecast did not change, so TiRex-2 cannot &quot;see&quot; a front coming from the west. Only future values of an input changed the forecast." }),
      h("li", { html: `<b>Sudden changes.</b> On days that are 5 °C or more different from yesterday the model is wrong in ${f0(far.wrong)} % of the forecasts, against ${f0(like.wrong)} % on days like yesterday.` }),
      h("li", { html: "<b>The measured values are an analysis.</b> INCA combines stations, radar and a weather model. It is very good for temperature but less exact in the mountains, so part of an error may come from the data." }),
      h("li", { html: `<b>Small test.</b> One year, ${S.n_points} points on a 15 km grid, and ${R.fronts.filter((f) => f.accepted).length} cold fronts. We find almost none in winter.` }))
  }));

  const impHost = h("div");
  lineChart(impHost, {
    series: [{ name: "Improvement over \"same as yesterday\"", color: COL.blue, xs: R.lead.leads, ys: R.lead.improvement }], xlim: [1, 24], xticks: [1, 6, 12, 18, 24], ylim: [0, 100],
    xlabel: "hours ahead", ylabel: "smaller error than yesterday (%)", yfmt: (v) => `${f0(v)} %`, xfmt: (x) => `${x} h ahead`, forceLegend: false, height: 300,
  });
  main.append(card({
    id: "improvement", title: "How much better than \"same as yesterday\"", questions: [4, 1],
    desc: "How much smaller TiRex-2's average error is than the error of repeating yesterday's temperature. The lead is large for the first hours and nearly gone after 24 hours.",
    body: impHost,
  }));

  const evHost = h("div");
  lineChart(evHost, {
    series: [
      { name: "All forecasts", color: COL.blue, xs: E.leads, ys: E.all }, { name: "During a cold front", color: COL.orange, xs: E.leads, ys: E.cold_front },
      { name: "During a cold drop", color: COL.aqua, xs: E.leads, ys: E.cold_drop }, { name: "During a thunderstorm", color: COL.violet, xs: E.leads, ys: E.thunderstorm },
    ], xlim: [1, 24], xticks: [1, 6, 12, 18, 24], ylim: [0, 7], xlabel: "hours ahead", ylabel: "average error (°C)", yfmt: (v) => `${fmt(v, 2)} °C`, xfmt: (x) => `${x} h ahead`, height: 320,
  });
  main.append(card({
    id: "events-by-lead", title: "Error in normal weather and at weather events", questions: [4, 2], related: [7],
    desc: "Average error by hours ahead. In the hours of a cold front, cold drop or thunderstorm the error is much larger, even for the first hours.",
    body: evHost, note: `Event hours in all forecasts (cold front ${E.n.cold_front.toLocaleString("en-GB")}, cold drop ${E.n.cold_drop.toLocaleString("en-GB")}, thunderstorm ${E.n.thunderstorm.toLocaleString("en-GB")} point-hours).`,
  }));

  const bandHost = h("div");
  situationBars(bandHost, "cover");
  main.append(card({
    id: "band", title: "Is the uncertainty band honest?", questions: [4, 2], related: [9],
    desc: "Share of true values inside the 10–90 % band. A well calibrated forecast is at 80 %. In normal weather the band is honest, but at weather events it is far too narrow: the model is too sure of itself when it matters.",
    body: bandHost, note: "Forecasts 1 to 12 hours ahead.",
  }));
  main.append(sources([
    'Auer, A. et al. (2025): <a href="https://arxiv.org/abs/2505.23719">TiRex</a>. Our smoke test of the covariate use: <code>scripts/tirex_smoke_test.py</code> in the repository (PR #8).',
    'How foundational are foundation models for time series forecasting? <a href="https://arxiv.org/abs/2510.00742">arXiv:2510.00742</a>: zero-shot skill depends on the training data.',
    "Haiden, T. et al. (2011): The Integrated Nowcasting through Comprehensive Analysis (INCA) system and its validation over the Eastern Alpine region. Weather and Forecasting 26, 166–183.",
    "Gneiting, T., Balabdaoui, F., Raftery, A. E. (2007): Probabilistic forecasts, calibration and sharpness. J. R. Stat. Soc. B 69, 243–268.",
  ]));
}

// ------------------------------------------------------------------------------------------------ Q5
function pageQ5(main) {
  const FE = R.front_error, M = R.mistakes, regions = R.regions, SH = R.start_heat;
  const meanOfFirst12 = SH.mae.map((row) => row.slice(0, 12).reduce((a, b) => a + b, 0) / 12);
  const worst = meanOfFirst12.indexOf(Math.max(...meanOfFirst12)), best = meanOfFirst12.indexOf(Math.min(...meanOfFirst12));
  const mean24 = (hr) => SH.mae[SH.hours.indexOf(hr)].reduce((a, b) => a + b, 0) / 24;
  const mAll = M[0], mCf = M[3];
  const before = Math.abs(FE.mean.slice(0, 11).reduce((a, b) => a + b, 0) / 11);
  main.append(...head(5), answer(
    `<b>Timing.</b> Before a front reaches a point the forecast is about ${f1(before)} °C too cold. Three hours after it arrives, the forecast is ${f1(FE.mean[15])} °C too warm, because the model keeps the old temperature too long, and the true value is inside the band only ${f0(FE.cover[15])} % of the time. ` +
    `Of the forecasts that are wrong by more than 2 °C, ${f0(mAll.too_warm)} % are too warm in general, but ${f0(mCf.too_warm)} % during cold fronts.<br>` +
    `<b>Regions.</b> The differences are small (average error ${f1(regions[0].mae)} °C in the west, ${f1(regions[1].mae)} °C in the centre, ${f1(regions[2].mae)} °C in the east); the Alps are slightly better.<br>` +
    `<b>Neighbours.</b> Points with more neighbours are not better, which is expected: the model never saw its neighbours.<br>` +
    `<b>Start time.</b> For 24 hours ahead the start time hardly matters (${fmt(mean24(0), 2)} °C from 00:00 UTC, ${fmt(mean24(19), 2)} °C from 19:00 UTC). For the next 12 hours a start at ${String(SH.hours[worst]).padStart(2, "0")}:00 UTC is worst (${fmt(meanOfFirst12[worst], 2)} °C) and ${String(SH.hours[best]).padStart(2, "0")}:00 UTC is best (${fmt(meanOfFirst12[best], 2)} °C).`));

  const fe1 = h("div"), fe2 = h("div");
  const t = (x) => (x === 0 ? "front arrives" : x < 0 ? `${-x} h before the front arrives` : `${x} h after the front arrives`);
  lineChart(fe1, {
    series: [{ name: "Mean error", color: COL.blue, xs: FE.rel, ys: FE.mean }], band: { xs: FE.rel, lo: FE.q25, hi: FE.q75, color: COL.blue, name: "Middle half of the errors" },
    refs: [{ y: 0, label: "no error" }], vmarks: [{ x: 0, label: "front arrives" }], xlim: [-12, 12], xticks: [-12, -6, 0, 6, 12], xlabel: "hours since the front reached the point",
    ylabel: "forecast − measured (°C)", yfmt: (v) => `${fmt(v, 2)} °C`, xfmt: t, height: 260, forceLegend: true,
  });
  lineChart(fe2, {
    series: [{ name: "True value inside the band", color: COL.blue, xs: FE.rel, ys: FE.cover }], refs: [{ y: 80, label: "should be 80 %" }], vmarks: [{ x: 0, label: "front arrives" }],
    xlim: [-12, 12], xticks: [-12, -6, 0, 6, 12], ylim: [0, 100], xlabel: "hours since the front reached the point", ylabel: "inside the band (%)", yfmt: (v) => `${f0(v)} %`, xfmt: t, height: 220,
  });
  main.append(card({
    id: "around-front", title: "Error around the front arrival", questions: [5, 4], related: [4, 6, 8, 9],
    desc: "Forecast minus measured temperature, by hours since the front reached each point. Positive means the forecast is too warm. The model is too cold before the front, jumps to too warm at the arrival and stays too warm for hours. Below: the true value is inside the band far too rarely.",
    body: h("div", {}, fe1, h("div", { style: "height:10px" }), fe2),
    note: `${FE.runs} forecasts started 6 or 12 hours before ${FE.fronts} fronts (the first front of the year is too early for the 28-day history), forecasts 1 to 24 hours ahead. The lead time grows along the axis, so part of the rise in error comes from longer forecasts.`,
  }));

  const warmHost = h("div");
  barChart(warmHost, {
    rows: M.map((x) => ({ label: x.label, value: x.too_warm, n: x.n_wrong })), max: 100, unit: " %", valueLabel: "Of the forecasts wrong by more than 2 °C, too warm", ref: { value: 50, label: "half" }, color: COL.orange, labelWidth: 200,
  });
  main.append(card({
    id: "warm-cold", title: "Too warm or too cold?", questions: [5],
    desc: "Of all forecasts that are wrong by more than 2 °C, how many are too warm (the rest are too cold). In normal weather the model is more often too cold, mainly on sunny days. At weather events it is almost always too warm.",
    body: warmHost, note: "Forecasts 1 to 12 hours ahead. The number of mistakes behind each bar is shown on hover.",
  }));

  const P = R.points, mapHost = h("div"), mapScaleHost = h("div"), regionHost = h("div");
  let metric = "mae", pmap;
  const maeMax = Math.max(...P.mae12), lim = Math.max(0.3, Math.max(...P.bias12.map(Math.abs)));
  const fill = (i) => (metric === "mae" ? SEQ((P.mae12[i] - 0.9) / (maeMax - 0.9)) : DIV(P.bias12[i] / (2 * lim) + 0.5));
  const tipFor = (i) => `<b>${pointLabel(i)}</b><br>Average error: <b>${fmt(P.mae12[i], 2)} °C</b><br>Bias: ${P.bias12[i] > 0 ? "+" : ""}${fmt(P.bias12[i], 2)} °C (${P.bias12[i] > 0 ? "too warm" : "too cold"})<br>${P.neighbours[i]} direct neighbours`;
  const drawScale = () => mapScaleHost.replaceChildren(metric === "mae"
    ? scaleBar({ stops: SEQ_STOPS, min: "0.9 °C", max: `${fmt(maeMax, 1)} °C`, label: "average error, 1 to 12 hours ahead" })
    : scaleBar({ stops: DIV_STOPS, min: `${fmt(-lim, 1)} °C (too cold)`, max: `+${fmt(lim, 1)} °C (too warm)`, label: "forecast − measured" }));
  pmap = scatterMap(mapHost, { lon: P.lon, lat: P.lat, fill, tip: tipFor });
  drawScale();
  regionHost.append(h("table", {}, h("thead", {}, h("tr", {}, ["Region", "Points", "Average error", "Bias"].map((x) => h("th", {}, x)))),
    h("tbody", {}, regions.map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.n), h("td", {}, `${fmt(r.mae, 2)} °C`), h("td", {}, `${r.bias > 0 ? "+" : ""}${fmt(r.bias, 2)} °C`))))));
  main.append(card({
    id: "maps", title: "Where is it wrong?", questions: [5],
    desc: "Average error and bias for each point, forecasts 1 to 12 hours ahead. The errors are smallest in the Alps and larger in the northern lowlands. The bias is small everywhere; it is slightly too cold in the south and west.",
    controls: [segmented([["mae", "Average error"], ["bias", "Bias (too warm or too cold)"]], "mae", (v) => { metric = v; pmap.recolor(); drawScale(); })],
    body: h("div", {}, mapHost, mapScaleHost, h("div", { style: "height:12px" }), regionHost),
    note: `${R.summary.n_spread} start times spread over the year. Regions are cut by the east–west position (Lambert x below 300 km, 300–500 km, above 500 km). A likely reason for the lowland errors is the stronger daily temperature swing there; we have not tested it.`,
  }));

  const nbHost = h("div");
  barChart(nbHost, {
    rows: R.neighbour_stats.map((x) => ({ label: `${x.neighbours} direct ${x.neighbours === 1 ? "neighbour" : "neighbours"}`, value: x.mae, n: x.n, tip: `<b>${x.neighbours} direct neighbours</b><br>${x.n} points<br>Average error: <b>${fmt(x.mae, 2)} °C</b>` })),
    max: 2, unit: " °C", fmt: (v) => fmt(v, 2), valueLabel: "Average error", labelWidth: 170,
  });
  main.append(card({
    id: "neighbours", title: "Do points with more neighbours get better forecasts?", questions: [5],
    desc: "Average error by the number of direct neighbours on the 15 km grid (4 = inside the country, fewer = at the border). More neighbours do not help. This is expected, because TiRex-2 only used the history of one point and never saw its neighbours.",
    body: nbHost, note: "Hover a bar for the number of points.",
  }));

  const heatHost = h("div"), maxHeat = Math.max(...SH.mae.flat());
  heatmap(heatHost, {
    cols: SH.leads.map(String), rows: SH.hours.map((x) => `${String(x).padStart(2, "0")}:00`), z: SH.mae, color: (v) => SEQ(v / maxHeat), colTickEvery: 1, xlabel: "hours ahead", ylabel: "forecast start (UTC)", height: 300,
    tip: (ri, ci) => `<b>Start ${String(SH.hours[ri]).padStart(2, "0")}:00 UTC, ${SH.leads[ci]} h ahead</b><br>Average error: ${fmt(SH.mae[ri][ci], 2)} °C<br>${SH.n[ri]} start times`, tableFmt: (v) => fmt(v, 2),
  });
  main.append(card({
    id: "start-time", title: "Does the start time matter?", questions: [5],
    desc: "Average error by forecast start hour (rows) and hours ahead (columns). Dark = small error. A forecast started in the morning has a larger error in its first hours, because it has to predict the daytime warming; one started in the evening covers the calm night first.",
    body: h("div", {}, heatHost, scaleBar({ stops: SEQ_STOPS, min: "0 °C", max: `${fmt(maxHeat, 1)} °C`, label: "average error" })), note: "Start hours 00, 03, 06, 09, 12, 15, 18, 19 and 21 UTC.",
  }));
  main.append(sources([
    'Skok, G., Lledó, L. (2024): <a href="https://arxiv.org/abs/2407.20624">Quantifying double-penalty effects and mitigating their impact on forecast verification</a>.',
    "Whiteman, C. D. (2000): Mountain Meteorology: Fundamentals and Applications. Oxford University Press (valleys, basins and the daily temperature cycle).",
    'Valley inversions against weather model output: <a href="https://amt.copernicus.org/articles/18/1039/2025/">Atmos. Meas. Tech. 18, 1039 (2025)</a>; Hughes, J. K. et al. (2015): <a href="https://gmd.copernicus.org/articles/8/3105/2015/">Assessment of valley cold pools and clouds in a very high-resolution NWP model</a>, Geosci. Model Dev. 8, 3105.',
    'Auer, A. et al. (2025): <a href="https://arxiv.org/abs/2505.23719">TiRex</a>.',
  ]));
}

// ------------------------------------------------------------------------------------------------ Carlos's findings
// his questions and findings, as he reported them; where they overlap with our charts the cards link to them
const CARLOS_FINDINGS = {
  1: ["No, 2–10 weeks give the same error.", [4], []],
  2: ["No.", [4], []],
  3: ["Yes, the more it stands out the more, and a Sunday flag helps. A single fixed Sunday is ignored. A rerun on 40 dates is in progress.", [4], []],
  4: ["No, about 21 % of the drop, for every front.", [4, 5], [["q5.html#around-front", "Error around the front arrival"], ["q1.html#detail", "One forecast in detail"]]],
  5: ["No, none of them.", [4], [["q4.html#limits", "What the model does not see"]]],
  6: ["It adopts the new cold level, but never extends a fall that's still going on.", [5], [["q5.html#around-front", "Error around the front arrival"]]],
  7: ["Only about 3 h before.", [4], [["q4.html#events-by-lead", "Error in normal weather and at weather events"]]],
  8: ["Barely less sure, and normal again after about a day.", [5], [["q5.html#around-front", "Error around the front arrival (band coverage)"]]],
  9: ["On normal days yes. With a front coming, no: half the hours are colder than the whole band.", [1, 2, 4], [["q1.html#by-lead", "Error by hours ahead (band coverage)"], ["q2.html#situations", "Right and wrong by weather situation"], ["q4.html#band", "Is the uncertainty band honest?"], ["q5.html#around-front", "Error around the front arrival"]]],
  10: ["It can't get there realistically. Inserted drops widen the band only up to a point, and it narrows again for big or many drops.", [4], []],
  11: ["All 4 weeks: about 35 % of the effect comes from the last week, with a mild focus on the same hour of day.", [4], []],
  12: ["In about half of them, but it's not a usable warning sign: after a warm-up, a front follows only 5.5 % of the time.", [4], []],
};

function pageCarlos(main) {
  main.append(h("div", { class: "qnum" }, "Findings by Carlos"), h("h1", { class: "q" }, "Carlos's questions and findings"),
    h("p", { class: "answer", html: "These are the questions Carlos works on, with his findings as he reported them. They are <b>not computed by this dashboard</b>. Where one of our charts overlaps with a question, the chart says so and links here, and the card below links back to the chart, so no question is answered twice. The weekly-pattern result (C3) is provisional: a rerun on 40 dates is in progress." }));
  for (const [n, [finding, ours, charts]] of Object.entries(CARLOS_FINDINGS)) {
    main.append(h("section", { class: "viz", id: `c${n}` }, h("h2", {}, CARLOS[n]),
      h("div", { class: "answers" }, h("span", { class: "lbl" }, "Carlos's question"), h("span", { class: "qchip", style: "cursor:default" }, `C${n}`),
        h("span", { class: "lbl", style: "margin-left:10px" }, "Also bears on"), ours.map((q) => h("a", { class: "qchip", href: QUESTIONS[q].page, title: QUESTIONS[q].long }, `Q${q} · ${QUESTIONS[q].short}`))),
      h("p", { class: "owner" }, "Owner: Carlos"), h("p", { class: "finding" }, finding),
      charts.length ? h("p", { class: "note" }, "Our charts on the same topic: ", charts.map(([href, label], i) => [i ? " · " : "", h("a", { href }, label)])) : null));
  }
  main.append(sources(["Carlos Elizondo, own experiments with TiRex-2 for Phase I. The details and the code are in his part of the repository [check: add the path or the PR here]."]));
}

// ------------------------------------------------------------------------------------------------ start
async function startPage() {
  const main = h("main", { id: "main" });
  document.body.append(main);
  try {
    [R] = await Promise.all([getJson("data/results.json")]);
    if (["q1", "q2"].includes(PAGE)) await loadRuns();
    ({ q1: pageQ1, q2: pageQ2, q3: pageQ3, q4: pageQ4, q5: pageQ5, carlos: pageCarlos })[PAGE](main);
  } catch (err) {
    main.append(h("p", { class: "answer" }, `Could not load the data: ${err.message}`));
    console.error(err);
  }
}
const PAGE = document.body.dataset.page;
startPage();
