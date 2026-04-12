"""
OpenEnv / HF layout shim: some tooling expects server/app.py with app + main().

The real FastAPI app lives at repo root (main.py). CMD uses: uvicorn main:app
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from main import app as app  # noqa: E402


def main(host: str = "0.0.0.0", port: int = 7860) -> None:
    import uvicorn

    uvicorn.run("server.app:app", host=host, port=port, factory=False)


if __name__ == "__main__":
    main()
