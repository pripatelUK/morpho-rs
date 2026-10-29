// Usage: node check_page.cjs <page.html> — executes the page's inline scripts in jsdom and reports errors.
const { JSDOM, VirtualConsole } = require("jsdom");
const fs = require("fs");

const vc = new VirtualConsole();
const errors = [];
vc.on("jsdomError", (e) => errors.push(e.message));
vc.on("error", (e) => errors.push(String(e)));

const html = fs.readFileSync(process.argv[2], "utf8").replace(/<link[^>]*>/g, "");
const dom = new JSDOM(html, {
  runScripts: "dangerously",
  virtualConsole: vc,
  pretendToBeVisual: true,
  beforeParse(w) {
    w.ResizeObserver = class { observe() {} };
    w.matchMedia = () => ({ matches: false, addEventListener() {} });
    w.SVGElement.prototype.getComputedTextLength = function () { return (this.textContent || "").length * 6; };
    w.SVGElement.prototype.getBoundingClientRect = () => ({ left: 0, top: 0, width: 800, height: 240 });
  },
});

const d = dom.window.document;
const report = (label) => {
  const out = {};
  for (const key of ["tvl", "apy", "flow", "alloc"]) {
    const vis = ["comb", "v2"].find((s) => !d.getElementById(`${key}-plot-${s}`).hidden);
    const plot = d.getElementById(`${key}-plot-${vis}`);
    out[key] = {
      visible: vis,
      title: d.getElementById(`${key}-title`).textContent,
      paths: plot.querySelectorAll("path").length,
      legend: d.getElementById(`${key}-legend`).children.length,
      tableRows: d.getElementById(`${key}-table-${vis}`).querySelectorAll("tbody tr").length,
    };
  }
  console.log(label, JSON.stringify(out, null, 1));
};

report("initial");
d.getElementById("scope-v2").click();
report("after V2 click");
d.getElementById("scope-comb").click();
console.log("comb pressed:", d.getElementById("scope-comb").getAttribute("aria-pressed"));
console.log("errors:", errors.length ? errors : "none");
