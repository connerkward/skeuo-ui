// Vertex AI auth — the ONE auth mechanism for every Director/vision call in this
// pipeline (director.ts). Replaces OpenAI entirely: zero gpt-4o, zero api.openai.com,
// zero OPENAI_API_KEY anywhere downstream of this module.
//
// Two runtimes, two ways to get a bearer token for the SAME Vertex generateContent API:
//
//   • Prod (Cloudflare Pages Function — functions/api/*): no gcloud CLI, no
//     child_process. A GCP_SERVICE_ACCOUNT_KEY JSON secret is exchanged for an access
//     token via the standard OAuth2 service-account JWT-bearer flow (RS256, signed with
//     WebCrypto — no Node/Google client libs needed, so this file is safe to bundle into
//     the Worker). Cached in-memory per isolate until ~1 min before expiry.
//     Verified against Google's live docs (2026-07-10): JWT claims {iss, scope, aud, iat,
//     exp}, signed RS256, POSTed x-www-form-urlencoded to https://oauth2.googleapis.com/token
//     with grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=<jwt>.
//
//   • Dev (Node, via server/devApiPlugin.ts + server/gcloudAuth.ts): the developer's own
//     `gcloud auth print-access-token` session against project muser-2605300220 — the SAME
//     project + auth proven working today by tools/mask-align-exp/gen12/genskin.py's
//     edit_vertex(). This module itself never shells out (that would break the Worker
//     bundle); the caller resolves that token and passes it in as `devToken`.
//
// getVertexAccessToken() returns null when NEITHER path is configured — callers (director.ts)
// treat that as "no Director available" and fall back to the deterministic heuristic. It
// NEVER throws and NEVER touches any OpenAI endpoint.

export const VERTEX_PROJECT = "muser-2605300220";
const TOKEN_SCOPE = "https://www.googleapis.com/auth/cloud-platform";
const TOKEN_URI = "https://oauth2.googleapis.com/token";

interface ServiceAccountKey {
  client_email: string;
  private_key: string;
  token_uri?: string;
}

function base64url(bytes: ArrayBuffer | Uint8Array): string {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  for (let i = 0; i < b.length; i++) bin += String.fromCharCode(b[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function base64urlJson(obj: unknown): string {
  return base64url(new TextEncoder().encode(JSON.stringify(obj)));
}

// Derive the imported-key type structurally off `crypto.subtle.importKey` itself
// (rather than naming the ambient `CryptoKey` type directly) — this file is compiled
// under three different lib configs (browser/app DOM lib, Worker lib, plain Node lib
// for the dev-server build), and only some of those expose a global `CryptoKey`
// *type* alongside the value; deriving it structurally works under all three.
type ImportedKey = Awaited<ReturnType<typeof crypto.subtle.importKey>>;

// service-account JSON keys ship a PKCS8 PEM private key; WebCrypto's importKey wants
// the raw DER bytes underneath the PEM armor.
async function importPrivateKey(pem: string): Promise<ImportedKey> {
  const body = pem
    .replace(/-----BEGIN PRIVATE KEY-----/, "")
    .replace(/-----END PRIVATE KEY-----/, "")
    .replace(/\s+/g, "");
  const der = Uint8Array.from(atob(body), (c) => c.charCodeAt(0));
  return crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
}

let saCache: { token: string; exp: number } | null = null;

async function getServiceAccountToken(keyJson: string): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  if (saCache && saCache.exp - 60 > now) return saCache.token;
  const sa = JSON.parse(keyJson) as ServiceAccountKey;
  const aud = sa.token_uri || TOKEN_URI;
  const header = { alg: "RS256", typ: "JWT" };
  const claims = { iss: sa.client_email, scope: TOKEN_SCOPE, aud, iat: now, exp: now + 3600 };
  const signingInput = `${base64urlJson(header)}.${base64urlJson(claims)}`;
  const key = await importPrivateKey(sa.private_key);
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(signingInput));
  const jwt = `${signingInput}.${base64url(sig)}`;
  const r = await fetch(aud, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `grant_type=${encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer")}&assertion=${encodeURIComponent(jwt)}`,
  });
  if (!r.ok) throw new Error(`vertex service-account token exchange ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const data = (await r.json()) as { access_token: string; expires_in?: number };
  saCache = { token: data.access_token, exp: now + (data.expires_in ?? 3600) };
  return data.access_token;
}

export interface VertexAuthOpts {
  // Prod: the GCP_SERVICE_ACCOUNT_KEY secret's raw JSON. Takes priority when present.
  serviceAccountKey?: string;
  // Dev: an already-resolved bearer token from `gcloud auth print-access-token`,
  // refreshed by the caller (server/gcloudAuth.ts). Used when serviceAccountKey is unset.
  devToken?: string;
}

// Resolve a bearer token for calling aiplatform.googleapis.com, or null if neither auth
// path is configured/working. Never throws (a failed exchange is caught and logged).
export async function getVertexAccessToken(opts: VertexAuthOpts): Promise<string | null> {
  if (opts.serviceAccountKey) {
    try {
      return await getServiceAccountToken(opts.serviceAccountKey);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn(`[vertexAuth] service-account token exchange failed: ${e instanceof Error ? e.message : e}`);
      return null;
    }
  }
  return opts.devToken ?? null;
}
