import { useCallback, useEffect, useState } from "react";
import { Composite } from "./player/Composite";
import { playerTemplate } from "./template/winamp-layout";
import { skinList, skinTemplateUrl } from "./player/skins";
import type { Template } from "./template/schema";
import "./skins/all"; // app.css + player.css + every skin palette (shared with the widget)
// ── feature: template editor + generate-from-prompt ──────────────────────────
import { type RuntimeSkin } from "./generate/CreatePanel";
import { CreateWizard } from "./generate/CreateWizard";
import { TemplateEditor } from "./editor/TemplateEditor";
import "./generate/create.css";
// ── feature: Spotify connect & control ───────────────────────────────────────
import { useSpotify } from "./spotify/useSpotify";
import { SpotifyConnect } from "./spotify/SpotifyConnect";
import "./spotify/spotify.css";
// ── feature: mobile swipe shell ──────────────────────────────────────────────
import { MobileChrome } from "./mobile/MobileChrome";
// ── feature: desktop widget handoff (skeuo:// → Tauri app) ───────────────────
import { DesktopHandoff } from "./desktop/DesktopHandoff";
// ── feature: export the running skin as an animated GIF ──────────────────────
import { ExportGifButton } from "./export/ExportGifButton";
import { Brand } from "./components/Brand";
import { initialSkinParam } from "./platform";

// expose the single-source-of-truth template for tooling (wireframe/mask export)
(window as unknown as { __template: unknown }).__template = playerTemplate;

const skinHasFrame = (id: string) => !!skinList.find((s) => s.id === id)?.has.includes("frame");

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
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState<Template | null>(null);          // live editor override
  const [diskTemplate, setDiskTemplate] = useState<Template | null>(null); // registry skin's real template.json
  const activeRuntime = runtimeSkins.find((s) => s.id === skinId);

  // Spotify: drive the skin from real playback only in spotify mode
  const sp = useSpotify();
  const [mode, setMode] = useState<"local" | "spotify">("local");
  const spotifyDrive = mode === "spotify" ? sp.drive : null;
  // auto-engage Spotify mode once linked, so the player isn't still showing the
  // local demo while the panel says "connected" (the user can switch back)
  useEffect(() => { if (sp.status === "connected") setMode("spotify"); }, [sp.status]);

  // responsive: below ~820px mount the swipe shell instead of the sidebar
  const [mobile, setMobile] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 820px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 820px)");
    const on = () => setMobile(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  // load the selected registry skin's actual template.json so the editor edits
  // the real on-disk layout (runtime skins carry their template inline)
  const diskUrl = activeRuntime ? undefined : skinTemplateUrl(skinId);
  useEffect(() => {
    if (!diskUrl) { setDiskTemplate(null); return; }
    let live = true;
    fetch(diskUrl).then((r) => r.json()).then((t) => { if (live) setDiskTemplate(t); }).catch(() => {});
    return () => { live = false; };
  }, [diskUrl]);

  const onCreated = useCallback((s: RuntimeSkin) => {
    setRuntimeSkins((rs) => [...rs, s]);
    setSkinId(s.id);
    setShowCreate(false);
    setEdited(null);
  }, []);

  const editorTemplate: Template = activeRuntime ? activeRuntime.template : diskTemplate ?? playerTemplate;
  const editorFrame = activeRuntime?.frameUrl
    ?? (skinHasFrame(skinId) ? `/skins/${skinId}/frame.png` : undefined);

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
  return (
    <div className="page">
      <aside className="sidebar">
        {/* ── header: brand · what-it-is · primary action ── */}
        <div className="sb-header">
          <Brand className="sidebar-brand" />
          <p className="sb-tagline">
            One sentence becomes a <b>real, working</b> skeuomorphic player that
            drives your music. Pick a skin below, or make your own.
          </p>
          <button className={`sb-cta ${showCreate ? "open" : ""}`} onClick={() => setShowCreate((v) => !v)}>
            {showCreate
              ? <>× Close create</>
              : <><span className="sb-cta-plus">+</span> Create a skin</>}
          </button>
          <a className="sb-howlink" href="/process/" target="_blank" rel="noopener">
            How does it work? <span className="arr">→</span>
          </a>
        </div>

        {/* ── scrolling body: skin list + secondary groups ── */}
        <div className="sb-body">
          <div className="sb-skins">
          <p className="sb-label">Skins</p>
          {visible.map((s) => (
            <button key={s.id} className={`style-btn ${s.id === skinId ? "active" : ""}`}
              onClick={() => { setSkinId(s.id); setEdited(null); }}>
              <img className="thumb" loading="lazy" alt=""
                src={skinHasFrame(s.id) ? `/skins/${s.id}/frame.png` : "/favicon.svg"}
                onError={(e) => { (e.currentTarget as HTMLImageElement).src = "/favicon.svg"; }} />
              <span className="meta"><span className="name">{s.name}</span><span className="blurb">{s.blurb}</span></span>
            </button>
          ))}
          {runtimeSkins.length > 0 && <p className="sb-label" style={{ marginTop: 4 }}>Your skins</p>}
          {runtimeSkins.map((s) => (
            <button key={s.id} className={`style-btn ${s.id === skinId ? "active" : ""}`}
              onClick={() => { setSkinId(s.id); setEdited(null); }}>
              <img className="thumb" loading="lazy" alt="" src={s.frameUrl}
                onError={(e) => { (e.currentTarget as HTMLImageElement).src = "/favicon.svg"; }} />
              <span className="meta"><span className="name">{s.name}</span><span className="blurb">{s.blurb}</span></span>
            </button>
          ))}
          </div>

        {/* ── secondary: customize · connect · desktop ── */}
        <div className="sb-footer">
          <div className="sb-group">
            <p className="sb-label">Customize</p>
            <button className="feature-btn" onClick={() => { setEdited(null); setEditing(true); }}>
              ✎ Edit template
            </button>
            <label className="wire-toggle-row">
              <input type="checkbox" checked={wire} onChange={(e) => setWire(e.target.checked)} />
              <span>Show wireframe</span>
            </label>
          </div>
          <div className="sb-group">
            <p className="sb-label">Connect</p>
            <SpotifyConnect sp={sp} mode={mode} onMode={setMode} />
            <DesktopHandoff
              skinId={skinId}
              skinName={[...visible, ...runtimeSkins].find((s) => s.id === skinId)?.name ?? skinId}
            />
          </div>
          <div className="hint">
            One template → many skins. Buttons / sliders are baked sprites;
            the clock, spectrum, marquee &amp; playlist are live.
          </div>
        </div>
        </div>
      </aside>
      <main className="stage">
        <div className="stage-inner">
          <Composite
            template={playerTemplate}
            skinId={skinId}
            showWireframe={wire}
            runtime={runtimeView}
            templateOverride={edited ?? undefined}
            spotifyDrive={spotifyDrive}
          />
        </div>
      </main>

      {showCreate && (
        <div className="wiz-modal" onPointerDown={(e) => e.target === e.currentTarget && setShowCreate(false)}>
          <button className="create-close" onClick={() => setShowCreate(false)} aria-label="Close create">×</button>
          <CreateWizard onCreated={onCreated} />
        </div>
      )}
      {editing && (
        <TemplateEditor
          template={editorTemplate}
          frameUrl={editorFrame}
          onApply={setEdited}
          onClose={() => { setEditing(false); setEdited(null); }}
        />
      )}
      <ExportGifButton skinId={skinId} />
    </div>
  );
}
