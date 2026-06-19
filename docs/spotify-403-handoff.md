# Spotify 403 — handoff context

**Status:** OAuth is FIXED (build 0.1.2). Login returns to the app and a token is
obtained — the user reaches the Spotify Web API. The API then returns **403** on
the authenticated calls. Post-auth authorization problem, not login/redirect.

## ⭐ KEY FACT (2026-06-18): works on WEB, fails ONLY on iOS TestFlight

The user confirmed the **exact same Spotify flow succeeds on the website**
(skeuo.fm) and 403s **only in the TestFlight iOS app**. Same client ID, same
scopes, same Web API. **This rules out the two "account-wide" causes** — they would
fail on web too:
- ❌ NOT Premium-required (a Free account would 403 on web as well).
- ❌ NOT the web account missing from User Management (it works on web → it's allowlisted).

So the difference is **iOS-flow-specific**. Given the body is "user not registered,"
the token the iOS app obtained almost certainly belongs to a **DIFFERENT Spotify
account than the allowlisted one** — i.e., the phone's Safari was already signed
into Spotify as another account, so the OAuth consented as that account (no
re-login prompt), and that account isn't in User Management.

**Confirm in ~1 min:** call `GET https://api.spotify.com/v1/me` with the iOS token
and read `email`/`id`; compare to the account that works on web / is in User
Management. (Add a temporary `console.error(await api.call('/me'))` after connect,
or read it off the device.) If they differ → that's it.

**Fixes:** on the phone, sign Safari OUT of Spotify (or use the account switcher /
a private tab) and authorize with the SAME account that's allowlisted — OR add the
phone's actual account to User Management. Longer term, forcing the account chooser
(`show_dialog=true` on the authorize URL) avoids silently reusing Safari's session.

---

### (Superseded) earlier ranked hypotheses — kept for reference

## Symptom

After connecting Spotify in the iOS app, the API call fails. The app surfaces the
raw error from `src/spotify/api.ts` `call()`:

```
Spotify API 403 <endpoint>: <Spotify response body>
```

User-reported wording: **"spotify api 403 … user is not registered for this."**
That phrasing matches Spotify's **Development-Mode** body
`{"error":{"status":403,"message":"User not registered in the Developer Dashboard"}}`.
⚠️ **Get the EXACT body + endpoint first** — it disambiguates the three causes below.
It's already in the thrown `Error.message` (endpoint + full body); have the user
read it verbatim, or add a temporary `console.error`/on-screen dump of it.

## App config (from the user's dashboard, 2026-06-18)

- App: **Skeuo.FM**, Client ID `98e0d056151a4f84b42fefef4b9441e8`
- **App Status: Development mode** ← only allowlisted users (≤25) can use it
- Redirect URIs: `https://skeuo.fm/callback`, `http://127.0.0.1:14565/callback`, `https://skeuo.fm/`
- APIs: Web API, Web Playback SDK
- **Scopes requested** (`src/spotify/auth.ts` `SCOPES`):
  `user-read-playback-state`, `user-modify-playback-state`,
  `user-read-currently-playing`, **`streaming`**, `playlist-read-private`

## Endpoints called (all `https://api.spotify.com/v1`, see `src/spotify/api.ts`)

`/me/player`, `/me/playlists`, `/me/player/devices`, and the control mutations
`/me/player/{play,pause,next,previous,seek,volume,shuffle,repeat}`. The model is
**"control the user's active Spotify device via the Web API"** (no in-app audio on
iOS — the Web Playback SDK "play here" is gated off on mobile in
`SpotifyConnect.tsx` via `isMobileApp()`).

## Three hypotheses (ranked) — the exact 403 body decides which

1. **Premium required (STRONGEST, and independent of User Management).**
   `user-modify-playback-state` + `streaming` + all `/me/player/*` **control**
   endpoints require the END USER to have **Spotify Premium**. A **Free** account
   gets **403 on playback control no matter what** — adding them to User Management
   changes nothing, which fits "I added the user and it still 403s." Body for this
   case mentions `PREMIUM_REQUIRED` / "Premium required". **→ Check the user's
   Spotify tier first (Free vs Premium).** If Free, this is a hard product
   constraint: there is no Web-API playback control for Free users; the UX must
   change (open-in-Spotify, 30s preview clips, or read-only "now playing").

2. **Dev-mode allowlist mismatch.** The email added to **User Management** must
   match the Spotify account's **real** email exactly. Gotcha: if they sign into
   Spotify with **Continue with Google/Apple**, the account email is that provider
   email, not what they'd guess. Verify at <https://www.spotify.com/account/profile/>.
   Also: User Management changes can take a few minutes to propagate, and the app
   may hold a token issued before registration → **disconnect + reconnect** for a
   fresh token. Body for this case: "User not registered in the Developer Dashboard".

3. **Scope/token issue.** Less likely (the token is obtained and basic calls would
   then also 401/403 differently). Confirm the granted scopes on the token match
   what the failing endpoint needs.

## What's already been tried

- User added themself to **User Management** → still 403. (Consistent with #1
  Premium, OR #2 email-mismatch/propagation/stale-token.)

## Fastest repro loop (DON'T need TestFlight)

The 403 is the **same Web API call on web and iOS**. Reproduce on the **website**
(<https://skeuo.fm>) signed into the *same* Spotify account — open devtools,
Connect Spotify, watch the Network tab for the `api.spotify.com/v1/...` request and
read the 403 response body + which endpoint. Iterate there; no app rebuild needed.
(On web, `redirectUri()` is the page origin; the API/scope behavior is identical.)

## Relevant files

- `src/spotify/auth.ts` — SCOPES, PKCE, token exchange, `CLIENT_ID`
- `src/spotify/api.ts` — `call()` (where the 403 is thrown, with body), all endpoints
- `src/spotify/useSpotify.ts` — connect lifecycle, login(), the drive
- `src/spotify/SpotifyConnect.tsx` / `src/mobile/MobileSpotify.tsx` — UI
- `src/platform.ts` — `redirectUri()` per shell (iOS uses `https://skeuo.fm/callback`)
- `docs/ios.md` — the OAuth-return architecture (HTTPS bounce → `skeuo://` deep link)

## Concrete next steps for the agent

1. Get the **exact** 403 body + endpoint (read `Error.message` / Network tab).
2. Determine the test account's **tier (Free vs Premium)** — settle hypothesis #1.
3. If Premium: decide the Free-user UX (this is a product decision, surface it).
4. If dev-mode: verify User Management email == account email; reconnect for a fresh
   token; wait for propagation. Consider requesting Spotify **Extended Quota Mode**
   for public (non-allowlisted) use.
