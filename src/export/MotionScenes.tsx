import type { Cfg } from "./cfg";

// ─────────────────────────────────────────────────────────────────────────────
// MOTION-GRAPHICS SCENES — a multi-colored "product commercial" reel.
// Each scene animates the skins as lightweight static body images on GPU
// transforms (translate/rotate/scale) so capture is buttery-smooth at 60fps —
// unlike the live composites, which can't sustain framerate with 20+ on screen.
// Pick a scene with ?mode=mg&scene=streams|swarm|parade|orbit|cascade.
// ─────────────────────────────────────────────────────────────────────────────

// a vibrant, color-diverse pool (each has a transparent frame.png body)
const POOL = [
  "frog", "bondi", "burger", "maw", "halo", "biomech", "wmp", "scarab",
  "pebble", "obelisk", "vortex", "flesh", "spore", "slab", "toilet",
  "tomato", "mexico",
];
const FRAME = (id: string) => `/skins/${id}/frame.png?v=nb19`;
const Skin = ({ id, className, style }: { id: string; className?: string; style?: React.CSSProperties }) => (
  <img className={`mg-skin ${className ?? ""}`} src={FRAME(id)} alt="" draggable={false} style={style} />
);

// rotate the pool so each column/lane starts on a different color
const slice = (start: number, n: number) =>
  Array.from({ length: n }, (_, i) => POOL[(start + i) % POOL.length]);

/* STREAMS — vertical columns scrolling in alternating directions, varied speed.
   Seamless: each column renders its set twice and translates 0 → -50%. */
function Streams({ cols }: { cols: number }) {
  const dur = [26, 20, 30, 23, 28, 18, 24];
  return (
    <div className="mg-streams" style={{ ["--cols" as string]: cols }}>
      {Array.from({ length: cols }, (_, c) => {
        const items = slice(c * 3, 6);
        const up = c % 2 === 0;
        return (
          <div className="mg-col" key={c}>
            <div className={`mg-col-track ${up ? "up" : "down"}`} style={{ animationDuration: `${dur[c % dur.length]}s` }}>
              {[...items, ...items].map((id, i) => <Skin id={id} key={i} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* SWARM — two crossing diagonal streams (↗ and ↘), eased, continuous. */
function Swarm() {
  const N = 7;
  const lane = (dirClass: string, start: number) => (
    <div className={`mg-diag ${dirClass}`}>
      {slice(start, N).map((id, i) => (
        <Skin id={id} key={i} className="mg-fly"
          style={{ animationDelay: `${-(i * (14 / N)).toFixed(2)}s` }} />
      ))}
    </div>
  );
  return <div className="mg-swarm">{lane("ne", 0)}{lane("se", 5)}</div>;
}

/* PARADE — a horizontal conveyor of devices sliding across, gentle bob. */
function Parade() {
  const items = slice(0, 9);
  return (
    <div className="mg-parade">
      <div className="mg-parade-track">
        {[...items, ...items].map((id, i) => (
          <div className="mg-parade-item" key={i} style={{ animationDelay: `${-(i * 0.4).toFixed(2)}s` }}>
            <Skin id={id} />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ORBIT — a ring of skins revolving around a featured center, each counter-
   rotating to stay upright. Premium hero turntable. */
function Orbit({ center }: { center: string }) {
  const ring = slice(1, 8).filter((s) => s !== center);
  const n = ring.length;
  return (
    <div className="mg-orbit">
      <div className="mg-ring">
        {ring.map((id, i) => (
          <div className="mg-orbiter" key={id} style={{ transform: `rotate(${(i / n) * 360}deg) translateY(-560px)` }}>
            <div className="mg-orbiter-in"><Skin id={id} /></div>
          </div>
        ))}
      </div>
      <div className="mg-center"><Skin id={center} /></div>
    </div>
  );
}

/* CASCADE — skins fall in staggered with a springy ease, float-loop in a loose
   grid. Bouncy, playful. */
function Cascade() {
  const items = slice(2, 12);
  return (
    <div className="mg-cascade">
      {items.map((id, i) => (
        <div className="mg-drop" key={i}
          style={{ left: `${8 + (i % 4) * 24}%`, top: `${10 + Math.floor(i / 4) * 30}%`,
            animationDelay: `${(i * 0.22).toFixed(2)}s` }}>
          <Skin id={id} />
        </div>
      ))}
    </div>
  );
}

export function MotionScenes({ scene, cfg, center }: { scene: string; cfg: Cfg; center?: string }) {
  const body =
    scene === "swarm" ? <Swarm /> :
    scene === "parade" ? <Parade /> :
    scene === "orbit" ? <Orbit center={center ?? "maw"} /> :
    scene === "cascade" ? <Cascade /> :
    <Streams cols={cfg.cols || 5} />;
  return <div className={`mg-stage scene-${scene}`}>{body}</div>;
}
