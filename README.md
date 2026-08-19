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

```sh
.venv/bin/python scripts/make_icons.py
.venv/bin/python scripts/build_wallet.py
.venv/bin/pytest -q
```
