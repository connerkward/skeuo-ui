import { useEffect } from "react";
import { Composite, type RuntimeSkinView } from "../player/Composite";
import type { Template } from "../template/schema";
import type { SkinAssets } from "../player/skins";
import type { SpotifyDrive, SpotifyHook } from "../spotify/useSpotify";
import { useSwipe } from "./useSwipe";
import { Brand } from "../components/Brand";
import { MobileSpotify } from "./MobileSpotify";
import { MobileSkinStrip } from "./MobileSkinStrip";
import { skinFont, skinFontStyle } from "../player/skinFonts";

interface Props {
  template: Template;
  skins: SkinAssets[];          // visible skins (already !hidden filtered)
  skinId: string;
  setSkinId: (id: string) => void;
  onCreate?: () => void;        // fired by the trailing "Generate your own" page
  // Spotify connect lives in the top bar; the drive (when in spotify mode) makes
  // the on-screen skin reflect real playback instead of the local demo.
  sp: SpotifyHook;
  mode: "local" | "spotify";
  setMode: (m: "local" | "spotify") => void;
  spotifyDrive: SpotifyDrive | null;
  // top-bar treatment matching the desktop bar:
  connectEnabled?: boolean;      // show the Spotify connect pill (hidden while broken)
  share?: React.ReactNode;       // the Share button (rendered by App)
  // cloud/generated skins in the carriage need a per-skin runtime so they render
  // through the SAME <Composite runtime={…}> path as desktop — without it a cloud
  // skin would fall back to the bundled donor template and show the wrong device.
  // Map of skin id → resolved runtime view; absent ids render as built-ins.
  runtimes?: Record<string, RuntimeSkinView>;
}

// Mobile shell (<820px): a compact top bar + a swipeable carriage of skins,
// with a trailing "+ Generate your own" page. Desktop never mounts this.
export function MobileChrome({ template, skins, skinId, setSkinId, onCreate, sp, mode, setMode, spotifyDrive,
  connectEnabled, share, runtimes }: Props) {
  // pages = every visible skin, plus one trailing "create" page
  const createIdx = skins.length;
  const startIdx = Math.max(0, skins.findIndex((s) => s.id === skinId));
  const sw = useSwipe(skins.length + 1, startIdx);

  // keep the app's skinId in sync with the swiped page (skip the create page)
  useEffect(() => {
    if (sw.index < skins.length) setSkinId(skins[sw.index].id);
  }, [sw.index, skins, setSkinId]);

  const fire = () => {
    onCreate?.();
    window.dispatchEvent(new CustomEvent("skeuo:create"));
  };

  return (
    <div className="m-shell">
      <header className="m-topbar">
        <Brand size="sm" className="m-title" />
        <div className="m-topbar-actions">
          {share}
          {connectEnabled && <MobileSpotify sp={sp} mode={mode} setMode={setMode} />}
          <button className="m-cta" onClick={fire} aria-label="Create your own skin">
            <span className="m-cta-mark">✦</span> Create
          </button>
        </div>
      </header>

      <div className="m-stage" {...sw.bind}>
        {/* small skin title + blurb tucked in the corner (the skin's identity,
            since the full-screen narrow view has no side title card) */}
        {sw.index < skins.length && (
          <div className="m-skin-label">
            <span className="m-skin-name" style={skinFontStyle(skinFont(skins[sw.index].id))}>
              {skins[sw.index].name.replace(/\s*✦\s*$/, "")}
            </span>
            <span className="m-skin-blurb">{skins[sw.index].blurb}</span>
          </div>
        )}
        <div
          className="m-track"
          style={{
            transform: `translateX(calc(${-sw.index * 100}% + ${sw.dragX}px))`,
            transition: sw.dragging ? "none" : "transform .34s cubic-bezier(.22,.61,.36,1)",
          }}
        >
          {skins.map((s, i) => (
            <div className="m-page" key={s.id}>
              {/* only mount the composite for nearby pages — the audio/canvas
                  graph is heavy; off-screen skins render an empty placeholder */}
              {Math.abs(i - sw.index) <= 1 ? (
                // drive the CURRENT page from real Spotify when connected; the
                // neighbors stay on the local demo (off-screen, about to mount).
                // cloud/generated skins pass their resolved runtime so they render
                // their OWN device frame + template (not the bundled donor).
                <Composite template={template} skinId={s.id}
                  runtime={runtimes?.[s.id]}
                  spotifyDrive={i === sw.index ? spotifyDrive : null} />
              ) : (
                <div className="m-placeholder" />
              )}
            </div>
          ))}
          <div className="m-page m-create" key="__create">
            <button className="m-create-card" onClick={fire}>
              <span className="m-create-plus">+</span>
              <span className="m-create-label">Generate your own</span>
              <span className="m-create-sub">Design a new skeuomorphic skin</span>
            </button>
          </div>
        </div>
      </div>

      <MobileSkinStrip
        skins={skins}
        index={sw.index}
        createIdx={createIdx}
        onPick={(i) => sw.goTo(i)}
      />
    </div>
  );
}
