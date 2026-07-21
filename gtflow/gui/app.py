from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlsplit

from pydantic import ValidationError

from gtflow.gui.runtime import (
    artifacts_response,
    build_config,
    default_config,
    output_bundle,
    readiness_state,
    rebuild_artifacts_with_codebook,
    run_pipeline,
    source_segments,
)
from gtflow.models.schemas import Codebook
from gtflow.pipeline.gioia_editing import apply_gioia_alignment_edits
from gtflow.pipeline.retry_utils import PipelineCancelled


STATIC_DIR = Path(__file__).with_name("static")

# These are hard resource boundaries for the local HTTP surface. Provider-level
# timeouts/retries and RunConfig bounds provide the corresponding outbound bound.
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_INPUT_CHARS = 2_000_000
MAX_SOURCE_SEGMENTS = 10_000
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 100_000
MAX_ALIGN_ROWS = 2_000
MAX_CODEBOOK_ENTRIES = 2_000
MAX_CONCURRENT_RUNS = 1
MAX_RETAINED_JOBS = 4
JOB_RETENTION_SECONDS = 60 * 60

CSRF_HEADER = "X-GTFlow-CSRF"
_CSRF_LOCK = threading.Lock()
_RUN_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)
_JOB_STORE_INIT_LOCK = threading.Lock()


class RunCancelled(Exception):
    """Raised by the progress callback at safe stage boundaries."""


@dataclass
class RunJob:
    job_id: str
    status: str = "queued"
    progress: int = 0
    stage: str = "queued"
    message: str = "Queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    edit_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    export_config: Any = field(default=None, repr=False)
    artifacts: Any = field(default=None, repr=False)
    result: Optional[Dict[str, Any]] = field(default=None, repr=False)
    bundle: Optional[bytes] = field(default=None, repr=False)
    error: Optional[Dict[str, str]] = None
    revision: int = 0

    def public(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "can_cancel": self.status in ("queued", "running", "cancelling"),
            "revision": self.revision,
        }
        if self.error:
            payload["error"] = dict(self.error)
        if self.status == "succeeded" and self.result is not None:
            payload["result"] = self.result
            payload["download_url"] = f"/api/jobs/{self.job_id}/bundle"
        return payload


class APIError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _job_store(server: Any) -> Tuple["OrderedDict[str, RunJob]", threading.RLock]:
    jobs = getattr(server, "gtflow_jobs", None)
    lock = getattr(server, "gtflow_jobs_lock", None)
    if jobs is None or lock is None:
        with _JOB_STORE_INIT_LOCK:
            jobs = getattr(server, "gtflow_jobs", None)
            lock = getattr(server, "gtflow_jobs_lock", None)
            if jobs is None or lock is None:
                jobs = OrderedDict()
                lock = threading.RLock()
                setattr(server, "gtflow_jobs", jobs)
                setattr(server, "gtflow_jobs_lock", lock)
    return jobs, lock


def _cleanup_jobs(server: Any) -> None:
    jobs, lock = _job_store(server)
    cutoff = time.time() - JOB_RETENTION_SECONDS
    terminal = {"succeeded", "failed", "cancelled"}
    with lock:
        for job_id, job in list(jobs.items()):
            if job.status in terminal and job.updated_at < cutoff:
                jobs.pop(job_id, None)
        while len(jobs) >= MAX_RETAINED_JOBS:
            removable = next((job_id for job_id, job in jobs.items() if job.status in terminal), None)
            if removable is None:
                break
            jobs.pop(removable, None)


def _valid_job_id(job_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{24,64}", job_id or ""))


def _get_job(server: Any, job_id: str) -> RunJob:
    if not _valid_job_id(job_id):
        raise APIError(HTTPStatus.NOT_FOUND, "job_not_found", "The analysis job was not found.")
    jobs, lock = _job_store(server)
    with lock:
        job = jobs.get(job_id)
        if job is None:
            raise APIError(HTTPStatus.NOT_FOUND, "job_not_found", "The analysis job was not found.")
        return job


def _pipeline_stage(label: str) -> str:
    lowered = label.lower()
    if "segment" in lowered:
        return "segmenting"
    if "open coding" in lowered:
        return "open-coding"
    if "codebook" in lowered:
        return "codebook"
    if "axial" in lowered:
        return "axial-coding"
    if "selective" in lowered:
        return "selective-coding"
    if "negative" in lowered or "saturation" in lowered:
        return "validation"
    return "finalizing"


def _run_background_job(server: Any, job: RunJob, conf: Any, text: str, source_name: str) -> None:
    jobs, lock = _job_store(server)

    def update(**values: Any) -> None:
        with lock:
            current = jobs.get(job.job_id)
            if current is None:
                return
            for name, value in values.items():
                setattr(current, name, value)
            current.updated_at = time.time()

    def progress(value: int, label: str) -> None:
        if job.cancel_event.is_set():
            raise RunCancelled
        bounded = min(94, max(1, int(value)))
        update(status="running", progress=bounded, stage=_pipeline_stage(label), message=label)

    try:
        if job.cancel_event.is_set():
            raise RunCancelled
        update(status="running", progress=1, stage="starting", message="Starting analysis")
        artifacts = run_pipeline(
            conf,
            text,
            progress=progress,
            source_name=source_name,
            cancel_event=job.cancel_event,
        )
        if job.cancel_event.is_set():
            raise RunCancelled
        update(status="running", progress=96, stage="packaging", message="Building audit bundle")
        bundle = output_bundle(conf, artifacts)
        if job.cancel_event.is_set():
            raise RunCancelled
        result = artifacts_response(artifacts)
        update(
            status="succeeded",
            progress=100,
            stage="complete",
            message="Complete",
            artifacts=artifacts,
            result=result,
            bundle=bundle,
            error=None,
        )
    except (RunCancelled, PipelineCancelled):
        update(
            status="cancelled",
            stage="cancelled",
            message="Cancelled",
            error={"code": "cancelled", "message": "The analysis run was cancelled."},
        )
    except Exception as exc:
        if os.getenv("GTFLOW_UI_DEBUG"):
            print(f"GTFlow background job failed: {type(exc).__name__}")
        update(
            status="failed",
            stage="failed",
            message="Analysis failed",
            error={
                "code": "pipeline_failed",
                "message": "The analysis pipeline failed. Verify provider, model, endpoint, and credential settings.",
            },
        )
    finally:
        _RUN_SLOTS.release()


class GTFlowHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def resolve_static_path(requested: str) -> Optional[Path]:
    """Resolve a URL asset path without allowing POSIX or Windows escapes."""

    if not isinstance(requested, str) or not requested or "\x00" in requested:
        return None

    # Decode repeatedly so double-encoded traversal is not reinterpreted by a
    # downstream layer. Three rounds are enough to reject rather than normalize.
    decoded = requested
    for _ in range(3):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    if "\x00" in decoded:
        return None

    windows_path = PureWindowsPath(decoded)
    posix_path = PurePosixPath(decoded.replace("\\", "/"))
    if windows_path.is_absolute() or windows_path.drive or posix_path.is_absolute():
        return None

    parts = posix_path.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None

    base = STATIC_DIR.resolve()
    try:
        candidate = base.joinpath(*parts).resolve()
        candidate.relative_to(base)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _server_csrf_token(server: Any) -> str:
    token = getattr(server, "gtflow_csrf_token", None)
    if isinstance(token, str) and token:
        return token
    with _CSRF_LOCK:
        token = getattr(server, "gtflow_csrf_token", None)
        if not isinstance(token, str) or not token:
            token = secrets.token_urlsafe(32)
            setattr(server, "gtflow_csrf_token", token)
    return token


def run_server(host: str = "127.0.0.1", port: int = 8501) -> None:
    server = GTFlowHTTPServer((host, port), GTFlowHandler)
    _server_csrf_token(server)
    print(f"GTFlow UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class GTFlowHandler(BaseHTTPRequestHandler):
    server_version = "GTFlowUI/0.5"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(20)

    def version_string(self) -> str:
        return self.server_version

    def do_GET(self) -> None:
        path = self._request_path()
        if path in ("/", "/index.html"):
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            requested = path[len("/static/") :]
            self._serve_static(requested)
            return
        if path == "/api/default-config":
            conf = default_config()
            data = conf.model_dump(mode="python")
            data["provider"]["api_key"] = None
            self._send_json(data, extra_headers={CSRF_HEADER: _server_csrf_token(self.server)})
            return
        job_match = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]{24,64})(/bundle)?", path)
        if job_match:
            try:
                if job_match.group(2):
                    self._handle_job_bundle(job_match.group(1))
                else:
                    self._handle_job_status(job_match.group(1))
            except APIError as exc:
                self._send_error(exc.status, exc.code, exc.message)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not_found", "The requested resource was not found.")

    def do_POST(self) -> None:
        path = self._request_path()
        handlers = {
            "/api/preview": self._handle_preview,
            "/api/readiness": self._handle_readiness,
            "/api/run": self._handle_run,
            "/api/jobs": self._handle_create_job,
            "/api/align-codebook": self._handle_align_codebook,
        }
        handler = handlers.get(path)
        if handler is None:
            self.close_connection = True
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "The requested endpoint was not found.")
            return

        try:
            # Size/type checks intentionally run first so an oversized request is
            # rejected without reading its body, even when other headers are bad.
            payload = self._read_json()
            self._require_same_origin()
            self._require_csrf()
            handler(payload)
        except APIError as exc:
            self._send_error(exc.status, exc.code, exc.message)
        except ValidationError as exc:
            details = [
                {"field": ".".join(str(part) for part in error.get("loc", ())), "type": error.get("type", "invalid")}
                for error in exc.errors(include_url=False, include_input=False)
            ]
            self._send_error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "validation_error",
                "One or more request fields are invalid.",
                details=details[:32],
            )
        except (BrokenPipeError, ConnectionError, TimeoutError):
            self.close_connection = True
        except Exception as exc:
            if os.getenv("GTFLOW_UI_DEBUG"):
                self.log_error("Unhandled %s", type(exc).__name__)
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                "The server could not complete the request.",
            )

    def do_OPTIONS(self) -> None:
        self._method_not_allowed()

    def do_PUT(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        path = self._request_path()
        match = re.fullmatch(r"/api/jobs/([A-Za-z0-9_-]{24,64})", path)
        if match is None:
            self._method_not_allowed()
            return
        try:
            self._require_empty_body()
            self._require_same_origin()
            self._require_csrf()
            self._handle_cancel_job(match.group(1))
        except APIError as exc:
            self._send_error(exc.status, exc.code, exc.message)

    def do_TRACE(self) -> None:
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        self.close_connection = True
        self._send_error(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "method_not_allowed",
            "This HTTP method is not supported.",
            extra_headers={"Allow": "GET, POST, DELETE"},
        )

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("GTFLOW_UI_DEBUG"):
            message = format % args
            # Avoid logging query-string credentials or bearer-like values.
            message = re.sub(r"(?i)(api[_-]?key|token|secret|authorization)=([^&\s]+)", r"\1=[redacted]", message)
            super().log_message("%s", message[:2048])

    def _request_path(self) -> str:
        try:
            return unquote(urlsplit(self.path).path)
        except (UnicodeError, ValueError):
            return ""

    def _handle_preview(self, payload: Dict[str, Any]) -> None:
        conf = build_config(payload)
        text, source_name = self._source_input(payload)
        try:
            segments = self._bounded_segments(text, source_name, conf) if text else []
        except ValueError as exc:
            raise APIError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_source", _safe_source_error(exc)) from exc
        self._send_json(
            {
                "segments": [segment.model_dump() for segment in segments[:80]],
                "stats": {
                    "segments": len(segments),
                    "characters": len(text),
                    "avg_chars": round(len(text) / max(1, len(segments))),
                },
                "readiness": readiness_state(
                    conf,
                    text,
                    source_name,
                    credential_configured=bool(payload.get("credential_configured")),
                ),
            }
        )

    def _handle_readiness(self, payload: Dict[str, Any]) -> None:
        conf = build_config(payload)
        text, source_name = self._source_input(payload)
        if text:
            try:
                self._bounded_segments(text, source_name, conf)
            except ValueError as exc:
                raise APIError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_source", _safe_source_error(exc)) from exc
        self._send_json(readiness_state(conf, text, source_name))

    def _handle_create_job(self, payload: Dict[str, Any]) -> None:
        conf = build_config(payload)
        text, source_name = self._source_input(payload)
        try:
            self._bounded_segments(text, source_name, conf)
        except ValueError as exc:
            raise APIError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_source", _safe_source_error(exc)) from exc

        ready = readiness_state(conf, text, source_name)
        if not ready["ready"]:
            raise APIError(
                HTTPStatus.BAD_REQUEST,
                "not_ready",
                "Input text or provider settings are incomplete.",
            )

        _cleanup_jobs(self.server)
        jobs, lock = _job_store(self.server)
        with lock:
            if len(jobs) >= MAX_RETAINED_JOBS:
                raise APIError(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    "job_capacity",
                    "Too many analysis jobs are retained. Download completed work and try again later.",
                )
        if not _RUN_SLOTS.acquire(blocking=False):
            raise APIError(
                HTTPStatus.TOO_MANY_REQUESTS,
                "run_busy",
                "Another analysis run is already in progress.",
            )

        export_conf = conf.model_copy(deep=True)
        export_conf.provider = export_conf.provider.model_copy(update={"api_key": None, "extra_headers": {}})
        job = RunJob(job_id=secrets.token_urlsafe(24), export_config=export_conf)
        with lock:
            jobs[job.job_id] = job
        worker = threading.Thread(
            target=_run_background_job,
            args=(self.server, job, conf, text, source_name),
            daemon=True,
            name=f"gtflow-job-{job.job_id[:8]}",
        )
        try:
            worker.start()
        except Exception:
            with lock:
                jobs.pop(job.job_id, None)
            _RUN_SLOTS.release()
            raise APIError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "job_start_failed",
                "The analysis job could not be started.",
            )
        self._send_json(
            job.public(),
            status=HTTPStatus.ACCEPTED,
            extra_headers={"Location": f"/api/jobs/{job.job_id}"},
        )

    def _handle_job_status(self, job_id: str) -> None:
        _cleanup_jobs(self.server)
        job = _get_job(self.server, job_id)
        _, lock = _job_store(self.server)
        with lock:
            payload = job.public()
        self._send_json(payload)

    def _handle_job_bundle(self, job_id: str) -> None:
        job = _get_job(self.server, job_id)
        _, lock = _job_store(self.server)
        with lock:
            status = job.status
            bundle = job.bundle
        if status != "succeeded" or bundle is None:
            raise APIError(
                HTTPStatus.CONFLICT,
                "bundle_not_ready",
                "The analysis bundle is not ready for download.",
            )
        self._send_bytes(
            bundle,
            "application/zip",
            extra_headers={"Content-Disposition": 'attachment; filename="gtflow_output.zip"'},
        )

    def _handle_cancel_job(self, job_id: str) -> None:
        job = _get_job(self.server, job_id)
        _, lock = _job_store(self.server)
        with lock:
            if job.status not in ("queued", "running", "cancelling"):
                raise APIError(
                    HTTPStatus.CONFLICT,
                    "job_not_cancellable",
                    "The analysis job is no longer cancellable.",
                )
            job.cancel_event.set()
            job.status = "cancelling"
            job.stage = "cancelling"
            job.message = "Cancellation requested"
            job.updated_at = time.time()
            payload = job.public()
        self._send_json(payload, status=HTTPStatus.ACCEPTED)

    def _handle_run(self, payload: Dict[str, Any]) -> None:
        conf = build_config(payload)
        text, source_name = self._source_input(payload)
        try:
            self._bounded_segments(text, source_name, conf)
        except ValueError as exc:
            raise APIError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_source", _safe_source_error(exc)) from exc

        ready = readiness_state(conf, text, source_name)
        if not ready["ready"]:
            raise APIError(
                HTTPStatus.BAD_REQUEST,
                "not_ready",
                "Input text or provider settings are incomplete.",
            )

        if not _RUN_SLOTS.acquire(blocking=False):
            raise APIError(
                HTTPStatus.TOO_MANY_REQUESTS,
                "run_busy",
                "Another analysis run is already in progress.",
            )
        try:
            try:
                artifacts = run_pipeline(conf, text, source_name=source_name)
                bundle = output_bundle(conf, artifacts)
            except Exception as exc:
                raise APIError(
                    HTTPStatus.BAD_GATEWAY,
                    "pipeline_failed",
                    "The analysis pipeline failed. Verify provider, model, endpoint, and credential settings.",
                ) from exc
        finally:
            _RUN_SLOTS.release()
        self._send_json(artifacts_response(artifacts, bundle))

    def _handle_align_codebook(self, payload: Dict[str, Any]) -> None:
        raw_codebook = payload.get("codebook")
        rows = payload.get("rows")
        job_id = payload.get("job_id")
        if not isinstance(raw_codebook, dict) or not isinstance(rows, list):
            raise APIError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_alignment",
                "codebook must be an object and rows must be an array.",
            )
        entries = raw_codebook.get("entries", [])
        if not isinstance(entries, list) or len(entries) > MAX_CODEBOOK_ENTRIES or len(rows) > MAX_ALIGN_ROWS:
            raise APIError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "alignment_too_large",
                "The alignment request exceeds the allowed row count.",
            )
        if job_id is not None and not isinstance(job_id, str):
            raise APIError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_alignment",
                "job_id must be a string when provided.",
            )
        if not job_id:
            codebook = Codebook.model_validate(raw_codebook)
            edited = apply_gioia_alignment_edits(codebook, rows)
            self._send_json(edited.model_dump())
            return

        job = _get_job(self.server, job_id)
        with job.edit_lock:
            _, lock = _job_store(self.server)
            with lock:
                if job.status != "succeeded" or job.artifacts is None:
                    raise APIError(
                        HTTPStatus.CONFLICT,
                        "job_not_editable",
                        "Only a completed analysis job can be edited.",
                    )
                artifacts = job.artifacts
            edited = apply_gioia_alignment_edits(artifacts.codebook, rows)
            updated_artifacts = rebuild_artifacts_with_codebook(artifacts, edited)
            bundle = output_bundle(job.export_config or default_config(), updated_artifacts)
            result = artifacts_response(updated_artifacts)
            with lock:
                job.artifacts = updated_artifacts
                job.bundle = bundle
                job.result = result
                job.revision += 1
                job.updated_at = time.time()
        self._send_json(
            {
                "codebook": edited.model_dump(),
                "result": result,
                "download_url": f"/api/jobs/{job.job_id}/bundle",
            }
        )

    def _source_input(self, payload: Dict[str, Any]) -> Tuple[str, str]:
        text = payload.get("text", "")
        source_name = payload.get("source_name", "")
        if not isinstance(text, str) or not isinstance(source_name, str):
            raise APIError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_source",
                "text and source_name must be strings.",
            )
        if len(text) > MAX_INPUT_CHARS:
            raise APIError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "input_too_large",
                f"Input text must not exceed {MAX_INPUT_CHARS} characters.",
            )
        if len(source_name) > 1024 or any(ord(char) < 32 for char in source_name):
            raise APIError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_source_name",
                "source_name is invalid.",
            )
        return text, source_name

    def _bounded_segments(self, text: str, source_name: str, conf: Any) -> list[Any]:
        segments = source_segments(
            text,
            source_name,
            conf.run.segmentation_strategy,
            conf.run.max_segment_chars,
        )
        if len(segments) > MAX_SOURCE_SEGMENTS:
            raise APIError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "too_many_segments",
                f"The source must produce at most {MAX_SOURCE_SEGMENTS} segments.",
            )
        return segments

    def _serve_static(self, requested: str) -> None:
        path = resolve_static_path(requested)
        if path is None:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_path", "The static asset path is invalid.")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type += "; charset=utf-8"
        self._serve_file(path, content_type)

    def _serve_file(self, path: Path, content_type: str) -> None:
        try:
            if not path.exists() or not path.is_file():
                raise FileNotFoundError
            data = path.read_bytes()
        except (FileNotFoundError, OSError):
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "The requested resource was not found.")
            return
        self.send_response(HTTPStatus.OK)
        self._send_security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _require_empty_body(self) -> None:
        if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Encoding"):
            self.close_connection = True
            raise APIError(HTTPStatus.BAD_REQUEST, "unexpected_body", "This request must not include a body.")
        raw_length = self.headers.get("Content-Length")
        if raw_length in (None, "", "0"):
            return
        try:
            length = int(raw_length, 10)
        except ValueError as exc:
            self.close_connection = True
            raise APIError(HTTPStatus.BAD_REQUEST, "invalid_content_length", "Content-Length is invalid.") from exc
        if length != 0:
            self.close_connection = True
            raise APIError(HTTPStatus.BAD_REQUEST, "unexpected_body", "This request must not include a body.")

    def _read_json(self) -> Dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json" and not content_type.endswith("+json"):
            self.close_connection = True
            raise APIError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "unsupported_media_type",
                "Content-Type must be application/json.",
            )
        if self.headers.get("Content-Encoding"):
            self.close_connection = True
            raise APIError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "unsupported_content_encoding",
                "Compressed request bodies are not supported.",
            )
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            raise APIError(
                HTTPStatus.LENGTH_REQUIRED,
                "content_length_required",
                "A valid Content-Length header is required.",
            )
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self.close_connection = True
            raise APIError(
                HTTPStatus.LENGTH_REQUIRED,
                "content_length_required",
                "A valid Content-Length header is required.",
            )
        try:
            length = int(raw_length, 10)
        except ValueError as exc:
            self.close_connection = True
            raise APIError(HTTPStatus.BAD_REQUEST, "invalid_content_length", "Content-Length is invalid.") from exc
        if length < 0:
            self.close_connection = True
            raise APIError(HTTPStatus.BAD_REQUEST, "invalid_content_length", "Content-Length is invalid.")
        if length > MAX_REQUEST_BYTES:
            self.close_connection = True
            raise APIError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "request_too_large",
                f"JSON requests must not exceed {MAX_REQUEST_BYTES} bytes.",
            )
        raw = self.rfile.read(length)
        if len(raw) != length:
            self.close_connection = True
            raise APIError(HTTPStatus.BAD_REQUEST, "incomplete_body", "The request body was incomplete.")
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise APIError(HTTPStatus.BAD_REQUEST, "invalid_json", "The request body is not valid UTF-8 JSON.") from exc
        if not isinstance(data, dict):
            raise APIError(HTTPStatus.BAD_REQUEST, "invalid_json_type", "JSON body must be an object.")
        _validate_json_complexity(data)
        return data

    def _require_same_origin(self) -> None:
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if not origin or not host or not _origin_matches_host(origin, host):
            raise APIError(
                HTTPStatus.FORBIDDEN,
                "origin_rejected",
                "POST requests must come from this GTFlow origin.",
            )
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site and fetch_site.lower() not in ("same-origin", "none"):
            raise APIError(HTTPStatus.FORBIDDEN, "origin_rejected", "Cross-site requests are not allowed.")

    def _require_csrf(self) -> None:
        supplied = self.headers.get(CSRF_HEADER, "")
        expected = _server_csrf_token(self.server)
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise APIError(
                HTTPStatus.FORBIDDEN,
                "csrf_rejected",
                "The CSRF token is missing or invalid. Reload the GTFlow page and try again.",
            )

    def _send_json(
        self,
        payload: Any,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._send_security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if self.close_connection:
            self.send_header("Connection", "close")
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        *,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.send_response(status)
        self._send_security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_error(
        self,
        status: HTTPStatus,
        code: str,
        message: str,
        *,
        details: Optional[list[Dict[str, Any]]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        error: Dict[str, Any] = {"code": code, "message": message}
        if details:
            error["details"] = details
        self._send_json({"error": error}, status=status, extra_headers=extra_headers)

    def _send_security_headers(self) -> None:
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; connect-src 'self'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")


def _safe_source_error(exc: ValueError) -> str:
    message = str(exc)
    if re.fullmatch(r"Invalid (JSONL at line \d+: [A-Za-z0-9 _.,:'\"-]+|CSV input: [A-Za-z0-9 _.,:'\"-]+)", message):
        return message[:300]
    return "The source data could not be parsed."


def _validate_json_complexity(value: Any) -> None:
    stack = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise APIError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "json_too_complex",
                "The JSON request is too deeply nested or contains too many values.",
            )
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def _origin_matches_host(origin: str, host: str) -> bool:
    try:
        parsed_origin = urlsplit(origin)
        parsed_host = urlsplit(f"//{host}")
        if (
            parsed_origin.scheme.lower() != "http"
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path not in ("", "/")
            or parsed_origin.query
            or parsed_origin.fragment
            or not parsed_origin.hostname
            or not parsed_host.hostname
        ):
            return False
        origin_port = parsed_origin.port or 80
        host_port = parsed_host.port or 80
        origin_name = parsed_origin.hostname.lower().rstrip(".")
        host_name = parsed_host.hostname.lower().rstrip(".")
        return origin_name == host_name and origin_port == host_port
    except (TypeError, ValueError):
        return False


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
