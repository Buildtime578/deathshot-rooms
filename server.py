"""Deathshot room list server.

Hosts that opt in POST their room here every ~10 seconds; the in-game browser GETs the list.
Rooms that stop sending heartbeats disappear after TTL seconds. Nothing is stored on disk.

    GET  /ping          wake-up / health check (the game calls this when it launches)
    GET  /rooms         JSON list of live rooms
    POST /rooms         create or refresh a room (JSON body, see validate())
    POST /rooms/close   remove a room: {"r": "<room id>"}

The host's public IP is taken from the request, so hosts never have to type it in.
Only the standard library is used, so there is nothing to install.
"""
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TTL = 30          # seconds without a heartbeat before a room is dropped
MAX_ROOMS = 100
MAX_PER_IP = 3

rooms = {}        # room id -> room dict
lock = threading.Lock()


def now():
    return time.time()


def prune():
    cutoff = now() - TTL
    for rid in [r for r, v in rooms.items() if v["seen"] < cutoff]:
        del rooms[rid]


def validate(d):
    """Returns a clean room dict or None."""
    try:
        if d.get("g") != "deathshot":
            return None
        rid = str(d["r"])
        if not re.fullmatch(r"[0-9a-zA-Z]{4,32}", rid):
            return None
        port = int(d["p"])
        if not 1024 <= port <= 65535:
            return None
        return {
            "rid": rid,
            "name": str(d.get("n", "Player"))[:24],
            "port": port,
            "players": max(1, min(int(d.get("c", 1)), 8)),
            "max": max(1, min(int(d.get("m", 4)), 8)),
            "diff": max(0, min(int(d.get("d", 1)), 4)),
            "in_game": bool(d.get("s", False)),
        }
    except (KeyError, ValueError, TypeError):
        return None


class Handler(BaseHTTPRequestHandler):
    def client_ip(self):
        for h in ("CF-Connecting-IP", "X-Forwarded-For"):
            v = self.headers.get(h)
            if v:
                return v.split(",")[0].strip()
        return self.client_address[0]

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > 2048:
                return None
            return json.loads(self.rfile.read(n))
        except (ValueError, TypeError):
            return None

    def do_GET(self):
        if self.path == "/ping" or self.path == "/":
            self.send(200, "ok", "text/plain")
        elif self.path == "/rooms":
            with lock:
                prune()
                out = [{"r": v["rid"], "n": v["name"], "ip": v["ip"], "p": v["port"], "c": v["players"],
                        "m": v["max"], "d": v["diff"], "s": v["in_game"]} for v in rooms.values()]
            self.send(200, json.dumps(out))
        else:
            self.send(404, "not found", "text/plain")

    def do_POST(self):
        d = self.read_json()
        if not isinstance(d, dict):
            return self.send(400, '{"ok":false}')
        ip = self.client_ip()
        if self.path == "/rooms":
            room = validate(d)
            if room is None:
                return self.send(400, '{"ok":false}')
            room["ip"] = ip
            room["seen"] = now()
            with lock:
                prune()
                mine = [r for r in rooms.values() if r["ip"] == ip and r["rid"] != room["rid"]]
                if len(mine) >= MAX_PER_IP or (room["rid"] not in rooms and len(rooms) >= MAX_ROOMS):
                    return self.send(429, '{"ok":false}')
                rooms[room["rid"]] = room
            self.send(200, '{"ok":true}')
        elif self.path == "/rooms/close":
            with lock:
                r = rooms.get(str(d.get("r", "")))
                if r and r["ip"] == ip:
                    del rooms[r["rid"]]
            self.send(200, '{"ok":true}')
        else:
            self.send(404, "not found", "text/plain")

    def log_message(self, fmt, *args):
        print("%s %s" % (self.client_ip(), fmt % args), flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print("Deathshot room server on port %d" % port, flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
