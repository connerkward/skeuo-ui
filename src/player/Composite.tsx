import { useEffect, useRef } from "react";
import type { Region, Template } from "../template/schema";
import { fmtTime } from "./data";
import { usePlayer, type PlayerState } from "./usePlayer";
import { Visualizer } from "./Visualizer";
import { layerUrl, skinHas, skinBaked } from "./skins";

interface Props {
  template: Template;
  skinId: string;
  showWireframe?: boolean;
}

// The runtime compositor. Reads the template and positions every region at its
// normalized rect — the SAME coords the wireframe exporter uses — so generated
// art and live widgets always line up. Sprite regions show baked art (or a CSS
// fallback); dynamic regions render live React content.
export function Composite({ template, skinId, showWireframe }: Props) {
  const ps = usePlayer(skinId);
  const { canvas } = template;

  const frameStyle: React.CSSProperties = skinHas(skinId, "frame")
    ? { backgroundImage: `url(${layerUrl(skinId, "frame")})`, backgroundSize: "100% 100%" }
    : {};

  return (
    <div
      className={`player ${showWireframe ? "is-wireframe" : ""}`}
      data-skin={skinId}
      style={{ aspectRatio: `${canvas.w} / ${canvas.h}`, ...frameStyle }}
    >
      {/* styled-but-empty screens, if generated */}
      {skinHas(skinId, "screen") && (
        <img className="layer screen-layer" src={layerUrl(skinId, "screen")} alt="" />
      )}

      {template.regions.map((r) => (
        <RegionView key={r.id} region={r} ps={ps} skinId={skinId} wire={!!showWireframe} />
      ))}
    </div>
  );
}

function pct(r: Region["rect"]): React.CSSProperties {
  return {
    position: "absolute",
    left: `${r.x * 100}%`,
    top: `${r.y * 100}%`,
    width: `${r.w * 100}%`,
    height: `${r.h * 100}%`,
  };
}

function RegionView({ region: r, ps, skinId, wire }: {
  region: Region; ps: PlayerState; skinId: string; wire: boolean;
}) {
  const style = pct(r.rect);

  if (wire) {
    return (
      <div className={`wire wire-${r.kind}`} style={style} data-content={r.content}>
        <span>{r.label ?? r.id}</span>
      </div>
    );
  }

  const baked = skinBaked(skinId);

  // recessed screen backdrop (decorative; live content overlays it).
  // when the frame image bakes the screens, render nothing here.
  if (r.kind === "display" && r.content === "sprite") {
    if (baked) return <div className="region" style={style} />;
    const bg: React.CSSProperties = skinHas(skinId, "screen") ? atlas(skinId, "screen", r) : {};
    return <div className="region screen-bg" style={{ ...style, ...bg }} />;
  }

  // baked sprite override for component regions (sliced from the components atlas)
  const spriteStyle: React.CSSProperties =
    !baked && r.layer === "components" && skinHas(skinId, "components")
      ? atlas(skinId, "components", r) : {};
  const sprited = Object.keys(spriteStyle).length > 0;

  return (
    <div className="region" style={style}>
      {renderControl(r, ps, sprited || baked, spriteStyle, baked)}
    </div>
  );
}

// Slice one region's window out of a full-canvas atlas image.
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

  // ---------- dynamic regions ----------
  if (r.content === "dynamic") {
    switch (r.dynamicType) {
      case "title":
        return <div className="dyn title-text">{r.id === "pl-title" ? "PLAYLIST EDITOR" : ps.content.station}</div>;
      case "time":
        return (
          <div className="dyn lcd-time" data-paused={!ps.playing}>
            {fmtTime(ps.elapsed)}
          </div>
        );
      case "visualizer":
        return <Visualizer playing={ps.playing} />;
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
          const total = ps.content.tracks.reduce((s, t) => s + t.seconds, 0);
          return <div className="dyn pl-summary">{ps.content.tracks.length} tracks · {fmtTime(total)}</div>;
        }
        return (
          <div className="dyn display-meta">
            <span><b>{ps.content.bitrate}</b> kbps</span>
            <span><b>{ps.content.khz}</b> kHz</span>
            <span className={`stereo ${ps.playing ? "on" : ""}`}>stereo</span>
          </div>
        );
      case "eq-curve":
        return <EqCurve bands={ps.eqBands} active={ps.eqOn} />;
      case "playlist":
        return (
          <ol className="dyn pl-list">
            {ps.content.tracks.map((t, i) => (
              <li
                key={i}
                className={`pl-row ${i === ps.trackIdx ? "current" : ""}`}
                onClick={() => ps.select(i)}
                onDoubleClick={() => { ps.select(i); ps.play(); }}
              >
                <span className="pl-num">{i + 1}.</span>
                <span className="pl-name">{t.artist} — {t.title}</span>
                <span className="pl-dur">{fmtTime(t.seconds)}</span>
              </li>
            ))}
          </ol>
        );
    }
  }

  // ---------- sprite (interactive) regions ----------
  if (r.kind === "button") {
    const onClick = btnHandler(r, ps);
    return (
      <button className={`tbtn ${spr}`} style={sprite} onClick={onClick} title={r.label ?? r.id}>
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
  // In baked mode the channel comes from the art (no baked knob), so the
  // slider renders a transparent track + a single live thumb on top.
  const sSprite = baked ? {} : sprite;
  const sSprited = baked || sprited;
  if (r.kind === "slider-h") return <SliderH r={r} ps={ps} sprite={sSprite} sprited={sSprited} />;
  if (r.kind === "slider-v") return <SliderV r={r} ps={ps} sprite={sSprite} sprited={sSprited} />;
  return null;
}

const GLYPH: Record<string, string> = {
  prev: "⏮", play: "▶", pause: "❚❚", stop: "■", next: "⏭", eject: "⏏",
  "pl-prev": "⏮", "pl-play": "▶", "pl-pause": "❚❚", "pl-next": "⏭",
  "pl-add": "ADD", "pl-rem": "REM", "pl-sel": "SEL", "pl-misc": "MISC", presets: "PRESETS",
};
function glyph(r: Region) { return GLYPH[r.id] ?? r.label ?? ""; }

function btnHandler(r: Region, ps: PlayerState): () => void {
  switch (r.bind ?? r.id) {
    case "prev": return ps.prev;
    case "play": return ps.play;
    case "pause": return ps.pause;
    case "stop": return ps.stop;
    case "next": return ps.next;
    case "eject": return ps.eject;
    default: return () => {};
  }
}

function toggleBinding(r: Region, ps: PlayerState): [boolean, () => void] {
  switch (r.bind) {
    case "shuffle": return [ps.shuffle, ps.toggleShuffle];
    case "repeat":  return [ps.repeat, ps.toggleRepeat];
    case "eqOn":    return [ps.eqOn, () => ps.setEqOn((v) => !v)];
    case "eqAuto":  return [ps.eqAuto, () => ps.setEqAuto((v) => !v)];
    default:        return [false, () => {}];
  }
}

/* ---------- sliders ---------- */
function SliderH({ r, ps, sprite, sprited }: { r: Region; ps: PlayerState; sprite: React.CSSProperties; sprited: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const value =
    r.bind === "volume" ? ps.volume :
    r.bind === "balance" ? ps.balance :
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
  const d = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * w;
    const y = h - v * h;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={`dyn eq-curve-svg ${active ? "" : "off"}`}>
      <line x1="0" y1={h / 2} x2={w} y2={h / 2} className="eq-curve-mid" />
      <path d={d} className="eq-curve-line" />
    </svg>
  );
}
