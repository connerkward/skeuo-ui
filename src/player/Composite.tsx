import { useEffect, useRef, useState } from "react";
import type { Region, Template } from "../template/schema";
import { fmtTime } from "./data";
import { usePlayer, type PlayerState } from "./usePlayer";
import { Visualizer } from "./Visualizer";
import { layerUrl, skinHas, skinBaked, skinTemplateUrl, skinStyle, skinLive } from "./skins";

interface Props {
  template: Template;
  skinId: string;
  showWireframe?: boolean;
}

// The runtime compositor. Reads the template and positions every region at its
// normalized rect — the SAME coords the exporter uses — so generated art and
// live widgets always line up. Sprite regions show baked art (or a CSS
// fallback); dynamic regions render live React; decoration regions are baked-
// only (no runtime element).
export function Composite({ template, skinId, showWireframe }: Props) {
  const ps = usePlayer(skinId);

  // skins with an extracted layout fetch their own template at runtime
  const [loaded, setLoaded] = useState<Template | null>(null);
  const url = skinTemplateUrl(skinId);
  useEffect(() => {
    if (!url) { setLoaded(null); return; }
    let live = true;
    fetch(url, { cache: "reload" }).then((r) => r.json()).then((t) => { if (live) setLoaded(t); });
    return () => { live = false; };
  }, [url]);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef<{ ox: number; oy: number; px: number; py: number } | null>(null);
  useEffect(() => {
    const m = (e: MouseEvent) => {
      if (!drag.current) return;
      setPos({ x: drag.current.ox + e.clientX - drag.current.px, y: drag.current.oy + e.clientY - drag.current.py });
    };
    const u = () => (drag.current = null);
    window.addEventListener("mousemove", m);
    window.addEventListener("mouseup", u);
    return () => { window.removeEventListener("mousemove", m); window.removeEventListener("mouseup", u); };
  }, []);
  const startDrag = (e: React.MouseEvent) => {
    drag.current = { ox: pos.x, oy: pos.y, px: e.clientX, py: e.clientY };
  };

  // all hooks above this line — safe to early-return now
  const styleId = skinStyle(skinId);
  const active = url ? loaded : template;
  if (!active) return <div className="player" data-skin={styleId} style={{ aspectRatio: "1024 / 1536" }} />;
  const tpl = active;
  const { canvas } = tpl;
  const baked = skinBaked(skinId);
  const hasFrame = skinHas(skinId, "frame");

  // "art mode": skins whose layout was vision-EXTRACTED (own templateUrl) have
  // imprecise control boxes, so we suppress the small live decorations (thumbs,
  // knob needles, segment highlights, labels) that would float off the baked
  // art, and keep only the forgiving live SCREEN content (clock/marquee/playlist).
  const art = !!url;
  // wild skins: EMPTY baked screens + CV-detected screen regions → render live
  // content into the detected screens (controls stay baked, not overlaid).
  const liveArt = art && skinLive(skinId);

  return (
    <div
      className={`player ${showWireframe ? "is-wireframe" : ""} ${hasFrame ? "has-frame" : ""} ${art ? "art" : ""}`}
      data-skin={styleId}
      style={{ aspectRatio: `${canvas.w} / ${canvas.h}`, transform: `translate(${pos.x}px, ${pos.y}px)` }}
    >
      {/* generated chrome as a transparent layer (lets each skin's silhouette differ) */}
      {hasFrame && !showWireframe && <img className="layer frame-layer" src={layerUrl(skinId, "frame")} alt="" />}
      {skinHas(skinId, "screen") && !showWireframe && (
        <img className="layer screen-layer" src={layerUrl(skinId, "screen")} alt="" />
      )}

      {/* Extracted/wild skins are coherent AI-designed images (controls + screen
          content already baked in), and their control positions aren't known
          precisely — so render them as the pure aligned artwork rather than
          overlay misplaced live widgets. Canonical skins overlay live content. */}
      {(!art || liveArt || showWireframe) && tpl.regions.map((r) => (
        <RegionView key={r.id} region={r} ps={ps} skinId={skinId}
          wire={!!showWireframe} baked={baked} onTitleDown={startDrag} />
      ))}
    </div>
  );
}

function pct(r: Region["rect"]): React.CSSProperties {
  return {
    position: "absolute",
    left: `${r.x * 100}%`, top: `${r.y * 100}%`,
    width: `${r.w * 100}%`, height: `${r.h * 100}%`,
  };
}

function RegionView({ region: r, ps, skinId, wire, baked, onTitleDown }: {
  region: Region; ps: PlayerState; skinId: string; wire: boolean;
  baked: boolean; onTitleDown: (e: React.MouseEvent) => void;
}) {
  const style = pct(r.rect);

  if (wire) {
    return (
      <div className={`wire wire-${r.kind}`} style={style} data-content={r.content}>
        <span>{r.label ?? r.id}</span>
      </div>
    );
  }

  // decoration is baked into the frame art — nothing to render at runtime
  if (r.kind === "flourish") return null;

  // recessed screen backdrop (live content overlays it). baked art supplies it.
  // a per-skin scrim guarantees text contrast when the baked screen came out
  // lighter than the skin's text (set via --screen-scrim).
  if (r.kind === "display" && r.content === "sprite") {
    if (baked) return <div className="region screen-scrim" style={style} />;
    const bg = skinHas(skinId, "screen") ? atlas(skinId, "screen", r) : {};
    return <div className="region screen-bg" style={{ ...style, ...bg }} />;
  }

  const spriteStyle: React.CSSProperties =
    !baked && r.layer === "components" && skinHas(skinId, "components") ? atlas(skinId, "components", r) : {};
  const sprited = Object.keys(spriteStyle).length > 0;

  const titleDown = r.dynamicType === "title" && r.id === "titlebar" ? onTitleDown : undefined;
  return (
    <div className={`region ${titleDown ? "draggable" : ""}`} style={style} onMouseDown={titleDown}>
      {renderControl(r, ps, sprited || baked, spriteStyle, baked)}
    </div>
  );
}

function atlas(skinId: string, layer: "components" | "screen", r: Region): React.CSSProperties {
  const { x, y, w, h } = r.rect;
  return {
    backgroundImage: `url(${layerUrl(skinId, layer)})`,
    backgroundSize: `${100 / w}% ${100 / h}%`,
    backgroundPosition: `${w < 1 ? (x / (1 - w)) * 100 : 0}% ${h < 1 ? (y / (1 - h)) * 100 : 0}%`,
    backgroundRepeat: "no-repeat",
  };
}

function renderControl(
  r: Region, ps: PlayerState, sprited: boolean, sprite: React.CSSProperties, baked = false
): React.ReactNode {
  const spr = sprited ? "sprited" : "";

  if (r.content === "dynamic") {
    switch (r.dynamicType) {
      case "title":
        return <div className="dyn title-text">{r.id === "pl-title" ? "PLAYLIST EDITOR" : ps.content.station}</div>;
      case "time":
        return <div className="dyn lcd-time" data-paused={!ps.playing}>{fmtTime(ps.elapsed)}</div>;
      case "visualizer":
        return <Visualizer playing={ps.playing} analyser={ps.analyser} />;
      case "marquee":
        return (
          <div className="dyn marquee">
            <span className="marquee-text">
              {ps.trackIdx + 1}. {ps.track.artist} — {ps.track.title}
              &nbsp;&nbsp;·&nbsp;&nbsp;{fmtTime(ps.track.seconds)}
              &nbsp;&nbsp;·&nbsp;&nbsp;{ps.content.station}
            </span>
          </div>
        );
      case "meta":
        if (r.id === "pl-summary") {
          const total = ps.tracks.reduce((s, t) => s + t.seconds, 0);
          return <div className="dyn pl-summary">{ps.tracks.length} tracks · {fmtTime(total)}</div>;
        }
        return (
          <div className="dyn display-meta">
            <span><b>{ps.content.bitrate}</b>k</span>
            <span><b>{ps.content.khz}</b>kHz</span>
            <span className={`stereo ${ps.playing ? "on" : ""}`}>stereo</span>
          </div>
        );
      case "eq-curve":
        return <EqCurve bands={ps.eqBands} active={ps.eqOn} />;
      case "playlist":
        return (
          <ol className="dyn pl-list">
            {ps.tracks.map((t, i) => (
              <li key={i} className={`pl-row ${i === ps.trackIdx ? "current" : ""}`}
                onClick={() => ps.select(i)} onDoubleClick={() => { ps.select(i); ps.play(); }}>
                <span className="pl-num">{i + 1}.</span>
                <span className="pl-name">{t.artist} — {t.title}</span>
                <span className="pl-dur">{fmtTime(t.seconds)}</span>
              </li>
            ))}
          </ol>
        );
    }
  }

  if (r.kind === "button") {
    return (
      <button className={`tbtn ${spr}`} style={sprite} onClick={btnHandler(r, ps)} title={r.label ?? r.id}>
        {!sprited && glyph(r)}
      </button>
    );
  }
  if (r.kind === "toggle") {
    const [on, toggle] = toggleBinding(r, ps);
    return (
      <button className={`toggle ${spr}`} style={sprite} data-on={on} onClick={toggle} title={r.label ?? r.id}>
        {!sprited && (r.label ?? r.id)}
      </button>
    );
  }
  if (r.kind === "segmented") return <Segmented r={r} ps={ps} baked={baked} />;
  if (r.kind === "knob") return <Knob r={r} ps={ps} baked={baked} />;
  if (r.kind === "xy") return <XYPad ps={ps} baked={baked} />;

  const sSprite = baked ? {} : sprite;
  const sSprited = baked || sprited;
  if (r.kind === "slider-h") return <SliderH r={r} ps={ps} sprite={sSprite} sprited={sSprited} />;
  if (r.kind === "slider-v") return <SliderV r={r} ps={ps} sprite={sSprite} sprited={sSprited} />;
  return null;
}

const GLYPH: Record<string, string> = {
  prev: "⏮", play: "▶", pause: "❚❚", stop: "■", next: "⏭", eject: "⏏",
  "pl-prev": "⏮", "pl-play": "▶", "pl-pause": "❚❚", "pl-next": "⏭",
  "pl-add": "ADD", "pl-rem": "REM", "pl-sel": "SEL", "pl-misc": "MISC",
};
const glyph = (r: Region) => GLYPH[r.id] ?? r.label ?? "";

function btnHandler(r: Region, ps: PlayerState): () => void {
  switch (r.bind ?? r.id) {
    case "prev": return ps.prev;  case "play": return ps.play;
    case "pause": return ps.pause; case "stop": return ps.stop;
    case "next": return ps.next;  case "eject": return ps.eject;
    case "mute": return ps.toggleMute;
    case "volUp": return () => ps.setVolume(Math.min(1, ps.volume + 0.12));
    case "volDown": return () => ps.setVolume(Math.max(0, ps.volume - 0.12));
    case "presetNext": case "presets": return () => ps.setEqPreset((ps.eqPreset + 1) % 4);
    case "eqOnToggle": return () => ps.setEqOn((v) => !v);
    case "pl-add": return ps.addTrack;
    case "pl-rem": return ps.removeTrack;
    case "pl-sel": return () => ps.select(0);
    case "pl-misc": return ps.sortList;
    default: return () => {};
  }
}
function toggleBinding(r: Region, ps: PlayerState): [boolean, () => void] {
  switch (r.bind) {
    case "shuffle": return [ps.shuffle, ps.toggleShuffle];
    case "eqOn":    return [ps.eqOn, () => ps.setEqOn((v) => !v)];
    case "eqAuto":  return [ps.eqAuto, () => ps.setEqAuto((v) => !v)];
    case "mute":    return [ps.muted, ps.toggleMute];
    default:        return [false, () => {}];
  }
}

/* ---------- segmented selector ---------- */
function Segmented({ r, ps, baked }: { r: Region; ps: PlayerState; baked: boolean }) {
  const opts = r.options ?? [];
  const active = r.bind === "repeatMode" ? ps.repeatMode : r.bind === "eqPreset" ? ps.eqPreset : 0;
  const set = (i: number) => {
    if (r.bind === "repeatMode") ps.setRepeatMode(i);
    else if (r.bind === "eqPreset") ps.setEqPreset(i);
  };
  return (
    <div className={`segmented ${baked ? "baked" : ""}`}>
      {opts.map((o, i) => (
        <button key={o} className="seg" data-active={i === active} onClick={() => set(i)} title={`${r.label}: ${o}`}>
          <span>{o}</span>
        </button>
      ))}
    </div>
  );
}

/* ---------- rotary knob ---------- */
function Knob({ r, ps, baked }: { r: Region; ps: PlayerState; baked: boolean }) {
  const value = r.bind === "volume" ? ps.volume : r.bind === "balance" ? ps.balance : 0.5;
  const setV = r.bind === "volume" ? ps.setVolume : ps.setBalance;
  const drag = useRef<{ y: number; v: number } | null>(null);
  useEffect(() => {
    const m = (e: MouseEvent) => {
      if (!drag.current) return;
      const dv = (drag.current.y - e.clientY) / 140;       // drag up = increase
      setV(Math.max(0, Math.min(1, drag.current.v + dv)));
    };
    const u = () => (drag.current = null);
    window.addEventListener("mousemove", m); window.addEventListener("mouseup", u);
    return () => { window.removeEventListener("mousemove", m); window.removeEventListener("mouseup", u); };
  }, [setV]);
  const angle = -135 + value * 270;
  return (
    <div className={`knob ${baked ? "baked" : ""}`} title={`${r.label}: ${(value * 100) | 0}%`}
      onMouseDown={(e) => { drag.current = { y: e.clientY, v: value }; }}>
      <div className="knob-body">
        <div className="knob-ind" style={{ transform: `translateX(-50%) rotate(${angle}deg)` }} />
      </div>
      <span className="knob-label">{r.label}</span>
    </div>
  );
}

/* ---------- XY pad ---------- */
function XYPad({ ps, baked }: { ps: PlayerState; baked: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const set = (cx: number, cy: number) => {
    const rc = ref.current?.getBoundingClientRect(); if (!rc) return;
    ps.setTone({
      x: Math.max(0, Math.min(1, (cx - rc.left) / rc.width)),
      y: Math.max(0, Math.min(1, 1 - (cy - rc.top) / rc.height)),
    });
  };
  useEffect(() => {
    const m = (e: MouseEvent) => drag.current && set(e.clientX, e.clientY);
    const u = () => (drag.current = false);
    window.addEventListener("mousemove", m); window.addEventListener("mouseup", u);
    return () => { window.removeEventListener("mousemove", m); window.removeEventListener("mouseup", u); };
  }, []);
  return (
    <div ref={ref} className={`xy ${baked ? "baked" : ""}`} title="Stereo field"
      onMouseDown={(e) => { drag.current = true; set(e.clientX, e.clientY); }}>
      <div className="xy-grid" />
      <div className="xy-puck" style={{ left: `${ps.tone.x * 100}%`, top: `${(1 - ps.tone.y) * 100}%` }} />
    </div>
  );
}

/* ---------- sliders ---------- */
function SliderH({ r, ps, sprite, sprited }: { r: Region; ps: PlayerState; sprite: React.CSSProperties; sprited: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const value =
    r.bind === "volume" ? ps.volume : r.bind === "balance" ? ps.balance :
    r.bind === "seek" ? (ps.track.seconds ? ps.elapsed / ps.track.seconds : 0) : 0;
  const set = (clientX: number) => {
    const rc = ref.current?.getBoundingClientRect(); if (!rc) return;
    const v = Math.max(0, Math.min(1, (clientX - rc.left) / rc.width));
    if (r.bind === "volume") ps.setVolume(v);
    else if (r.bind === "balance") ps.setBalance(v);
    else if (r.bind === "seek") ps.seekTo(v);
  };
  useEffect(() => {
    const m = (e: MouseEvent) => drag.current && set(e.clientX);
    const u = () => (drag.current = false);
    window.addEventListener("mousemove", m); window.addEventListener("mouseup", u);
    return () => { window.removeEventListener("mousemove", m); window.removeEventListener("mouseup", u); };
  }, []);
  return (
    <div ref={ref} className={`sk-slider-h ${sprited ? "sprited" : ""}`} style={sprite}
      onMouseDown={(e) => { drag.current = true; set(e.clientX); }} title={r.label}>
      {!sprited && <><div className="rail" /><div className="fill" style={{ width: `${value * 100}%` }} /></>}
      <div className="thumb" style={{ left: `${value * 100}%` }} />
    </div>
  );
}

function SliderV({ r, ps, sprite, sprited }: { r: Region; ps: PlayerState; sprite: React.CSSProperties; sprited: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const idx = r.index ?? 0;
  const value = ps.eqBands[idx] ?? 0.5;
  const disabled = !ps.eqOn;
  const set = (clientY: number) => {
    if (disabled) return;
    const rc = ref.current?.getBoundingClientRect(); if (!rc) return;
    ps.setEqBand(idx, Math.max(0, Math.min(1, 1 - (clientY - rc.top) / rc.height)));
  };
  useEffect(() => {
    const m = (e: MouseEvent) => drag.current && set(e.clientY);
    const u = () => (drag.current = false);
    window.addEventListener("mousemove", m); window.addEventListener("mouseup", u);
    return () => { window.removeEventListener("mousemove", m); window.removeEventListener("mouseup", u); };
  }, [disabled]);
  return (
    <div className="eq-slot">
      <div ref={ref} className={`sk-slider-v ${sprited ? "sprited" : ""}`} data-disabled={disabled} style={sprite}
        onMouseDown={(e) => { drag.current = true; set(e.clientY); }} title={r.label}>
        {!sprited && <><div className="rail" /><div className="fill" style={{ height: `${value * 100}%` }} /></>}
        <div className="thumb" style={{ bottom: `${value * 100}%` }} />
      </div>
      <span className="eq-label">{r.label}</span>
    </div>
  );
}

function EqCurve({ bands, active }: { bands: number[]; active: boolean }) {
  const pts = bands.slice(1);
  const w = 100, h = 30;
  const d = pts.map((v, i) => `${i === 0 ? "M" : "L"}${((i / (pts.length - 1)) * w).toFixed(1)},${(h - v * h).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={`dyn eq-curve-svg ${active ? "" : "off"}`}>
      <line x1="0" y1={h / 2} x2={w} y2={h / 2} className="eq-curve-mid" />
      <path d={d} className="eq-curve-line" />
    </svg>
  );
}
