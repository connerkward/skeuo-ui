import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Composite } from "./player/Composite";
import { SkinThumb } from "./player/SkinThumb";
import { useDocumentPip } from "./player/useDocumentPip";
import { playerTemplate } from "./template/winamp-layout";
import { skinList, thumbUrl } from "./player/skins";
import "./skins/all"; // app.css + player.css + every skin palette (shared with the widget)
// ── feature: generate-from-prompt ────────────────────────────────────────────
import { type RuntimeSkin } from "./generate/CreatePanel";
import { CreateWizard } from "./generate/CreateWizard";
import "./generate/create.css";
// ── feature: Spotify connect & control ───────────────────────────────────────
import { useSpotify } from "./spotify/useSpotify";
import { SpotifyConnect } from "./spotify/SpotifyConnect";
import "./spotify/spotify.css";
// ── feature: mobile swipe shell ──────────────────────────────────────────────
import { MobileChrome } from "./mobile/MobileChrome";
import { MobileSpotify } from "./mobile/MobileSpotify";
// ── feature: desktop widget handoff (skeuo:// → Tauri app) ───────────────────
import { DesktopHandoff } from "./desktop/DesktopHandoff";
// ── feature: export the running skin as an animated GIF ──────────────────────
import { ExportGifButton } from "./export/ExportGifButton";
import { Brand } from "./components/Brand";
import { initialSkinParam, isMobileApp } from "./platform";

// expose the single-source-of-truth template for tooling (wireframe/mask export)
(window as unknown as { __template: unknown }).__template = playerTemplate;

// Document-PiP "Float player" button is hidden for now — the PiP window's
// browser-owned chrome (title bar, opaque rectangular frame) can't be removed,
// so it doesn't match the transparent Tauri widget. The hook + portal stay
// wired (the docked player renders through the same portal); flip to re-enable.
const FLOAT_ENABLED = false;
// Spotify "Connect" is hidden until the playback issue is fixed; flip to re-enable.
const CONNECT_ENABLED = false;

export default function App() {
  const visible = skinList.filter((s) => !s.hidden);
  // honor a shared ?skin=<id> link (skeuo.fm/?skin=…) when it names a known skin
  // (built-in or a persisted generated one); otherwise the first skin.
  const [skinId, setSkinId] = useState(() => {
    const p = initialSkinParam();
    if (!p) return visible[0].id;
    if (visible.some((s) => s.id === p)) return p;
    try { if ((JSON.parse(localStorage.getItem("skeuo:skins") || "[]") as RuntimeSkin[]).some((s) => s.id === p)) return p; } catch { /* ignore */ }
    return visible[0].id;
  });
  const [wire, setWire] = useState(false);

  // generate-from-prompt + live template editor. Generated skins are PAID content —
  // persist them to localStorage (frames live on disk via the server `store`, so the
  // entries are just small URLs) and rehydrate on load so a reload/restart never wipes them.
  const [runtimeSkins, setRuntimeSkins] = useState<RuntimeSkin[]>(() => {
    try { return JSON.parse(localStorage.getItem("skeuo:skins") || "[]") as RuntimeSkin[]; }
    catch { return []; }
  });
  useEffect(() => {
    try { localStorage.setItem("skeuo:skins", JSON.stringify(runtimeSkins)); }
    catch { try { localStorage.setItem("skeuo:skins", JSON.stringify(runtimeSkins.slice(-6))); } catch { /* quota; keep last 6 */ } }
  }, [runtimeSkins]);
  // keep ?skin= in sync with the active skin so the address bar + any copied link
  // always reflect what's on screen, even after switching skins.
  useEffect(() => {
    try {
      const u = new URL(window.location.href);
      u.searchParams.set("skin", skinId);
      window.history.replaceState(null, "", u);
    } catch { /* ignore */ }
  }, [skinId]);
  const [showCreate, setShowCreate] = useState(false);
  const activeRuntime = runtimeSkins.find((s) => s.id === skinId);
  const activeMeta = [...visible, ...runtimeSkins].find((s) => s.id === skinId);

  // Spotify: drive the skin from real playback only in spotify mode
  const sp = useSpotify();
  const [mode, setMode] = useState<"local" | "spotify">("local");
  const spotifyDrive = mode === "spotify" ? sp.drive : null;
  // auto-engage Spotify mode once linked, so the player isn't still showing the
  // local demo while the panel says "connected" (the user can switch back)
  useEffect(() => { if (sp.status === "connected") setMode("spotify"); }, [sp.status]);

  // responsive: below ~820px mount the swipe shell instead of the sidebar. The
  // iOS app ALWAYS uses the mobile shell (full-screen skin + swipe), regardless
  // of viewport — it's a phone app, never the desktop sidebar.
  const [mobile, setMobile] = useState(() =>
    isMobileApp() || (typeof window !== "undefined" && window.matchMedia("(max-width: 820px)").matches));
  useEffect(() => {
    if (isMobileApp()) { setMobile(true); return; }
    const mq = window.matchMedia("(max-width: 820px)");
    const on = () => setMobile(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  // Float the running skin into an always-on-top Document-PiP window (desktop
  // Chrome/Edge). `host` is the in-page portal target; the live <Composite> is
  // portaled into either it or the PiP window, so floating never remounts the
  // player — the same instance keeps driving Spotify.
  const pip = useDocumentPip();
  const [pipHost, setPipHost] = useState<HTMLElement | null>(null);
  // top-bar popovers (Connect / Desktop) — only one open at a time
  const [panel, setPanel] = useState<null | "connect" | "desktop">(null);

  const onCreated = useCallback((s: RuntimeSkin) => {
    setRuntimeSkins((rs) => [...rs, s]);
    setSkinId(s.id);
    setShowCreate(false);
  }, []);

  const runtimeView = activeRuntime
    ? { frameUrl: activeRuntime.frameUrl, template: activeRuntime.template, style: activeRuntime.style }
    : undefined;

  // ── mobile shell ───────────────────────────────────────────────────────────
  if (mobile) {
    // a generated skin isn't in the registry carriage — show it full-screen
    if (activeRuntime) {
      return (
        <div className="m-shell">
          <header className="m-topbar">
            <button className="m-menu" onClick={() => setSkinId(visible[0].id)} aria-label="Back to skins">← skins</button>
            <h1 className="m-title">{activeRuntime.name}</h1>
            <div className="m-topbar-actions">
              <MobileSpotify sp={sp} mode={mode} setMode={setMode} />
            </div>
          </header>
          <div className="m-stage">
            <div className="m-page">
              <Composite template={playerTemplate} skinId={skinId} runtime={runtimeView} spotifyDrive={spotifyDrive} />
            </div>
          </div>
        </div>
      );
    }
    return (
      <>
        <MobileChrome
          template={playerTemplate}
          skins={visible}
          skinId={skinId}
          setSkinId={setSkinId}
          onCreate={() => setShowCreate(true)}
          sp={sp}
          mode={mode}
          setMode={setMode}
          spotifyDrive={spotifyDrive}
        />
        {showCreate && (
          <div className="wiz-modal" onPointerDown={(e) => e.target === e.currentTarget && setShowCreate(false)}>
            <button className="create-close" onClick={() => setShowCreate(false)} aria-label="Close create">×</button>
            <CreateWizard onCreated={onCreated} />
          </div>
        )}
      </>
    );
  }

  // ── desktop ──────────────────────────────────────────────────────────────────
  // Layout by the user's flow:
  //   • BROWSE — a scrolling left sidebar of skins (animated thumbnail + name)
  //   • the selected skin shown large in the stage
  //   • CREATE your own — the loud green top-bar CTA
  //   • Connect / Desktop live in the top bar; Share + Template-view sit next to
  //     the skin (the artifact). Edit was removed.
  const closePanel = () => setPanel(null);
  return (
    <div className="app">
      <header className="topbar">
        <Brand className="topbar-brand" />
        <p className="topbar-tag">
          One sentence → a <b>real, working</b> skeuomorphic player that drives your music.
        </p>
        <a className="topbar-how" href="/process/" target="_blank" rel="noopener">
          How it works <span className="arr">→</span>
        </a>
        <div className="topbar-right">
          <button className={`tb-btn ${wire ? "on" : ""}`} onClick={() => setWire((v) => !v)}
            title="Show the control template (wireframe) over the skin">
            <WireIcon /> Template view
          </button>
          {CONNECT_ENABLED && (
            <button className={`tb-btn ${sp.status === "connected" ? "on" : ""}`}
              onClick={() => setPanel("connect")} title="Drive the player with your Spotify">
              <span className="tb-dot" data-status={sp.status} />
              {sp.status === "connected" ? "Spotify" : "Connect"}
            </button>
          )}
          <button className="tb-btn" onClick={() => setPanel("desktop")}
            title="Run this skin as a desktop widget">
            ⤓ Desktop
          </button>
          {/* the ONE call-to-action — everything else is subordinate to this */}
          <button className={`tb-cta ${showCreate ? "open" : ""}`} onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? <>× Close</> : <><span className="tb-cta-plus">✦</span> Create your own skin</>}
          </button>
        </div>
      </header>

      {/* left gallery — scrolling skin list with animated thumbnails + names */}
      <aside className="gallery">
        <div className="gallery-list">
          <p className="gallery-label">Skins</p>
          {visible.map((s) => (
            <button key={s.id} className={`skin-row ${s.id === skinId ? "active" : ""}`}
              onClick={() => setSkinId(s.id)} title={`${s.name} — ${s.blurb}`}>
              <SkinThumb skinId={s.id} imgSrc={thumbUrl(s.id)} />
              <span className="skin-row-meta">
                <span className="skin-row-name">{s.name}</span>
                <span className="skin-row-blurb">{s.blurb}</span>
              </span>
            </button>
          ))}
          {runtimeSkins.length > 0 && <p className="gallery-label sub">Your skins</p>}
          {runtimeSkins.map((s) => (
            <button key={s.id} className={`skin-row ${s.id === skinId ? "active" : ""}`}
              onClick={() => setSkinId(s.id)} title={s.name}>
              <SkinThumb skinId={s.id} imgSrc={s.frameUrl} animate={false} />
              <span className="skin-row-meta">
                <span className="skin-row-name">{s.name}</span>
                <span className="skin-row-blurb">{s.blurb}</span>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="stage">
        <div className="stage-inner">
          {/* portal target when docked; empty while the player is floating */}
          <div className="player-host" ref={setPipHost} />
          {pip.pipWindow && (
            <div className="stage-popped">
              <span className="pop-ico">⧉</span>
              <p>Player is floating in its own window.</p>
              <button className="pop-back" onClick={pip.close}>Bring it back</button>
            </div>
          )}
          {/* meta panel — beside the player on wide screens, below it on narrow */}
          <div className="stage-meta">
            <figcaption className="stage-caption">
              <span className="cap-name">{activeMeta?.name ?? skinId}</span>
              {activeMeta?.blurb && <span className="cap-blurb">{activeMeta.blurb}</span>}
            </figcaption>
            {/* the action ON the skin — Share (Connect/Template moved to the bar) */}
            <div className="skin-actions">
              <ExportGifButton
                skinId={skinId}
                template={playerTemplate}
                runtime={runtimeView}
                spotifyDrive={spotifyDrive}
              />
            </div>
          </div>
        </div>
      </main>

      {/* Connect / Desktop open as centered panels */}
      {panel && (
        <div className="panel-scrim" onPointerDown={(e) => e.target === e.currentTarget && closePanel()}>
          <div className="panel-card">
            <button className="panel-close" onClick={closePanel} aria-label="Close">×</button>
            {panel === "connect" && <SpotifyConnect sp={sp} mode={mode} onMode={setMode} />}
            {panel === "desktop" && (
              <>
                <DesktopHandoff skinId={skinId} skinName={activeMeta?.name ?? skinId} />
                {FLOAT_ENABLED && pip.supported && (
                  <button className="feature-btn pip-float-btn"
                    onClick={() => (pip.pipWindow ? pip.close() : pip.open())}>
                    {pip.pipWindow ? "⧉ Bring player back" : "⧉ Float player — no install"}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {showCreate && (
        <div className="wiz-modal" onPointerDown={(e) => e.target === e.currentTarget && setShowCreate(false)}>
          <button className="create-close" onClick={() => setShowCreate(false)} aria-label="Close create">×</button>
          <CreateWizard onCreated={onCreated} />
        </div>
      )}

      {/* ONE portal, container toggles dock ⇄ float so the player never remounts */}
      {pipHost && createPortal(
        <div className="pip-stage">
          <Composite
            template={playerTemplate}
            skinId={skinId}
            showWireframe={wire}
            runtime={runtimeView}
            spotifyDrive={spotifyDrive}
          />
        </div>,
        pip.pipWindow ? pip.pipWindow.document.body : pipHost,
      )}
    </div>
  );
}

function WireIcon() {
  return (
    <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 10h18M9 10v9" />
    </svg>
  );
}
