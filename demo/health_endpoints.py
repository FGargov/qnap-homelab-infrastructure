import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


FAILURE_FLAG = Path("/tmp/qnap-demo-unhealthy")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        unhealthy = FAILURE_FLAG.exists()
        if self.path == "/status.php":
            content_type = "application/json"
            body = json.dumps({
                "installed": True,
                "maintenance": unhealthy,
                "needsDbUpgrade": False,
            }).encode()
        elif self.path == "/healthcheck":
            content_type = "text/plain"
            body = b"false" if unhealthy else b"true"
        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    with ThreadingHTTPServer(("0.0.0.0", 8080), HealthHandler) as server:
        server.serve_forever()
