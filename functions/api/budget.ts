// GET /api/budget — the public remaining-budget readout for the UI.
//
// Returns the LIFETIME spend ledger that /api/generate enforces:
//   { capCents, spentCents, remainingCents }
// No secrets, no per-user data — just the global cost ceiling so the page can
// show "X of $10 left" and disable Generate when it's exhausted. The ledger
// (spend:cents) lives in the RATELIMIT KV and does NOT auto-reset; topping up =
// `wrangler kv key put --binding RATELIMIT spend:cents 0 --remote`.

interface Env {
  RATELIMIT?: KVNamespace;
  SPEND_CAP_CENTS?: string;
}

const SPEND_KEY = "spend:cents";
const DEFAULT_CAP_CENTS = 1000;

export const onRequestGet = async (ctx: { env: Env }): Promise<Response> => {
  const { env } = ctx;
  const capCents = Number(env.SPEND_CAP_CENTS ?? String(DEFAULT_CAP_CENTS));
  const spentCents = env.RATELIMIT ? Number((await env.RATELIMIT.get(SPEND_KEY)) ?? "0") : 0;
  const remainingCents = Math.max(0, capCents - spentCents);
  return new Response(JSON.stringify({ capCents, spentCents, remainingCents }), {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
};
