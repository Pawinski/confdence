# Confdence

Patient-owned record for Quebec. See [PRODUCT.md](PRODUCT.md).

## Local (file)

```sh
open /Users/apawinski/dev/health/confdence.html
```

Rebuild after changing `static/`:

```sh
python3 scripts/build_wallet.py
```

## Production (home screen)

GitHub Pages publishes `static/` from `main`.

https://pawinski.github.io/confdence/

On iPhone: open that URL in **Safari** → Share → **Add to Home Screen**. Facts stay in the phone’s browser.

Do not deploy `uvicorn` / `.data/health.db` with real health facts.

## Agents (MCP)

Off until you consent in the app (every risk checked). Then:

1. Download the agent pack from the app
2. `python3 mcp_consent.py install ~/Downloads/confdence-agent-pack.json`
3. Add to `~/.grok/config.toml` or this repo’s `.grok/config.toml`:

```toml
[mcp_servers.confdence]
command = "/Users/apawinski/dev/health/.venv/bin/python"
args = ["/Users/apawinski/dev/health/mcp_server.py"]
```

`python3 mcp_consent.py disable` turns the server back into a brick.

```sh
.venv/bin/python scripts/make_icons.py
.venv/bin/python scripts/build_wallet.py
.venv/bin/pytest -q
```
