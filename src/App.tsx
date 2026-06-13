import { useCallback, useEffect, useState } from "react";
import { Composite } from "./player/Composite";
import { playerTemplate } from "./template/winamp-layout";
import { skinList, skinTemplateUrl } from "./player/skins";
import type { Template } from "./template/schema";
import "./skins/app.css";
import "./skins/player.css";
import "./skins/winamp.css";
import "./skins/frog.css";
import "./skins/burger.css";
import "./skins/bondi.css";
import "./skins/toilet.css";
import "./skins/biomech.css";
import "./skins/wmp.css";
import "./skins/halo.css";
// ── feature: template editor + generate-from-prompt ──────────────────────────
import { CreatePanel, type RuntimeSkin } from "./generate/CreatePanel";
import { TemplateEditor } from "./editor/TemplateEditor";
import "./generate/create.css";
// ── feature: Spotify connect & control ───────────────────────────────────────
import { useSpotify } from "./spotify/useSpotify";
import { SpotifyConnect } from "./spotify/SpotifyConnect";
import "./spotify/spotify.css";
// ── feature: mobile swipe shell ──────────────────────────────────────────────
import { MobileChrome } from "./mobile/MobileChrome";

// expose the single-source-of-truth template for tooling (wireframe/mask export)
(window as unknown as { __template: unknown }).__template = playerTemplate;

const skinHasFrame = (id: string) => !!skinList.find((s) => s.id === id)?.has.includes("frame");

export default function App() {
  const visible = skinList.filter((s) => !s.hidden);
  const [skinId, setSkinId] = useState(visible[0].id);
  const [wire, setWire] = useState(false);

  // generate-from-prompt + live template editor
  const [runtimeSkins, setRuntimeSkins] = useState<RuntimeSkin[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState<Template | null>(null);          // live editor override
  const [diskTemplate, setDiskTemplate] = useState<Template | null>(null); // registry skin's real template.json
  const activeRuntime = runtimeSkins.find((s) => s.id === skinId);

  // Spotify: drive the skin from real playback only in spotify mode
  const sp = useSpotify();
  const [mode, setMode] = useState<"local" | "spotify">("local");
  const spotifyDrive = mode === "spotify" ? sp.drive : null;

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
          <div className="create-drawer m-create-drawer">
            <button className="create-close" onClick={() => setShowCreate(false)} aria-label="Close create">×</button>
            <CreatePanel onCreated={onCreated} />
          </div>
        )}
      </>
    );
  }

  // ── desktop ──────────────────────────────────────────────────────────────────
  return (
    <div className="page">
      <aside className="sidebar">
        <h1>Skin</h1>
        {visible.map((s) => (
          <button key={s.id} className={`style-btn ${s.id === skinId ? "active" : ""}`}
            onClick={() => { setSkinId(s.id); setEdited(null); }}>
            <span className="name">{s.name}</span>
            <span className="blurb">{s.blurb}</span>
          </button>
        ))}
        {runtimeSkins.map((s) => (
          <button key={s.id} className={`style-btn ${s.id === skinId ? "active" : ""}`}
            onClick={() => { setSkinId(s.id); setEdited(null); }}>
            <span className="name">{s.name}</span>
            <span className="blurb">{s.blurb}</span>
          </button>
        ))}
        <button className="feature-btn" onClick={() => setShowCreate((v) => !v)}>
          {showCreate ? "× Close create" : "+ Create skin"}
        </button>
        <button className="feature-btn" onClick={() => { setEdited(null); setEditing(true); }}>
          ✎ Edit template
        </button>
        <label className="wire-toggle-row">
          <input type="checkbox" checked={wire} onChange={(e) => setWire(e.target.checked)} />
          <span>Wireframe (template)</span>
        </label>
        <SpotifyConnect sp={sp} mode={mode} onMode={setMode} />
        <div className="hint">
          One template → many skins. Buttons / sliders are baked sprites;
          the clock, spectrum, marquee &amp; playlist are live.
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
        <div className="create-drawer">
          <CreatePanel onCreated={onCreated} />
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
    </div>
  );
}
