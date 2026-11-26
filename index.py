"""Entry point for serverless hosts that look for a FastAPI ``app`` in the project root (Vercel).

Locally you do not need this file: use start.bat / start.sh (or ``python backend/run.py``).
The web app is served by the same FastAPI app from ``frontend/dist`` (built during deployment).

If the app cannot even be imported (a missing library, a broken file), a tiny fallback app answers
every request with the error, so the browser shows the real reason instead of a generic
"function failed" page. It needs nothing but the Python standard library.
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))  # make the `app` package importable

try:
    from app.main import app
except Exception as _exc:  # noqa: BLE001 - any import problem must become a readable page
    _frames = traceback.extract_tb(_exc.__traceback__)[-4:]
    _REPORT = (
        "CropDoc GB could not start on this server.\n\n"
        + "".join(traceback.format_exception_only(type(_exc), _exc))
        + "\nWhere:\n"
        + "".join(f"  {Path(f.filename).name}:{f.lineno} in {f.name}\n" for f in _frames)
        + "\nHelp: docs/deploy.md (Vercel section) in the project repository.\n"
    ).encode()
    print(_REPORT.decode(), file=sys.stderr)

    async def app(scope, receive, send):  # minimal ASGI app (no FastAPI needed)
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"cache-control", b"no-store")],
            }
        )
        await send({"type": "http.response.body", "body": _REPORT})


__all__ = ["app"]
