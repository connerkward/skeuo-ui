import { Device } from "./Device";
import type { Cfg } from "./cfg";

// ─────────────────────────────────────────────────────────────────────────────
// MOTION-GRAPHICS SCENES — a multi-colored "product commercial" reel of the
// LIVE skins: real working buttons, screens, and the EQ spectrum moving as if to
// music. Devices stream/orbit/parade on GPU transforms. Counts are kept moderate
// so the live composites sustain framerate.
//   ?mode=mg&scene=streams|swarm|parade|orbit|cascade
// ─────────────────────────────────────────────────────────────────────────────

const POOL = [
  "frog", "bondi", "burger", "maw", "halo", "biomech", "wmp", "scarab",
  "pebble", "obelisk", "vortex", "flesh", "tomato", "mexico", "slab",
];
const slice = (start: number, n: number) =>
  Array.from({ length: n }, (_, i) => POOL[(start + i) % POOL.length]);

/* STREAMS — vertical columns of live devices scrolling in alternating
   directions, varied speed. Seamless: each column renders its set twice. */
function Streams({ cols }: { cols: number }) {
  const dur = [24, 19, 28, 22, 26];
  const w = Math.round((1080 - 80) / cols - 26);   // fit width, no horizontal clip
  return (
    <div className="mg-streams" style={{ ["--cols" as string]: cols }}>
      {Array.from({ length: cols }, (_, c) => {
        const items = slice(c * 3, 2);
        return (
          <div className="mg-col" key={c}>
            <div className={`mg-col-track ${c % 2 === 0 ? "up" : "down"}`} style={{ animationDuration: `${dur[c % dur.length]}s` }}>
              {[...items, ...items].map((id, i) => <Device key={i} skin={id} w={w} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* SWARM — live devices flying on two crossing diagonals, eased, continuous. */
function Swarm() {
  const N = 4;
  const lane = (dir: string, start: number) => (
    <div className={`mg-diag ${dir}`}>
      {slice(start, N).map((id, i) => (
        <div className="mg-fly" key={i} style={{ animationDelay: `${-(i * (14 / N)).toFixed(2)}s` }}>
          <Device skin={id} w={300} />
        </div>
      ))}
    </div>
  );
  return <div className="mg-swarm">{lane("ne", 0)}{lane("se", 6)}</div>;
}

/* PARADE — a horizontal conveyor of live devices, gentle bob. */
function Parade() {
  const items = slice(0, 4);
  return (
    <div className="mg-parade">
      <div className="mg-parade-track">
        {[...items, ...items].map((id, i) => (
          <div className="mg-parade-item" key={i} style={{ animationDelay: `${-(i * 0.5).toFixed(2)}s` }}>
            <Device skin={id} w={360} />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ORBIT — a ring of live skins revolving around a featured center, each
   counter-rotating to stay upright. */
function Orbit({ center }: { center: string }) {
  const ring = slice(1, 7).filter((s) => s !== center).slice(0, 6);
  const n = ring.length;
  return (
    <div className="mg-orbit">
      <div className="mg-ring">
        {ring.map((id, i) => (
          <div className="mg-orbiter" key={id} style={{ transform: `rotate(${(i / n) * 360}deg) translateY(-580px)` }}>
            <div className="mg-orbiter-in"><Device skin={id} w={230} /></div>
          </div>
        ))}
      </div>
      <div className="mg-center"><Device skin={center} w={430} /></div>
    </div>
  );
}

/* CASCADE — live devices fall in staggered with a springy ease, then float. */
function Cascade() {
  const items = slice(2, 8);
  return (
    <div className="mg-cascade">
      {items.map((id, i) => (
        <div className="mg-drop" key={i}
          style={{ left: `${10 + (i % 3) * 30}%`, top: `${14 + Math.floor(i / 3) * 40}%`,
            animationDelay: `${(i * 0.2).toFixed(2)}s` }}>
          <Device skin={id} w={250} />
        </div>
      ))}
    </div>
  );
}

/* FAN — live devices fanned like a hand of cards (center frontmost, every device
   animating its own UI). `mode`: static (held), out (deal out from a stack), in
   (cards fly IN from off-screen to assemble the fan). `anchor`: center, or bottom
   (bottoms converge low in the frame — the hand-of-cards look). */
function Fan({ mode, anchor }: { mode: "static" | "out" | "in"; anchor: "center" | "bottom" }) {
  const skins = ["frog", "bondi", "maw", "halo", "wmp", "burger", "biomech"];
  const n = skins.length;
  const baseY = anchor === "bottom" ? 540 : 0;
  return (
    <div className={`mg-fan mode-${mode} anchor-${anchor}`} style={{ ["--baseY" as string]: `${baseY}px` }}>
      {skins.map((id, i) => {
        const k = i - (n - 1) / 2;
        const dx = Math.round(k * 210), dy = -Math.round(Math.abs(k) * 58), ang = k * 9;
        const z = 100 - Math.round(Math.abs(k) * 10);
        const vars = { ["--dx" as string]: `${dx}px`, ["--dy" as string]: `${dy}px`, ["--ang" as string]: `${ang}deg`,
          zIndex: z, animationDelay: `${(Math.abs(k) * 0.12).toFixed(2)}s` } as React.CSSProperties;
        return <div className="fan-card" key={id} style={vars}><Device skin={id} w={360} /></div>;
      })}
    </div>
  );
}

export function MotionScenes({ scene, cfg, center }: { scene: string; cfg: Cfg; center?: string }) {
  const body =
    scene === "swarm" ? <Swarm /> :
    scene === "parade" ? <Parade /> :
    scene === "orbit" ? <Orbit center={center ?? "maw"} /> :
    scene === "cascade" ? <Cascade /> :
    scene === "fan" ? <Fan mode="static" anchor="center" /> :
    scene === "fanout" ? <Fan mode="out" anchor="center" /> :
    scene === "fanbottom" ? <Fan mode="static" anchor="bottom" /> :
    scene === "fanin" ? <Fan mode="in" anchor="bottom" /> :
    <Streams cols={cfg.cols || 3} />;
  return <div className={`mg-stage scene-${scene}`}>{body}</div>;
}
