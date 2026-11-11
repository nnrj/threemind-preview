"""Serve the history locally, without PostgreSQL, credentials or simulation workers."""

import argparse
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from threemind_lab.document_api import register_document_routes
from threemind_lab.documents import Documents

ROOT = Path(__file__).resolve().parents[1]


def create_reader():
    app = FastAPI(title="ThreeMind history reader", docs_url=None, redoc_url=None)
    app.state.documents = Documents(ROOT)
    register_document_routes(app)
    dist = (ROOT / "threemind-ui/dist").resolve()

    @app.get("/")
    def index():
        return RedirectResponse("/history")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Read-only history service; Lab endpoints are not started")
        file = (dist / path).resolve()
        if file.is_relative_to(dist) and file.is_file():
            return FileResponse(file)
        if path not in ("history", "docs"):
            raise HTTPException(404, "This service only serves history and documentation")
        if not (dist / "index.html").is_file():
            raise HTTPException(503, "Build threemind-ui first: npm run build")
        return FileResponse(dist / "index.html")

    return app


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8911)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    uvicorn.run(create_reader(), host="127.0.0.1", port=args.port, access_log=False)
