// Cross-validation test for the extract9/extract10 → maskAlign.ts port.
//
//   node src/generate/maskAlign.test.mjs
//
// Runs the TS fit + gate primitives on the SAME pixels the python experiment processed
// and asserts every fit and gate verdict matches the python-recorded values.
//
// Three pixel sources (all panels 2304×3712, devFrac 0.75, backdrop 235,235,238):
//   src10    tools/mask-align-exp/assets10/paint.png (committed PNG; extract10 rHi=1.3)
//   src9s41  git 9a0aad0:assets9/paint.png + its regions.json (extract9 rHi=1.25;
//            the seed-41 generation — nonzero leak/ring counts make it the richest case)
//   src9s43  /private/tmp/skeuo-maskexp/assets9/paint.png (the seed-43 WINNER whose gate
//            verdicts are recorded in committed assets9/regions.json `gates`; the committed
//            paint.webp is lossy so the original PNG lives out-of-band — SOFT-SKIPPED when
//            absent so this suite stays green on other machines)
//
// Reference constants below were produced by /tmp-run of the VERBATIM python code
// (extract9.py/extract10.py/run9.py fits + gates wrapped in functions; scipy/numpy/PIL),
// dumped with full float precision. Python faithfulness was itself verified: recomputed
// seed-43 ring/shape verdicts and vol/bal seats matched the values recorded in committed
// assets9/regions.json exactly (seat maxDelta 0.0), and recomputed assets10 fits reproduce
// the committed assets10/regions.json device/seat entries bit-for-bit.
//
// Tolerances: fit centres/radii within one search-grid step (circle step 3px, rrect step
// 4px) — numpy means use pairwise summation vs our sequential loop, so a near-exact score
// tie could flip argmax by one step; everything integer (leak/ring pixel counts, emptiness
// floor) is asserted EXACTLY, and every PASS/FAIL verdict must be identical.

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import UPNG from "upng-js";
import {
  grayscale, gradientMag, circleFit, rrectFit, globalDrift,
  leakGate, emptinessGate, runStripGates,
} from "./maskAlign.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const EXP = path.join(repoRoot, "tools", "mask-align-exp");

// ---------------------------------------------------------------------------------------
// Python reference values (full precision; see header for provenance).
const REF = {
  src10: {
    dims: [2304, 3712],
    circle: {
      vol: { score: 46.42585955149102, cx: 832.0, cy: 2173.9999999999995, r: 123.05,
        device: [0.30770399305555557, 0.5525188577586205, 0.10681423611111111, 0.06629849137931035],
        seat: [0.3611111111111111, 0.5856681034482757, 0.05340711805555556] },
      bal: { score: 42.84787954319787, cx: 1460.9999999999998, cy: 2170.5, r: 126.225,
        device: [0.5793294270833332, 0.550720635775862, 0.10957031249999999, 0.06800915948275862],
        seat: [0.6341145833333333, 0.5847252155172413, 0.054785156249999994] },
    },
    drift: [-0.004991319444444444, 0.00013469827586206896],
    rrect: {
      tog: { score: 23.967633871053078, cx: 1147.5, cy: 2448.0, w: 214.11999999999995, h: 298.53,
        device: [0.45157986111111115, 0.6192712823275862, 0.09293402777777776, 0.0804229525862069] },
      seek: { score: 54.76292006164413, cx: 1115.5, cy: 1844.9999999999998, w: 903.9599999999999, h: 116.45,
        device: [0.2879861111111111, 0.48135102370689653, 0.39234375, 0.03137122844827586] },
    },
    leakCounts: { prev: 0, play: 0, next: 0, stop: 0, vol: 0, bal: 0, seek: 0, tog: 0, screen: 0 },
    emptiness: {
      vol: { brightFrac: 0.0, floor: 38.0, pass: true },
      bal: { brightFrac: 0.0, floor: 34.0, pass: true },
      seek: { brightFrac: 0.04, floor: 27.0, pass: true },
      tog: { brightFrac: 0.0, floor: 32.0, pass: true },
    },
    ring: {
      vol: { leak_colour: "-", px: 0, pass: true }, bal: { leak_colour: "-", px: 0, pass: true },
      seek: { leak_colour: "-", px: 0, pass: true }, tog_off: { leak_colour: "-", px: 0, pass: true },
      tog_on: { leak_colour: "-", px: 0, pass: true },
    },
    shape: {
      vol: { aspect: 1.003, fill: 0.77, expected: "round", pass: true },
      bal: { aspect: 1.007, fill: 0.773, expected: "round", pass: true },
      seek: { aspect: 1.626, fill: 0.873, expected: "landscape-pill", pass: true },
      tog_off: { aspect: 0.652, fill: 0.923, expected: "portrait", pass: true },
      tog_on: { aspect: 0.655, fill: 0.924, expected: "portrait", pass: true },
    },
  },
  src9s41: {
    dims: [2304, 3712],
    circle: {
      vol: { score: 33.5885842121929, cx: 737.0, cy: 1958.4999999999998, r: 129.975,
        device: [0.26346571180555556, 0.4925983297413793, 0.11282552083333333, 0.07002963362068965],
        seat: [0.3198784722222222, 0.5276131465517241, 0.056412760416666666] },
      bal: { score: 34.57399642249358, cx: 1551.0000000000002, cy: 1959.4999999999998, r: 129.625,
        device: [0.616916232638889, 0.49296201508620685, 0.1125217013888889, 0.06984105603448276],
        seat: [0.6731770833333335, 0.5278825431034482, 0.05626085069444445] },
    },
    drift: [-0.004774305555555556, -0.0017510775862068966],
    rrect: {
      tog: { score: 17.487039496843014, cx: 1142.5, cy: 2608.5, w: 306.28999999999996, h: 167.49999999999997 },
      seek: { score: 21.519288309412758, cx: 1100.0, cy: 2291.0, w: 755.16, h: 108.80999999999999 },
    },
    leakCounts: { prev: 0, play: 0, next: 0, stop: 0, vol: 0, bal: 0, seek: 0, tog: 15790, screen: 0 },
    emptiness: {
      vol: { brightFrac: 0.04289012336772239, floor: 22.0, pass: true },
      bal: { brightFrac: 0.0, floor: 22.0, pass: true },
      seek: { brightFrac: 0.04120051635111876, floor: 34.0, pass: true },
      tog: { brightFrac: 0.06752333616195902, floor: 37.0, pass: true },
    },
    ring: {
      vol: { leak_colour: "-", px: 0, pass: true }, bal: { leak_colour: "-", px: 0, pass: true },
      seek: { leak_colour: "-", px: 0, pass: true },
      tog_off: { leak_colour: "tog", px: 7854, pass: false },
      tog_on: { leak_colour: "tog", px: 14903, pass: false },
    },
    shape: {
      vol: { aspect: 0.962, fill: 0.774, expected: "round", pass: true },
      bal: { aspect: 0.961, fill: 0.791, expected: "round", pass: true },
      seek: { aspect: 1.353, fill: 0.857, expected: "landscape-pill", pass: true },
      tog_off: { aspect: 0.448, fill: 0.909, expected: "portrait", pass: true },
      tog_on: { aspect: 0.571, fill: 0.874, expected: "portrait", pass: true },
    },
  },
  src9s43: {
    dims: [2304, 3712],
    circle: {
      vol: { score: 6.789758026361671, cx: 820.4999999999999, cy: 2126.5, r: 123.44999999999999,
        device: [0.30253906249999996, 0.5396147629310345, 0.10716145833333332, 0.06651400862068965],
        seat: [0.35611979166666663, 0.5728717672413793, 0.05358072916666666] },
      bal: { score: 7.304323719953623, cx: 1458.5, cy: 2130.0, r: 134.925,
        device: [0.5744683159722223, 0.5374663254310345, 0.11712239583333334, 0.07269665948275862],
        seat: [0.6330295138888888, 0.5738146551724138, 0.05856119791666667] },
    },
    drift: [-0.010416666666666666, -0.0004040948275862069],
    rrect: {
      tog: { score: 11.493360013680194, cx: 1094.0, cy: 2583.0, w: 271.31999999999994, h: 410.96999999999986 },
      // seek regenerated 2026-07-08: the first reference run raced the groove-sliver repair
      // (paint.png rewritten mid-run at 18:56:11; ref run 18:53-18:57) and recorded a fit on
      // pre-repair groove pixels (7.808@w=1103). Re-run of the same verbatim python on the
      // stable post-repair paint gives this value, which the TS port matches to 4 ulp.
      seek: { score: 7.201699927281865, cx: 1248.4999999999998, cy: 1820.0000000000002, w: 801.55, h: 132.30999999999997 },
    },
    leakCounts: { prev: 0, play: 0, next: 0, stop: 0, vol: 0, bal: 0, seek: 0, tog: 0, screen: 0 },
    emptiness: {
      vol: { brightFrac: 0.0, floor: 31.0, pass: true },
      bal: { brightFrac: 0.00010082000268853341, floor: 32.0, pass: true },
      seek: { brightFrac: 0.0, floor: 37.0, pass: true },
      tog: { brightFrac: 0.0, floor: 15.0, pass: true },
    },
    ring: {
      vol: { leak_colour: "-", px: 0, pass: true }, bal: { leak_colour: "-", px: 0, pass: true },
      seek: { leak_colour: "-", px: 0, pass: true }, tog_off: { leak_colour: "-", px: 0, pass: true },
      tog_on: { leak_colour: "-", px: 0, pass: true },
    },
    shape: {
      vol: { aspect: 0.935, fill: 0.727, expected: "round", pass: true },
      bal: { aspect: 0.993, fill: 0.707, expected: "round", pass: true },
      seek: { aspect: 1.665, fill: 0.866, expected: "landscape-pill", pass: true },
      tog_off: { aspect: 0.627, fill: 0.935, expected: "portrait", pass: true },
      tog_on: { aspect: 0.634, fill: 0.929, expected: "portrait", pass: true },
    },
  },
};

// run9.py guide palette (assets9 sources); assets10 keys come from its regions.json.
const KEYS9 = [
  ["prev", [255, 90, 60]], ["play", [0, 120, 255]], ["next", [240, 180, 0]], ["stop", [170, 80, 255]],
  ["vol", [0, 190, 90]], ["bal", [0, 200, 220]], ["seek", [255, 140, 30]], ["tog", [255, 90, 160]],
  ["screen", [100, 255, 0]],
];
const CELLS = ["vol", "bal", "seek", "tog_off", "tog_on"].map((name, i) => ({
  name, fx: 0.11 + 0.195 * i,
  expect: { vol: "round", bal: "round", seek: "landscape-pill", tog_off: "portrait", tog_on: "portrait" }[name],
}));

// ---------------------------------------------------------------------------------------
function decodePNG(buf) {
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const img = UPNG.decode(ab);
  return { data: new Uint8ClampedArray(UPNG.toRGBA8(img)[0]), width: img.width, height: img.height };
}
const gitShow = (spec) =>
  execFileSync("git", ["show", spec], { maxBuffer: 64 * 1024 * 1024, cwd: repoRoot });

let failures = 0;
const row = (src, name, py, ts, delta, ok) => {
  if (!ok) failures++;
  console.log(
    `${(src + " " + name).padEnd(34)} py=${String(py).padEnd(22)} ts=${String(ts).padEnd(22)}` +
    ` Δ=${typeof delta === "number" ? delta.toExponential(2) : delta}  ${ok ? "OK" : "FAIL"}`,
  );
};
const close = (src, name, py, ts, tol) => row(src, name, py, ts, Math.abs(ts - py), Math.abs(ts - py) <= tol);
const equal = (src, name, py, ts) => row(src, name, py, ts, "-", Object.is(py, ts) || py === ts);

function runSource(label, paint, regions, ref, rHi, guideKeys, leakKeys) {
  const { data, width: W, height: H } = paint;
  equal(label, "dims.W", ref.dims[0], W);
  equal(label, "dims.H", ref.dims[1], H);
  const devFrac = regions.devFrac;
  const regs = regions.regions;

  const gm = gradientMag(grayscale({ data, width: W, height: H }), W, H);

  // circle fits + drift (extract9/10)
  const samples = [];
  const tsSeat = {};
  for (const k of ["vol", "bal"]) {
    const mb = regs[k].maskDevice;
    const f = circleFit(gm, W, H, mb, rHi);
    samples.push([f.cx - (mb[0] + mb[2] / 2) * W, f.cy - (mb[1] + mb[3] / 2) * H]);
    const r = ref.circle[k];
    close(label, `circle.${k}.cx px`, r.cx, f.cx, 3.5);
    close(label, `circle.${k}.cy px`, r.cy, f.cy, 3.5);
    close(label, `circle.${k}.r  px`, r.r, f.r, 3.5);
    row(label, `circle.${k}.score`, r.score, f.score, Math.abs(f.score - r.score) / r.score, true); // report-only
    tsSeat[k] = [f.cx / W, f.cy / H, f.r / W];
  }
  const [gdx, gdy] = globalDrift(samples, W, H);
  close(label, "drift.x norm", ref.drift[0], gdx, 3.5 / W);
  close(label, "drift.y norm", ref.drift[1], gdy, 3.5 / H);

  // rrect fits on maskDevice + TS drift (end-to-end: uses OUR drift, matches python's
  // pipeline exactly when the circle fits above landed on the same argmax)
  const tsRR = {};
  for (const k of ["tog", "seek"]) {
    const mb = regs[k].maskDevice;
    const f = rrectFit(gm, W, H, [mb[0] + gdx, mb[1] + gdy, mb[2], mb[3]]);
    const r = ref.rrect[k];
    close(label, `rrect.${k}.cx px`, r.cx, f.cx, 6);
    close(label, `rrect.${k}.cy px`, r.cy, f.cy, 6);
    close(label, `rrect.${k}.w  px`, r.w, f.w, 6);
    close(label, `rrect.${k}.h  px`, r.h, f.h, 6);
    row(label, `rrect.${k}.score`, r.score, f.score, Math.abs(f.score - r.score) / r.score, true); // report-only
    tsRR[k] = [(f.cx - f.w / 2) / W, (f.cy - f.h / 2) / H, f.w / W, f.h / H];
  }

  // leak gate — exact integer pixel counts per guide colour
  const leak = leakGate(paint, leakKeys.map(([name, rgb]) => ({ name, rgb })));
  for (const [name] of leakKeys) equal(label, `leak.${name} px`, ref.leakCounts[name], leak.counts[name]);

  // relative emptiness gate — exact floor, brightFrac to 1e-12, same verdict
  for (const k of ["vol", "bal", "seek", "tog"]) {
    const e = emptinessGate(paint, regs[k].device);
    const r = ref.emptiness[k];
    equal(label, `empty.${k}.floor`, r.floor, e.floor);
    close(label, `empty.${k}.brightFrac`, r.brightFrac, e.brightFrac, 1e-12);
    equal(label, `empty.${k}.pass`, r.pass, e.pass);
  }

  // per-cell ring + shape gates — exact px counts, identical verdicts
  const gates = runStripGates(paint, devFrac, CELLS,
    guideKeys.map(([name, rgb]) => ({ name, rgb })), [235, 235, 238]);
  for (const c of CELLS) {
    const rr = ref.ring[c.name], tr = gates.ring[c.name];
    equal(label, `ring.${c.name}.colour`, rr.leak_colour, tr.leakColour);
    equal(label, `ring.${c.name}.px`, rr.px, tr.px);
    equal(label, `ring.${c.name}.pass`, rr.pass, tr.pass);
    const rs = ref.shape[c.name], tsv = gates.shape[c.name];
    close(label, `shape.${c.name}.aspect`, rs.aspect, tsv.aspect, 6e-4); // ref rounded to 3dp
    close(label, `shape.${c.name}.fill`, rs.fill, tsv.fill, 6e-4);
    equal(label, `shape.${c.name}.expected`, rs.expected, tsv.expected);
    equal(label, `shape.${c.name}.pass`, rs.pass, tsv.pass);
  }

  // recorded regions.json cross-check — the values the python experiment SHIPPED
  const nt = 3.5 / W; // one circle-grid step, normalized
  for (const k of ["vol", "bal"]) {
    const rec = regs[k].seat;
    if (rec) for (let i = 0; i < 3; i++) close(label, `recorded.seat.${k}[${i}]`, rec[i], tsSeat[k][i], nt);
  }
  return { tsRR };
}

// --- src10: committed assets10 (extract10, rHi=1.3, palette-agnostic keys) --------------
{
  const paint = decodePNG(fs.readFileSync(path.join(EXP, "assets10", "paint.png")));
  const regions = JSON.parse(fs.readFileSync(path.join(EXP, "assets10", "regions.json"), "utf8"));
  const keys10 = Object.entries(regions.keys);
  const guides10 = ["vol", "bal", "seek", "tog"].map((k) => [k, regions.keys[k]]);
  const { tsRR } = runSource("src10", paint, regions, REF.src10, 1.3, guides10, keys10);
  // assets10 regions.json device entries ARE the python fit outputs — assert we reproduce them
  for (const k of ["seek", "tog"]) {
    const rec = regions.regions[k].device;
    for (let i = 0; i < 4; i++) close("src10", `recorded.device.${k}[${i}]`, rec[i], tsRR[k][i], 6 / 2304);
  }
}

// --- src9s41: the 9a0aad0 generation (extract9, rHi=1.25, walkman palette) ---------------
{
  const paint = decodePNG(gitShow("9a0aad0:tools/mask-align-exp/assets9/paint.png"));
  const regions = JSON.parse(gitShow("9a0aad0:tools/mask-align-exp/assets9/regions.json").toString("utf8"));
  runSource("src9s41", paint, regions, REF.src9s41, 1.25, KEYS9.slice(4, 8), KEYS9);
}

// --- src9s43: seed-43 winner (out-of-band PNG; committed regions.json records its gates) --
{
  const p43 = "/private/tmp/skeuo-maskexp/assets9/paint.png";
  if (!fs.existsSync(p43)) {
    console.log("src9s43: SKIPPED — seed-43 original PNG not present at " + p43);
  } else {
    const paint = decodePNG(fs.readFileSync(p43));
    const regions = JSON.parse(fs.readFileSync(path.join(EXP, "assets9", "regions.json"), "utf8"));
    runSource("src9s43", paint, regions, REF.src9s43, 1.25, KEYS9.slice(4, 8), KEYS9);
    // the committed `gates` object is the experiment's recorded verdict for this paint —
    // re-derive it with the TS port and require identity
    const gates = runStripGates(paint, regions.devFrac, CELLS,
      KEYS9.slice(4, 8).map(([name, rgb]) => ({ name, rgb })), [235, 235, 238]);
    for (const c of CELLS) {
      const rr = regions.gates.ring[c.name];
      equal("src9s43", `gates.ring.${c.name}`, `${rr.leak_colour}/${rr.px}/${rr.pass}`,
        `${gates.ring[c.name].leakColour}/${gates.ring[c.name].px}/${gates.ring[c.name].pass}`);
      const rs = regions.gates.shape[c.name];
      const tv = gates.shape[c.name];
      const okA = Math.abs(rs.aspect - tv.aspect) <= 6e-4 && Math.abs(rs.fill - tv.fill) <= 6e-4;
      row("src9s43", `gates.shape.${c.name}`, `${rs.aspect}/${rs.fill}/${rs.pass}`,
        `${tv.aspect.toFixed(4)}/${tv.fill.toFixed(4)}/${tv.pass}`, "-", okA && rs.pass === tv.pass);
    }
  }
}

console.log(failures === 0 ? "\nmaskAlign.test.mjs: ALL PASS" : `\nmaskAlign.test.mjs: ${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
