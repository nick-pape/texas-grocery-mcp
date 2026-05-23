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

### Changed
- `session_save_instructions` now documents the **real-Chrome CDP recapture** flow
  instead of the Playwright-MCP `browser_navigate`/`browser_run_code` flow (which
  HEB's reese84/Incapsula anti-bot blocks — you can't complete a human login in an
  automated browser).

### Fixed
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
