import { useEffect, useState } from "react";
import { Visualizer } from "./Visualizer";
import { skinTemplateUrl } from "./skins";
import type { Template, Region } from "../template/schema";

// An animated skin thumbnail — a low-res image with the REAL visualizer rendered
// at its REAL position (read from the skin's template), so a list of these reads
// as a row of live little players. Same idea the mobile filmstrip uses; shared
// here for the desktop gallery sidebar.
//
// `animate` off (runtime/generated skins, which have no registry template URL)
// just shows the static image.
export function SkinThumb({ skinId, imgSrc, animate = true }: {
  skinId: string;
  imgSrc: string;
  animate?: boolean;
}) {
  return (
    <span className="skin-thumb">
      <img className="skin-thumb-img" src={imgSrc} alt="" draggable={false}
        loading="lazy" decoding="async"
        onError={(e) => { (e.currentTarget as HTMLImageElement).src = "/favicon.svg"; }} />
      {animate && <ThumbVis skinId={skinId} />}
    </span>
  );
}

// Overlay the skin's visualizer region(s) at their normalized rects, driven by the
// mock animation (no analyser) — mirrors Composite's visualizer variant selection.
function ThumbVis({ skinId }: { skinId: string }) {
  const [tpl, setTpl] = useState<Template | null>(null);
  const url = skinTemplateUrl(skinId);
  useEffect(() => {
    if (!url) return;
    let live = true;
    fetch(url).then((r) => r.json()).then((t: Template) => { if (live) setTpl(t); }).catch(() => {});
    return () => { live = false; };
  }, [url]);
  if (!tpl) return null;
  const viz = tpl.regions.filter((r) => r.content === "dynamic" && r.dynamicType === "visualizer");
  return (
    <>
      {viz.map((r) => (
        <span key={r.id} className={`skin-thumb-vis ${r.shape === "ellipse" ? "is-round" : ""}`} style={rectStyle(r)}>
          {renderViz(r)}
        </span>
      ))}
    </>
  );
}

function rectStyle(r: Region): React.CSSProperties {
  const { x, y, w, h } = r.rect;
  return { position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` };
}

function renderViz(r: Region) {
  if (r.shape === "ellipse")
    return <Visualizer playing analyser={null} variant="radial" dialStyle={r.dialStyle ?? "bars"} />;
  if (r.vis === "teeth") return <Visualizer playing analyser={null} variant="teeth" />;
  if (r.vis === "ribbon") return <Visualizer playing analyser={null} variant="ribbon" path={r.path} />;
  return <Visualizer playing analyser={null} />;
}
