// Desktop deep-link + tray wiring (JS side). Only active under Tauri.
//
// Two custom-scheme shapes arrive from the OS:
//   skeuo://skin/<id>          — the website's "open in desktop player" handoff
//   skeuo://callback?code=...  — the Spotify OAuth return (system browser → app)
// plus an in-app `set-skin` event the Rust tray menu emits when you pick a skin.
//
// We subscribe in JS (rather than parsing in Rust) so the routing logic lives
// next to the code it drives. The Rust side only registers the deep-link +
// single-instance plugins and builds the tray.

import { isTauri } from "../platform";
import { handleRedirectCallback } from "../spotify/auth";

type SkinHandler = (skinId: string) => void;

function route(url: string, onSkin: SkinHandler): void {
  let u: URL;
  try { u = new URL(url); } catch { return; }
  // skeuo://callback?code=... → finish the OAuth exchange
  if (u.host === "callback" || u.pathname.replace(/^\/+/, "").startsWith("callback")) {
    void handleRedirectCallback(url).catch((e) => console.error("[skeuo] oauth callback:", e));
    return;
  }
  // skeuo://skin/<id> → switch the widget's skin
  if (u.host === "skin") {
    const id = u.pathname.replace(/^\/+/, "");
    if (id) onSkin(id);
  }
}

// Wire cold-start URLs, live URLs, and tray events. Returns an unsubscribe fn.
export async function initDeepLinks(onSkin: SkinHandler): Promise<() => void> {
  if (!isTauri()) return () => {};
  const cleanups: Array<() => void> = [];
  try {
    const dl = await import("@tauri-apps/plugin-deep-link");
    // cold start: app was launched by clicking a skeuo:// URL
    try {
      const current = await dl.getCurrent();
      current?.forEach((u) => route(u, onSkin));
    } catch { /* none on a plain launch */ }
    // warm: a URL arrives while already running (single-instance forwards it)
    cleanups.push(await dl.onOpenUrl((urls) => urls.forEach((u) => route(u, onSkin))));
  } catch (e) {
    console.error("[skeuo] deep-link init:", e);
  }
  try {
    const { listen } = await import("@tauri-apps/api/event");
    cleanups.push(await listen<string>("set-skin", (e) => onSkin(e.payload)));
  } catch (e) {
    console.error("[skeuo] tray event init:", e);
  }
  return () => cleanups.forEach((c) => c());
}
