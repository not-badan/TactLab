"""Web entry point for a standalone, publicly hosted TactLab instance."""
import gzip
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from model import settings
from outputs import archive, preview

cad_lock = Lock()

@lru_cache(maxsize=8)
def preview_bytes(key):
    return gzip.compress(json.dumps(preview(json.loads(key)), separators=(",", ":")).encode(), compresslevel=3)

async def generate(request):
    if request.headers.get("content-type","").split(";")[0].strip() != "application/json":
        return JSONResponse({"error":"Ожидались параметры в JSON."}, status_code=415)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 4096:
            return JSONResponse({"error":"Слишком большой запрос."}, status_code=413)
        body.extend(chunk)
    try:
        params = settings(json.loads(body))
    except (ValueError, TypeError, RecursionError):
        return JSONResponse({"error":"Проверьте тип, размеры и параметры посадки."}, status_code=422)
    def calculate():
        with cad_lock:
            if request.url.path == "/api/model":
                data = preview_bytes(json.dumps(params,sort_keys=True))
                return Response(data, media_type="application/json", headers={"Content-Encoding":"gzip"})
            return Response(archive(params),media_type="application/zip",
                            headers={"Content-Disposition":f'attachment; filename="Tact-{params["mode"]}.zip"'})
    try:
        return await run_in_threadpool(calculate)
    except Exception:
        logging.exception("CAD error")
        return JSONResponse({"error":"Не удалось построить модель. Проверьте сочетание размеров."}, status_code=422)

async def health(request):
    return JSONResponse({"ok":True})

app = Starlette(routes=[
    Route("/api/health",health),
    Route("/api/model",generate,methods=["POST"]),
    Route("/api/export",generate,methods=["POST"]),
    Mount("/",StaticFiles(directory=Path(__file__).parent/"public", html=True))
])

if __name__ == "__main__":
    uvicorn.run(app,host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","8096")),
                limit_concurrency=24,timeout_keep_alive=5)
