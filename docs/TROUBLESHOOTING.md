# Troubleshooting Guide

This guide covers common issues and their solutions when using the Texas Grocery MCP.

## Table of Contents

- [Session & Authentication Issues](#session--authentication-issues)
- [Product Search Issues](#product-search-issues)
- [Cart Issues](#cart-issues)
- [Store Issues](#store-issues)
- [Network & API Issues](#network--api-issues)
- [Installation Issues](#installation-issues)

---

## Session & Authentication Issues

### "Session expired" / "needs_refresh: true"

**Symptoms:**
- `session_status` shows `authenticated: false` or `needs_refresh: true`
- Operations return "Login required" errors

**Solution:**
```
1. Call session_refresh(headless=False)
2. Complete login in the browser window that opens
3. Tell the assistant "done" when you've logged in
4. The assistant will call session_refresh() again to save the session
```

**If auto-login is configured:**
```
1. Call session_refresh() - it will attempt automatic login
2. If CAPTCHA appears, you'll get a screenshot and need to solve it manually
3. After solving, tell the assistant "done"
```

---

### "Security challenge detected" / WAF Block

**Symptoms:**
- `security_challenge_detected: true` in search results
- Browser shows "Please verify you are human"
- Screenshot shows hCaptcha or "Additional security check required"

**Cause:** HEB's Web Application Firewall (WAF) detected automated access.

**Solution:**
```
1. Call session_refresh(headless=False)
2. Solve the CAPTCHA in the browser window
3. Navigate around the site briefly (search for a product, click a category)
4. Tell the assistant "done"
```

**Prevention:**
- Don't make too many rapid requests
- Use `product_search_batch` instead of many individual searches
- Keep your session refreshed (don't let it expire completely)

---

### "Could not find login form" Error

**Symptoms:**
- `session_refresh` returns `error: login_form_not_found`
- Screenshot shows unexpected page content

**Causes:**
- HEB changed their login page structure
- Network issue caused incomplete page load
- WAF blocked the request before login page loaded

**Solution:**
```
1. Check the screenshot to see what loaded
2. Try session_refresh(headless=False, timeout=60000) with longer timeout
3. If WAF page shows, solve it first, then retry
4. If still failing, try session_clear() then session_refresh(headless=False)
```

---

### Credentials Not Working

**Symptoms:**
- `session_save_credentials` succeeded but auto-login fails
- "Invalid credentials" error during login

**Solution:**
```
1. Verify your HEB.com credentials work by logging in manually at heb.com
2. Check for typos in email/password
3. Clear and re-save credentials:
   - session_clear_credentials()
   - session_save_credentials(email="your@email.com", password="yourpassword")
4. Test with session_refresh()
```

---

## Product Search Issues

### "No products found" / Empty Results

**Symptoms:**
- `product_search` returns `count: 0`
- `data_source: typeahead_suggestions`

**Causes:**
- Query too specific or misspelled
- Store doesn't carry the product
- Session expired (falling back to limited search)

**Solutions:**

1. **Try broader search terms:**
   - Instead of "HEB Organics Whole Milk 1 Gallon" try "organic milk"
   - Instead of "boneless skinless chicken breast" try "chicken breast"

2. **Check store availability:**
   ```
   store_search("your address")
   store_change("store_id_from_results")
   product_search("your query")
   ```

3. **Refresh session if data_source is "typeahead_suggestions":**
   ```
   session_refresh()
   product_search("your query")
   ```

---

### "Cannot add to cart - missing product_id"

**Symptoms:**
- Product has `_warning: "Cannot add to cart - missing product_id"`
- `product_id` starts with "suggestion-"

**Cause:** The search fell back to typeahead suggestions which don't have real product IDs.

**Solution:**
```
1. Refresh your session: session_refresh()
2. Search again with the same query
3. If still getting suggestions, try a more specific query
4. Or use product_get with a known product_id
```

---

### Search Returns "price: null"

**Symptoms:**
- Products have `price: null` or no pricing info

**Cause:** Not authenticated or store not set.

**Solution:**
```
1. Check session: session_status()
2. If not authenticated: session_refresh(headless=False)
3. Set a store: store_change("store_id")
4. Search again
```

---

## Cart Issues

### "CART_ADD_NOT_VERIFIED" Error

**Symptoms:**
- `cart_add` returns `code: CART_ADD_NOT_VERIFIED`
- Item doesn't appear in cart

**Cause:** The item was sent to HEB but couldn't be verified in the cart afterwards.

**Possible reasons:**
- Product is out of stock
- Product ID is wrong
- Session issue

**Solution:**
```
1. Verify the product exists: product_get(product_id="...")
2. Check if it's available: look for available: true
3. Try cart_add_with_retry which handles ID mismatches
4. If still failing, refresh session and retry
```

---

### "SKU not found" / Wrong Product Added

**Symptoms:**
- `cart_add` succeeds but wrong item appears
- Error mentions SKU mismatch

**Cause:** The `product_id` and `sku_id` don't match.

**Solution:**
```
1. Search for the product fresh: product_search("product name")
2. Note BOTH IDs from results:
   - product_id (short, e.g., "127074")
   - sku (long, e.g., "127074-HEB")
3. Use both in cart_add:
   cart_add(product_id="127074", sku_id="127074-HEB", quantity=1, confirm=True)
```

---

### Cart Shows Different Store's Prices

**Symptoms:**
- Cart prices don't match what you searched
- Items marked "unavailable at your store"

**Cause:** Your HEB account store doesn't match the store you searched.

**Solution:**
```
1. Check your current store: store_get_default()
2. Change to the correct store: store_change("desired_store_id")
3. If conflicts appear, either:
   - Clear cart first, then change store
   - Or use store_change(store_id="...", ignore_conflicts=True)
```

---

## Store Issues

### "STORE_NOT_ELIGIBLE" Error

**Symptoms:**
- `store_change` returns `code: STORE_NOT_ELIGIBLE`
- Message says store doesn't support online shopping

**Cause:** Some HEB stores are in-store only (no curbside/delivery).

**Solution:**
```
1. Search for nearby stores: store_search("your address")
2. Look for stores with supports_curbside: true
3. Choose one of those stores
```

---

### "Geocoding failed" / Can't Find Stores

**Symptoms:**
- `store_search` returns no results
- Error mentions geocoding failure

**Causes:**
- Address not recognized
- Geocoding service unavailable

**Solutions:**

1. **Try different address formats:**
   - Full address: "1234 Main St, Austin, TX 78701"
   - Just zip code: "78701"
   - City and state: "Austin, TX"

2. **Use known store IDs directly:**
   ```
   # Common Austin area stores:
   store_change("465")  # HEB Mueller
   store_change("573")  # HEB Hancock
   ```

---

## Network & API Issues

### Timeout Errors

**Symptoms:**
- Operations fail with timeout errors
- "Connection timed out" messages

**Solutions:**
```
1. Check your internet connection
2. Try again - HEB's servers may be slow
3. For session_refresh, increase timeout:
   session_refresh(headless=False, timeout=60000)
```

---

### "Circuit breaker open"

**Symptoms:**
- Multiple operations fail
- `health_ready` shows circuit breaker open

**Cause:** Too many consecutive failures triggered the circuit breaker.

**Solution:**
```
1. Wait 30 seconds for the circuit breaker to recover
2. Check health_ready() - wait until graphql_api status is "up"
3. Retry your operation
```

---

## Installation Issues

### "Playwright not installed"

**Symptoms:**
- `session_refresh` says Playwright not available
- Browser-based features don't work

**Solution:**
```bash
# Install with browser support
pip install texas-grocery-mcp[browser]

# Or with uv:
uv pip install texas-grocery-mcp[browser]

# Install browser binaries
playwright install chromium
```

---

### "Chromium not found"

**Symptoms:**
- Session refresh fails to launch browser
- Error mentions missing Chromium

**Solution:**
```bash
playwright install chromium
```

---

## Error Code Reference

| Code | Meaning | Solution |
|------|---------|----------|
| `NO_STORE_SET` | No default store configured | Use `store_change("store_id")` |
| `STORE_NOT_ELIGIBLE` | Store doesn't support online orders | Choose a different store |
| `CART_ADD_NOT_VERIFIED` | Item add couldn't be confirmed | Check product availability, retry |
| `CART_CONFLICT` | Cart has items unavailable at new store | Use `ignore_conflicts=True` or clear cart |
| `INVALID_PRODUCT_ID` | Product ID format is wrong | Use ID from `product_search` results |
| `PRODUCT_NOT_FOUND` | Product doesn't exist | Verify product ID |
| `LOGIN_REQUIRED` | Session expired | Use `session_refresh(headless=False)` |
| `FETCH_ERROR` | Network/API error | Check connection, retry |

---

## Getting More Help

If you're still stuck:

1. **Check session status:** `session_status()` - provides diagnostic info
2. **Check health:** `health_ready()` - shows component status
3. **Enable debug logging:** Set `LOG_LEVEL=DEBUG` environment variable
4. **Report issues:** https://github.com/mgwalkerjr95/texas-grocery-mcp/issues

When reporting issues, include:
- The error message/code
- Output from `session_status()`
- What you were trying to do
- Any screenshots if session_refresh provided them
