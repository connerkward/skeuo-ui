// DEV-ONLY live pipeline view (mounted on ?cutcompare and ?pipeline). Shows EVERY stage
// of the skin pipeline as an interactive artifact, with per-stage loading spinners, using
// the REAL shipping functions (combinedBlueprint, serverCutout/BiRefNet, cutFromTransparentStrip,
// /api/extract) — not proxies. The sprite-isolation stage BRANCHES into approaches (BiRefNet
// light vs heavy). ?id=<substr> picks the skin; default = newest.
import { useEffect, useState } from "react";
import {
  fetchPaintCanvas, cropDevice, cropStrip, serverCutout, blobToCanvas, cutFromTransparentStrip,
} from "../generate/cutoutClient";
import { combinedBlueprint, type BlueprintLayout } from "../generate/blueprint";
import { apiUrl } from "../platform";
import type { Template, Region } from "../template/schema";

type Status = "pending" | "loading" | "done" | "error";
type Cv = HTMLCanvasElement;
const CHECKER = "conic-gradient(#3a3a3a 90deg,#2a2a2a 0 180deg,#3a3a3a 0 270deg,#2a2a2a 0) 0 0/16px 16px";

const dataUrl = (c: Cv) => c.toDataURL("image/png");

interface SpriteCut { bind: string; kind: string; light: string; heavy: string; lw: number; lh: number }
interface Box { bind: string; x: number; y: number; w: number; h: number; conf?: number }

export default function Pipeline() {
  const [id, setId] = useState("");
  const [prompt, setPrompt] = useState(""); const [model, setModel] = useState("");
  const [st, setSt] = useState<Record<string, Status>>({});
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

    // 1. PACKED BLUEPRINT (recompute the real combinedBlueprint from the template)
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

    // 5. SPRITE ISOLATION — branched (light vs heavy), real cutFromTransparentStrip
    set("isolation", "loading");
    const cutFrom = (ts: Cv | null, cr: [number, number, number, number]): Cv | null => {
      if (!ts) return null;
      const fx = ts.width / W, fy = ts.height / stripHOrig;
      const [nx, ny, nw, nh] = cr;
      return cutFromTransparentStrip(ts, nx * W * fx, (ny * H - syOrig) * fy, nw * W * fx, nh * H * fy);
    };
    const out: SpriteCut[] = [];
    for (const cell of layout.cells) {
      const l = cutFrom(tLight, cell.cellRect), h = cutFrom(tHeavy, cell.cellRect);
      out.push({ bind: cell.bind, kind: cell.kind, light: l ? dataUrl(l) : "", heavy: h ? dataUrl(h) : "", lw: l?.width ?? 0, lh: l?.height ?? 0 });
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

      // 7. FINAL — device frame + each isolated sprite placed at its snapped box (or template rect)
      set("final", "loading");
      const byId = new Map(boxes.map((b) => [b.bind, b] as const));
      const fin = document.createElement("canvas"); fin.width = frame.width; fin.height = frame.height;
      const fc = fin.getContext("2d")!; fc.drawImage(frame, 0, 0);
      for (const cell of layout.cells) {
        const sprite = cutFrom(tLight, cell.cellRect); if (!sprite) continue;
        const r = template.regions.find((x) => x.id === cell.bind) as Region | undefined;
        const box = byId.get(cell.bind);
        const rect = box ? { x: box.x, y: box.y, w: box.w, h: box.h } : (r ? r.rect : null);
        if (!rect) continue;
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
      <Stage n={2} title="Packed blueprint (device sockets + control slots)" status={st.blueprint}>
        {blueprintUrl && <img src={blueprintUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6, background: "#fff" }} />}
      </Stage>
      <Stage n={3} title="Painted sprite sheet (device + strip)" status={st.paint}>
        {paintUrl && <img src={paintUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6 }} />}
      </Stage>
      <Stage n={4} title="BiRefNet — device frame (background removed)" status={st.frame}>
        {frameUrl && <img src={frameUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6, background: CHECKER }} />}
      </Stage>
      <Stage n={5} title="BiRefNet — whole strip isolated (light · heavy branches)" status={st.strip}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div><div style={{ opacity: 0.55, fontSize: 11 }}>light (default)</div>{stripLightUrl && <img src={stripLightUrl} style={{ maxWidth: 520, width: "100%", borderRadius: 6, background: CHECKER }} />}</div>
          <div><div style={{ opacity: 0.55, fontSize: 11 }}>heavy (low-contrast tune)</div>{stripHeavyUrl && <img src={stripHeavyUrl} style={{ maxWidth: 520, width: "100%", borderRadius: 6, background: CHECKER }} />}</div>
        </div>
      </Stage>
      <Stage n={6} title="Sprite isolation — per control, BRANCHED (light vs heavy)" status={st.isolation}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 12 }}>
          {cuts.map((c) => (
            <figure key={c.bind} style={{ margin: 0, border: "1px solid #2a2c30", borderRadius: 6, overflow: "hidden", background: "#16181b" }}>
              <div style={{ display: "flex" }}>
                {(["light", "heavy"] as const).map((k) => (
                  <div key={k} style={{ flex: 1, height: 100, display: "grid", placeItems: "center", background: CHECKER, borderRight: k === "light" ? "1px solid #000" : "none" }}>
                    {c[k] ? <img src={c[k]} style={{ maxWidth: "88%", maxHeight: "88%" }} /> : <span style={{ color: "#ff6b6b", fontSize: 9 }}>—</span>}
                  </div>
                ))}
              </div>
              <figcaption style={{ padding: "5px 7px", fontSize: 11 }}><b>{c.bind}</b> · {c.kind}<br /><span style={{ opacity: 0.5 }}>light {c.lw}×{c.lh} · heavy</span></figcaption>
            </figure>
          ))}
        </div>
      </Stage>
      <Stage n={7} title="VLM snap/warp — gpt-4o control boxes on the device" status={st.vlm}>
        {vlmUrl && <img src={vlmUrl} style={{ maxWidth: 360, width: "100%", borderRadius: 6, background: CHECKER }} />}
      </Stage>
      <Stage n={8} title="Final — isolated sprites placed on the skin" status={st.final}>
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
