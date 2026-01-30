# Reliable Store Search Design

## Problem

The current store search fails silently for many valid location queries:
- Neighborhood names ("Rice Military", "Montrose")
- Partial addresses ("Washington Ave, Houston")
- Some zip codes and city names

This happens because:
1. HEB's StoreSearch API is sensitive to address format
2. When the API returns empty results, we fall back to a hardcoded list of 3 stores
3. Users get no feedback about why their search failed

## Goals

1. **Always find nearby stores** - Handle informal location queries by geocoding first
2. **Never fail silently** - Return clear feedback about what was tried and why it failed

## Solution: Geocoding + Query Variations

### Overview

Convert user input to coordinates using a geocoding service, extract structured address components, then try multiple query formats against HEB's API until one succeeds.

```
User: "Rice Military, Houston"
        ↓
   Geocoding (Nominatim)
        ↓
   {lat: 29.76, lon: -95.41, zip: "77007", city: "Houston", state: "TX"}
        ↓
   Try queries in order:
     1. "77007" → HEB API
     2. "Houston, TX" → HEB API
     3. "Rice Military, Houston" → HEB API
        ↓
   Sort results by distance from geocoded point
        ↓
   Return stores + detailed feedback
```

### Geocoding Service

**Provider:** Nominatim (OpenStreetMap)
- Free, no API key required
- Handles neighborhoods, landmarks, partial addresses
- Returns structured address components

**Endpoint:**
```
GET https://nominatim.openstreetmap.org/search
    ?q={address}
    &format=json
    &addressdetails=1
    &limit=1
    &countrycodes=us
```

**Required headers:**
```
User-Agent: texas-grocery-mcp/1.0 (contact@example.com)
```

**Rate limiting:** Max 1 request/second (we'll do 1 per search, well under limit)

**Response parsing:**
```python
@dataclass
class GeocodingResult:
    latitude: float
    longitude: float
    city: str | None
    state: str | None
    postcode: str | None
    display_name: str
```

### Query Variation Strategy

Try queries in this order (stop when results found):

| Priority | Query Format | Example | Rationale |
|----------|--------------|---------|-----------|
| 1 | Zip code | "77007" | Most reliable with HEB's API |
| 2 | City, State | "Houston, TX" | Broad fallback |
| 3 | Original input | "Rice Military" | User might know something we don't |

**Timeouts:**
- Each HEB API query: 5 seconds
- Total search operation: 15 seconds
- Geocoding: 5 seconds

### Distance Calculation

After receiving stores from HEB's API, recalculate distance from the geocoded point (not HEB's internal geocoding) using Haversine formula:

```python
def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    # Earth radius in miles
    R = 3959
    # ... standard haversine calculation
```

Sort results by this calculated distance.

### Error Handling & Feedback

**Successful response:**
```python
{
    "stores": [...],
    "count": 5,
    "search_address": "Rice Military, Houston",
    "geocoded": {
        "latitude": 29.7632,
        "longitude": -95.4145,
        "display_name": "Rice Military, Houston, TX 77007"
    }
}
```

**Failed response (no stores found):**
```python
{
    "stores": [],
    "count": 0,
    "search_address": "Rice Military, Houston",
    "geocoded": {
        "latitude": 29.7632,
        "longitude": -95.4145,
        "display_name": "Rice Military, Houston, TX 77007"
    },
    "attempts": [
        {"query": "77007", "result": "no_stores"},
        {"query": "Houston, TX", "result": "no_stores"},
        {"query": "Rice Military, Houston", "result": "no_stores"}
    ],
    "error": "No HEB stores found within 25 miles. HEB operates primarily in Texas.",
    "suggestions": [
        "Verify this is a Texas location",
        "Try increasing the search radius"
    ]
}
```

**Failure messages by scenario:**

| Scenario | Error Message |
|----------|---------------|
| Geocoding failed | "Couldn't locate '{input}'. Try a zip code or street address." |
| No stores in radius | "No HEB stores found within {radius} miles of {location}." |
| HEB API error | "HEB's store locator is temporarily unavailable. Try again shortly." |
| Location outside Texas | "No HEB stores found. HEB operates primarily in Texas and Mexico." |

### Architecture

**New file:** `src/texas_grocery_mcp/services/geocoding.py`
```python
class GeocodingService:
    """Geocoding via Nominatim (OpenStreetMap)."""

    async def geocode(self, address: str) -> GeocodingResult | None:
        """Convert address to coordinates and structured components."""

    def calculate_distance(self, lat1, lon1, lat2, lon2) -> float:
        """Haversine distance in miles."""
```

**Modified:** `src/texas_grocery_mcp/clients/graphql.py`
- Import and use `GeocodingService`
- New method: `_try_store_queries()` - tries multiple query variations
- Modified: `search_stores()` - orchestrates geocoding + query attempts + feedback

**No changes to:**
- `src/texas_grocery_mcp/tools/store.py` - MCP tool interface stays the same
- Any other files

### Dependencies

No new packages. Uses `httpx` (already a dependency).

## Implementation Tasks

1. **Create geocoding service** - New `services/geocoding.py` with `GeocodingService` class
2. **Add Haversine distance calculation** - Helper function for distance sorting
3. **Update `search_stores()`** - Integrate geocoding, query variations, and feedback
4. **Add tests** - Unit tests for geocoding, integration tests for store search
5. **Remove hardcoded fallback** - Delete `KNOWN_STORES` constant (no longer needed)

## Testing Plan

**Unit tests:**
- Geocoding service parses Nominatim responses correctly
- Haversine calculation produces correct distances
- Query variation order is correct

**Integration tests:**
- "77007" returns stores (zip code)
- "Houston, TX" returns stores (city/state)
- "Rice Military, Houston" returns stores (neighborhood)
- "Invalid Location XYZ" returns helpful error
- Geocoding timeout falls back gracefully

**Manual verification:**
- Search for "3663 Washington Ave, Houston" finds Washington Heights H-E-B
- Search for "downtown Austin" finds nearby stores
- Search for "New York, NY" returns clear "no HEB stores" message

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Nominatim rate limiting | We do max 1 request per search; well under 1/second limit |
| Nominatim downtime | Fall back to trying original query directly against HEB |
| HEB API changes | Existing circuit breaker + retry logic handles transient failures |
| Geocoding returns wrong location | Show geocoded location in response so user can correct |

## Success Criteria

1. "Rice Military, Houston" finds Washington Heights H-E-B at 3663 Washington Ave
2. Failed searches return actionable error messages
3. No increase in average search latency beyond 500ms
4. All existing tests continue to pass
