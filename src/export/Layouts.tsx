import { Device } from "./Device";
import { skinList } from "../player/skins";
import type { Cfg } from "./cfg";

// the user's favorites, color-ordered so the green family (frog / pebble / halo)
// is never adjacent to another green. bondi=blue · burger=warm · biomech=bronze.
const FAV = ["frog", "bondi", "pebble", "burger", "halo", "biomech"];

const nameOf = (id: string) => (skinList.find((s) => s.id === id)?.name ?? id).replace(/\s*✦\s*$/, "");
const pick = (cfg: Cfg) => (cfg.skins && cfg.skins.length ? cfg.skins : FAV);

function Header({ sub, tag }: { sub: string; tag: string }) {
  return (
    <div className="hdr">
      <span className="mark">skeuo<b>/ui</b></span>
      <span className="meta">{sub}</span>
      <span className="spacer" />
      <span className="tag">{tag}</span>
    </div>
  );
}

/* ============================================================
   FAN — devices fanned out like a hand of cards, drop shadows,
   the center card frontmost.
   ============================================================ */
export function FanSheet({ cfg }: { cfg: Cfg }) {
  const skins = pick(cfg);
  const n = skins.length;
  const spread = 10 * cfg.dev;          // degrees between cards
  const h = 720 * cfg.dev;
  return (
    <>
      <Header sub="fan · favorites" tag={`${n} skins`} />
      <div className="fan-wrap">
        {skins.map((s, i) => {
          const k = i - (n - 1) / 2;          // -.. 0 .. +
          const ang = k * spread;
          const dx = k * 234;                  // wide horizontal spread
          const dy = -Math.abs(k) * 64;        // lift outer cards into an upward arc
          const z = 100 - Math.round(Math.abs(k) * 10);
          return (
            <div key={s} className="fan-item"
              style={{ transform: `translate(${dx}px, ${dy}px) rotate(${ang}deg)`, zIndex: z }}>
              <Device skin={s} h={h} />
            </div>
          );
        })}
      </div>
      <div className="ftr"><span>{skins.map(nameOf).join(" · ")}</span><span className="spacer" /><span>skeuo-ui.pages.dev</span></div>
    </>
  );
}

/* ============================================================
   CENTER — one hero centered & frontmost, the rest bleeding in
   from the edges, partially in frame, behind, with shadows.
   ?center=<id> chooses the hero (default = middle of FAV).
   ============================================================ */
const RING: { x: number; y: number; rot: number; h: number }[] = [
  { x: 12, y: 16, rot: -10, h: 560 },   // top-left
  { x: 88, y: 15, rot: 9, h: 560 },     // top-right
  { x: 6, y: 64, rot: -7, h: 620 },     // left
  { x: 94, y: 65, rot: 8, h: 620 },     // right
  { x: 30, y: 96, rot: -5, h: 520 },    // bottom-left
  { x: 72, y: 97, rot: 6, h: 520 },     // bottom-right
];
export function CenterSheet({ cfg, center }: { cfg: Cfg; center?: string }) {
  const skins = pick(cfg);
  const hero = center && skins.includes(center) ? center : skins[Math.floor(skins.length / 2)];
  const rest = skins.filter((s) => s !== hero);
  return (
    <>
      <Header sub={`center · ${hero}`} tag={`${skins.length} skins`} />
      <div className="center-wrap">
        {rest.map((s, i) => {
          const p = RING[i % RING.length];
          return (
            <div key={s} className="edge-item"
              style={{ left: `${p.x}%`, top: `${p.y}%`, transform: `translate(-50%,-50%) rotate(${p.rot}deg)`, zIndex: 10 + i }}>
              <Device skin={s} h={p.h * cfg.dev} />
            </div>
          );
        })}
        <div className="center-item" style={{ zIndex: 50 }}>
          <Device skin={hero} h={1080 * cfg.dev} />
        </div>
      </div>
      <div className="ftr"><span>hero {nameOf(hero)} · others partially in frame</span><span className="spacer" /><span>skeuo-ui.pages.dev</span></div>
    </>
  );
}

/* ============================================================
   SCATTER — a playful overlapping pile, varied size + rotation,
   drop shadows, filling the frame.
   ============================================================ */
const SCAT: { x: number; y: number; rot: number; h: number }[] = [
  { x: 26, y: 26, rot: -12, h: 720 },
  { x: 70, y: 22, rot: 10, h: 640 },
  { x: 18, y: 62, rot: 7, h: 680 },
  { x: 78, y: 64, rot: -9, h: 700 },
  { x: 46, y: 44, rot: 3, h: 820 },     // center-ish, biggest, front
  { x: 50, y: 84, rot: -4, h: 600 },
];
export function ScatterSheet({ cfg }: { cfg: Cfg }) {
  const skins = pick(cfg);
  return (
    <>
      <Header sub="scatter · favorites" tag={`${skins.length} skins`} />
      <div className="center-wrap">
        {skins.map((s, i) => {
          const p = SCAT[i % SCAT.length];
          const z = Math.round(p.h);     // bigger = frontmost
          return (
            <div key={s} className="edge-item"
              style={{ left: `${p.x}%`, top: `${p.y}%`, transform: `translate(-50%,-50%) rotate(${p.rot}deg)`, zIndex: z }}>
              <Device skin={s} h={p.h * cfg.dev} />
            </div>
          );
        })}
      </div>
      <div className="ftr"><span>{skins.map(nameOf).join(" · ")}</span><span className="spacer" /><span>skeuo-ui.pages.dev</span></div>
    </>
  );
}
