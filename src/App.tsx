import { useCallback, useEffect, useState } from "react";
import { Composite } from "./player/Composite";
import { playerTemplate } from "./template/winamp-layout";
import { skinList, skinTemplateUrl } from "./player/skins";
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
// ── BEGIN feature wiring: template editor + generate-from-prompt ──────────────
import type { Template } from "./template/schema";
import { CreatePanel, type RuntimeSkin } from "./generate/CreatePanel";
import { TemplateEditor } from "./editor/TemplateEditor";
import "./generate/create.css";
// ── END feature wiring ───────────────────────────────────────────────────────

// expose the single-source-of-truth template for tooling (wireframe/mask export)
(window as unknown as { __template: unknown }).__template = playerTemplate;

export default function App() {
  const visible = skinList.filter((s) => !s.hidden);
  const [skinId, setSkinId] = useState(visible[0].id);
  const [wire, setWire] = useState(false);

  // ── feature state ──────────────────────────────────────────────────────────
  const [runtimeSkins, setRuntimeSkins] = useState<RuntimeSkin[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState<Template | null>(null); // live editor override
  const [diskTemplate, setDiskTemplate] = useState<Template | null>(null); // registry skin's real template.json

  const activeRuntime = runtimeSkins.find((s) => s.id === skinId);

  // load the selected registry skin's actual template.json so the editor edits
  // the real on-disk layout (not a regenerated approximation).
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

  // template currently being edited: a runtime skin's own, the registry skin's
  // real on-disk template (once loaded), else the canonical one.
  const editorTemplate: Template = activeRuntime
    ? activeRuntime.template
    : diskTemplate ?? playerTemplate;
  const editorFrame = activeRuntime?.frameUrl
    ?? (skinHasFrame(skinId) ? `/skins/${skinId}/frame.png` : undefined);
  // ───────────────────────────────────────────────────────────────────────────

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
        {/* ── feature controls ── */}
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
            runtime={activeRuntime ? { frameUrl: activeRuntime.frameUrl, template: activeRuntime.template, style: activeRuntime.style } : undefined}
            templateOverride={edited ?? undefined}
          />
        </div>
      </main>

      {/* ── feature overlays ── */}
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

// ── feature helper (kept out of the render path) ─────────────────────────────
function skinHasFrame(id: string): boolean { return !!skinList.find((s) => s.id === id)?.has.includes("frame"); }
