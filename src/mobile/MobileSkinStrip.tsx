import { useEffect, useRef, useState } from "react";
import { Visualizer } from "../player/Visualizer";
import { thumbUrl } from "../player/skins";
import type { SkinAssets } from "../player/skins";

// The bottom tray on mobile: a horizontally-scrolling filmstrip of skin minis —
// a LOW-RES WebP thumbnail (~16 KB) of each skin with a small animated visualizer
// over it, so the strip reads as "alive" without loading the 2–5 MB full frames
// (loading dozens of those is what made the strip crawl). Tap a mini to jump to
// that skin; the active one is ringed and auto-scrolled into view.
//
// Perf: only minis in (or just off) the viewport mount their image + canvas — an
// IntersectionObserver tracks visibility so a long skin list doesn't run dozens
// of canvas loops or image loads at once. Off-screen items render an empty
// same-size slot, so scroll geometry never shifts.
export function MobileSkinStrip({ skins, index, createIdx, onPick }: {
  skins: SkinAssets[];
  index: number;       // current page (a skin index, or createIdx for the create page)
  createIdx: number;
  onPick: (i: number) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const [live, setLive] = useState<Set<number>>(new Set());

  // mount/unmount minis as they enter/leave the strip viewport (preload a bit)
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
          <span className="m-strip-mini">
            {live.has(i) ? (
              <>
                <img className="m-mini-img" src={thumbUrl(s.id)} alt="" draggable={false}
                  loading="lazy" decoding="async" />
                <span className="m-mini-vis"><Visualizer playing analyser={null} bars={7} /></span>
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
