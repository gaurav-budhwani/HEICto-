#!/usr/bin/env python3
"""
app.py - Production-ready, cloud-deployable web server for Apple HEIC & image conversion.

Runs natively on macOS with zero dependencies, and deploys effortlessly to Linux/Docker/Cloud
(Render, Railway, Fly.io, Google Cloud Run, Heroku, VPS).
"""

import io
import json
import mimetypes
import os
import shutil
import socket
import sys
import tempfile
import time
import urllib.parse
import uuid
import zipfile
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any, Optional

import converter

DEFAULT_PORT = 5173
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "heic_converter_cache")

os.makedirs(CACHE_DIR, exist_ok=True)

# In-memory store of completed jobs
JOBS: Dict[str, Dict[str, Any]] = {}


def clean_old_cache(max_age_seconds: int = 3600):
    """Remove cache files older than 1 hour to keep storage tidy."""
    now = time.time()
    try:
        for fname in os.listdir(CACHE_DIR):
            fpath = os.path.join(CACHE_DIR, fname)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age_seconds:
                try:
                    os.remove(fpath)
                except OSError:
                    pass
    except Exception:
        pass


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for concurrent uploads and downloads."""
    daemon_threads = True
    allow_reuse_address = True


class ConverterRequestHandler(SimpleHTTPRequestHandler):
    """Handles static files, API endpoints, and downloads."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {args[0]} - {args[1]}\n")
        sys.stdout.flush()

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, Authorization")
        self.end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        # Health checks for cloud platforms (Render, Railway, Kubernetes, etc.)
        if path in ("/health", "/api/health"):
            self.send_json({"status": "healthy", "uptime": time.time()})
            return

        if path == "/api/system":
            self.send_json(converter.check_system_support())
            return

        if path.startswith("/api/thumbnail/"):
            job_id = path[len("/api/thumbnail/"):]
            job = JOBS.get(job_id)
            if job and os.path.exists(job.get("thumb_path", "")):
                self.serve_file(job["thumb_path"], "image/jpeg")
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Thumbnail not found")
            return

        if path.startswith("/api/download/"):
            job_id = path[len("/api/download/"):]
            job = JOBS.get(job_id)
            if job and os.path.exists(job.get("converted_path", "")):
                filename = job.get("download_filename", "converted_image")
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                self.serve_file(job["converted_path"], content_type, download_filename=filename)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found or expired")
            return

        if path in ("/", "/index.html"):
            self.serve_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
            return

        super().do_GET()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path == "/api/convert":
            self.handle_convert()
            return

        if path == "/api/download-zip":
            self.handle_download_zip()
            return

        if path == "/api/clear":
            self.handle_clear()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def handle_convert(self):
        """Convert single image upload."""
        try:
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data"):
                self.send_json({"error": "Expected multipart/form-data"}, status=400)
                return

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_json({"error": "Empty upload body"}, status=400)
                return

            body = self.rfile.read(content_length)
            parsed = self.parse_multipart(body, content_type)

            files = parsed.get("files", [])
            params = parsed.get("params", {})

            if not files:
                self.send_json({"error": "No file uploaded"}, status=400)
                return

            uploaded_file = files[0]
            original_filename = uploaded_file.get("filename", "image.heic")
            file_data = uploaded_file.get("data", b"")

            target_format = params.get("format", "png").lower().strip()
            quality = int(params.get("quality", "100"))
            color_profile = params.get("color_profile", "srgb").lower().strip()
            max_dimension = int(params.get("max_dimension", "0"))

            ext_map = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "webp": ".webp", "tiff": ".tiff", "bmp": ".bmp", "pdf": ".pdf"}
            target_ext = ext_map.get(target_format, f".{target_format}")

            base_name, _ = os.path.splitext(original_filename)
            converted_filename = f"{base_name}{target_ext}"

            job_id = str(uuid.uuid4())
            original_ext = os.path.splitext(original_filename)[1] or ".heic"
            orig_path = os.path.join(CACHE_DIR, f"{job_id}_orig{original_ext}")
            conv_path = os.path.join(CACHE_DIR, f"{job_id}_conv{target_ext}")
            thumb_path = os.path.join(CACHE_DIR, f"{job_id}_thumb.jpg")

            with open(orig_path, "wb") as f:
                f.write(file_data)

            orig_info = converter.get_image_info(orig_path)

            t0 = time.time()
            conv_result = converter.convert_image(
                input_path=orig_path,
                output_path=conv_path,
                target_format=target_format,
                quality=quality,
                color_profile=color_profile,
                max_dimension=max_dimension,
            )
            duration_ms = int((time.time() - t0) * 1000)

            converter.generate_thumbnail(conv_path, thumb_path, max_size=360)
            conv_info = conv_result.get("info", {})

            JOBS[job_id] = {
                "id": job_id,
                "original_filename": original_filename,
                "download_filename": converted_filename,
                "original_path": orig_path,
                "converted_path": conv_path,
                "thumb_path": thumb_path,
                "orig_info": orig_info,
                "conv_info": conv_info,
                "created_at": time.time(),
            }

            self.send_json({
                "success": True,
                "job_id": job_id,
                "original_filename": original_filename,
                "converted_filename": converted_filename,
                "original_info": orig_info,
                "converted_info": conv_info,
                "duration_ms": duration_ms,
                "color_profile_used": color_profile,
                "download_url": f"/api/download/{job_id}",
                "thumbnail_url": f"/api/thumbnail/{job_id}",
            })

        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_download_zip(self):
        """Batch export to ZIP archive."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            job_ids = data.get("job_ids", [])

            if not job_ids:
                self.send_json({"error": "No files selected"}, status=400)
                return

            zip_buffer = io.BytesIO()
            used_names = set()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for jid in job_ids:
                    job = JOBS.get(jid)
                    if job and os.path.exists(job.get("converted_path", "")):
                        fname = job["download_filename"]
                        base, ext = os.path.splitext(fname)
                        counter = 1
                        while fname in used_names:
                            fname = f"{base}_{counter}{ext}"
                            counter += 1
                        used_names.add(fname)
                        zip_file.write(job["converted_path"], arcname=fname)

            zip_data = zip_buffer.getvalue()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="converted_images.zip"')
            self.send_header("Content-Length", str(len(zip_data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(zip_data)

        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_clear(self):
        """Purge jobs and temporary conversion cache."""
        count = len(JOBS)
        for job in JOBS.values():
            for key in ["original_path", "converted_path", "thumb_path"]:
                p = job.get(key)
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        JOBS.clear()
        self.send_json({"success": True, "cleared_count": count})

    def serve_file(self, file_path: str, content_type: str, download_filename: Optional[str] = None):
        if not os.path.exists(file_path):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        file_size = os.path.getsize(file_path)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        if download_filename:
            safe_fname = urllib.parse.quote(download_filename)
            self.send_header("Content-Disposition", f'attachment; filename="{download_filename}"; filename*=UTF-8\'\'{safe_fname}')
        self.end_headers()

        with open(file_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def send_json(self, data: Any, status: int = 200):
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def parse_multipart(body: bytes, content_type: str) -> Dict[str, Any]:
        boundary = None
        for item in content_type.split(";"):
            item = item.strip()
            if item.startswith("boundary="):
                boundary = item[len("boundary="):].strip('"').encode("latin-1")
                break

        if not boundary:
            raise ValueError("No multipart boundary specified")

        parts = body.split(b"--" + boundary)
        result = {"files": [], "params": {}}

        for part in parts:
            if not part or part == b"--\r\n" or part == b"--" or part == b"\r\n":
                continue
            if b"\r\n\r\n" not in part:
                continue

            header_bytes, payload = part.split(b"\r\n\r\n", 1)
            if payload.endswith(b"\r\n"):
                payload = payload[:-2]

            headers = {}
            for line in header_bytes.split(b"\r\n"):
                if b":" in line:
                    k, v = line.split(b":", 1)
                    headers[k.decode("latin-1").strip().lower()] = v.decode("latin-1").strip()

            disp = headers.get("content-disposition", "")
            name, filename = None, None
            for item in disp.split(";"):
                item = item.strip()
                if item.startswith("name="):
                    name = item[5:].strip('"')
                elif item.startswith("filename="):
                    filename = item[9:].strip('"')

            if filename is not None and filename != "":
                result["files"].append({
                    "name": name,
                    "filename": filename,
                    "content_type": headers.get("content-type", "application/octet-stream"),
                    "data": payload,
                })
            elif name:
                result["params"][name] = payload.decode("utf-8", errors="replace")

        return result


def find_free_port(start_port: int = DEFAULT_PORT) -> int:
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return port
            except OSError:
                port += 1
    return start_port


def run_server(port: Optional[int] = None):
    clean_old_cache()
    # Support cloud environment variables (PORT, HOST)
    env_port = os.environ.get("PORT")
    env_host = os.environ.get("HOST", "0.0.0.0")

    actual_port = int(env_port) if env_port else (port if port else find_free_port(DEFAULT_PORT))
    server_address = (env_host, actual_port)
    httpd = ThreadedHTTPServer(server_address, ConverterRequestHandler)

    print("=" * 64)
    print("  🍎 HEICto- — Professional Image Converter")
    print(f"  ⚡ Listening on: http://{env_host}:{actual_port}")
    support = converter.check_system_support()
    print(f"  🎨 Engine: {support['engine']}")
    print("=" * 64)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    run_server(port_arg)
