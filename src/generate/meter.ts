// Shared, KV-backed edge meter — a LIFETIME spend ledger + per-IP/day request caps,
// used by BOTH /api/generate and /api/cutout (the two paid fal endpoints).
//
// WHY: the old per-IP limiter (ratelimit.ts) is an in-memory Map — per CF isolate,
// reset on cold start, so the real ceiling was (isolates × cap) ≈ no limit. And the
// cutout endpoint had NO metering at all, so it was a loopable unbounded fal bill.
// This module moves both caps to the RATELIMIT KV namespace, which is edge-shared, so
// the caps actually hold in production.
//
// RESERVE-BEFORE-SPEND: we increment the ledger BEFORE the paid call and refund on
// failure, which shrinks (does not eliminate) the read-modify-write race vs charging
// only after success. KV is eventually consistent, so a concurrent burst can still
// overshoot the cap slightly — a Durable Object is the next step for strict atomicity.
// Documented here rather than silently claimed.

export interface MeterKV {
  get(k: string): Promise<string | null>;
  put(k: string, v: string, o?: { expirationTtl?: number }): Promise<void>;
}
export interface MeterEnv {
  RATELIMIT?: MeterKV;       // KV namespace (absent in local dev → meter is a no-op)
  SPEND_CAP_CENTS?: string;  // lifetime budget ceiling in cents (default 1000 = $10)
}

const SPEND_KEY = "spend:cents";
const DEFAULT_CAP_CENTS = 1000;
const IP_TTL_SECONDS = 90_000;          // ~25h — safely covers one UTC day
const day = (): string => new Date().toISOString().slice(0, 10);

// est cost of one BiRefNet cutout call in cents (conservative — leans toward
// stopping early; the legit flow runs ~2 per skin: device + control strip).
export const BIREFNET_COST_CENTS = 3;

export interface IpBucket { name: string; max: number }
export interface Reservation { ok: boolean; reason?: string }

// Check the lifetime spend cap (+ an optional per-IP/day bucket) and, if within
// budget, RESERVE estCents (and 1 IP unit) up front. Returns {ok:false,reason} to
// refuse BEFORE any paid call. No KV binding (local dev) → always ok (don't block
// iteration). Distinct ipBucket names keep gen vs cutout budgets independent.
export async function reserve(
  env: MeterEnv, ip: string, estCents: number, ipBucket?: IpBucket,
): Promise<Reservation> {
  const kv = env.RATELIMIT;
  if (!kv) return { ok: true };
  const cap = Number(env.SPEND_CAP_CENTS ?? String(DEFAULT_CAP_CENTS));
  const spent = Number((await kv.get(SPEND_KEY)) ?? "0");
  if (spent + estCents > cap) {
    return { ok: false, reason: "Budget exhausted — paused until the owner tops up." };
  }
  if (ipBucket) {
    const ipKey = `ip:${ipBucket.name}:${ip}:${day()}`;
    const n = Number((await kv.get(ipKey)) ?? "0");
    if (n >= ipBucket.max) {
      return { ok: false, reason: `daily limit reached (${ipBucket.max}/day per IP)` };
    }
    await kv.put(ipKey, String(n + 1), { expirationTtl: IP_TTL_SECONDS });
  }
  await kv.put(SPEND_KEY, String(spent + estCents));
  return { ok: true };
}

// Refund a reservation when the paid call FAILED — don't bill our own error.
export async function refund(
  env: MeterEnv, ip: string, estCents: number, ipBucket?: IpBucket,
): Promise<void> {
  const kv = env.RATELIMIT;
  if (!kv) return;
  const spent = Number((await kv.get(SPEND_KEY)) ?? "0");
  await kv.put(SPEND_KEY, String(Math.max(0, spent - estCents)));
  if (ipBucket) {
    const ipKey = `ip:${ipBucket.name}:${ip}:${day()}`;
    const n = Number((await kv.get(ipKey)) ?? "0");
    if (n > 0) await kv.put(ipKey, String(n - 1), { expirationTtl: IP_TTL_SECONDS });
  }
}

export const GEN_BUCKET: IpBucket = { name: "gen", max: 5 };   // 5 generations / IP / day
export const CUT_BUCKET: IpBucket = { name: "cut", max: 40 };  // generous; spend cap is the real backstop
