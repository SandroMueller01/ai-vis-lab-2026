"use strict";
// Shared helpers of all pages: the five questions, colours, small DOM builders, navigation, tooltip and cards.

const QUESTIONS = {
  1: { short: "How often is it wrong?", long: "How often does the system make mistakes?", page: "q1.html" },
  2: { short: "When is it right or wrong?", long: "In what situations is the system likely to be correct or incorrect?", page: "q2.html" },
  3: { short: "What is a cold front?", long: "How do we define a cold front?", page: "q3.html" },
  4: { short: "What are the limits?", long: "What are the limitations of the system?", page: "q4.html" },
  5: { short: "What kind of mistakes?", long: "What kind of mistakes does it make? Regions, neighbours and start times", page: "q5.html" },
};

const COL = { blue: "#3987e5", orange: "#d95926", aqua: "#199e70", violet: "#9085e9", red: "#e66767", text: "#e7ebf0", sec: "#9aa6b3", muted: "#6f7c89", line: "#2e3842" };
const SVGNS = "http://www.w3.org/2000/svg";

// element builders: h("div", {class: "x", onclick: fn}, child, ...) and s("circle", {...}) for svg
function h(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) e.append(kid.nodeType ? kid : document.createTextNode(kid));
  return e;
}

function s(tag, props = {}, ...kids) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") e.setAttribute("class", v);
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) e.append(kid);
  return e;
}

const byId = (id) => document.getElementById(id);
const fmt = (x, d = 1) => Number(x).toFixed(d);
const pct = (x) => `${Math.round(x)} %`;

// colour scales: SEQ for magnitudes (dark = small, light = large on the dark surface), DIV for signed values
function ramp(stops) {
  const rgb = stops.map((c) => [1, 3, 5].map((k) => parseInt(c.slice(k, k + 2), 16)));
  return (t) => {
    t = Math.max(0, Math.min(1, t));
    const x = t * (rgb.length - 1), i = Math.min(Math.floor(x), rgb.length - 2), f = x - i;
    const c = rgb[i].map((v, j) => Math.round(v + (rgb[i + 1][j] - v) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  };
}
const SEQ_STOPS = ["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"];
const DIV_STOPS = ["#3987e5", "#6b6a65", "#e66767"];
const SEQ = ramp(SEQ_STOPS);
const DIV = ramp(DIV_STOPS);
const cssGradient = (stops) => `linear-gradient(90deg, ${stops.join(",")})`;

// tooltip shared by all charts
const tip = {
  el: null,
  show(html, ev) {
    if (!this.el) { this.el = h("div", { id: "tt", hidden: true }); document.body.append(this.el); }
    this.el.innerHTML = html;
    this.el.hidden = false;
    const w = this.el.offsetWidth, hh = this.el.offsetHeight;
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - 14;
    if (y + hh > window.innerHeight - 8) y = ev.clientY - hh - 14;
    this.el.style.left = `${Math.max(8, x)}px`;
    this.el.style.top = `${Math.max(8, y)}px`;
  },
  hide() { if (this.el) this.el.hidden = true; },
};

function renderNav(current) {
  const links = [["explore", "index.html", "Explore the data"], ...Object.entries(QUESTIONS).map(([n, q]) => [`q${n}`, q.page, `Q${n} · ${q.short}`])];
  const nav = h("nav", { id: "nav", "aria-label": "Pages" },
    h("a", { class: "brand", href: "index.html" }, "Austria weather explorer"),
    links.map(([key, href, label]) => h("a", { class: "link", href, "aria-current": key === current ? "page" : null }, label)));
  document.body.prepend(nav);
}

// "Answers: Q1 · ..." chips; each links to the page of that question
function chips(nums, verb = "Answers") {
  return h("div", { class: "answers" }, h("span", { class: "lbl" }, nums.length > 1 ? `${verb} questions` : `${verb} question`),
    nums.map((n) => h("a", { class: "qchip", href: QUESTIONS[n].page, title: QUESTIONS[n].long }, `Q${n} · ${QUESTIONS[n].short}`)));
}

// a visualisation card; every one names the questions it answers
function card({ id, title, questions, desc, controls, body, note }) {
  return h("section", { class: "viz", id }, h("h2", {}, title), chips(questions), desc ? h("p", { class: "desc" }, desc) : null,
    controls ? h("div", { class: "controls" }, controls) : null, body, note ? h("p", { class: "note" }, note) : null);
}

// segmented control: options [[value, label], ...]
function segmented(options, value, onChange) {
  const wrap = h("div", { class: "seg", role: "group" });
  const set = (v) => {
    wrap.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
    onChange(v);
  };
  for (const [v, label] of options) wrap.append(h("button", { type: "button", "data-v": v, "aria-pressed": String(v === value), onclick: () => set(v) }, label));
  return wrap;
}

// every chart has a table twin
function tableView(host, { headers, rows }) {
  host.querySelectorAll(":scope > details.tbl").forEach((d) => d.remove());
  host.append(h("details", { class: "tbl" }, h("summary", {}, "Show as table"),
    h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, headers.map((x) => h("th", {}, x)))),
      h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c) => h("td", {}, c)))))))));
}

function sources(list) {
  return h("div", { class: "sources" }, h("h2", {}, "Sources"), h("ul", {}, list.map((t) => h("li", { html: t }))));
}

renderNav(document.body.dataset.page);
if (byId("qchips")) byId("qchips").append(chips([3], "Helps with"));
