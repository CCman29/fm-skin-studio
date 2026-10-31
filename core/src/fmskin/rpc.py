"""Line-delimited JSON-RPC over stdin/stdout for the desktop app.

Request:  {"id": 1, "method": "packs.create", "params": {"name": "My Skin"}}
Response: {"id": 1, "result": ...}  or  {"id": 1, "error": {"message": ..., "type": ...}}
Event:    {"event": "progress", "data": {...}}   (no id; e.g. while building the index)
"""

from __future__ import annotations

import json
import sys
import threading
import traceback

from .service import ERRORS, Service

METHODS = {
    "ping": "ping", "settings.get": "settings", "settings.set": "set_settings", "paths.get": "get_paths",
    "index.status": "index_status", "index.build": "build_index",
    "tokens.groups": "token_groups", "tokens.list": "tokens", "sheets.get": "sheet",
    "screens.list": "screens", "screens.get": "screen",
    "packs.list": "packs", "packs.create": "create_pack", "packs.get": "pack", "packs.rename": "rename_pack",
    "packs.setTokens": "set_tokens", "packs.screenSheet": "screen_sheet", "packs.writeScreenSheet": "write_screen_sheet",
    "packs.addAsset": "add_asset", "packs.validate": "validate", "packs.export": "export_pack",
    "packs.import": "import_pack", "packs.delete": "delete_pack",
    "fonts.catalog": "font_catalog", "packs.useFont": "use_font", "packs.resetFont": "reset_font",
    "packs.useBuiltinFont": "use_builtin_font", "packs.bars": "bars", "packs.setBars": "set_bars",
    "tokens.areas": "areas", "tokens.usage": "token_usage", "packs.applyRecipe": "apply_recipe", "recipe.defaults": "recipe_defaults", "recipe.preview": "recipe_preview", "recipe.fields": "recipe_fields",
    "preview.assets": "preview_assets", "preview.panel": "preview_panel", "preview.screen": "preview_screen",
    "layouts.place": "place_panels", "layouts.apply": "apply_layouts", "layouts.backups": "layout_backups",
    "layouts.restore": "restore_layouts", "log.events": "log_events",
    "editor.screens": "screen_catalog", "editor.settings": "screen_settings", "packs.screenBackdrop": "screen_backdrop",
    "packs.screenBackdrops": "screen_backdrops", "coded.list": "coded_areas", "coded.set": "set_coded_area",
    "packs.image": "pack_image", "preview.localImage": "local_image", "editor.shots": "reference_shots", "editor.setShot": "set_reference_shot",
    "editor.shot": "reference_image", "editor.pick": "pick_settings",
    "drafts.open": "draft_open", "drafts.status": "draft_status", "drafts.save": "draft_save", "drafts.discard": "draft_discard", "drafts.dirty": "draft_dirty",
    "settings.skinsFolder": "set_skins_folder", "settings.backupFolder": "set_backup_folder", "packs.share": "share_pack",
    "gamelink.status": "gamelink_status", "gamelink.install": "gamelink_install", "gamelink.remove": "gamelink_remove",
    "gamelink.screen": "gamelink_screen", "gamelink.reload": "gamelink_reload", "gamelink.screenshot": "gamelink_screenshot", "gamelink.live": "gamelink_live",
    "packs.systemText": "system_text", "packs.setSystemText": "set_system_text",
}


def call(service: Service, method: str, params: dict, progress=None) -> dict:
    """Run one request; returns a response dict with result or error."""
    attr = METHODS.get(method)
    if not attr:
        return {"error": {"message": f"Unknown method {method}", "type": "MethodNotFound"}}
    try:
        fn = getattr(service, attr)
        result = fn(progress=progress, **params) if method == "index.build" else fn(**params)
        return {"result": result}
    except ERRORS as e:
        message = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
        return {"error": {"message": message, "type": type(e).__name__}}
    except Exception as e:  # report, keep serving
        return {"error": {"message": str(e), "type": type(e).__name__, "trace": traceback.format_exc(limit=5)}}


def serve_http(port: int = 8765, service: Service | None = None) -> None:
    """Development only: the same API over HTTP on localhost so the UI can run in a normal browser."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    service = service or Service()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "http://localhost:5174")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):  # noqa: N802
            self._send(204, {})

        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._send(200, call(service, body.get("method", ""), body.get("params") or {}))

        def log_message(self, *args):
            pass

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def serve(service: Service | None = None, stdin=None, stdout=None) -> None:
    service = service or Service()
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    lock = threading.Lock()

    def send(message: dict) -> None:
        with lock:
            stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
            stdout.flush()

    def progress(stage: str, i: int, n: int) -> None:
        send({"event": "progress", "data": {"stage": stage, "done": i + 1, "total": n}})

    send({"event": "ready", "data": service.ping()})
    for line in stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except ValueError:
            send({"id": None, "error": {"message": "Invalid JSON", "type": "ParseError"}})
            continue
        rid, method, params = request.get("id"), request.get("method"), request.get("params") or {}
        if method == "shutdown":
            send({"id": rid, "result": True})
            break
        send({"id": rid} | call(service, method, params, progress))
