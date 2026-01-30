# Texas Grocery MCP

An MCP (Model Context Protocol) server that enables AI agents to interact with HEB grocery stores for product search, cart management, and pickup scheduling.

## Features

- **Store Search**: Find HEB stores by address or zip code
- **Product Search**: Search products with pricing and availability
- **Cart Management**: Add/remove items with human-in-the-loop confirmation
- **Pickup Scheduling**: Schedule curbside pickup times

## Installation

```bash
pip install texas-grocery-mcp
```

### Prerequisites

This MCP uses **Microsoft Playwright MCP** for authentication. Install it alongside:

```bash
npm install -g @anthropic-ai/mcp-playwright
```

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@anthropic-ai/mcp-playwright"]
    },
    "heb": {
      "command": "uvx",
      "args": ["texas-grocery-mcp"],
      "env": {
        "HEB_DEFAULT_STORE": "590"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HEB_DEFAULT_STORE` | Default store ID | None |
| `REDIS_URL` | Redis cache URL | None (in-memory) |
| `LOG_LEVEL` | Logging level | INFO |

## Usage

### Finding a Store

```
User: Find HEB stores near Austin, TX

Agent uses: store_search(address="Austin, TX", radius_miles=10)
```

### Searching Products

```
User: Search for organic milk

Agent uses: store_set_default(store_id="590")
Agent uses: product_search(query="organic milk")
```

### Adding to Cart

Cart operations require authentication via Playwright MCP:

```
User: Add 2 gallons of milk to my cart

Agent uses: cart_add(product_id="123456", quantity=2)
# Returns preview with confirm=true instruction

Agent uses: cart_add(product_id="123456", quantity=2, confirm=true)
# Executes the action
```

## Authentication

For cart operations, authenticate using Playwright MCP:

1. `browser_navigate('https://www.heb.com/login')`
2. Complete login in the browser
3. Save storage state:
   ```javascript
   await page.context().storageState({ path: '~/.texas-grocery-mcp/auth.json' })
   ```
4. Retry cart operations

## Available Tools

### Store Tools
- `store_search` - Find stores by address
- `store_set_default` - Set preferred store
- `store_get_default` - Get current default store

### Product Tools
- `product_search` - Search products
- `product_get` - Get product details

### Cart Tools
- `cart_check_auth` - Check authentication status
- `cart_get` - View cart contents
- `cart_add` - Add item (requires confirmation)
- `cart_remove` - Remove item (requires confirmation)

### Health Tools
- `health_live` - Liveness probe
- `health_ready` - Readiness probe with component status

## Development

```bash
# Clone repository
git clone https://github.com/yourusername/texas-grocery-mcp
cd texas-grocery-mcp

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check src/

# Run type checking
mypy src/
```

### Docker Development

```bash
# Build and run with Redis
docker-compose up --build

# Run tests in container
docker-compose run texas-grocery-mcp pytest
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User's MCP Environment                    │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │  Playwright MCP     │    │     Texas Grocery MCP       │ │
│  │  (Browser Auth)     │───▶│     (Grocery Logic)         │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
│                                        │                     │
└────────────────────────────────────────┼─────────────────────┘
                                         │
                                         ▼
                                  HEB GraphQL API
```

## License

MIT
