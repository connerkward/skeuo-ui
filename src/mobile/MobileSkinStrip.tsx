import { useEffect, useRef, useState } from "react";
import { Visualizer } from "../player/Visualizer";
import { thumbUrl, skinTemplateUrl, skinStyle, layerUrl, skinHas } from "../player/skins";
import type { SkinAssets } from "../player/skins";
import type { Template, Region } from "../template/schema";

// The bottom tray on mobile: a horizontally-scrolling filmstrip of skin minis —
// a LOW-RES WebP thumbnail (~16 KB) of each skin with the REAL visualizer
// rendered at its REAL position (read from the skin's template), so the strip
// reads as a row of live little players without loading the 2–5 MB full frames.
// Tap a mini to jump to that skin; the active one is ringed and auto-scrolled in.
//
// Perf: only minis in (or just off) the viewport mount — an IntersectionObserver
// tracks visibility so a long list never runs dozens of canvas loops / image
// loads at once. Off-screen items keep an empty same-size slot (stable scroll).
export function MobileSkinStrip({ skins, index, createIdx, onPick }: {
  skins: SkinAssets[];
  index: number;       // current page (a skin index, or createIdx for the create page)
  createIdx: number;
  onPick: (i: number) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const [live, setLive] = useState<Set<number>>(new Set());
  const preloaded = useRef<Set<number>>(new Set());

  // After the critical thumbnail/main-player network settles, warm the FULL-SIZE
  // skin assets for the minis currently in view, at idle priority, so tapping one
  // loads the full <Composite> instantly (cache hit). requestIdleCallback naturally
  // defers until the page is quiet, so this never competes with the thumbs/main
  // player. We warm frame + screen (via Image) and the template (via fetch) — NOT
  // the sprites dir (~10 MB/skin, far too heavy).
  useEffect(() => {
    const ric: typeof window.requestIdleCallback | undefined =
      typeof window !== "undefined" ? window.requestIdleCallback : undefined;
    const schedule = (cb: () => void) =>
      ric ? ric(cb, { timeout: 1500 }) : window.setTimeout(cb, 600);
    for (const i of live) {
      if (i >= skins.length) continue;          // skip the trailing "+" create item
      if (preloaded.current.has(i)) continue;
      preloaded.current.add(i);
      const id = skins[i].id;
      schedule(() => {
        new Image().src = layerUrl(id, "frame");
        if (skinHas(id, "screen")) new Image().src = layerUrl(id, "screen");
        const t = skinTemplateUrl(id);
        if (t) fetch(t).catch(() => {});
      });
    }
  }, [live, skins]);

  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    const io = new IntersectionObserver(
      (entries) => setLive((prev) => {
        const next = new Set(prev);
        for (const e of entries) {
          const i = Number((e.target as HTMLElement).dataset.idx);
          if (e.isIntersecting) next.add(i); else next.delete(i);
        }
        return next;
      }),
      { root, rootMargin: "160px" },
    );
    items.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [skins.length]);

  // keep the active item centered as the user swipes the big carriage
  useEffect(() => {
    items.current[index]?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [index]);

  return (
    <nav className="m-strip" ref={scroller} aria-label="skins">
      {skins.map((s, i) => (
        <button
          key={s.id}
          data-idx={i}
          ref={(el) => { items.current[i] = el; }}
          className={`m-strip-item ${i === index ? "on" : ""}`}
          onClick={() => onPick(i)}
          aria-label={s.name}
          aria-current={i === index}
          title={s.name}
        >
          <span className="m-strip-mini" data-skin={skinStyle(s.id)}>
            {live.has(i) ? (
              <>
                <img className="m-mini-img" src={s.frameUrl ?? thumbUrl(s.id)} alt="" draggable={false}
                  loading="lazy" decoding="async"
                  onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} />
                <MiniVis skinId={s.id} />
              </>
            ) : null}
          </span>
        </button>
      ))}
      <button
        data-idx={createIdx}
        ref={(el) => { items.current[createIdx] = el; }}
        className={`m-strip-item m-strip-create ${index === createIdx ? "on" : ""}`}
        onClick={() => onPick(createIdx)}
        aria-label="Generate your own"
        title="Generate your own"
      >
        <span className="m-strip-plus">+</span>
      </button>
    </nav>
  );
}

// Render the skin's visualizer region(s) at their real normalized rects over the
// thumbnail — the SAME placement + variant the full Composite uses, just driven
// by the mock animation (no analyser). Mirrors Composite.renderControl's
// visualizer branch so a dial skin gets the radial dial, a teeth/ribbon skin its
// own shape, etc.
function MiniVis({ skinId }: { skinId: string }) {
  const [tpl, setTpl] = useState<Template | null>(null);
  const url = skinTemplateUrl(skinId);
  useEffect(() => {
    if (!url) return;
    let liveFetch = true;
    fetch(url).then((r) => r.json()).then((t: Template) => { if (liveFetch) setTpl(t); }).catch(() => {});
    return () => { liveFetch = false; };
  }, [url]);
  if (!tpl) return null;
  const vizRegions = tpl.regions.filter(
    (r) => r.content === "dynamic" && r.dynamicType === "visualizer",
  );
  return (
    <>
      {vizRegions.map((r) => (
        <span key={r.id} className={`m-mini-vis ${r.shape === "ellipse" ? "is-round" : ""}`} style={rectStyle(r)}>
          {renderViz(r)}
        </span>
      ))}
    </>
  );
}

function rectStyle(r: Region): React.CSSProperties {
  const { x, y, w, h } = r.rect;
  return {
    position: "absolute",
    left: `${x * 100}%`, top: `${y * 100}%`,
    width: `${w * 100}%`, height: `${h * 100}%`,
  };
}

// same variant selection as Composite: ellipse → radial dial; teeth/ribbon keep
// their shape; everything else is the linear spectrum.
function renderViz(r: Region) {
  if (r.shape === "ellipse")
    return <Visualizer playing analyser={null} variant="radial" dialStyle={r.dialStyle ?? "bars"} />;
  if (r.vis === "teeth") return <Visualizer playing analyser={null} variant="teeth" />;
  if (r.vis === "ribbon") return <Visualizer playing analyser={null} variant="ribbon" path={r.path} />;
  return <Visualizer playing analyser={null} />;
}
