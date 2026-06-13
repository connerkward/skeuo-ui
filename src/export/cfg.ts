import { useEffect, useState } from "react";
import { skinTemplateUrl } from "../player/skins";

// URL-param config — every export page is tunable without code edits:
//   ?ts=1.2   text scale
//   ?mg=64    outer margin (px)
//   ?gap=22   grid gap (px)
//   ?pad=18   cell pad (px)
//   ?cols=3   grid columns
//   ?dev=0.92 device fit fraction (shrink devices inside their box)
//   ?skins=maw,wmp,halo,...   which skins (grid / sprites order)
export interface Cfg { ts: number; mg: number; gap: number; pad: number; cols: number; dev: number; skins?: string[]; }

export function readCfg(): Cfg {
  const q = new URLSearchParams(location.search);
  const num = (k: string, d: number) => (q.has(k) ? Number(q.get(k)) : d);
  const skins = q.get("skins");
  return {
    ts: num("ts", 1),
    mg: num("mg", 48),
    gap: num("gap", 18),
    pad: num("pad", 16),
    cols: num("cols", 2),
    dev: num("dev", 1),
    skins: skins ? skins.split(",").filter(Boolean) : undefined,
  };
}

export function cssVars(c: Cfg): React.CSSProperties {
  return {
    ["--ts" as string]: String(c.ts),
    ["--mg" as string]: `${c.mg}px`,
    ["--gap" as string]: `${c.gap}px`,
    ["--pad" as string]: `${c.pad}px`,
    ["--cols" as string]: String(c.cols),
    ["--dev" as string]: String(c.dev),
  };
}

// fetch a skin's template canvas aspect (w/h); 0.667 (2:3) until loaded
export function useAspect(skin: string): number {
  const [a, setA] = useState(0.667);
  useEffect(() => {
    const url = skinTemplateUrl(skin);
    if (!url) return;
    let live = true;
    fetch(url).then((r) => r.json()).then((t) => { if (live) setA(t.canvas.w / t.canvas.h); }).catch(() => {});
    return () => { live = false; };
  }, [skin]);
  return a;
}
