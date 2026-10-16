"""A local SponsorBlock stand-in, shared by the SponsorBlock and command tests."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest


class SponsorBlockServer:
    """A local SponsorBlock stand-in answering every request with a fixed status and body."""

    def __init__(self) -> None:
        self.status = 200
        self.body = b"[]"
        self.paths: list[str] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                server.paths.append(self.path)
                self.send_response(server.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(server.body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"


@pytest.fixture
def server() -> Iterator[SponsorBlockServer]:
    stand_in = SponsorBlockServer()
    thread = threading.Thread(target=stand_in.httpd.serve_forever, daemon=True)
    thread.start()
    yield stand_in
    stand_in.httpd.shutdown()
    stand_in.httpd.server_close()
