// DEV-ONLY live pipeline view (mounted on ?cutcompare and ?pipeline). Shows EVERY stage
// of the skin pipeline as an interactive artifact, with per-stage loading spinners, using
// the REAL shipping functions (combinedBlueprint, serverCutout/BiRefNet, cutFromTransparentStrip,
// /api/extract) — not proxies. The sprite-isolation stage BRANCHES into approaches (BiRefNet
// light vs heavy). ?id=<substr> picks the skin; default = newest.
import { useEffect, useState } from "react";
import {
  fetchPaintCanvas, cropDevice, cropStrip, serverCutout, blobToCanvas, cutFromTransparentStrip,
  segmentStripByComponents,
} from "../generate/cutoutClient";
import { combinedBlueprint, type BlueprintLayout } from "../generate/blueprint";
import { apiUrl } from "../platform";
import type { Template, Region } from "../template/schema";

type Status = "pending" | "loading" | "done" | "error";
type Cv = HTMLCanvasElement;
const CHECKER = "conic-gradient(#3a3a3a 90deg,#2a2a2a 0 180deg,#3a3a3a 0 270deg,#2a2a2a 0) 0 0/16px 16px";

const dataUrl = (c: Cv) => c.toDataURL("image/png");

interface SpriteCut { bind: string; kind: string; cc: string; grid: string; w: number; h: number; fell: boolean }
interface Box { bind: string; x: number; y: number; w: number; h: number; conf?: number }

export default function Pipeline() {
  const [id, setId] = useState("");
  const [prompt, setPrompt] = useState(""); const [model, setModel] = useState("");
  const [st, setSt] = useState<Record<string, Status>>({});
  const [templateUrl, setTemplateUrl] = useState("");
  const [blueprintUrl, setBlueprintUrl] = useState("");
  const [paintUrl, setPaintUrl] = useState("");
  const [frameUrl, setFrameUrl] = useState("");
  const [stripLightUrl, setStripLightUrl] = useState("");
  const [stripHeavyUrl, setStripHeavyUrl] = useState("");
  const [cuts, setCuts] = useState<SpriteCut[]>([]);
  const [vlmUrl, setVlmUrl] = useState("");        // device + boxes overlay
  const [finalUrl, setFinalUrl] = useState("");    // device + placed sprites
  const set = (k: string, s: Status) => setSt((p) => ({ ...p, [k]: s }));

  useEffect(() => { void run(); /* eslint-disable-next-line */ }, []);

  async function run() {
    const all = (await fetch("/api/dev/gens").then((r) => r.json())).ids as string[];
    const want = new URLSearchParams(location.search).get("id") || "";
    const gid = all.find((x) => x.includes(want)) || all[0];
    if (!gid) return;
    setId(gid);
    const base = `/generated/${gid}`;
    const [layout, template, meta] = await Promise.all([
      fetch(`${base}-layout.json`).then((r) => r.json() as Promise<BlueprintLayout>),
      fetch(`${base}-template.json`).then((r) => r.json() as Promise<Template>),
      fetch(`${base}-meta.json`).then((r) => r.json()).catch(() => ({})),
    ]);
    setPrompt((meta as { prompt?: string }).prompt ?? gid);
    setModel((meta as { model?: string }).model ?? "?");

    // 1. TEMPLATE — the control layout (regions) as a labeled diagram (device 2:3)
    set("template", "loading");
    try {
      const tW = 400, tH = 600;
      const KC: Record<string, string> = { button: "#5bd3ff", knob: "#ffb454", toggle: "#b68cff", "slider-h": "#5fffa0", "slider-v": "#5fffa0", "slider-arc": "#5fffa0", display: "#888", segmented: "#ff9a5b", xy: "#ff7a7a" };
      const rects = template.regions.map((r) => {
        const c = KC[r.kind] || "#aaa";
        const x = r.rect.x * tW, y = r.rect.y * tH, w = r.rect.w * tW, h = r.rect.h * tH;
        const lbl = (r.bind || r.id).replace(/[<>&]/g, "");
        return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="6" fill="${c}33" stroke="${c}" stroke-width="2"/>`
          + `<text x="${(x + 4).toFixed(1)}" y="${(y + 15).toFixed(1)}" font-size="12" fill="${c}" font-family="ui-monospace,monospace">${lbl}</text>`;
      }).join("");
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${tW}" height="${tH}" viewBox="0 0 ${tW} ${tH}"><rect width="100%" height="100%" fill="#16181b"/>${rects}</svg>`;
      setTemplateUrl(`data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`);
      set("template", "done");
    } catch { set("template", "error"); }

    // 2. PACKED BLUEPRINT (recompute the real combinedBlueprint from the template)
    set("blueprint", "loading");
    try { setBlueprintUrl(`data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(combinedBlueprint(template.regions).svg)))}`); set("blueprint", "done"); }
    catch { set("blueprint", "error"); }

    // 2. PAINTED SHEET
    set("paint", "loading");
    setPaintUrl(`${base}-paint.png`); set("paint", "done");
    const paint = await fetchPaintCanvas(`${base}-paint.png`);
    const W = paint.width, H = paint.height;
    const syOrig = Math.round(H * layout.devFrac), stripHOrig = Math.max(1, H - syOrig);

    // 3. BiRefNet — device frame
    set("frame", "loading");
    let frame: Cv | null = null;
    try { frame = await blobToCanvas(await serverCutout(cropDevice(paint, layout.devFrac))); setFrameUrl(dataUrl(frame)); set("frame", "done"); }
    catch { set("frame", "error"); }

    // 4. BiRefNet — whole strip (light + heavy branches)
    set("strip", "loading");
    const strip = cropStrip(paint, layout.devFrac);
    let tLight: Cv | null = null, tHeavy: Cv | null = null;
    try { tLight = await blobToCanvas(await serverCutout(strip)); setStripLightUrl(dataUrl(tLight)); } catch { /* */ }
    try { tHeavy = await blobToCanvas(await serverCutout(strip, "General Use (Heavy)")); setStripHeavyUrl(dataUrl(tHeavy)); } catch { /* */ }
    set("strip", tLight || tHeavy ? "done" : "error");

    // chosen sprite per control (CC primary, grid fallback) — reused by the final composite
    const finalSprites: Record<string, Cv | null> = {};

    // 5. SPRITE ISOLATION — the SHIPPING method: connected-component segmentation of the
    // whole matted strip (segmentStripByComponents), with the old per-cell grid crop shown
    // alongside for comparison + used as the fallback when a cell captures no component.
    set("isolation", "loading");
    const cutFrom = (ts: Cv | null, cr: [number, number, number, number]): Cv | null => {
      if (!ts) return null;
      const fx = ts.width / W, fy = ts.height / stripHOrig;
      const [nx, ny, nw, nh] = cr;
      return cutFromTransparentStrip(ts, nx * W * fx, (ny * H - syOrig) * fy, nw * W * fx, nh * H * fy);
    };
    const seg = tHeavy ? segmentStripByComponents(tHeavy, layout.cells) : {};
    const out: SpriteCut[] = [];
    for (const cell of layout.cells) {
      const ccCv = (seg[cell.bind] ?? null) as Cv | null;
      const gridCv = cutFrom(tHeavy, cell.cellRect);
      const chosen = ccCv ?? gridCv;            // ship logic: CC primary, grid fallback
      finalSprites[cell.bind] = chosen;
      out.push({ bind: cell.bind, kind: cell.kind, cc: ccCv ? dataUrl(ccCv) : "", grid: gridCv ? dataUrl(gridCv) : "", w: chosen?.width ?? 0, h: chosen?.height ?? 0, fell: !ccCv });
      setCuts([...out]);
    }
    set("isolation", "done");

    // 6. VLM SNAP/WARP — /api/extract → boxes overlaid on the device frame
    set("vlm", "loading");
    try {
      if (!frame) throw new Error("no frame");
      const ALIGN = new Set(["button", "toggle", "slider-h", "slider-v", "knob", "slider-arc", "segmented", "xy", "display"]);
      const controls = template.regions.filter((r) => ALIGN.has(r.kind)).map((r) => ({ bind: r.id, kind: r.kind, label: r.label || r.bind }));
      const bg = document.createElement("canvas"); bg.width = frame.width; bg.height = frame.height;
      const bx = bg.getContext("2d")!; bx.fillStyle = "#808080"; bx.fillRect(0, 0, bg.width, bg.height); bx.drawImage(frame, 0, 0);
      const resp = await fetch(apiUrl("/api/extract"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ imageDataUrl: bg.toDataURL("image/png"), controls }) });
      const boxes = ((await resp.json()) as { boxes: Box[] }).boxes ?? [];
      // overlay
      const ov = document.createElement("canvas"); ov.width = frame.width; ov.height = frame.height;
      const oc = ov.getContext("2d")!; oc.drawImage(frame, 0, 0);
      oc.lineWidth = 4; oc.font = "bold 22px ui-monospace, monospace";
      for (const b of boxes) {
        const x = b.x * ov.width, y = b.y * ov.height, w = b.w * ov.width, h = b.h * ov.height;
        oc.strokeStyle = "#19e0ff"; oc.strokeRect(x, y, w, h);
        const lbl = `${b.bind}${b.conf != null ? ` ${b.conf.toFixed(2)}` : ""}`;
        const tw = oc.measureText(lbl).width;
        oc.fillStyle = "rgba(0,0,0,0.78)"; oc.fillRect(x, y - 26, tw + 10, 26);
        oc.fillStyle = "#19e0ff"; oc.fillText(lbl, x + 4, y - 6);
      }
      setVlmUrl(dataUrl(ov)); set("vlm", "done");

      // 7. FINAL — device frame + each isolated sprite placed at its DETERMINISTIC TEMPLATE rect.
      // VLM boxes are NOT used for placement: the painted device has empty sockets, so the VLM has
      // nothing to detect/snap to. Placement is driven entirely by template.regions[].rect.
      set("final", "loading");
      const fin = document.createElement("canvas"); fin.width = frame.width; fin.height = frame.height;
      const fc = fin.getContext("2d")!; fc.drawImage(frame, 0, 0);
      for (const cell of layout.cells) {
        const sprite = finalSprites[cell.bind]; if (!sprite) continue;
        const r = template.regions.find((x) => x.id === cell.bind) as Region | undefined;
        if (!r) continue;
        const rect = r.rect;
        fc.drawImage(sprite, rect.x * fin.width, rect.y * fin.height, rect.w * fin.width, rect.h * fin.height);
      }
      setFinalUrl(dataUrl(fin)); set("final", "done");
    } catch { set("vlm", "error"); set("final", "error"); }
  }

  return (
    <div style={{ background: "#0d0e10", color: "#eee", minHeight: "100vh", padding: "16px clamp(12px,3vw,40px)", font: "13px ui-monospace, Menlo, monospace" }}>
      <h1 style={{ fontSize: 19, margin: "0 0 2px" }}>Skin pipeline — live · {id}</h1>
      <div style={{ opacity: 0.6, marginBottom: 16 }}>{prompt} · <span style={{ color: "#5BE0C0" }}>{model}</span> · ?id=&lt;substr&gt;</div>

      <Stage n={1} title="Prompt" status="done"><div style={{ padding: 12, fontSize: 14 }}>“{prompt}”</div></Stage>
      <Stage n={2} title="Template — control layout (regions on the 2:3 device)" status={st.template}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
          {templateUrl && <img src={templateUrl} style={{ maxWidth: 300, width: "100%", borderRadius: 6, border: "1px solid #2a2c30" }} />}
          <TemplateLegend />
        </div>
      </Stage>
      <Stage n={3} title="Packed blueprint (device sockets + control slots, on 9:16)" status={st.blueprint}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
          {blueprintUrl && <img src={blueprintUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6, background: "#fff" }} />}
          <BlueprintLegend />
        </div>
      </Stage>
      <Stage n={4} title="Painted sprite sheet (device + strip)" status={st.paint}>
        {paintUrl && <img src={paintUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6 }} />}
      </Stage>
      <Stage n={5} title="BiRefNet — device frame (background removed)" status={st.frame}>
        {frameUrl && <img src={frameUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6, background: CHECKER }} />}
      </Stage>
      <Stage n={6} title="BiRefNet — whole strip isolated (heavy model)" status={st.strip}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div><div style={{ opacity: 0.55, fontSize: 11 }}>light (default)</div>{stripLightUrl && <img src={stripLightUrl} style={{ maxWidth: 520, width: "100%", borderRadius: 6, background: CHECKER }} />}</div>
          <div><div style={{ opacity: 0.55, fontSize: 11 }}>heavy (low-contrast tune)</div>{stripHeavyUrl && <img src={stripHeavyUrl} style={{ maxWidth: 520, width: "100%", borderRadius: 6, background: CHECKER }} />}</div>
        </div>
      </Stage>
      <Stage n={7} title="Sprite isolation — connected components (SHIP) vs grid (fallback)" status={st.isolation}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 12 }}>
          {cuts.map((c) => (
            <figure key={c.bind} style={{ margin: 0, border: `1px solid ${c.fell ? "#5a4a1f" : "#2a2c30"}`, borderRadius: 6, overflow: "hidden", background: "#16181b" }}>
              <div style={{ display: "flex" }}>
                {(["cc", "grid"] as const).map((k) => (
                  <div key={k} style={{ flex: 1, position: "relative", height: 100, display: "grid", placeItems: "center", background: CHECKER, borderRight: k === "cc" ? "1px solid #000" : "none" }}>
                    <span style={{ position: "absolute", top: 2, left: 3, fontSize: 8, opacity: 0.7, color: k === "cc" ? "#7CFF4F" : "#ffd27a" }}>{k === "cc" ? "CC (ship)" : "grid"}</span>
                    {c[k] ? <img src={c[k]} style={{ maxWidth: "88%", maxHeight: "88%" }} /> : <span style={{ color: "#ff6b6b", fontSize: 9 }}>—</span>}
                  </div>
                ))}
              </div>
              <figcaption style={{ padding: "5px 7px", fontSize: 11 }}><b>{c.bind}</b> · {c.kind}<br /><span style={{ opacity: 0.5 }}>{c.w}×{c.h} · {c.fell ? "grid fallback" : "connected-component"}</span></figcaption>
            </figure>
          ))}
        </div>
      </Stage>
      <Stage n={8} title="Placement — deterministic template positions (VLM snap DEPRECATED)" status={st.vlm}>
        <div style={{ fontSize: 12, opacity: 0.8, marginBottom: vlmUrl ? 10 : 0, lineHeight: 1.5, maxWidth: 560 }}>
          VLM snap is <b>no longer load-bearing</b> for placement. The painted device has <b>empty sockets</b>
          (no controls drawn into it), so gpt-4o has nothing to detect or snap to — every box it returns is a
          guess on a blank surface. Placement (stage 8) now uses the <b>deterministic template rects</b>
          (<code>template.regions[].rect</code>) instead. The /api/extract call below is kept only as a debug
          overlay; its boxes are <b>ignored</b>.
        </div>
        {vlmUrl && <img src={vlmUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6, background: CHECKER }} />}
      </Stage>
      <Stage n={9} title="Final — isolated sprites placed at template rects on the skin" status={st.final}>
        {finalUrl && <img src={finalUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6, background: CHECKER }} />}
      </Stage>
    </div>
  );
}

function Stage({ n, title, status, children }: { n: number; title: string; status?: Status; children: React.ReactNode }) {
  const dot = status === "done" ? "#7CFF4F" : status === "loading" ? "#ffd27a" : status === "error" ? "#ff6b6b" : "#555";
  return (
    <section style={{ border: "1px solid #2a2c30", borderRadius: 10, marginBottom: 14, overflow: "hidden" }}>
      <header style={{ background: "#16181b", padding: "8px 12px", display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 22, height: 22, borderRadius: 11, background: "#23262b", display: "grid", placeItems: "center", fontSize: 11 }}>{n}</span>
        <b style={{ flex: 1 }}>{title}</b>
        {status === "loading"
          ? <span className="pipe-spin" style={{ width: 14, height: 14, border: "2px solid #ffd27a", borderTopColor: "transparent", borderRadius: "50%", display: "inline-block" }} />
          : <span style={{ width: 10, height: 10, borderRadius: 5, background: dot }} />}
      </header>
      <div style={{ padding: 12 }}>{children}</div>
      <style>{"@keyframes pipe-rot{to{transform:rotate(360deg)}} .pipe-spin{animation:pipe-rot .8s linear infinite}"}</style>
    </section>
  );
}

function TemplateLegend() {
  const rows: { color: string; label: string }[] = [
    { color: "#5bd3ff", label: "button" },
    { color: "#ffb454", label: "knob" },
    { color: "#b68cff", label: "toggle" },
    { color: "#5fffa0", label: "slider / seek" },
    { color: "#888", label: "display / screen" },
    { color: "#ff9a5b", label: "segmented" },
    { color: "#ff7a7a", label: "xy pad" },
  ];
  return (
    <div style={{ border: "1px solid #2a2c30", borderRadius: 8, background: "#16181b", padding: "10px 12px", fontSize: 11.5, lineHeight: 1.4, minWidth: 200, maxWidth: 280 }}>
      <div style={{ fontWeight: 700, marginBottom: 8, opacity: 0.85 }}>Control kinds</div>
      <div style={{ display: "grid", gap: 6 }}>
        {rows.map((r) => (
          <div key={r.label} style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ width: 14, height: 14, borderRadius: 3, background: `${r.color}33`, border: `2px solid ${r.color}`, boxSizing: "border-box" }} />
            <span><b style={{ color: r.color }}>{r.label}</b></span>
          </div>
        ))}
      </div>
      <div style={{ opacity: 0.55, marginTop: 8, fontSize: 10.5 }}>each box = a control region at its template rect (bind labelled). Sliders/seek are device/CSS — not cut as sprites.</div>
    </div>
  );
}

function BlueprintLegend() {
  const rows: { color: string; ring?: boolean; label: string; desc: string }[] = [
    { color: "rgb(255,40,120)", ring: true, label: "magenta ring", desc: "control socket anchor — where a control goes" },
    { color: "rgb(218,218,224)", label: "faint grey shape", desc: "device body silhouette" },
    { color: "#2a2c30", label: "dark rounded bars", desc: "recessed screens / displays" },
    { color: "transparent", label: "blank bottom band", desc: "the (label-less) control strip — bare control parts get painted here" },
  ];
  return (
    <div style={{ border: "1px solid #2a2c30", borderRadius: 8, background: "#16181b", padding: "10px 12px", fontSize: 11.5, lineHeight: 1.4, minWidth: 240, maxWidth: 320 }}>
      <div style={{ fontWeight: 700, marginBottom: 8, opacity: 0.85 }}>Legend</div>
      <div style={{ display: "grid", gap: 8 }}>
        {rows.map((r) => (
          <div key={r.label} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <span
              style={{
                flex: "0 0 auto", width: 14, height: 14, marginTop: 1, borderRadius: 3,
                background: r.ring ? "transparent" : r.color,
                border: r.ring ? `3px solid ${r.color}` : (r.color === "transparent" ? "1px dashed #6a6c70" : "1px solid rgba(255,255,255,0.15)"),
                boxSizing: "border-box",
              }}
            />
            <span><b>{r.label}</b> — <span style={{ opacity: 0.75 }}>{r.desc}</span></span>
          </div>
        ))}
      </div>
    </div>
  );
}
