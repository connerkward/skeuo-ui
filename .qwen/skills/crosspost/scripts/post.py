#!/usr/bin/env python3
"""Crosspost API poster — Reddit + Twitter/X. Stdlib only, no pip installs.

Loads secrets from the repo's .env (git-ignored). HN is intentionally NOT here:
it has no posting API and goes through Claude-in-Chrome on a live session.

Usage:
  post.py reddit --sr <subreddit> --title <t> [--url <u> | --text <body>]
  post.py twitter --text <tweet> [--reply-to <tweet_id>]

Prints the permalink/URL of the created post on success; exits non-zero on error.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env():
    if not ENV_PATH.exists():
        sys.exit(f"error: {ENV_PATH} not found. Copy .env.example to .env and fill it in.")
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def require(*names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"error: missing in .env: {', '.join(missing)}")
    return [os.environ[n] for n in names]


def http(req):
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# --- Reddit -----------------------------------------------------------------
UA = "crosspost/1.0 by script"


def reddit(args):
    cid, csec, user, pw = require(
        "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"
    )
    auth = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    body = urllib.parse.urlencode(
        {"grant_type": "password", "username": user, "password": pw}
    ).encode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=body,
        headers={"Authorization": f"Basic {auth}", "User-Agent": UA},
    )
    status, resp = http(req)
    tok = json.loads(resp).get("access_token") if status == 200 else None
    if not tok:
        sys.exit(f"error: reddit auth failed ({status}): {resp}")

    fields = {"api_type": "json", "sr": args.sr, "title": args.title}
    if args.url:
        fields["kind"] = "link"
        fields["url"] = args.url
    else:
        fields["kind"] = "self"
        fields["text"] = args.text or ""
    req = urllib.request.Request(
        "https://oauth.reddit.com/api/submit",
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Authorization": f"Bearer {tok}", "User-Agent": UA},
    )
    status, resp = http(req)
    data = json.loads(resp) if status == 200 else {}
    errs = data.get("json", {}).get("errors") if data else None
    if status != 200 or errs:
        sys.exit(f"error: reddit submit failed ({status}): {resp}")
    print(data["json"]["data"]["url"])


# --- Twitter / X (OAuth 1.0a) ----------------------------------------------
def _q(s):
    return urllib.parse.quote(str(s), safe="")


def _oauth_header(method, url, ck, cs, tk, ts):
    oauth = {
        "oauth_consumer_key": ck,
        "oauth_token": tk,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": base64.b64encode(os.urandom(16)).decode().strip("="),
        "oauth_version": "1.0",
    }
    # JSON body is not part of the OAuth signature base for application/json requests.
    base_params = "&".join(f"{_q(k)}={_q(v)}" for k, v in sorted(oauth.items()))
    base = f"{method}&{_q(url)}&{_q(base_params)}"
    key = f"{_q(cs)}&{_q(ts)}"
    sig = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(oauth.items()))


def twitter(args):
    ck, cs, tk, ts = require(
        "TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"
    )
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": args.text}
    if args.reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": args.reply_to}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": _oauth_header("POST", url, ck, cs, tk, ts),
            "Content-Type": "application/json",
        },
    )
    status, resp = http(req)
    data = json.loads(resp) if resp else {}
    if status not in (200, 201) or "data" not in data:
        sys.exit(f"error: tweet failed ({status}): {resp}")
    tid = data["data"]["id"]
    user = os.environ.get("TWITTER_USERNAME", "i")
    print(f"https://x.com/{user}/status/{tid}")


def main():
    load_env()
    p = argparse.ArgumentParser(description="Crosspost API poster")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("reddit")
    r.add_argument("--sr", required=True)
    r.add_argument("--title", required=True)
    r.add_argument("--url")
    r.add_argument("--text")
    r.set_defaults(func=reddit)

    t = sub.add_parser("twitter")
    t.add_argument("--text", required=True)
    t.add_argument("--reply-to")
    t.set_defaults(func=twitter)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
