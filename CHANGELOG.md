# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `scripts/capture_session.py` — capture a live, human-authenticated HEB session
  (cookies + localStorage, incl. the `reese84` anti-bot token) from a real Chrome
  started with `--remote-debugging-port`, into Playwright `storageState` JSON. This
  is the reliable recovery when HEB's anti-bot blocks automated/headless re-login.
- **Background reese84 keep-warm loop:** the server now proactively renews the
  reese84 anti-bot token on a timer (new `reese84_keepwarm_interval_s` setting, env
  `REESE84_KEEPWARM_INTERVAL_S`, default `540`s / ~9 min; `0` disables). HEB's token
  renews ~every 11 min via page-load JS; previously the MCP only refreshed *lazily*
  before a tool call, so an idle MCP let the token expire and clustered refreshes
  into op bursts (more anti-bot heat + first-call latency). The loop also fires
  **once shortly after startup**, so the MCP gets itself into a good state right
  away instead of sitting idle until the first tool call. Runs as a background task
  (never blocks startup) and never crashes the server (all failures logged + retried
  next cycle).

### Changed
- `session_save_instructions` now documents the **real-Chrome CDP recapture** flow
  instead of the Playwright-MCP `browser_navigate`/`browser_run_code` flow (which
  HEB's reese84/Incapsula anti-bot blocks — you can't complete a human login in an
  automated browser).

### Fixed
- **Container-hardened the refresh browser (the reliability linchpin):** the
  Playwright Chromium launch lacked `--no-sandbox` / `--disable-dev-shm-usage`, so
  in a container it used the default 64 MB `/dev/shm` and crashed under memory
  pressure — leaving defunct Chrome zombies and a refresh that launched but never
  renewed reese84 (so keep-warm + the lazy `ensure_session` refresh silently did
  nothing and the session died on idle). Added `--no-sandbox`,
  `--disable-dev-shm-usage`, and `--disable-gpu` to all browser launches. This is
  what makes the in-container refresh reliable, which both keep-warm and the
  per-call lazy refresh depend on.
- **Account-mismatch guard:** `session_refresh` no longer auto-logs-in with stored
  credentials when they belong to a *different* account than the saved session.
  Previously a mismatched auto-login that happened to succeed would overwrite the
  existing account's `auth.json` with the wrong account's session. Added
  `get_session_account_email()` (reads the `loginEmail` cookie) and a guard that
  returns an `account_mismatch` error instead of clobbering the session.
- **Headed auto-refresh (`auto_refresh_headless`):** the background session
  auto-refresh hardcoded `headless=True`. HEB's Incapsula anti-bot returns HTTP
  401 to the *headless* refresh browser, so it could never renew the reese84
  token and the session silently died (every tool call then failed with "login
  required"). New `auto_refresh_headless` setting (env `AUTO_REFRESH_HEADLESS`,
  default `true` for compatibility) — set it `false` where a virtual display is
  available (e.g. `xvfb` in a container) to refresh via a headed browser that
  passes the anti-bot, keeping the session self-sustaining. When headed mode
  hits a fully-expired session it now cleans up the handoff browser and returns
  `LOGIN_REQUIRED` instead of leaving it hanging.
- **User-Agent now matches the captured session (reese84-renewal fix):** the
  refresh browser **and** the httpx API client hardcoded a `Mac Chrome 120` UA,
  but sessions captured from a real browser carry that browser's UA (e.g. Windows
  Chrome). HEB's Incapsula **binds the reese84 token to the browser UA and
  silently refuses to renew it for a mismatched UA** — every refresh returned
  HTTP 200 but the token's `renewTime` froze, so the session died with no error.
  Added `heb_browser_user_agent` setting + `get_browser_user_agent()` which
  prefers `<auth_dir>/browser_ua.txt` (written by `capture_session.py` from the
  real capture browser). All 3 Playwright contexts + the API client now use it,
  so refresh/API always match the captured fingerprint.
- **Headless refresh no longer false-aborts on a normal page (the real fix):** the
  content-heuristic `_detect_security_challenge` mis-flags HEB's normal page (served
  behind an Incapsula JS shell) as a "security challenge" and aborted refreshes that
  would have succeeded — verified: a raw page load renews reese84 with HTTP 200 in the
  exact conditions where the refresh reported a challenge. The headless refresh now keys
  success off **reese84 actually renewing** (its `renewTime` advancing) and only checks
  for a real challenge/login if it did NOT renew. Note this supersedes the
  `auto_refresh_headless` workaround above: **headless is the working mode for HEB**; the
  headed/xvfb path draws a real hCaptcha — keep `AUTO_REFRESH_HEADLESS` unset/`true`.
- **`session_refresh` no longer reports false success on a stale token:** the
  headless refresh did a single 5s wait then fell through to "save + success" even
  when reese84 hadn't actually renewed — so it would persist a stale token, report
  success, and the *next* operation would fail with "login required". It now (a)
  **polls** for renewal (~21s, since under load HEB's reese84 JS can take well over
  5s to issue a fresh token) instead of a one-shot check, and (b) **raises
  `BrowserRefreshError`** ("reese84 did not renew … retry shortly") when the page
  loaded fine and we're still authenticated but the token stayed stale — rather than
  lying about success. Callers/keep-warm retry shortly instead of trusting a dead
  session.

## [0.1.2] - 2026-02-02

### Changed
- README redesign with emojis and improved formatting
- Feature tables for better readability
- Tools organized in clean tables

### Fixed
- Placeholder link in TROUBLESHOOTING.md

### Removed
- firebase-debug.log from repository

## [0.1.1] - 2026-02-02

### Added
- Project URLs in PyPI metadata (homepage, repository, issues, changelog)
- PyPI, license, and CI badges in README
- CONTRIBUTING.md, SECURITY.md documentation

### Fixed
- GitHub repository URL in README

## [0.1.0] - 2026-02-02

### Added

- Initial public release
- **Store Tools**
  - `store_search` - Find HEB stores by address or zip code
  - `store_change` - Set preferred store (syncs with HEB.com when authenticated)
  - `store_get_default` - Get current default store
- **Product Tools**
  - `product_search` - Search products by name with pricing and availability
  - `product_search_batch` - Search multiple products at once (up to 20 queries)
  - `product_get` - Get comprehensive product details (ingredients, nutrition, warnings, dietary attributes)
- **Cart Tools**
  - `cart_check_auth` - Check authentication status
  - `cart_get` - View cart contents
  - `cart_add` - Add item with human-in-the-loop confirmation
  - `cart_add_many` - Bulk add multiple items
  - `cart_add_with_retry` - Add item with automatic retry on failure
  - `cart_remove` - Remove item with confirmation
- **Coupon Tools**
  - `coupon_list` - List available digital coupons
  - `coupon_search` - Search coupons by keyword
  - `coupon_categories` - Get coupon category list
  - `coupon_clip` - Clip a coupon to your account
  - `coupon_clipped` - List your clipped coupons
- **Session Tools**
  - `session_status` - Check session health and token expiration
  - `session_refresh` - Refresh/login with embedded browser or Playwright MCP
  - `session_save_credentials` - Save credentials for auto-login (secure keyring storage)
  - `session_clear_credentials` - Remove saved credentials
  - `session_clear` - Clear saved session (logout)
- **Health Tools**
  - `health_live` - Liveness probe
  - `health_ready` - Readiness probe with component status
- Fast session refresh with embedded Playwright (~15 seconds)
- Human-in-the-loop confirmation for cart and coupon operations
- Request throttling to prevent rate limiting
- In-memory and Redis caching support
- Docker support with docker-compose
- CI/CD with GitHub Actions

[0.1.1]: https://github.com/mgwalkerjr95/texas-grocery-mcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/mgwalkerjr95/texas-grocery-mcp/releases/tag/v0.1.0
