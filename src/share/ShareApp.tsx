import { useEffect, useMemo, useState } from "react";
import type { Template } from "../template/schema";
import { Composite, type RuntimeSkinView } from "../player/Composite";
import { playerTemplate } from "../template/winamp-layout";
import "../skins/all"; // app.css + player.css + every skin palette (shared with the app/widget)
// reused feature surfaces — same components the main studio uses
import { useSpotify } from "../spotify/useSpotify";
import { SpotifyConnect } from "../spotify/SpotifyConnect";
import "../spotify/spotify.css";
import { DesktopHandoff } from "../desktop/DesktopHandoff";
import { Brand } from "../components/Brand";
import "./share.css";

// The payload /api/skin/<id> returns (see functions/api/skin/[id].ts).
interface SkinPayload {
  id: string;
  frameUrl: string;
  template: Template;
  meta: { prompt?: string; model?: string; style?: string; variant?: string; createdAt?: string } | null;
  sprites?: boolean;   // skin has per-control cut sprites → render those, not the donor set
}

type Load =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; skin: SkinPayload };

function skinIdFromUrl(): string | null {
  const id = new URLSearchParams(window.location.search).get("id");
  return id && id.trim() ? id.trim() : null;
}

export default function ShareApp() {
  const id = useMemo(skinIdFromUrl, []);
  const [load, setLoad] = useState<Load>({ state: "loading" });

  useEffect(() => {
    if (!id) { setLoad({ state: "error", message: "No skin id in the link." }); return; }
    // keep the canonical share URL pointing at this exact skin (for crawlers / OG)
    setCanonical(`https://skeuo.fm/share?id=${encodeURIComponent(id)}`);
    let live = true;
    fetch(`/api/skin/${encodeURIComponent(id)}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 404 ? "That skin couldn't be found." : `Couldn't load the skin (${r.status}).`);
        return (await r.json()) as SkinPayload;
      })
      .then((skin) => { if (live) setLoad({ state: "ready", skin }); })
      .catch((e: Error) => { if (live) setLoad({ state: "error", message: e.message }); });
    return () => { live = false; };
  }, [id]);

  // Spotify: drive the shared skin from real playback once connected.
  const sp = useSpotify();
  const [mode, setMode] = useState<"local" | "spotify">("local");
  useEffect(() => { if (sp.status === "connected") setMode("spotify"); }, [sp.status]);
  const spotifyDrive = mode === "spotify" ? sp.drive : null;

  if (load.state !== "ready") {
    return (
      <div className="share-shell">
        <header className="share-top"><Brand /></header>
        <div className="share-center">
          {load.state === "loading"
            ? <p className="share-msg">Loading shared player…</p>
            : <p className="share-msg share-err">{load.message}</p>}
          <a className="share-cta" href="/">Create your own →</a>
        </div>
      </div>
    );
  }

  const { skin } = load;
  const name = skin.meta?.prompt?.trim() || "Shared skin";
  const runtimeView: RuntimeSkinView = {
    frameUrl: skin.frameUrl,
    template: skin.template,
    style: skin.meta?.style || "winamp", // donor style drives [data-skin] palette CSS
    sprites: skin.sprites ?? false,      // render this skin's cut sprites when it has them
  };

  return (
    <div className="share-shell">
      <header className="share-top">
        <a href="/" className="share-brand-link" aria-label="skeuo.fm home"><Brand /></a>
      </header>

      <main className="share-main">
        <section className="share-stage">
          <Composite
            template={playerTemplate}
            skinId={skin.id}
            runtime={runtimeView}
            spotifyDrive={spotifyDrive}
          />
          <h1 className="share-name">{name}</h1>
          {skin.meta?.prompt && <p className="share-prompt">"{skin.meta.prompt}"</p>}
        </section>

        <aside className="share-panel">
          {/* 1 — Share this skin */}
          <ShareRow id={skin.id} name={name} />

          {/* 2 — Connect Spotify (drive the player with real music) */}
          <SpotifyConnect sp={sp} mode={mode} onMode={setMode} />

          {/* 3 — Open in the desktop player (skeuo://skin/<id>) */}
          <DesktopHandoff skinId={skin.id} skinName={name} />

          {/* 4 — Make your own */}
          <a className="share-cta share-create" href="/">Create your own →</a>
        </aside>
      </main>
    </div>
  );
}

function ShareRow({ id, name }: { id: string; name: string }) {
  const url = `https://skeuo.fm/share?id=${encodeURIComponent(id)}`;
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch { /* clipboard blocked — the field is selectable as a fallback */ }
  };
  const nativeShare = async () => {
    if (navigator.share) {
      try { await navigator.share({ title: `${name} — skeuo.fm`, text: "A working skeuomorphic music player", url }); }
      catch { /* user dismissed */ }
    } else { void copy(); }
  };
  const canNativeShare = typeof navigator !== "undefined" && !!navigator.share;
  return (
    <div className="sh-row">
      <div className="sh-head"><span className="sh-dot" /><span className="sh-title">Share this skin</span></div>
      <div className="sh-link" title={url}>{url}</div>
      <div className="sh-actions">
        <button className="sh-btn" onClick={copy}>{copied ? "Copied ✓" : "Copy link"}</button>
        {canNativeShare && <button className="sh-btn sh-btn-ghost" onClick={nativeShare}>Share…</button>}
      </div>
    </div>
  );
}

function setCanonical(href: string): void {
  let el = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!el) { el = document.createElement("link"); el.rel = "canonical"; document.head.appendChild(el); }
  el.href = href;
}
