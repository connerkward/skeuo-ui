# /api/generate is down on skeuo.fm — CF Worker CPU limit (error 1102) — handoff

**Status:** the wizard error is now *legible* but generation still fails in production.
Local dev is unaffected. This doc is everything the next agent needs.

## Symptom
- In the deployed wizard, generating a skin shows: `server returned 503 (text/html…) — the
  generate endpoint errored or timed out` (before my client fix it showed the raw
  `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`).
- `POST https://skeuo.fm/api/generate` → **HTTP 503, body `error code: 1102`** (consistent).
- `/api/budget` (a lightweight Function, no fal) returns 200 fine, so the deployment itself
  is healthy — only the *generate* Function fails.

## Root cause (confirmed from live logs)
`npx wrangler pages deployment tail <deployment-id> --project-name skeuo-ui --format=json`
while firing a generate showed:
```
outcome: "exceededCpu"   exceptions: [{ message: "Worker exceeded CPU time limit." }]
wallTime: 27624 ms   cpuTime: 2010 ms
```
The fal paint call is I/O (waiting on a subrequest does NOT count toward CPU). The CPU is
burned by the **pure-JS image post-processing after the paint**:
`UPNG.decode` + `toRGBA8` + `cutoutAlpha` (connected-components / flood-fill / hole-fill)
+ **`UPNG.encode`** (JS deflate) of a **2K (~1365×2048) RGBA** PNG. That ~2 s of CPU trips
the Worker CPU ceiling → CF `1102`.

Key code:
- `src/generate/pipeline.ts` → `generateSkin()`; the cutout call is **line ~243**
  (`const framePng = await deps.cutout(paintPng)`). Paint resolution is set in `falSubmit()`
  **line ~166** (`resolution: "2K"`).
- `functions/api/generate.ts` → the Worker's `cutout()` (UPNG decode/encode) + `onRequestPost`.
- `src/generate/blueprint.ts` → `cutoutAlpha()` — the heavy pixel work. **It is runtime-agnostic
  / browser-safe** (this matters for the recommended fix).
- `server/devApiPlugin.ts` → the LOCAL path (resvg-js + UPNG). **No CPU limit locally**, which is
  why `npm run dev` generation works fine and only the deployed Worker fails.

## What I already changed (both deployed)
1. **Client hardening — commit `92a1159`.** `postGenerate()` in `src/generate/api.ts` reads the
   response as text, checks status + content-type, and returns a readable `GenerateError` instead
   of throwing on HTML. `CreateWizard.tsx` and `CreatePanel.tsx` both call it. This only fixes the
   *message*, not the failure.
2. **`wrangler.toml` — added `[limits] cpu_ms = 300_000`** (max 5 min), deployed
   (`82007fb9.skeuo-ui.pages.dev`). **UNVERIFIED — and probably a no-op.** Per Cloudflare docs,
   `cpu_ms` only applies on the **Workers Standard Usage Model (paid)**. Strong evidence this
   account is on the **free/Bundled plan**: a paid plan's default CPU limit is 30 s, and a 2 s job
   would not have tripped `exceededCpu` — it did. So `cpu_ms` is likely ignored and the site is
   probably still 503ing. **First action for the next agent: confirm the plan, then re-test.**

## Reproduce / diagnose
```bash
# fire a one-pass generate (cheaper, still hits the cutout CPU path)
curl -s -o /dev/null -w "HTTP %{http_code} time=%{time_total}s\n" \
  -X POST https://skeuo.fm/api/generate -H "Content-Type: application/json" \
  -d '{"prompt":"a small green frog","variant":"minimal","envelope":false}'

# live logs (needs a deployment id from `wrangler pages deployment list`)
npx wrangler pages deployment list --project-name skeuo-ui
npx wrangler pages deployment tail <id> --project-name skeuo-ui --format=json   # look for outcome/exceptions
```
- CF account id: `809de311af5196443687f347cc8c65cb` · Pages project: `skeuo-ui` (domains skeuo.fm,
  www.skeuo.fm, skeuo-ui.pages.dev).
- **Deploy is MANUAL:** `npm run deploy` = `tsc -b && vite build && stage-process` then
  `wrangler pages deploy dist --project-name skeuo-ui`. **No git auto-deploy** — pushing to GitHub
  does NOT update the live site.

## Recommended fixes (pick by plan)
1. **Confirm the plan first.** If **paid** → `cpu_ms=300000` (already in `wrangler.toml`, deployed)
   should cover the ~2 s; just verify with the curl above. Done.
2. **If free — the real fix is to get the heavy image work OFF the Worker.** Best option,
   plan-independent: **return the raw paint PNG URL + template; run `cutoutAlpha` in the BROWSER**
   (canvas; `cutoutAlpha` in `blueprint.ts` already runs client-side). Removes UPNG decode/encode +
   cutout from the Worker entirely (Worker then only rasterizes the tiny wells SVG + orchestrates
   fal I/O). Touches: the `GenerateResult`/response contract (`src/generate/api.ts`,
   `pipeline.ts`), the client render that consumes `frameUrl`, the `/share` page, and the R2 store
   (store the raw paint; cutout at view time). Note the wells-blueprint rasterize still runs in the
   Worker — it's a simple vector so it should be cheap, but profile it on free.
3. **Or upgrade to Workers Paid ($5/mo)** and keep `cpu_ms=300000` — smallest code change (already
   done), but it's a billing decision for the owner.
4. **Partial CPU trims** (help margin, likely insufficient alone on free): drop paint `resolution`
   `"2K"→"1K"` in `pipeline.ts` `falSubmit` (~½ the cutout cost, costs skin resolution); and/or
   replace `UPNG.encode` with a faster encoder / skip the re-encode (e.g. emit raw RGBA or a
   cheaper format). The `"pending"` branch already exists in the contract if you want to go async
   (`GeneratePending`), but async alone doesn't remove the cutout CPU — it still has to run
   somewhere.

## One-line summary
Worker dies on the post-paint JS image cutout (`exceededCpu`, ~2 s CPU). `cpu_ms` is deployed but
only works on the paid plan; if the account is free, move `cutoutAlpha` to the browser (or upgrade
the plan). Client already shows a clean error. Deploy is manual via `npm run deploy`.
