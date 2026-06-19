import { useEffect, useRef, useState } from "react";
import { Composite } from "../player/Composite";
import type { Template } from "../template/schema";
import type { SkinAssets } from "../player/skins";

// The bottom tray on mobile: a horizontally-scrolling filmstrip of LIVE mini
// players (each a real <Composite/>, animating via the same mock visualizer the
// big one uses) — replaces the old page-dots. Tap a mini to jump to that skin;
// the active one is ringed and auto-scrolled into view.
//
// Perf: only minis in (or just off) the viewport mount a Composite — an
// IntersectionObserver tracks visibility so a long skin list doesn't run dozens
// of canvas loops at once. Off-screen items render an empty same-size slot, so
// scroll geometry never shifts.
export function MobileSkinStrip({ template, skins, index, createIdx, onPick }: {
  template: Template;
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
            {live.has(i) ? <Composite template={template} skinId={s.id} /> : null}
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
