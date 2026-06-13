// HARD per-IP daily rate limit + global daily cost cap. In-memory only — this
// resets on every Worker/process restart and is NOT shared across CF edge
// locations (each isolate has its own Map). For real production use a durable
// store (KV/Durable Object/D1). See the stub note in functions/api/generate.ts.
export const COST_PER_GEN_USD = 0.30;     // observed ~$0.30 fal per 2-pass generation
export const MAX_PER_IP_PER_DAY = 5;      // hard cap per client IP
export const MAX_GLOBAL_USD_PER_DAY = 6;  // hard global daily spend ceiling

interface Bucket { day: string; count: number }
const perIp = new Map<string, Bucket>();
let global: Bucket = { day: "", count: 0 };

const today = () => new Date().toISOString().slice(0, 10);

export interface RateDecision { ok: boolean; reason?: string }

export function checkAndReserve(ip: string): RateDecision {
  const day = today();
  if (global.day !== day) global = { day, count: 0 };
  if ((global.count + 1) * COST_PER_GEN_USD > MAX_GLOBAL_USD_PER_DAY) {
    return { ok: false, reason: `daily cost cap reached ($${MAX_GLOBAL_USD_PER_DAY})` };
  }
  let b = perIp.get(ip);
  if (!b || b.day !== day) { b = { day, count: 0 }; perIp.set(ip, b); }
  if (b.count >= MAX_PER_IP_PER_DAY) {
    return { ok: false, reason: `daily limit reached (${MAX_PER_IP_PER_DAY}/day per IP)` };
  }
  b.count += 1;
  global.count += 1;
  return { ok: true };
}

// release a reservation if generation failed (don't bill the user for our error)
export function release(ip: string): void {
  const b = perIp.get(ip);
  if (b && b.count > 0) b.count -= 1;
  if (global.count > 0) global.count -= 1;
}
