from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from gtflow.config import AppConfig
from gtflow.gui.runtime import (
    artifacts_response,
    build_config,
    default_config,
    output_bundle,
    readiness_state,
    run_pipeline,
    source_segments,
)
from gtflow.pipeline.gioia_editing import apply_gioia_alignment_edits
from gtflow.models.schemas import Codebook


STATIC_DIR = Path(__file__).with_name("static")


def run_server(host: str = "127.0.0.1", port: int = 8501) -> None:
    server = ThreadingHTTPServer((host, port), GTFlowHandler)
    print(f"GTFlow UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class GTFlowHandler(BaseHTTPRequestHandler):
    server_version = "GTFlowUI/0.4"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if self.path.startswith("/static/"):
            requested = self.path.split("?", 1)[0].replace("/static/", "", 1)
            self._serve_static(requested)
            return
        if self.path == "/api/default-config":
            conf = default_config()
            data = conf.model_dump(mode="python")
            data["provider"]["api_key"] = None
            self._send_json(data)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/api/preview":
                self._handle_preview(payload)
            elif self.path == "/api/readiness":
                conf = build_config(payload)
                self._send_json(
                    readiness_state(
                        conf,
                        str(payload.get("text") or ""),
                        str(payload.get("source_name") or ""),
                    )
                )
            elif self.path == "/api/run":
                self._handle_run(payload)
            elif self.path == "/api/align-codebook":
                self._handle_align_codebook(payload)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("GTFLOW_UI_DEBUG"):
            super().log_message(format, *args)

    def _handle_preview(self, payload: Dict[str, Any]) -> None:
        conf = build_config(payload)
        text = str(payload.get("text") or "")
        source_name = str(payload.get("source_name") or "")
        segments = source_segments(text, source_name, conf.run.segmentation_strategy, conf.run.max_segment_chars) if text else []
        self._send_json(
            {
                "segments": [segment.model_dump() for segment in segments[:80]],
                "stats": {
                    "segments": len(segments),
                    "characters": len(text),
                    "avg_chars": round(len(text) / max(1, len(segments))),
                },
                "readiness": readiness_state(conf, text, source_name),
            }
        )

    def _handle_run(self, payload: Dict[str, Any]) -> None:
        conf = build_config(payload)
        text = str(payload.get("text") or "")
        source_name = str(payload.get("source_name") or "")
        ready = readiness_state(conf, text, source_name)
        if not ready["ready"]:
            self._send_error(HTTPStatus.BAD_REQUEST, "Input text or provider settings are incomplete.")
            return
        artifacts = run_pipeline(conf, text, source_name=source_name)
        bundle = output_bundle(conf, artifacts)
        self._send_json(artifacts_response(artifacts, bundle))

    def _handle_align_codebook(self, payload: Dict[str, Any]) -> None:
        codebook = Codebook.model_validate(payload.get("codebook") or {})
        rows = payload.get("rows") or []
        edited = apply_gioia_alignment_edits(codebook, rows)
        self._send_json(edited.model_dump())

    def _serve_static(self, requested: str) -> None:
        safe_name = requested.replace("\\", "/").strip("/")
        if ".." in safe_name:
            self._send_error(HTTPStatus.BAD_REQUEST, "Invalid path")
            return
        path = STATIC_DIR / safe_name
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type += "; charset=utf-8"
        self._serve_file(path, content_type)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
