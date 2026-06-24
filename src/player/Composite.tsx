import { useEffect, useMemo, useRef, useState } from "react";
import type { Region, Template } from "../template/schema";
import { fmtTime } from "./data";
import { usePlayer, type PlayerState } from "./usePlayer";
import { Visualizer } from "./Visualizer";
import { buildSpline, splineAt, splineProject } from "./spline";
import { layerUrl, skinHas, skinBaked, skinTemplateUrl, skinStyle, skinLive, skinSprites, skinMolded, spriteUrl } from "./skins";
import type { SpotifyDrive } from "../spotify/useSpotify";

// A skin created at runtime (POST /api/generate): its frame is an inline URL
// and its template lives in memory, so it bypasses the on-disk registry lookups.
export interface RuntimeSkinView {
  frameUrl: string;
  template: Template;
  style: string;        // donor style id for sprites/palette ([data-skin])
}

interface Props {
  template: Template;
  skinId: string;
  showWireframe?: boolean;
  // runtime-generated skin (Create panel): inline frame + in-memory template
  runtime?: RuntimeSkinView;
  // live-editor preview: replace the active template's regions without refetch
  templateOverride?: Template;
  // when present, the skin drives REAL Spotify playback (see useSpotify)
  spotifyDrive?: SpotifyDrive | null;
}

// The runtime compositor. Reads the template and positions every region at its
// normalized rect — the SAME coords the exporter uses — so generated art and
// live widgets always line up. Sprite regions show baked art (or a CSS
// fallback); dynamic regions render live React; decoration regions are baked-
// only (no runtime element).
export function Composite({ template, skinId, showWireframe, runtime, templateOverride, spotifyDrive }: Props) {
  const ps = usePlayer(skinId, spotifyDrive);

  // skins with an extracted layout fetch their own template at runtime.
  // Runtime-generated skins carry their template inline (no fetch).
  const [loaded, setLoaded] = useState<Template | null>(null);
  const url = runtime ? undefined : skinTemplateUrl(skinId);
  useEffect(() => {
    if (!url) { setLoaded(null); return; }
    let live = true;
    fetch(url, { cache: "reload" }).then((r) => r.json()).then((t) => { if (live) setLoaded(t); });
    return () => { live = false; };
  }, [url]);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef<{ ox: number; oy: number; px: number; py: number } | null>(null);
  useEffect(() => {
    const m = (e: PointerEvent) => {
      if (!drag.current) return;
      setPos({ x: drag.current.ox + e.clientX - drag.current.px, y: drag.current.oy + e.clientY - drag.current.py });
    };
    const u = () => (drag.current = null);
    window.addEventListener("pointermove", m);
    window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
  }, []);
  const startDrag = (e: React.PointerEvent) => {
    drag.current = { ox: pos.x, oy: pos.y, px: e.clientX, py: e.clientY };
  };

  // all hooks above this line — safe to early-return now
  // runtime skins resolve frame/template/style inline; everything else from the registry
  const styleId = runtime ? runtime.style : skinStyle(skinId);
  const resolved = runtime ? runtime.template : url ? loaded : template;
  // the editor's live override wins (same skin, edited regions)
  const active = templateOverride ?? resolved;
  if (!active) return <div className="player" data-skin={styleId} style={{ aspectRatio: "1024 / 1536" }} />;
  const tpl = active;
  const { canvas } = tpl;
  const baked = runtime ? false : skinBaked(skinId);
  const hasFrame = runtime ? true : skinHas(skinId, "frame");
  const frameSrc = runtime ? runtime.frameUrl : layerUrl(skinId, "frame");

  // "art mode": skins whose layout was vision-EXTRACTED (own templateUrl) or
  // generated at runtime have coherent baked art, so we suppress the small live
  // decorations and keep only the forgiving live SCREEN content.
  const art = !!url || !!runtime;
  // wild + runtime skins: EMPTY baked screens → render live content into them.
  const liveArt = art && (runtime ? true : skinLive(skinId));

  return (
    <div
      className={`player ${showWireframe ? "is-wireframe" : ""} ${hasFrame ? "has-frame" : ""} ${art ? "art" : ""}`}
      data-skin={styleId}
      style={{ aspectRatio: `${canvas.w} / ${canvas.h}`, transform: `translate(${pos.x}px, ${pos.y}px)` }}
    >
      {/* generated chrome as a transparent layer (lets each skin's silhouette differ) */}
      {hasFrame && !showWireframe && <img className="layer frame-layer" src={frameSrc} alt="" />}
      {/* wireframe: show the body ENVELOPE (the painted silhouette) as a faded ghost
          behind the control wires, so you can see where the body sits vs the controls */}
      {hasFrame && showWireframe && <img className="layer envelope-ghost" src={frameSrc} alt="body envelope" />}
      {!runtime && skinHas(skinId, "screen") && !showWireframe && (
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
  baked: boolean; onTitleDown: (e: React.PointerEvent) => void;
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

  const titleDown = r.dynamicType === "title" && r.id === "titlebar" ? onTitleDown : undefined;
  const dyn = r.content === "dynamic" ? "region-dyn" : "";
  // round dial screens (orbit layout) clip their live content to the circle
  const clip: React.CSSProperties =
    r.kind === "display" && r.shape === "ellipse" ? { borderRadius: "50%", overflow: "hidden" } : {};
  return (
    <div className={`region ${dyn} ${titleDown ? "draggable" : ""}`} style={{ ...style, ...clip }} onPointerDown={titleDown}>
      {renderControl(r, ps, skinId)}
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

function renderControl(r: Region, ps: PlayerState, skinId: string): React.ReactNode {
  if (r.content === "dynamic") {
    switch (r.dynamicType) {
      case "title":
        return <div className="dyn title-text">{r.id === "pl-title" ? "PLAYLIST EDITOR" : ps.content.station}</div>;
      case "time":
        return <div className="dyn lcd-time" data-paused={!ps.playing}>{fmtTime(ps.elapsed)}</div>;
      case "visualizer": {
        // round dial screens (orbit/radial layouts) get a radial spectrum that
        // fills the disc, with the clock + track read out in the center hole —
        // so the dial is a live centerpiece, not a black void ringed by buttons.
        if (r.shape === "ellipse") {
          return (
            <div className="dial-vis">
              <Visualizer playing={ps.playing} analyser={ps.analyser} variant="radial" dialStyle={r.dialStyle ?? "bars"} />
              <div className="dial-readout">
                <span className="dial-time" data-paused={!ps.playing}>{fmtTime(ps.elapsed)}</span>
                <span className="dial-track">{ps.track.title}</span>
              </div>
            </div>
          );
        }
        if (r.vis === "teeth") return <Visualizer playing={ps.playing} analyser={ps.analyser} variant="teeth" />;
        if (r.vis === "ribbon") return <Visualizer playing={ps.playing} analyser={ps.analyser} variant="ribbon" path={r.path} />;
        return <Visualizer playing={ps.playing} analyser={ps.analyser} />;
      }
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
      case "cd":
        return <CdDisc ps={ps} />;
      case "albumart":
        return <AlbumArt ps={ps} />;
    }
  }

  // Controls are ALWAYS a live layer — never baked into the faceplate. When the
  // skin ships AI control SPRITES (with states), components render those;
  // otherwise the CSS-skeuomorphic fallback. Either way they're real & animated.
  const sp = skinSprites(skinId);
  if (r.kind === "button") {
    // MOLDED transport faces (sprites/btn-*.png): the icon is part of the
    // hardware art, in the skin's own material — a play button that READS
    // as a play button. Fallbacks: round wells take the knob cap + SVG icon;
    // rectangular wells 9-slice the generic button sprite + SVG icon.
    const round = r.shape === "ellipse";
    const rawBind = r.bind ?? r.id;
    // The main PLAY button is a real play/pause TOGGLE: while playing it shows
    // the pause face (skins ship btn-pause.png) and pauses; otherwise it plays.
    // So a single transport button works without a separate pause button.
    const isPlayPause = rawBind === "play";
    const bindId = isPlayPause && ps.playing ? "pause" : rawBind;
    const onClick = isPlayPause ? (ps.playing ? ps.pause : ps.play) : btnHandler(r, ps);
    const molded = sp && skinMolded(skinId) && ["prev", "play", "pause", "stop", "next"].includes(bindId);
    const face: React.CSSProperties = molded
      ? { backgroundImage: `url(${spriteUrl(skinId, `btn-${bindId}`)})`, backgroundPosition: "center", backgroundSize: "118% 118%", backgroundRepeat: "no-repeat" }
      : sp
        ? round
          ? { backgroundImage: `url(${spriteUrl(skinId, "knob")})`, backgroundSize: "100% 100%", backgroundColor: "transparent", boxShadow: "none", border: 0 }
          : { borderImage: `url(${spriteUrl(skinId, "button")}) 30% fill / 8px stretch`, borderStyle: "solid", borderWidth: "8px", backgroundColor: "transparent", boxShadow: "none" }
        : {};
    const g = molded ? null : glyph(r, bindId);
    if (typeof g === "string" && g.length > 2) face.fontSize = "1.7cqw";   // text labels fit the face
    return (
      <button className={`tbtn ${molded ? "molded" : ""} ${round ? "round" : ""} ${sp ? "sp-btn" : ""}`} style={face} onClick={onClick} title={r.label ?? r.id}>
        {g}
      </button>
    );
  }
  if (r.kind === "toggle") {
    const [on, toggle] = toggleBinding(r, ps);
    return <FlipSwitch skinId={skinId} label={r.label ?? r.id} on={on} toggle={toggle} />;
  }
  if (r.kind === "segmented") return <Segmented r={r} ps={ps} baked={false} />;
  if (r.kind === "knob") return <Knob r={r} ps={ps} skinId={skinId} />;
  if (r.kind === "xy") return <XYPad ps={ps} baked={false} />;
  if (r.kind === "slider-h") return <SliderH r={r} ps={ps} skinId={skinId} />;
  if (r.kind === "slider-arc") return <SliderArc r={r} ps={ps} />;
  if (r.kind === "slider-path") return <SliderPath r={r} ps={ps} />;
  if (r.kind === "slider-v") return <SliderV r={r} ps={ps} skinId={skinId} />;
  return null;
}

// Transport icons are drawn SVG, not font glyphs — Unicode transport chars
// (⏮ ▶ ❚❚) carry font-dependent metrics that never align across a row and
// read as text, not hardware. One 24×24 geometric family, inked by the
// skin's --btn-ink, identical optical weight and centering by construction.
const ICON: Record<string, React.ReactNode> = {
  prev:  <><rect x="4" y="4" width="3.2" height="16" rx="1" /><path d="M20 4.6v14.8a.8.8 0 0 1-1.25.66L8.1 12.66a.8.8 0 0 1 0-1.32L18.75 3.94A.8.8 0 0 1 20 4.6Z" /></>,
  play:  <path d="M6.5 4.3v15.4a.9.9 0 0 0 1.37.77l12.2-7.7a.9.9 0 0 0 0-1.54L7.87 3.53a.9.9 0 0 0-1.37.77Z" />,
  pause: <><rect x="5.5" y="4" width="4.6" height="16" rx="1.2" /><rect x="13.9" y="4" width="4.6" height="16" rx="1.2" /></>,
  stop:  <rect x="5" y="5" width="14" height="14" rx="1.6" />,
  next:  <><rect x="16.8" y="4" width="3.2" height="16" rx="1" /><path d="M4 4.6v14.8a.8.8 0 0 0 1.25.66l10.65-7.4a.8.8 0 0 0 0-1.32L5.25 3.94A.8.8 0 0 0 4 4.6Z" /></>,
  eject: <><path d="M12 4.5 4.8 13h14.4L12 4.5Z" /><rect x="5" y="16" width="14" height="3.4" rx="1.2" /></>,
};
ICON["pl-prev"] = ICON.prev; ICON["pl-play"] = ICON.play;
ICON["pl-pause"] = ICON.pause; ICON["pl-next"] = ICON.next;

const GLYPH: Record<string, string> = {
  "pl-add": "ADD", "pl-rem": "REM", "pl-sel": "SEL", "pl-misc": "MISC",
};
// iconId lets the play button render the pause icon while playing (it differs
// from r.id only for the play/pause toggle); the text-glyph fallback uses r.id.
const glyph = (r: Region, iconId: string = r.id): React.ReactNode => {
  const ic = ICON[iconId];
  if (ic) return <svg className="ticon" viewBox="0 0 24 24" aria-hidden="true">{ic}</svg>;
  return GLYPH[r.id] ?? r.label ?? "";
};

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

/* ---------- flip switch (real, animated toggle) ---------- */
function FlipSwitch({ skinId, label, on, toggle }: { skinId: string; label: string; on: boolean; toggle: () => void }) {
  if (skinSprites(skinId)) {
    // SPRITE switch: the same AI-rendered switch in two states; toggling swaps
    // the art (with a snap transition), not a CSS imitation.
    return (
      <button className="flipsw sp-sw" data-on={on} onClick={toggle} title={`${label}: ${on ? "ON" : "OFF"}`}>
        <span className="sp-sw-stack">
          <img src={spriteUrl(skinId, "switch-off")} alt="" draggable={false} className="sp-sw-img off" />
          <img src={spriteUrl(skinId, "switch-on")} alt="" draggable={false} className="sp-sw-img on" />
        </span>
        <span className="fsw-label">{label}</span>
      </button>
    );
  }
  return (
    <button className="flipsw" data-on={on} onClick={toggle} title={`${label}: ${on ? "ON" : "OFF"}`}>
      <span className="fsw-track"><span className="fsw-bat" /></span>
      <span className="fsw-label">{label}</span>
    </button>
  );
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
function Knob({ r, ps, skinId }: { r: Region; ps: PlayerState; skinId: string }) {
  const value = r.bind === "volume" ? ps.volume : r.bind === "balance" ? ps.balance : 0.5;
  const setV = r.bind === "volume" ? ps.setVolume : ps.setBalance;
  const drag = useRef<{ y: number; v: number } | null>(null);
  useEffect(() => {
    const m = (e: PointerEvent) => {
      if (!drag.current) return;
      const dv = (drag.current.y - e.clientY) / 140;       // drag up = increase
      setV(Math.max(0, Math.min(1, drag.current.v + dv)));
    };
    const u = () => (drag.current = null);
    window.addEventListener("pointermove", m); window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
  }, [setV]);
  const angle = -135 + value * 270;
  if (skinSprites(skinId)) {
    // SPRITE knob: the cap art is STATIC (so its lighting never rotates); a
    // live pointer element orbits the exact center instead.
    return (
      <div className="knob sp-knob" title={`${r.label}: ${(value * 100) | 0}%`}
        onPointerDown={(e) => { drag.current = { y: e.clientY, v: value }; }}>
        <img className="sp-knob-img" src={spriteUrl(skinId, "knob")} alt="" draggable={false} />
        <div className="sp-knob-ptr" style={{ transform: `rotate(${angle}deg)` }} />
        <span className="knob-label">{r.label}</span>
      </div>
    );
  }
  return (
    <div className="knob" title={`${r.label}: ${(value * 100) | 0}%`}
      onPointerDown={(e) => { drag.current = { y: e.clientY, v: value }; }}>
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
    const m = (e: PointerEvent) => drag.current && set(e.clientX, e.clientY);
    const u = () => (drag.current = false);
    window.addEventListener("pointermove", m); window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
  }, []);
  return (
    <div ref={ref} className={`xy ${baked ? "baked" : ""}`} title="Stereo field"
      onPointerDown={(e) => { drag.current = true; set(e.clientX, e.clientY); }}>
      <div className="xy-grid" />
      <div className="xy-puck" style={{ left: `${ps.tone.x * 100}%`, top: `${(1 - ps.tone.y) * 100}%` }} />
    </div>
  );
}

/* ---------- circular seek: the thumb rides an arc around the dial ---------- */
function SliderArc({ r, ps }: { r: Region; ps: PlayerState }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const a0 = r.arc?.start ?? 200, a1 = r.arc?.end ?? 340;
  const value = ps.track.seconds ? ps.elapsed / ps.track.seconds : 0;
  const set = (cx: number, cy: number) => {
    const rc = ref.current?.getBoundingClientRect(); if (!rc) return;
    // angle of the pointer around the ring center, y-down screen convention.
    // UNWRAP into the arc's own continuous range [a0-40, a0+320) so the value is
    // monotonic across the whole arc and never jumps at the 0deg seam — that seam
    // crossing was the "seek breaks past 50%" bug on top/side arcs.
    let a = (Math.atan2(cy - (rc.top + rc.height / 2), cx - (rc.left + rc.width / 2)) * 180) / Math.PI;
    const lo = a0 - 40;
    while (a < lo) a += 360;
    while (a >= lo + 360) a -= 360;
    const v = (a - a0) / (a1 - a0);
    // don't FREEZE when the drag drifts off the ring (the other failure mode) —
    // ignore only the far dead-zone, otherwise clamp to the nearest end.
    if (v < -0.3 || v > 1.3) return;
    ps.seekTo(Math.max(0, Math.min(1, v)));
  };
  useEffect(() => {
    const m = (e: PointerEvent) => drag.current && set(e.clientX, e.clientY);
    const u = () => (drag.current = false);
    window.addEventListener("pointermove", m); window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // geometry in a 100×100 viewBox; the ring radius leaves room for the thumb
  const R = 44;
  const pol = (a: number) => [50 + R * Math.cos((a * Math.PI) / 180), 50 + R * Math.sin((a * Math.PI) / 180)];
  const [sx, sy] = pol(a0); const [ex, ey] = pol(a1);
  const av = a0 + (a1 - a0) * value; const [tx, ty] = pol(av);
  const large = a1 - a0 > 180 ? 1 : 0;
  return (
    <div ref={ref} className="sk-slider-arc" title={`${r.label ?? "Seek"}: ${Math.round(value * 100)}%`}
      onPointerDown={(e) => { drag.current = true; set(e.clientX, e.clientY); }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        <path className="arc-rail" d={`M ${sx} ${sy} A ${R} ${R} 0 ${large} 1 ${ex} ${ey}`} />
        <path className="arc-fill" d={`M ${sx} ${sy} A ${R} ${R} 0 ${a1 - a0 > 180 && value > 0.5 ? 1 : 0} 1 ${tx} ${ty}`} />
        <circle className="arc-thumb" cx={tx} cy={ty} r="4.6" />
      </svg>
    </div>
  );
}

/* freeform seek: the thumb rides an arbitrary spline (r.path, normalized in the
   region rect). Falls back to a flat line when no path is authored. Value is
   arc-length along the curve — monotonic, so it can't break past 50%. */
function SliderPath({ r, ps }: { r: Region; ps: PlayerState }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const value = ps.track.seconds ? ps.elapsed / ps.track.seconds : 0;
  const sp = useMemo(() => buildSpline(r.path ?? []), [r.path]);
  const set = (clientX: number, clientY: number) => {
    const rc = ref.current?.getBoundingClientRect(); if (!rc) return;
    const px = (clientX - rc.left) / rc.width, py = (clientY - rc.top) / rc.height;
    ps.seekTo(Math.max(0, Math.min(1, splineProject(sp, px, py))));
  };
  useEffect(() => {
    const m = (e: PointerEvent) => drag.current && set(e.clientX, e.clientY);
    const u = () => (drag.current = false);
    window.addEventListener("pointermove", m); window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp]);
  const railD = sp.pts.map((p, i) => `${i ? "L" : "M"}${(p.x * 100).toFixed(2)} ${(p.y * 100).toFixed(2)}`).join(" ");
  const tip = Math.max(0, Math.min(1, value)) * sp.len;
  const fillD = sp.pts.filter((_, i) => sp.cum[i] <= tip)
    .map((p, i) => `${i ? "L" : "M"}${(p.x * 100).toFixed(2)} ${(p.y * 100).toFixed(2)}`).join(" ") || "M0 50";
  const th = splineAt(sp, value);
  return (
    <div ref={ref} className="sk-slider-path" title={`${r.label ?? "Seek"}: ${Math.round(value * 100)}%`}
      onPointerDown={(e) => { drag.current = true; set(e.clientX, e.clientY); }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <path className="bolt-rail" d={railD} />
        <path className="bolt-fill" d={fillD} />
      </svg>
      <span className="bolt-thumb" style={{ left: `${th.x * 100}%`, top: `${th.y * 100}%` }} />
    </div>
  );
}

/* ---------- sliders ---------- */
function SliderH({ r, ps, skinId }: { r: Region; ps: PlayerState; skinId: string }) {
  const thumbSprite: React.CSSProperties = skinSprites(skinId)
    ? { backgroundImage: `url(${spriteUrl(skinId, "thumb")})`, backgroundSize: "100% 100%", backgroundColor: "transparent", boxShadow: "none", borderRadius: 0 }
    : {};
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
    const m = (e: PointerEvent) => drag.current && set(e.clientX);
    const u = () => (drag.current = false);
    window.addEventListener("pointermove", m); window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
  }, []);
  return (
    <div ref={ref} className="sk-slider-h"
      onPointerDown={(e) => { drag.current = true; set(e.clientX); }} title={r.label}>
      <div className="rail" /><div className="fill" style={{ width: `${value * 100}%` }} />
      <div className="thumb" style={{ left: `calc(${value} * (100% - var(--thumb-h, 11px)))`, ...thumbSprite }} />
    </div>
  );
}

function SliderV({ r, ps, skinId }: { r: Region; ps: PlayerState; skinId: string }) {
  const thumbSprite: React.CSSProperties = skinSprites(skinId)
    ? { backgroundImage: `url(${spriteUrl(skinId, "thumb")})`, backgroundSize: "100% 100%", backgroundColor: "transparent", boxShadow: "none", borderRadius: 0 }
    : {};
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
    const m = (e: PointerEvent) => drag.current && set(e.clientY);
    const u = () => (drag.current = false);
    window.addEventListener("pointermove", m); window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
  }, [disabled]);
  return (
    <div className="eq-slot">
      <div ref={ref} className="sk-slider-v" data-disabled={disabled}
        onPointerDown={(e) => { drag.current = true; set(e.clientY); }} title={r.label}>
        <div className="rail" /><div className="fill" style={{ height: `${value * 100}%` }} />
        <div className="thumb" style={{ bottom: `calc(${value} * (100% - var(--thumb-h, 11px)))`, ...thumbSprite }} />
      </div>
      <span className="eq-label">{r.label}</span>
    </div>
  );
}

/* ---------- mock CD: album art on a spinning, reflective disc ----------
   The platter eases its angular velocity toward a cruise speed when playback
   starts and coasts back to a stop when paused/stopped, driven by rAF on a ref
   (no per-frame React re-render). The velocity follows a frame-rate-independent
   exponential approach — a short time constant on spin-up reads as a motor
   catching the disc; a long one on spin-down reads as friction letting it coast
   to rest. The disc is a generated photoreal silver CD data-side (no printed
   art); it rotates WITH the platter so its diffraction sweeps as it spins. An
   optional blurred album-cover layer tints the silver via mix-blend-mode:color
   — the metal's luminance kept, the album's hue applied. The specular gloss is
   FIXED — the light source doesn't move — which reads as a reflection off a
   spinning disc. */
const CD_ECHOES = 5;     // rotational-motion-blur layers (anti-strobe)
const CD_TRAIL = 1.4;    // trail length in FRAMES of motion the echoes span
const CD_SMEAR = 0.5;    // per-echo opacity (bottom layer stays opaque for coverage)
function CdDisc({ ps }: { ps: PlayerState }) {
  const layers = useRef<HTMLDivElement[]>([]);
  const stack = useRef<HTMLDivElement>(null);
  const playingRef = useRef(ps.playing);
  playingRef.current = ps.playing;
  useEffect(() => {
    let raf = 0, angle = 0, vel = 0, last = 0;
    // A real CD drive does two distinct things, so we model two distinct regimes
    // rather than easing toward a target with one curve:
    const CRUISE = 1000;       // deg/s cruise (~2.8 rev/s) — a CD spinning at FULL SPEED, not a slow platter
    const SPINUP_ACCEL = 1300; // deg/s² motor torque vs. the disc's inertia — sets how snappy 0→cruise feels (~1.0s)
    const KNEE = 0.82;         // governor: full torque until 82% of cruise, then taper to 0 — settles in without overshoot
    const FRIC_C = 18;         // deg/s² Coulomb (dry) friction — constant drag that brings it to an EXACT stop, and the gentle end-of-coast decel
    const FRIC_V = 1.4;        // 1/s viscous friction (∝ vel) — the hard initial slow; with FRIC_C sets the ~3s total coast
    const MAX_BLUR = 0.15;     // px isotropic softening on top — small; the ECHO layers do the anti-strobe smear
    const tick = (t: number) => {
      if (!last) last = t;
      const dt = Math.min(0.05, (t - last) / 1000); last = t;
      if (playingRef.current) {
        // motor: torque-limited ramp (near-linear) with a soft governor near cruise.
        // head = 1 (full torque) until KNEE·cruise, then falls linearly to 0 at cruise.
        const head = Math.max(0, Math.min(1, (CRUISE - vel) / (CRUISE * (1 - KNEE))));
        vel = Math.min(CRUISE, vel + SPINUP_ACCEL * head * dt);
      } else {
        // motor off: inertial coast. Coulomb + viscous friction — fast slow at speed,
        // gentle at the end, and the constant term guarantees a finite stop (no asymptote).
        vel -= (FRIC_C + FRIC_V * vel) * dt;
        if (vel < 0.4) vel = 0;
      }
      angle = (angle + vel * dt) % 360;
      // ROTATIONAL motion blur: isotropic blur can't mask the spin's strobe (the disc
      // jumps 8–17°/frame at cruise), so we stack N echo layers across `trail` frames of
      // motion — oldest at the back (opaque, for coverage), current angle on top. echoDeg
      // → 0 at rest, so the disc is sharp when stopped and smears only when spinning.
      const ls = layers.current, n = ls.length;
      const echoDeg = n > 1 ? (vel / 60) * CD_TRAIL / (n - 1) : 0;
      for (let i = 0; i < n; i++) {
        const el = ls[i]; if (!el) continue;
        const age = (n - 1) - i;
        el.style.transform = `rotate(${(angle - age * echoDeg).toFixed(2)}deg)`;
        el.style.opacity = i === 0 ? "1" : String(CD_SMEAR);
      }
      const st = stack.current;
      if (st) { const blur = (vel / CRUISE) * MAX_BLUR; st.style.filter = blur > 0.04 ? `blur(${blur.toFixed(2)}px)` : ""; }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  const cover = ps.track.cover;
  return (
    <div className="dyn cd-disc" data-playing={ps.playing}>
      <div className="cd-wrap">
        <div className="cd-platter">
          <div className="cd-stack" ref={stack}>
            {Array.from({ length: CD_ECHOES }).map((_, i) => (
              <div key={i} className="cd-surface" ref={(el) => { if (el) layers.current[i] = el; }} />
            ))}
          </div>
          {cover && <img className="cd-tint" src={cover} alt="" draggable={false} />}
        </div>
        <div className="cd-gloss" />
      </div>
    </div>
  );
}

/* the bare cover image as a placeable element (no disc) */
function AlbumArt({ ps }: { ps: PlayerState }) {
  const cover = ps.track.cover;
  return cover
    ? <img className="dyn albumart" src={cover} alt={`${ps.track.artist} — ${ps.track.title}`} draggable={false} />
    : <div className="dyn albumart albumart-fallback">
        <span className="cd-fb-title">{ps.track.title}</span>
        <span className="cd-fb-artist">{ps.track.artist}</span>
      </div>;
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
