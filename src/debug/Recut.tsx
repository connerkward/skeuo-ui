// DEV-ONLY: run the REAL shipping finishCutoutFull on a saved generation and show its
// actual output (device frame + each cut sprite). This exercises the exact code that
// ships (BiRefNet device cutout + BiRefNet strip isolation + neighbour-drop + heavy
// retry + uploads) — not a proxy. Mounted on ?recut=<id substr>.
import { useEffect, useState } from "react";
import { finishCutoutFull, type FinishResult } from "../generate/cutoutClient";
import type { BlueprintLayout } from "../generate/blueprint";
import type { Template } from "../template/schema";

const CHECKER = "conic-gradient(#3a3a3a 90deg,#2a2a2a 0 180deg,#3a3a3a 0 270deg,#2a2a2a 0) 0 0/18px 18px";

export default function Recut() {
  const [log, setLog] = useState<string[]>([]);
  const [res, setRes] = useState<FinishResult | null>(null);
  const [id, setId] = useState("");
  const add = (s: string) => setLog((l) => [...l, s]);

  useEffect(() => {
    (async () => {
      const all = (await fetch("/api/dev/gens").then((r) => r.json())).ids as string[];
      const want = new URLSearchParams(location.search).get("recut") || "";
      const gid = all.find((x) => x.includes(want)) || all[0];
      if (!gid) { add("no generations found"); return; }
      setId(gid);
      add(`running REAL finishCutoutFull on ${gid}…`);
      const base = `/generated/${gid}`;
      const [layout, template] = await Promise.all([
        fetch(`${base}-layout.json`).then((r) => r.json() as Promise<BlueprintLayout>),
        fetch(`${base}-template.json`).then((r) => r.json() as Promise<Template>),
      ]);
      try {
        const out = await finishCutoutFull(gid, `${base}-paint.png`, `${base}-frame.png`, layout, template);
        setRes(out);
        add(`done — ${Object.keys(out.spriteUrls).length} sprites cut + uploaded; sprites=${out.sprites}`);
      } catch (e) { add(`ERROR: ${e instanceof Error ? e.message : String(e)}`); }
    })();
  }, []);

  const sprites = res ? Object.entries(res.spriteUrls) : [];
  return (
    <div style={{ background: "#0d0e10", color: "#eee", minHeight: "100vh", padding: "16px clamp(12px,3vw,40px)", font: "13px ui-monospace, Menlo, monospace" }}>
      <h1 style={{ fontSize: 19 }}>Recut — REAL finishCutoutFull output · {id}</h1>
      <div style={{ opacity: 0.7, marginBottom: 14 }}>{log.map((l, i) => <div key={i}>{l}</div>)}</div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(220px,1fr) 2fr", gap: 18, alignItems: "start" }}>
        <div>
          <div style={{ opacity: 0.55, marginBottom: 6 }}>cut device frame</div>
          {res?.frameUrl && <img src={res.frameUrl + "?t=" + Date.now()} style={{ width: "100%", borderRadius: 6, background: CHECKER }} />}
        </div>
        <div>
          <div style={{ opacity: 0.55, marginBottom: 6 }}>cut sprites ({sprites.length}) — real shipping output, on checker</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 12 }}>
            {sprites.map(([bind, url]) => (
              <figure key={bind} style={{ margin: 0, border: "1px solid #2a2c30", borderRadius: 6, overflow: "hidden", background: "#16181b" }}>
                <div style={{ height: 140, display: "grid", placeItems: "center", background: CHECKER }}>
                  <img src={url + "?t=" + Date.now()} alt={bind} style={{ maxWidth: "90%", maxHeight: "90%" }} />
                </div>
                <figcaption style={{ padding: "5px 8px", fontSize: 12 }}><b>{bind}</b></figcaption>
              </figure>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
