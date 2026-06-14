import { useEffect, useRef, useState } from "react";
import type { Region, Template } from "../template/schema";
import { fmtTime } from "./data";
import { usePlayer, type PlayerState } from "./usePlayer";
import { Visualizer } from "./Visualizer";
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
              <Visualizer playing={ps.playing} analyser={ps.analyser} variant="radial" />
              <div className="dial-readout">
                <span className="dial-time" data-paused={!ps.playing}>{fmtTime(ps.elapsed)}</span>
                <span className="dial-track">{ps.track.title}</span>
              </div>
            </div>
          );
        }
        if (r.vis === "teeth") return <Visualizer playing={ps.playing} analyser={ps.analyser} variant="teeth" />;
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
    // angle of the pointer around the ring center, y-down screen convention
    let a = (Math.atan2(cy - (rc.top + rc.height / 2), cx - (rc.left + rc.width / 2)) * 180) / Math.PI;
    if (a < 0) a += 360;
    if (a < a0 - 14 || a > a1 + 14) return;       // ignore grabs off the track
    ps.seekTo(Math.max(0, Math.min(1, (a - a0) / (a1 - a0))));
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

/* ---------- bolt seek: the thumb rides a zigzag lightning path ---------- */
function SliderPath({ r, ps }: { r: Region; ps: PlayerState }) {
  const ref = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const value = ps.track.seconds ? ps.elapsed / ps.track.seconds : 0;
  const set = (clientX: number) => {
    const rc = ref.current?.getBoundingClientRect(); if (!rc) return;
    ps.seekTo(Math.max(0, Math.min(1, (clientX - rc.left) / rc.width)));
  };
  useEffect(() => {
    const m = (e: PointerEvent) => drag.current && set(e.clientX);
    const u = () => (drag.current = false);
    window.addEventListener("pointermove", m); window.addEventListener("pointerup", u);
    return () => { window.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); };
  }, []);
  // a zigzag lightning bolt across a 100×40 viewBox: N segments alternating hi/lo
  const N = 7, HI = 8, LO = 32;
  const pts = Array.from({ length: N + 1 }, (_, i) => [(i / N) * 100, i % 2 === 0 ? LO : HI] as const);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1]}`).join(" ");
  // thumb rides the bolt at `value`: x = value across width, y interpolated on the segment
  const seg = Math.min(N - 1, Math.floor(value * N));
  const t = value * N - seg;
  const tx = value * 100;
  const ty = pts[seg][1] + (pts[seg + 1][1] - pts[seg][1]) * t;
  const fillD = pts.slice(0, seg + 1).map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1]}`).join(" ") + ` L${tx.toFixed(1)} ${ty.toFixed(1)}`;
  return (
    <div ref={ref} className="sk-slider-path" title={`${r.label ?? "Seek"}: ${Math.round(value * 100)}%`}
      onPointerDown={(e) => { drag.current = true; set(e.clientX); }}>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none">
        <path className="bolt-rail" d={d} />
        <path className="bolt-fill" d={fillD} />
      </svg>
      <span className="bolt-thumb" style={{ left: `${tx}%`, top: `${(ty / 40) * 100}%` }} />
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
