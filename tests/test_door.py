"""The front door on port 80: each name reaches its own control panel."""
import http.client
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from door import make_handler, target_port  # noqa: E402


def panel(name):
    class P(BaseHTTPRequestHandler):
        def do_GET(self):
            body = ("%s %s" % (name, self.path)).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers["Content-Length"])
            got = self.rfile.read(n)
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("X-Got", got.decode())
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):
            pass
    return P


def serve(handler):
    s = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def ask(port, host, method="GET", path="/", body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    c.request(method, path, body=body, headers=headers)
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read().decode()


def test_names_choose_the_panel():
    assert target_port("equalize.local", 8080, 8081) == 8080
    assert target_port("Equalize.local:80", 8080, 8081) == 8080
    assert target_port("spotipi.local", 8080, 8081) == 8081
    assert target_port("192.168.1.241", 8080, 8081) == 8081      # typed the address
    assert target_port(None, 8080, 8081) == 8081


def test_visits_and_saves_pass_through():
    eq, sp = serve(panel("equalize")), serve(panel("spotipi"))
    door = serve(make_handler(eq.server_address[1], sp.server_address[1]))
    port = door.server_address[1]
    assert ask(port, "equalize.local", path="/status")[2] == "equalize /status"
    assert ask(port, "spotipi.local")[2] == "spotipi /"
    status, headers, _ = ask(port, "equalize.local", "POST", "/mode", "mode=on")
    assert status == 302 and headers["Location"] == "/" and headers["X-Got"] == "mode=on"


def test_a_panel_that_is_down_gets_a_plain_message():
    eq = serve(panel("equalize"))
    dead = serve(panel("x"))
    dead_port = dead.server_address[1]
    dead.shutdown()
    dead.server_close()
    door = serve(make_handler(eq.server_address[1], dead_port))
    status, _, body = ask(door.server_address[1], "spotipi.local")
    assert status == 502 and "isn't answering" in body
