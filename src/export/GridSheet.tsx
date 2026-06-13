import { useEffect, useRef } from "react";
import { Composite } from "../player/Composite";
import { playerTemplate } from "../template/winamp-layout";
import { skinList } from "../player/skins";
import { useAspect, type Cfg } from "./cfg";

// the best skins, default order (override with ?skins=)
const DEFAULT = ["maw", "wmp", "obelisk", "scarab", "halo", "pebble"];

function Tile({ skin, dev }: { skin: string; dev: number }) {
  const meta = skinList.find((s) => s.id === skin);
  const aspect = useAspect(skin);
  const wellRef = useRef<HTMLDivElement>(null);
  const devRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const well = wellRef.current, d = devRef.current;
    if (!well || !d) return;
    const fit = () => {
      const w = Math.min(well.clientWidth, well.clientHeight * aspect) * dev;
      d.style.setProperty("--w", `${Math.round(w)}px`);
    };
    fit();
    const ro = new ResizeObserver(fit); ro.observe(well);
    return () => ro.disconnect();
  }, [aspect, dev]);
  return (
    <div className="tile">
      <div className="well" ref={wellRef}>
        <div ref={devRef}><Composite template={playerTemplate} skinId={skin} /></div>
      </div>
      <div className="cap">
        <span className="n">{(meta?.name ?? skin).replace(/\s*✦\s*$/, "")}</span>
        <span className="id">{skin}</span>
      </div>
    </div>
  );
}

// GRID — a tight contact sheet of the best skins. Static-but-live (each device's
// spectrum/clock animate on their own); meant to be screenshotted as a single
// "here's the set" post.
export function GridSheet({ cfg }: { cfg: Cfg }) {
  const skins = (cfg.skins && cfg.skins.length ? cfg.skins : DEFAULT);
  return (
    <>
      <div className="hdr">
        <span className="mark">skeuo<b>/ui</b></span>
        <span className="meta">wip skins · contact sheet</span>
        <span className="spacer" />
        <span className="tag">{skins.length} skins · 2026-06-13</span>
      </div>
      <div className="grid-body">
        {skins.map((s) => <Tile key={s} skin={s} dev={cfg.dev} />)}
      </div>
      <div className="ftr">
        <span>ai bodies · drawn layout · molded sprites</span>
        <span className="spacer" />
        <span>skeuo-ui.pages.dev</span>
      </div>
    </>
  );
}
