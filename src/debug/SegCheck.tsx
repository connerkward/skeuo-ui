// DEV-ONLY (?segcheck): validate the REAL per-sprite segmentation across ALL skins.
// For each cached matte (public/seg-cache, produced once by /tmp/seg_cache_all.py) it runs
// the ACTUAL exported segmentStripByComponents() — the shipping function, not a proxy — and
// renders every captured sprite labeled, with a per-skin pass/fail header (captured/N + any
// missing binds). Fresh (label-less) and old (labeled) skins both, sorted labeled-last.
import { useEffect, useRef, useState } from "react";
import { blobToCanvas, segmentStripByComponents } from "../generate/cutoutClient";
import type { BlueprintLayout } from "../generate/blueprint";

const CHK = "conic-gradient(#3a3a3a 90deg,#2a2a2a 0 180deg,#3a3a3a 0 270deg,#2a2a2a 0) 0 0/14px 14px";

interface ManifestRow { id: string; labeled: boolean; ncells: number; error?: string }
interface Sprite { bind: string; kind: string; url: string | null; w: number; h: number }
interface SkinResult { id: string; labeled: boolean; matteUrl: string; sprites: Sprite[]; captured: number; total: number; missing: string[] }

export default function SegCheck() {
  const [rows, setRows] = useState<SkinResult[]>([]);
  const [status, setStatus] = useState("loading manifest…");
  const [filter, setFilter] = useState<"all" | "fail" | "labeled" | "fresh">("all");
  const started = useRef(false);

  useEffect(() => { if (started.current) return; started.current = true; void run(); /* eslint-disable-next-line */ }, []);

  async function run() {
    const manifest = (await fetch("/seg-cache/manifest.json").then((r) => r.json()).catch(() => [])) as ManifestRow[];
    if (!manifest.length) { setStatus("no manifest — run /tmp/seg_cache_all.py first"); return; }
    setStatus(`segmenting ${manifest.length} skins (real segmentStripByComponents)…`);
    let done = 0;
    for (const m of manifest) {
      try {
        const matteUrl = `/seg-cache/${m.id}-matte.png`;
        const [matteCanvas, layout] = await Promise.all([
          fetch(matteUrl).then((r) => r.blob()).then(blobToCanvas),
          fetch(`/seg-cache/${m.id}-layout.json`).then((r) => r.json() as Promise<BlueprintLayout>),
        ]);
        const seg = segmentStripByComponents(matteCanvas, layout.cells);
        const sprites: Sprite[] = layout.cells.map((c) => {
          const cv = seg[c.bind];
          return { bind: c.bind, kind: c.kind, url: cv ? cv.toDataURL("image/png") : null, w: cv?.width ?? 0, h: cv?.height ?? 0 };
        });
        const missing = sprites.filter((s) => !s.url).map((s) => s.bind);
        setRows((prev) => [...prev, {
          id: m.id, labeled: m.labeled, matteUrl, sprites,
          captured: sprites.length - missing.length, total: sprites.length, missing,
        }]);
      } catch (e) {
        setRows((prev) => [...prev, { id: m.id, labeled: m.labeled, matteUrl: "", sprites: [], captured: 0, total: m.ncells, missing: [`ERROR: ${e instanceof Error ? e.message : e}`] }]);
      }
      done++; setStatus(`segmented ${done}/${manifest.length}`);
    }
    setStatus(`done — ${done} skins`);
  }

  const shown = rows.filter((r) =>
    filter === "all" ? true : filter === "fail" ? r.missing.length > 0 : filter === "labeled" ? r.labeled : !r.labeled);
  const fails = rows.filter((r) => r.missing.length > 0).length;

  return (
    <div style={{ background: "#0d0e10", color: "#eee", minHeight: "100vh", padding: "16px clamp(12px,3vw,36px)", font: "13px ui-monospace,Menlo,monospace" }}>
      <h1 style={{ fontSize: 20, margin: "0 0 2px" }}>Per-sprite segmentation — validation across ALL skins</h1>
      <div style={{ opacity: 0.65, marginBottom: 10, maxWidth: "90ch" }}>
        Runs the REAL <code>segmentStripByComponents()</code> (connected components → nearest-cell → union) on every
        cached BiRefNet matte (<code>fal-ai/birefnet/v2 · Heavy</code>). Each tile = one captured sprite on checker,
        labeled by bind. A skin is a <b>fail</b> if any control captured no component (grid-crop fallback would run).
      </div>
      <div style={{ marginBottom: 14, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <b>{status}</b>
        <span style={{ opacity: 0.7 }}>· {rows.length} loaded · <span style={{ color: fails ? "#ff6b6b" : "#7CFF4F" }}>{fails} with missing</span></span>
        {(["all", "fail", "fresh", "labeled"] as const).map((f) => (
          <button key={f} onClick={() => setFilter(f)} style={{ background: filter === f ? "#2b6cff" : "#23262b", color: "#fff", border: "none", borderRadius: 6, padding: "3px 9px", cursor: "pointer", font: "inherit" }}>{f}</button>
        ))}
      </div>
      {shown.map((r) => (
        <section key={r.id} style={{ border: `1px solid ${r.missing.length ? "#5a2a2a" : "#2a2c30"}`, borderRadius: 10, marginBottom: 14, overflow: "hidden" }}>
          <header style={{ background: "#16181b", padding: "7px 12px", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <b>…{r.id.slice(-26)}</b>
            <span style={{ fontSize: 10, padding: "1px 7px", borderRadius: 10, background: r.labeled ? "#5a4a1f" : "#1f5a3a" }}>{r.labeled ? "labeled (old)" : "fresh"}</span>
            <span style={{ color: r.missing.length ? "#ff6b6b" : "#7CFF4F" }}>{r.captured}/{r.total} captured</span>
            {r.missing.length > 0 && <span style={{ color: "#ff8a8a" }}>missing: {r.missing.join(", ")}</span>}
          </header>
          <div style={{ padding: 10 }}>
            {r.matteUrl && <div style={{ marginBottom: 8 }}><div style={{ opacity: 0.5, fontSize: 10, marginBottom: 3 }}>matted strip (BiRefNet)</div><div style={{ background: CHK, borderRadius: 4, display: "inline-block", maxWidth: "100%" }}><img src={r.matteUrl} style={{ maxWidth: "100%", maxHeight: 110, display: "block" }} /></div></div>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(120px,1fr))", gap: 8 }}>
              {r.sprites.map((s, i) => (
                <figure key={s.bind + i} style={{ margin: 0, border: "1px solid #2a2c30", borderRadius: 6, overflow: "hidden", background: "#16181b" }}>
                  <div style={{ height: 90, display: "grid", placeItems: "center", background: CHK }}>
                    {s.url ? <img src={s.url} style={{ maxWidth: "86%", maxHeight: "86%" }} /> : <span style={{ color: "#ff6b6b", fontSize: 18 }}>—</span>}
                  </div>
                  <figcaption style={{ padding: "4px 6px", fontSize: 10.5 }}><b>{s.bind}</b> · {s.kind}<br /><span style={{ opacity: 0.5 }}>{s.url ? `${s.w}×${s.h}` : "no component → grid fallback"}</span></figcaption>
                </figure>
              ))}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
