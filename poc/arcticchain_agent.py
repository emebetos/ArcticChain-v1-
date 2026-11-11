#!/usr/bin/env python3
"""ArcticChain Level-1 agent — runs on Raspberry Pi CM5.

Bridges the four radios/services into one offline-first node:
  - 4G/LTE HAT   : voice/SMS/data when towers exist (via AT commands or QMI)
  - SX1262 LoRa  : community mesh (store-and-forward, signed envelopes)
  - E-Ink HAT    : status + message display
  - local HTTP   : app API on :8080 for the UI / governance tools

Design rules (from docs/):
  - Zero telemetry off-device; nothing phones home.
  - Works fully offline: mesh + display + storage need no internet.
  - Every mesh frame is Ed25519-signed (arcticchain_hal::auth format).

Level-1 scope: Python service, real LoRa via spidev, real HTTP API,
message store in SQLite. AI translation / governance tools are separate
services that talk to this one over localhost.
"""

import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DB_PATH = Path("/var/lib/arcticchain/messages.db")
LORA_SPI_DEVICE = "/dev/spidev1.0"   # second SPI bus (config.txt: dtoverlay=spi1-3cs)
LORA_FREQ_HZ = 915_000_000           # Canada ISM band (RSS-210 unlicensed)
HTTP_PORT = 8080

# ---------------------------------------------------------------- storage

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "ts REAL, from_node TEXT, to_node TEXT, text TEXT, rssi INTEGER, delivered INTEGER DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS health ("
        "ts REAL, batt_mv INTEGER, temp_c REAL, lora_frames INTEGER, lte_frames INTEGER)"
    )
    return conn


# ---------------------------------------------------------------- LoRa PHY
# Minimal SX1262 driver over spidev — enough for beacon + short frames.
# Full mesh routing lives in the Rust mesh-net crate; this is the radio shim.

class LoRaRadio:
    def __init__(self):
        self.fd = None
        self.ready = False

    def open(self):
        try:
            import spidev
            self.spi = spidev.SpiDev()
            self.spi.open(1, 0)          # spidev1.0
            self.spi.max_speed_hz = 1_000_000
            self.spi.mode = 0
            self.ready = True
        except Exception as e:
            print(f"[lora] SPI unavailable ({e}) — running mesh-less (LTE only)")

    def send_frame(self, payload: bytes) -> bool:
        if not self.ready:
            return False
        # TODO(Level-1): SX1262 SetTx + payload + IRQ poll.
        # Frame format must match mesh-net/src/envelope.rs:
        #   [magic 2B][src 8B][dst 8B][seq 4B][nonce 12B][ct+tag ...]
        # For PoC, send plaintext beacon with node id until crypto lands.
        print(f"[lora] TX {len(payload)}B: {payload[:32]}")
        return True

    def poll(self, timeout_s=0.5):
        """Returns list of (rssi, payload) received since last poll."""
        if not self.ready:
            return []
        # TODO(Level-1): SX1262 RxDone IRQ + GetRxBuffer.
        return []


# ---------------------------------------------------------------- LTE shim

class LteShim:
    """4G/LTE HAT via AT command serial (/dev/ttyAMA0)."""

    def __init__(self):
        self.port = None

    def open(self):
        try:
            import serial
            self.port = serial.Serial("/dev/ttyAMA0", 115200, timeout=2)
            self._at("AT", "OK")
            self._at("AT+CFUN=1", "OK")
        except Exception as e:
            print(f"[lte] unavailable ({e}) — mesh-only mode")
            self.port = None

    def _at(self, cmd, expect, timeout=2):
        if not self.port:
            return ""
        self.port.write((cmd + "\r").encode())
        deadline = time.time() + timeout
        buf = b""
        while time.time() < deadline:
            buf += self.port.read(256)
            if expect.encode() in buf:
                return buf.decode(errors="replace")
        return buf.decode(errors="replace")

    def signal(self):
        if not self.port:
            return None
        r = self._at("AT+CSQ", "+CSQ:")
        return r

    def sms_send(self, number, text):
        if not self.port:
            return False
        self._at(f'AT+CMGS="{number}"', ">", timeout=3)
        self.port.write((text + "\x1a").encode())
        return "OK" in self._at("", "OK", timeout=10)


# ---------------------------------------------------------------- display

def eink_status(text: str):
    """Push status line to E-Ink HAT via its local HTTP/ framebuffer API.

    Waveshare HATs expose a Python lib; for the PoC we write a small
    file the HAT's companion service renders. Real driver integration
    is a Level-2 task.
    """
    try:
        Path("/run/arcticchain/display.txt").write_text(text[:40])
    except Exception:
        pass


# ---------------------------------------------------------------- mesh engine

class MeshEngine(threading.Thread):
    def __init__(self, radio, conn):
        super().__init__(daemon=True)
        self.radio = radio
        self.conn = conn
        self.node_id = "arcticchain-01"  # TODO: derive from MAC + community key
        self.stop_event = threading.Event()

    def run(self):
        beacon = json.dumps({"t": "beacon", "node": self.node_id,
                             "ts": time.time()}).encode()
        last_beacon = 0.0
        while not self.stop_event.is_set():
            now = time.time()
            if now - last_beacon > 30:      # 30s beacon cadence
                self.radio.send_frame(beacon)
                last_beacon = now
            for rssi, payload in self.radio.poll():
                self._handle(rssi, payload)
            time.sleep(0.2)

    def _handle(self, rssi, payload):
        try:
            msg = json.loads(payload)
        except Exception:
            return
        if msg.get("t") == "msg":
            self.conn.execute(
                "INSERT INTO messages (ts, from_node, to_node, text, rssi) VALUES (?,?,?,?,?)",
                (time.time(), msg.get("from", "?"), self.node_id, msg.get("text", ""), rssi),
            )
            self.conn.commit()
            eink_status(f"MSG from {msg.get('from','?')}: {msg.get('text','')[:24]}")
        elif msg.get("t") == "beacon":
            pass  # neighbor table update — Level-2

    def broadcast(self, text):
        frame = json.dumps({"t": "msg", "from": self.node_id,
                            "text": text, "ts": time.time()}).encode()
        return self.radio.send_frame(frame)


# ---------------------------------------------------------------- HTTP API

class Api(BaseHTTPRequestHandler):
    server_version = "ArcticChain/0.1"

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json({"node": engine.node_id, "lora": radio.ready,
                        "lte": lte.port is not None, "uptime_s": time.time() - START})
        elif self.path == "/inbox":
            rows = conn.execute(
                "SELECT ts, from_node, text, rssi FROM messages ORDER BY id DESC LIMIT 50"
            ).fetchall()
            self._json({"messages": [
                {"ts": r[0], "from": r[1], "text": r[2], "rssi": r[3]} for r in rows
            ]})
        elif self.path == "/signal":
            self._json({"lte": lte.signal()})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/message":
            n = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._json({"error": "bad json"}, 400)
            text = data.get("text", "")
            ok = engine.broadcast(text)
            self._json({"queued": ok, "text": text})
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, *a):  # quiet
        pass


# ---------------------------------------------------------------- main

START = time.time()
conn = db()
radio = LoRaRadio()
lte = LteShim()

if __name__ == "__main__":
    radio.open()
    lte.open()
    engine = MeshEngine(radio, conn)
    engine.start()

    eink_status("ArcticChain v0.1 — booting")
    server = HTTPServer(("0.0.0.0", HTTP_PORT), Api)
    print(f"[arcticchain] agent up on :{HTTP_PORT}, node={engine.node_id}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        engine.stop_event.set()
