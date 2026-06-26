import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Composite } from "./player/Composite";
import { SkinThumb } from "./player/SkinThumb";
import { skinFont, skinFontStyle, ensureGoogleFont, isFontReady, preloadSkinFonts } from "./player/skinFonts";
import { useDocumentPip } from "./player/useDocumentPip";
import { playerTemplate } from "./template/winamp-layout";
import { skinList, thumbUrl, type SkinAssets } from "./player/skins";
import "./skins/all"; // app.css + player.css + every skin palette (shared with the widget)
// ── feature: generate-from-prompt ────────────────────────────────────────────
import { type RuntimeSkin } from "./generate/runtimeSkin";
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
import { initialSkinParam, isMobileApp, apiUrl } from "./platform";
import type { RuntimeSkinView } from "./player/Composite";
import type { Template } from "./template/schema";

// A row of the cloud skin INDEX (GET /api/skins) — published skins served by the
// backend that the app merges into the gallery AFTER the bundled built-ins, so new
// skins reach the app WITHOUT a rebuild. The full template is fetched lazily from
// /api/skin/<id> only when the skin becomes active (see resolveCloudRuntime).
interface CloudSkin {
  id: string;
  name: string;
  blurb: string;
  style: string;
  frameUrl: string;
  sprites: boolean;
  font?: string;
  createdAt?: string;
}

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
  // ?all reveals the normally-hidden catalog bodies (themed/iteration skins +
  // donors) in the gallery — a dev/review affordance for seeing every skin (and
  // its logomark font) at once. Default gallery still hides them.
  const showAll = typeof window !== "undefined" && new URLSearchParams(window.location.search).has("all");
  const visible = skinList.filter((s) => showAll || !s.hidden);
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

  // ── cloud skin index ─────────────────────────────────────────────────────────
  // Fetch published skins once at startup and merge them into the gallery AFTER the
  // bundled built-ins. Built-in ids win on collision (a cloud row with the same id
  // is dropped) so the static catalog is never shadowed. Failures are silent — the
  // gallery still works offline / without a backend.
  const [cloudSkins, setCloudSkins] = useState<CloudSkin[]>([]);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(apiUrl("/api/skins"), { cache: "no-store" });
        if (!r.ok) return;
        const data = (await r.json()) as { skins?: CloudSkin[] };
        if (!alive || !Array.isArray(data.skins)) return;
        const builtinIds = new Set(skinList.map((s) => s.id));
        setCloudSkins(data.skins.filter((s) => s && s.id && !builtinIds.has(s.id)));
      } catch { /* offline / no backend — gallery still works */ }
    })();
    return () => { alive = false; };
  }, []);
  // Honor a ?skin=<id> deep link to a CLOUD skin: the initial param is resolved against
  // built-ins + localStorage at mount (above), but cloud skins load async, so a link to a
  // cloud skin would fall back to visible[0]. Captured the original param at mount (the
  // skinId-sync effect rewrites the URL), and once /api/skins lands, switch to it — but
  // ONLY while still on the fallback, so it never overrides user navigation.
  const deepLinkParam = useRef(initialSkinParam());
  const deepLinkDone = useRef(false);
  useEffect(() => {
    if (deepLinkDone.current) return;
    const p = deepLinkParam.current;
    if (p && skinId === visible[0].id && cloudSkins.some((s) => s.id === p)) {
      deepLinkDone.current = true;
      setSkinId(p);
    }
  }, [cloudSkins, skinId, visible]);
  // resolved runtime views per cloud-skin id (template fetched lazily on activate)
  const [cloudRuntimes, setCloudRuntimes] = useState<Record<string, RuntimeSkinView>>({});
  const activeCloud = cloudSkins.find((s) => s.id === skinId);
  // when a cloud skin becomes active and we haven't resolved its template yet,
  // fetch /api/skin/<id> (the authoritative template) and cache the runtime view.
  useEffect(() => {
    if (!activeCloud || cloudRuntimes[activeCloud.id]) return;
    let alive = true;
    (async () => {
      try {
        const r = await fetch(apiUrl(`/api/skin/${encodeURIComponent(activeCloud.id)}`), { cache: "no-store" });
        if (!r.ok) return;
        const data = (await r.json()) as { template?: Template; frameUrl?: string; sprites?: boolean };
        const template = data.template;
        if (!alive || !template) return;
        const view: RuntimeSkinView = {
          frameUrl: apiUrl(data.frameUrl ?? activeCloud.frameUrl),
          template,
          style: activeCloud.style,
          sprites: data.sprites ?? activeCloud.sprites,
        };
        setCloudRuntimes((m) => ({ ...m, [activeCloud.id]: view }));
      } catch { /* keep showing the gallery; the device just won't resolve */ }
    })();
    return () => { alive = false; };
  }, [activeCloud, cloudRuntimes]);

  const activeRuntime = runtimeSkins.find((s) => s.id === skinId);
  // map of id → resolved runtime view for every cloud skin (drives the mobile
  // carriage; desktop reads the active one). Only resolved skins appear here.
  const activeCloudRuntime = activeCloud ? cloudRuntimes[activeCloud.id] : undefined;
  const activeMeta = [...visible, ...runtimeSkins, ...cloudSkins].find((s) => s.id === skinId);
  // the skin's logomark title font (loaded on demand inside <CinemaTitle>)
  const titleFont = skinFont(skinId, activeRuntime?.font);

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
  // preload the visible roster's logomark fonts up front so switching never pops in
  // (skinList is a stable module import, so the visible set is constant → run once).
  // With ?all, preload the WHOLE catalog so the revealed bodies don't pop in either.
  useEffect(() => {
    preloadSkinFonts(showAll ? undefined : skinList.filter((s) => !s.hidden).map((s) => s.id));
  }, [showAll]);
  // top-bar popovers (Connect / Desktop) — only one open at a time
  const [panel, setPanel] = useState<null | "connect" | "desktop">(null);

  const onCreated = useCallback((s: RuntimeSkin) => {
    setRuntimeSkins((rs) => [...rs, s]);
    setSkinId(s.id);
    setShowCreate(false);
  }, []);

  const runtimeView: RuntimeSkinView | undefined = activeRuntime
    ? { frameUrl: activeRuntime.frameUrl, template: activeRuntime.template, style: activeRuntime.style, sprites: activeRuntime.sprites }
    : activeCloudRuntime;

  // Cloud skins as minimal SkinAssets so they ride the mobile carriage alongside
  // the built-ins (appended AFTER them). Their device renders via the `runtimes`
  // map (resolved lazily as each becomes active); the entry itself just carries
  // id/name/blurb for the strip + label.
  // A locally-created skin that the owner has PUBLISHED also comes back in the cloud
  // index — dedup so it doesn't appear twice (duplicate React key) in the gallery.
  const runtimeIds = new Set(runtimeSkins.map((s) => s.id));
  const cloudVisible = cloudSkins.filter((s) => !runtimeIds.has(s.id));
  const cloudAsAssets: SkinAssets[] = cloudVisible.map((s) => ({
    id: s.id, name: s.name, blurb: s.blurb, has: ["frame"], frameUrl: s.frameUrl ? apiUrl(s.frameUrl) : undefined,
  }));
  // Locally-created (runtime) skins also ride the mobile carriage — same as the
  // desktop rail lists them. Without this a skin you just made on the phone never
  // appears in the gallery (it only flashed full-screen right after creation).
  const runtimeAsAssets: SkinAssets[] = runtimeSkins
    .filter((s) => !s.hidden)
    .map((s) => ({ id: s.id, name: s.name, blurb: s.blurb, has: ["frame"], frameUrl: s.frameUrl }));
  const galleryMobile = [...visible, ...runtimeAsAssets, ...cloudAsAssets];
  // render views for EVERY non-built-in skin in the carriage: cloud (lazily resolved)
  // + local runtime (resolved inline — its template/frame are already in memory).
  const carriageRuntimes: Record<string, RuntimeSkinView> = { ...cloudRuntimes };
  for (const s of runtimeSkins) {
    if (!s.hidden) carriageRuntimes[s.id] = { frameUrl: s.frameUrl, template: s.template, style: s.style, sprites: s.sprites };
  }

  // Owner-only publish: the cloud gallery is curated by the owner, not open UGC.
  // The owner enables the Publish UI by visiting once with ?ownerKey=<secret> (stored
  // to localStorage, stripped from the URL); the button is hidden for everyone else.
  // Publishing POSTs the marker with the X-Owner-Key header the server checks.
  const [ownerKey] = useState<string | null>(() => {
    try {
      const u = new URL(window.location.href);
      const k = u.searchParams.get("ownerKey");
      if (k) { localStorage.setItem("skeuo:ownerKey", k); u.searchParams.delete("ownerKey"); window.history.replaceState(null, "", u); }
      return localStorage.getItem("skeuo:ownerKey");
    } catch { return null; }
  });
  const [publishing, setPublishing] = useState<string | null>(null);
  const [publishedIds, setPublishedIds] = useState<Set<string>>(new Set());
  const publish = useCallback(async (s: RuntimeSkin) => {
    if (!ownerKey) return;
    setPublishing(s.id);
    try {
      const r = await fetch(apiUrl(`/api/finalize/${encodeURIComponent(s.id)}/publish`), {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Owner-Key": ownerKey },
        body: JSON.stringify({ name: s.name, blurb: s.blurb, font: s.font, style: s.style }),
      });
      if (r.ok) setPublishedIds((p) => new Set(p).add(s.id));
      else console.error("publish failed", r.status, await r.text().catch(() => ""));
    } catch (e) { console.error("publish error", e); }
    finally { setPublishing(null); }
  }, [ownerKey]);
  const publishLabel = (id: string) =>
    publishedIds.has(id) ? "✓ Published" : publishing === id ? "Publishing…" : "Publish to gallery";

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
              {ownerKey && (
                <button className="m-menu" onClick={() => publish(activeRuntime)}
                  disabled={publishing === activeRuntime.id || publishedIds.has(activeRuntime.id)}>
                  {publishedIds.has(activeRuntime.id) ? "✓" : publishing === activeRuntime.id ? "…" : "Publish"}
                </button>
              )}
              {CONNECT_ENABLED && <MobileSpotify sp={sp} mode={mode} setMode={setMode} />}
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
          skins={galleryMobile}
          skinId={skinId}
          setSkinId={setSkinId}
          onCreate={() => setShowCreate(true)}
          sp={sp}
          mode={mode}
          setMode={setMode}
          spotifyDrive={spotifyDrive}
          connectEnabled={CONNECT_ENABLED}
          runtimes={carriageRuntimes}
          share={
            <ExportGifButton
              skinId={skinId}
              template={playerTemplate}
              runtime={runtimeView}
              spotifyDrive={spotifyDrive}
            />
          }
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

      {/* left gallery — one scrolling list: built-in skins + your generated ones */}
      <aside className="gallery">
        <div className="gallery-list">
          <p className="gallery-label">Skins</p>
          {runtimeSkins.filter((s) => !s.hidden).map((s) => (
            <div key={s.id} className="skin-row-wrap">
              <button className={`skin-row ${s.id === skinId ? "active" : ""}`}
                onClick={() => setSkinId(s.id)} title={s.name}>
                <SkinThumb skinId={s.id} imgSrc={s.frameUrl} animate={false} />
                <span className="skin-row-meta">
                  <span className="skin-row-name">{s.name}</span>
                  <span className="skin-row-blurb">{s.blurb}</span>
                </span>
              </button>
              {/* "delete" = HIDE: drop it from the gallery but keep the raw skin in
                  storage for future processing (never destroyed) */}
              <button className="skin-row-del" aria-label={`Hide ${s.name}`} title="Hide this skin (kept in storage)"
                onClick={() => {
                  setRuntimeSkins((rs) => rs.map((x) => (x.id === s.id ? { ...x, hidden: true } : x)));
                  if (skinId === s.id) setSkinId(visible[0].id);
                }}>×</button>
              {ownerKey && (
                <button className="skin-row-del" style={{ width: "auto", padding: "0 8px", fontSize: 11 }}
                  title="Publish this skin to the shared cloud gallery"
                  disabled={publishing === s.id || publishedIds.has(s.id)}
                  onClick={() => publish(s)}>{publishLabel(s.id)}</button>
              )}
            </div>
          ))}
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
          {/* cloud skins (published via /api/skins) — appended AFTER the built-ins.
              thumb is the served frame; selecting one resolves its template lazily. */}
          {cloudVisible.map((s) => (
            <button key={s.id} className={`skin-row ${s.id === skinId ? "active" : ""}`}
              onClick={() => setSkinId(s.id)} title={`${s.name} — ${s.blurb}`}>
              <SkinThumb skinId={s.id} imgSrc={s.frameUrl} animate={false} />
              <span className="skin-row-meta">
                <span className="skin-row-name">{s.name}</span>
                <span className="skin-row-blurb">{s.blurb}</span>
              </span>
            </button>
          ))}
        </div>
      </aside>

      {/* main area: the full-height skin sized to its content, then the title card
          which FILLS the rest of the width and centers its text — so the text sits
          squarely between the skin's right edge and the frame's right edge. */}
      <div className="main">
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
          </div>
        </main>

        <section className="meta">
          <figcaption className="stage-caption">
            <CinemaTitle text={(activeMeta?.name ?? skinId).replace(/\s*✦\s*$/, "")} font={titleFont} />
            {activeMeta?.blurb && <span className="cap-blurb">{activeMeta.blurb}</span>}
          </figcaption>
          <div className="skin-actions">
            <ExportGifButton
              skinId={skinId}
              template={playerTemplate}
              runtime={runtimeView}
              spotifyDrive={spotifyDrive}
            />
          </div>
        </section>
      </div>

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

// The cinematic title logomark. (1) Loads the skin's Google font, holding the
// text hidden until it's ready so there's no FOUT pop-in (fallback never flashes).
// (2) Auto-fits the font-size DOWN from the CSS max so the whole name sits on one
// line inside its area — no wrapping, words always finish. Refits on resize.
function CinemaTitle({ text, font }: { text: string; font: ReturnType<typeof skinFont> }) {
  const ref = useRef<HTMLSpanElement>(null);
  // start visible if the font is already cached (preloaded) → no pop-in/fade
  const [ready, setReady] = useState(() => isFontReady(font));

  useEffect(() => {
    ensureGoogleFont(font);
    if (isFontReady(font)) { setReady(true); return; }   // cached → show instantly
    setReady(false);
    let alive = true;
    const spec = `${font.weight} 48px '${font.family}'`;
    const done = () => { if (alive) setReady(true); };
    const fonts = (document as Document & { fonts?: FontFaceSet }).fonts;
    if (fonts?.load) fonts.load(spec).then(() => fonts.ready).then(done, done);
    else done();
    return () => { alive = false; };
  }, [font.family, font.weight]);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !ready) return;
    const fit = () => {
      const box = el.parentElement;
      if (!box) return;
      el.style.fontSize = "";                              // back to the CSS max
      const max = parseFloat(getComputedStyle(el).fontSize) || 64;
      const avail = box.clientWidth;
      let size = max;
      el.style.fontSize = `${size}px`;
      let guard = 0;
      while (el.scrollWidth > avail && size > 13 && guard++ < 300) {
        size -= 1;
        el.style.fontSize = `${size}px`;
      }
    };
    fit();
    const ro = new ResizeObserver(fit);
    if (el.parentElement) ro.observe(el.parentElement);
    return () => ro.disconnect();
  }, [text, ready, font.family, font.weight]);

  return (
    <span ref={ref} className="cap-name"
      style={{ ...skinFontStyle(font), opacity: ready ? 1 : 0, transition: "opacity .28s ease" }}>
      {text}
    </span>
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
