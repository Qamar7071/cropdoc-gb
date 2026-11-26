"""Entry point for serverless hosts that look for a FastAPI ``app`` in the project root (Vercel).

Locally you do not need this file: use start.bat / start.sh (or ``python backend/run.py``).
The web app is served by the same FastAPI app from ``frontend/dist`` (built during deployment).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))  # make the `app` package importable

from app.main import app  # noqa: E402

__all__ = ["app"]
