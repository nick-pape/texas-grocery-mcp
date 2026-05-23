#!/usr/bin/env python3
"""Capture a live, human-authenticated HEB session into a Playwright
storageState JSON (cookies + localStorage) for this MCP's ``auth.json``.

Why this exists
---------------
HEB's reese84/Incapsula anti-bot rejects automated and headless logins
(HTTP 401). That means the embedded ``session_refresh`` *cannot* re-establish
a session once it has fully expired — it can only keep an already-valid
session warm. The reliable recovery is a **human** login in a **real** Chrome
(real browser + residential IP pass the anti-bot), then transplanting that
session into ``auth.json``.

This is NOT the Playwright-MCP ``browser_navigate``/``browser_run_code`` flow:
that drives an *automated* browser, which HEB blocks, and which you can't
interactively log into. This script instead reads the session out of a real
Chrome you started yourself.

Flow
----
1. Launch a real Chrome with a CLEAN profile + remote debugging, e.g.:

     # Windows
     "%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe" ^
       --remote-debugging-port=9222 --user-data-dir=%TEMP%\\heb-capture ^
       https://www.heb.com/my-account/login

     # macOS / Linux
     google-chrome --remote-debugging-port=9222 \
       --user-data-dir=/tmp/heb-capture https://www.heb.com/my-account/login

2. Log in as a human in that window (handle any 2FA / CAPTCHA). Land on a
   logged-in page (My Account or the cart).

3. Run this script to capture the session:

     python scripts/capture_session.py --out /path/to/auth.json

4. Verify by calling the ``session_status`` MCP tool (expect
   ``authenticated: true``). If the MCP runs elsewhere (e.g. a container),
   copy the produced JSON onto its auth volume first.

Note: ``connect_over_cdp()`` captures cookies but NOT localStorage, so
localStorage is read explicitly from the open page(s) — HEB keeps a ``reese84``
anti-bot token there in addition to the cookie, and the session is rejected
without it.

Requires: ``pip install playwright`` (the package only — no ``playwright
install`` browser download is needed, since this attaches to your existing
Chrome over CDP).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(
        "playwright is not installed. Install it with:\n"
        "  pip install playwright\n"
        "(no 'playwright install' needed — this attaches to your running Chrome)"
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--cdp-url",
        default="http://localhost:9222",
        help="DevTools endpoint of the Chrome started with "
        "--remote-debugging-port (default %(default)s)",
    )
    ap.add_argument("--out", required=True, help="output storageState JSON path (your auth.json)")
    ap.add_argument(
        "--origin-filter",
        default="heb.com",
        help="only capture localStorage for open pages whose URL contains this "
        "substring (default %(default)s)",
    )
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_url)
        if not browser.contexts:
            sys.exit("no browser contexts on the CDP endpoint — is Chrome running with "
                     "--remote-debugging-port?")
        ctx = browser.contexts[0]

        # cookies come back here; origins (localStorage) is empty over CDP.
        state = ctx.storage_state()

        # Collect localStorage + the browser User-Agent from the live page(s).
        origins: dict[str, list[dict[str, str]]] = {}
        user_agent: str | None = None
        for page in ctx.pages:
            if args.origin_filter and args.origin_filter not in page.url:
                continue
            try:
                origin = page.evaluate("() => location.origin")
                if user_agent is None:
                    user_agent = page.evaluate("() => navigator.userAgent")
                entries = page.evaluate(
                    "() => Object.entries(window.localStorage)"
                    ".map(([name, value]) => ({ name, value }))"
                )
            except Exception:
                continue
            if entries:
                origins[origin] = entries
        if origins:
            state["origins"] = [
                {"origin": o, "localStorage": ls} for o, ls in origins.items()
            ]

        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)

        # Write the captured browser's User-Agent next to auth.json. The MCP's
        # refresh browser + httpx API client read this so their UA matches the
        # captured session — HEB's Incapsula binds the reese84 token to the UA
        # and refuses to renew it for a mismatched browser (token freezes).
        if user_agent:
            ua_path = Path(args.out).resolve().parent / "browser_ua.txt"
            ua_path.write_text(user_agent, encoding="utf-8")
            print(f"wrote {ua_path}\n  UA: {user_agent}")
        browser.close()

    cookies = state.get("cookies", [])
    flt = args.origin_filter or ""
    matched = [c for c in cookies if flt in c.get("domain", "")]
    ls_keys = [i["name"] for o in state.get("origins", []) for i in o["localStorage"]]
    print(f"wrote {args.out}")
    print(f"  cookies={len(cookies)} matching-domain={len(matched)}")
    print(f"  origins={[o['origin'] for o in state.get('origins', [])]}")
    print(f"  localStorage keys={ls_keys}")
    if not matched:
        print("WARNING: no cookies matched the origin filter — are you logged in "
              "in the remote-debugging Chrome?", file=sys.stderr)
    if "reese84" not in ls_keys:
        print("WARNING: no reese84 localStorage token captured — the session may be "
              "rejected by HEB's anti-bot. Make sure a heb.com page is open.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
