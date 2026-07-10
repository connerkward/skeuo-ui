// Dev-only Vertex AI auth: shell out to `gcloud auth print-access-token` on the
// developer's own machine, against project muser-2605300220 — the same project +
// gcloud user-auth session already proven working by
// tools/mask-align-exp/gen12/genskin.py's edit_vertex(). Node-only (child_process);
// this file is imported ONLY by server/devApiPlugin.ts (the Vite dev-server plugin),
// never by src/generate/* or functions/api/* — those must stay bundleable into the
// Cloudflare Worker, which has no child_process.
//
// The token is cached and refreshed a few minutes before its ~1h expiry so every
// request doesn't spawn a subprocess.
import { execFileSync } from "node:child_process";

let cache: { token: string; exp: number } | null = null;

// Returns undefined (never throws) when `gcloud` isn't installed or the developer
// isn't logged in — callers fall back to the deterministic heuristic, same as the
// prod no-secret path.
export function getGcloudAccessToken(): string | undefined {
  const now = Math.floor(Date.now() / 1000);
  if (cache && cache.exp - 60 > now) return cache.token;
  try {
    const token = execFileSync("gcloud", ["auth", "print-access-token"], { encoding: "utf8" }).trim();
    if (!token) return undefined;
    cache = { token, exp: now + 50 * 60 }; // gcloud access tokens live ~1h; refresh at 50m
    return token;
  } catch {
    return undefined;
  }
}
