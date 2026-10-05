#!/usr/bin/env python3
"""
door.py -- the front door on port 80, when Equalize and Spotipi Photo share a Pi.

A Pi has one address, and a web address normally means port 80, so only one
program can answer http://<name>.local. This one answers, looks at which
name was typed, and passes the visit on:

    http://equalize.local   ->  Equalize's control panel   (127.0.0.1:8080)
    http://spotipi.local    ->  Spotipi Photo's            (127.0.0.1:8081)
    anything else           ->  Spotipi Photo's

Nothing is changed on the way through. The Pi answers to equalize.local
because equalize-name.sh announces that second name on the network.

    python3 door.py [--port 80] [--equalize 8080] [--spotipi 8081]

Standard library only.
"""

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailers", "transfer-encoding", "upgrade"}


def target_port(host_header, equalize_port, spotipi_port):
    """Which panel a visit is for, from the name in the address bar."""
    name = (host_header or "").split(":")[0].strip().lower()
    return equalize_port if name.split(".")[0] == "equalize" else spotipi_port


def make_handler(equalize_port, spotipi_port):
    class Door(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _pass_on(self):
            port = target_port(self.headers.get("Host"), equalize_port, spotipi_port)
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
                conn.request(self.command, self.path, body=body, headers=headers)
                resp = conn.getresponse()
                data = resp.read()
            except OSError:
                msg = ("That control panel isn't answering just now (port %d). "
                       "It may still be starting: try again in a moment.\n" % port).encode()
                self.send_response(502)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() not in HOP_BY_HOP and k.lower() != "content-length":
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
            conn.close()

        do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = _pass_on

        def log_message(self, *args):          # quiet: two pages poll every second
            pass

    return Door


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--equalize", type=int, default=8080)
    ap.add_argument("--spotipi", type=int, default=8081)
    a = ap.parse_args()
    ThreadingHTTPServer(("0.0.0.0", a.port), make_handler(a.equalize, a.spotipi)).serve_forever()


if __name__ == "__main__":
    main()
