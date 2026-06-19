import { useEffect } from "react";
import { Composite } from "../player/Composite";
import type { Template } from "../template/schema";
import type { SkinAssets } from "../player/skins";
import type { SpotifyDrive, SpotifyHook } from "../spotify/useSpotify";
import { useSwipe } from "./useSwipe";
import { Brand } from "../components/Brand";
import { MobileSpotify } from "./MobileSpotify";
import { MobileSkinStrip } from "./MobileSkinStrip";

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
}

// Mobile shell (<820px): a compact top bar + a swipeable carriage of skins,
// with a trailing "+ Generate your own" page. Desktop never mounts this.
export function MobileChrome({ template, skins, skinId, setSkinId, onCreate, sp, mode, setMode, spotifyDrive }: Props) {
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
          <MobileSpotify sp={sp} mode={mode} setMode={setMode} />
          <button className="m-menu" onClick={() => sw.goTo(createIdx)} aria-label="Generate your own skin">
            + skin
          </button>
        </div>
      </header>

      <div className="m-stage" {...sw.bind}>
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
                // neighbors stay on the local demo (off-screen, about to mount)
                <Composite template={template} skinId={s.id}
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
        template={template}
        skins={skins}
        index={sw.index}
        createIdx={createIdx}
        onPick={(i) => sw.goTo(i)}
      />
    </div>
  );
}
