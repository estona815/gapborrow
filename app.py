"""Loopback-only research prototype. No packages, persistence or external calls."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from engine import RESEARCH, calculate

WEB = Path(__file__).with_name("web")
FILES = {"/": (WEB/"index.html", "text/html; charset=utf-8"),
         "/style.css": (WEB/"style.css", "text/css; charset=utf-8"),
         "/app.js": (WEB/"app.js", "text/javascript; charset=utf-8"),
         "/cases.json": (RESEARCH/"cases.json", "application/json; charset=utf-8")}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log inputs or user data.

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        host = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == host and self.headers.get("Origin") in (None, "http://"+host)

    def do_GET(self):
        if not self.allowed():
            return self.reply(403, {"error": "다른 출처의 요청은 허용하지 않습니다."})
        path = urlsplit(self.path).path
        if path == "/favicon.ico":
            return self.reply(204, b"", "image/x-icon")
        if path not in FILES:
            return self.reply(404, {"error": "Not found"})
        file, mime = FILES[path]
        return self.reply(200, file.read_bytes(), mime)

    def do_POST(self):
        if not self.allowed():
            return self.reply(403, {"error": "다른 출처의 요청은 허용하지 않습니다."})
        if urlsplit(self.path).path != "/calculate":
            return self.reply(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.reply(400, {"error": "입력 길이를 확인하세요."})
        if length <= 0 or length > 24000:
            return self.reply(413, {"error": "입력 크기를 확인하세요."})
        if self.headers.get_content_type() != "application/json":
            return self.reply(415, {"error": "JSON 입력이 필요합니다."})
        try:
            payload = json.loads(self.rfile.read(length))
            result = calculate(payload)
        except (ValueError, UnicodeDecodeError) as exc:
            return self.reply(400, {"error": str(exc)})
        return self.reply(200, result)


def make_server(port=0):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
