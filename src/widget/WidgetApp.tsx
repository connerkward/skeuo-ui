// WidgetApp — what the Tauri desktop app (and ?widget=1 preview) renders.
//
// A single skin's <Composite> on a fully transparent background: the skin's
// frame PNG (with alpha) is the only visible thing, so the window reads as a
// shaped, non-rectangular floating player. Grabbing the frame drags the OS
// window; the transport drives the user's real Spotify (active device).
//
// Skin selection comes from (in order): the deep link the app was opened with
// (skeuo://skin/<id> or the tray menu), a ?skin= query for browser preview, or
// a sensible default. The website's "open in desktop player" button is what
// makes the handoff feel automatic.

import { useEffect, useState } from "react";
import { Composite } from "../player/Composite";
import { playerTemplate } from "../template/winamp-layout";
import { skinList } from "../player/skins";
import { useSpotify } from "../spotify/useSpotify";
import { initialSkinParam, isTauri } from "../platform";
import { initDeepLinks } from "../desktop/deeplink";
import { startWidgetDrag } from "./drag";
import { initClickThrough, updateClickThroughSkin } from "./clickthrough";
import "../skins/all"; // player + skin CSS (same set the website loads)
import "./widget.css";

const DEFAULT_SKIN = "pebble";

function validSkin(id: string | null): string | null {
  return id && skinList.some((s) => s.id === id) ? id : null;
}

export default function WidgetApp() {
  const [skinId, setSkinId] = useState(() => validSkin(initialSkinParam()) ?? DEFAULT_SKIN);
  const sp = useSpotify();

  // route deep links / tray picks into the skin (Tauri only; no-op on web)
  useEffect(() => {
    let dispose = () => {};
    void initDeepLinks((id) => { if (validSkin(id)) setSkinId(id); }).then((d) => { dispose = d; });
    return () => dispose();
  }, []);

  // Per-pixel click-through: clicks on the skin's transparent areas pass to the
  // app behind; clicks on the skin (and the top bar) hit the widget.
  useEffect(() => {
    updateClickThroughSkin(skinId);
    return initClickThrough();
  }, [skinId]);

  // the widget is always Spotify-driven; if not linked it falls back to the
  // local demo engine inside usePlayer (drive === null), so it's never blank.
  const drive = sp.status === "connected" ? sp.drive : null;
  const skin = skinList.find((s) => s.id === skinId);

  return (
    <div className="widget-root" onPointerDown={startWidgetDrag}>
      <WidgetBar
        skinName={skin?.name ?? skinId}
        status={sp.status}
        configured={sp.isConfigured}
        onConnect={sp.login}
      />
      {/* grabbing the skin BODY (flesh between controls) drags the OS window;
          controls opt out via NO_DRAG in drag.ts so they stay clickable */}
      <div className="widget-stage">
        <Composite template={playerTemplate} skinId={skinId} spotifyDrive={drive} />
      </div>
    </div>
  );
}

// A slim, auto-hiding top strip: skin name + Spotify connect/state + (in Tauri)
// a hide-to-tray close. Stays out of the way until you hover the top edge.
function WidgetBar({ skinName, status, configured, onConnect }: {
  skinName: string;
  status: ReturnType<typeof useSpotify>["status"];
  configured: boolean;
  onConnect: () => void;
}) {
  const hide = async () => {
    if (!isTauri()) return;
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      await getCurrentWindow().hide();
    } catch { /* noop */ }
  };

  const linked = status === "connected";
  const label =
    !configured ? "Spotify not configured"
    : status === "connecting" ? "Connecting…"
    : status === "error" ? "Spotify error"
    : linked ? "Spotify linked"
    : "Connect Spotify";

    // no data-no-drag: the bar's empty area drags the window (bubbles to the
    // widget-root handler); its buttons opt out via the `button` NO_DRAG rule.
  return (
    <div className="widget-bar">
      <span className="wb-skin">{skinName}</span>
      <button
        className="wb-sp"
        data-status={status}
        disabled={!configured || linked || status === "connecting"}
        onClick={onConnect}
        title={label}
      >
        <span className="wb-dot" data-status={status} />
        {label}
      </button>
      {isTauri() && (
        <button className="wb-close" onClick={hide} title="Hide to menu bar">×</button>
      )}
    </div>
  );
}
