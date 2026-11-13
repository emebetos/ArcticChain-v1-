#!/usr/bin/env python3
"""ArcticChain node agent v2 — store-and-forward mesh node.

Runs on Raspberry Pi CM5 (L1 Brick) or any Linux box for bench testing.
Bridges radios into one offline-first node:

  - LoRa SX1262  : community mesh (real radio on the Pi)
  - VirtualRadio : UDP-broadcast "radio" for bench/dev — two agents on
                   one machine form a REAL mesh today (acceptance test)
  - LTE shim     : optional backhaul (AT commands)
  - HTTP API     : :8080 — messages, peers, routes, dashboard

Store-and-forward rules:
  - Every message gets an id, dst, hops-left, signature placeholder.
  - Broadcast floods to all neighbors (epidemic, dedup by id).
  - Unicast forwards toward the neighbor that most recently heard dst.
  - Undeliverable messages stay queued and retry — offline IS the mode.

Env:
  ARCTIC_NODE_ID   node name            (default: hostname)
  ARCTIC_COMMUNITY community id         (default: "default")
  ARCTIC_RADIO      lora|virtual|none   (default: virtual on non-Pi)
  ARCTIC_PORT       HTTP port           (default: 8080)
  ARCTIC_VPORT      virtual radio port  (default: 9100)
"""

import hashlib
import hmac
import json
import os
import socket
import sqlite3
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

NODE_ID = os.environ.get("ARCTIC_NODE_ID", os.uname().nodename if hasattr(os, "uname") else "node-01")
COMMUNITY = os.environ.get("ARCTIC_COMMUNITY", "default")
COMMUNITY_KEY = os.environ.get("ARCTIC_KEY", "")      # HMAC key; empty = unsigned PoC
BACKHAUL_URL = os.environ.get("ARCTIC_BACKHAUL", "")  # e.g. http://server:9000
BACKHAUL_S = int(os.environ.get("ARCTIC_BACKHAUL_S", "30"))
POS = os.environ.get("ARCTIC_POS", "")                # "lat,lon" for map display
RADIO_KIND = os.environ.get("ARCTIC_RADIO", "virtual")

# message classes — queue priority per PROTOCOL_v1.md section 4
CLS_ORDER = {"alert": 0, "control": 1, "data": 2, "telemetry": 3}
CLS_SQL = ("CASE cls WHEN 'alert' THEN 0 WHEN 'control' THEN 1 "
           "WHEN 'data' THEN 2 ELSE 3 END")
HTTP_PORT = int(os.environ.get("ARCTIC_PORT", "8080"))
VPORT = int(os.environ.get("ARCTIC_VPORT", "9100"))
DB_PATH = Path(os.environ.get("ARCTIC_DB", "messages.db"))
MAX_HOPS = 8
BEACON_S = 10
GOSSIP_S = 3

START = time.time()

# ---------------------------------------------------------------- storage

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "id TEXT PRIMARY KEY, ts REAL, from_node TEXT, to_node TEXT,"
        " text TEXT, hops INTEGER, state TEXT DEFAULT 'pending',"
        " rssi INTEGER, delivered_ts REAL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS neighbors ("
        "node_id TEXT PRIMARY KEY, last_seen REAL, rssi INTEGER,"
        " heard_via TEXT, msg_count INTEGER DEFAULT 0)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS health ("
        "ts REAL, batt_mv INTEGER, temp_c REAL, tx INTEGER, rx INTEGER)")
    # v1 protocol columns — ALTER for pre-v1 databases
    for ddl in (
        "ALTER TABLE messages ADD COLUMN cls TEXT DEFAULT 'data'",
        "ALTER TABLE messages ADD COLUMN acked INTEGER DEFAULT 0",
        "ALTER TABLE neighbors ADD COLUMN pos TEXT",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass
    return conn

conn = db()


def mid():
    return hashlib.sha256(f"{NODE_ID}:{time.time_ns()}".encode()).hexdigest()[:16]


def store_msg(m):
    conn.execute(
        "INSERT OR IGNORE INTO messages"
        " (id, ts, from_node, to_node, text, hops, state, rssi, cls)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (m["id"], m.get("ts", time.time()), m.get("from", "?"),
         m.get("to", "*"), m.get("text", ""), m.get("hops", MAX_HOPS),
         "pending" if m.get("to") != NODE_ID else "delivered",
         m.get("rssi", -999), m.get("cls", "data")))
    conn.commit()


def seen(m_id):
    return conn.execute("SELECT 1 FROM messages WHERE id=?", (m_id,)).fetchone() is not None


def pending_for(node):
    return conn.execute(
        f"SELECT id, from_node, to_node, text, hops, cls FROM messages"
        f" WHERE state='pending' AND to_node=?"
        f" ORDER BY {CLS_SQL}, ts LIMIT 20",
        (node,)).fetchall()


def all_pending():
    return conn.execute(
        f"SELECT id, from_node, to_node, text, hops, cls FROM messages"
        f" WHERE state='pending'"
        f" ORDER BY {CLS_SQL}, ts LIMIT 50").fetchall()


def inbox():
    return conn.execute(
        "SELECT ts, from_node, to_node, text, hops, rssi, cls FROM messages"
        " WHERE to_node=? OR to_node='*' ORDER BY ts DESC LIMIT 50",
        (NODE_ID,)).fetchall()


# ---------------------------------------------------------------- radios

class VirtualRadio:
    """UDP broadcast 'radio' — real mesh between agents on one machine."""

    def __init__(self, port):
        self.port = port
        self.ready = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", port))
        self.sock.settimeout(0.2)

    def send(self, frame: bytes):
        try:
            self.sock.sendto(frame, ("<broadcast>", self.port))
            return True
        except Exception:
            return False

    def poll(self):
        out = []
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
                out.append((-60, data))   # virtual rssi
            except socket.timeout:
                break
            except Exception:
                break
        return out


class LoRaRadio:
    """SX1262 over spidev — real radio on the Pi. Shim until driver lands."""

    def __init__(self):
        self.ready = False

    def open(self):
        try:
            import spidev
            self.spi = spidev.SpiDev()
            self.spi.open(1, 0)
            self.spi.max_speed_hz = 1_000_000
            self.ready = True
        except Exception as e:
            print(f"[lora] SPI unavailable ({e}) — virtual radio only")

    def send(self, frame: bytes):
        if not self.ready:
            return False
        print(f"[lora] TX {len(frame)}B")
        return True     # TODO: SX1262 SetTx — driver lands with hardware

    def poll(self):
        return []


# ---------------------------------------------------------------- engine

class Engine(threading.Thread):
    def __init__(self, radio):
        super().__init__(daemon=True)
        self.radio = radio
        self.stop_event = threading.Event()
        self.tx = self.rx = 0
        self.last_beacon = 0.0
        self.last_gossip = 0.0

    # -- frames ---------------------------------------------------------
    def _frame(self, kind, **kw):
        f = {"t": kind, "node": NODE_ID, "community": COMMUNITY,
             "ts": time.time(), **kw}
        if COMMUNITY_KEY:
            f["sig"] = self._sign(f)
        return json.dumps(f).encode()

    @staticmethod
    def _sign(f):
        """HMAC-SHA256 over canonical frame (sig field excluded)."""
        body = {k: v for k, v in f.items() if k != "sig"}
        canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hmac.new(COMMUNITY_KEY.encode(), canon.encode(),
                        hashlib.sha256).hexdigest()[:32]

    @staticmethod
    def _verify(f):
        if not COMMUNITY_KEY:
            return True                     # unsigned PoC mode
        sig = f.get("sig", "")
        return hmac.compare_digest(sig, Engine._sign(f))

    def beacon(self):
        kw = {}
        if POS:
            try:
                kw["pos"] = [float(v) for v in POS.split(",")]
            except ValueError:
                pass
        return self._frame("beacon", battery=99, **kw)

    def send_msg(self, to, text, cls="data"):
        if cls not in CLS_ORDER:
            cls = "data"
        m = {"t": "msg", "id": mid(), "from": NODE_ID, "to": to,
             "text": text, "hops": MAX_HOPS, "ts": time.time(), "cls": cls}
        store_msg(m)
        return self.radio.send(self._frame("msg", **m))

    def send_ack(self, m_id):
        return self.radio.send(self._frame(
            "ack", **{"id": m_id, "from": NODE_ID}))

    # -- receive --------------------------------------------------------
    def _handle(self, rssi, payload):
        try:
            f = json.loads(payload)
        except Exception:
            return
        if f.get("community") != COMMUNITY or f.get("node") == NODE_ID:
            return
        if not self._verify(f):
            print(f"[mesh] rejected bad-signature frame from {f.get('node')}")
            return
        self.rx += 1
        peer = f.get("node", "?")
        pos = json.dumps(f["pos"]) if f.get("pos") else None
        conn.execute(
            "INSERT INTO neighbors (node_id, last_seen, rssi, heard_via,"
            " msg_count, pos) VALUES (?,?,?,?,1,?)"
            " ON CONFLICT(node_id) DO UPDATE SET"
            " last_seen=excluded.last_seen, rssi=excluded.rssi,"
            " msg_count=neighbors.msg_count+1,"
            " pos=COALESCE(excluded.pos, neighbors.pos)",
            (peer, time.time(), rssi, RADIO_KIND, pos))
        conn.commit()

        t = f.get("t")
        if t == "beacon":
            pass
        elif t == "msg" or t == "task":
            self._on_msg(f if t == "msg" else {**f, "cls": "control"}, rssi)
        elif t == "ack":
            # delivery receipt — mark our own originated message acked
            conn.execute(
                "UPDATE messages SET state='acked', acked=1"
                " WHERE id=? AND from_node=?",
                (f.get("id"), NODE_ID))
            conn.commit()

    def _on_msg(self, f, rssi):
        m_id = f.get("id")
        to = f.get("to", "*")
        if not m_id or seen(m_id):
            return
        store_msg({**f, "rssi": rssi})
        hops = int(f.get("hops", MAX_HOPS)) - 1
        if to == NODE_ID:
            conn.execute("UPDATE messages SET state='delivered', delivered_ts=? WHERE id=?",
                         (time.time(), m_id))
            conn.commit()
            print(f"[mesh] DELIVERED {m_id} from {f.get('from')}")
            if to != "*" and f.get("from") != NODE_ID:
                self.send_ack(m_id)          # unicast delivery receipt
                self.tx += 1
            return
        if hops <= 0:
            conn.execute("UPDATE messages SET state='expired' WHERE id=?", (m_id,))
            conn.commit()
            return
        # forward: flood for broadcast; toward best next-hop for unicast
        f2 = dict(f, hops=hops, cls=f.get("cls", "data"))
        if to == "*":
            self.radio.send(self._frame("msg", **f2))
            self.tx += 1
        else:
            nxt = self.best_next_hop(to)
            if nxt:
                self.radio.send(self._frame("msg", **f2))
                self.tx += 1

    def best_next_hop(self, dst):
        """Neighbor that most recently relayed/heard dst (or any fresh peer)."""
        row = conn.execute(
            "SELECT node_id FROM neighbors WHERE node_id=? AND last_seen>?",
            (dst, time.time() - 120)).fetchone()
        if row:
            return row[0]
        row = conn.execute(
            "SELECT node_id FROM neighbors ORDER BY last_seen DESC LIMIT 1").fetchone()
        return row[0] if row else None

    # -- periodic -------------------------------------------------------
    def gossip(self):
        """Re-send pending messages to neighbors (store-forward retry)."""
        pend = all_pending()
        if not pend:
            return
        neigh = conn.execute(
            "SELECT node_id FROM neighbors WHERE last_seen>?",
            (time.time() - 60,)).fetchall()
        if not neigh:
            return
        for nid, frm, to, text, hops, cls in pend:
            for (peer,) in neigh:
                self.radio.send(self._frame(
                    "msg", **{"id": nid, "from": frm, "to": to,
                              "text": text, "hops": hops, "cls": cls,
                              "ts": time.time()}))
                self.tx += 1

    def run(self):
        while not self.stop_event.is_set():
            now = time.time()
            if now - self.last_beacon > BEACON_S:
                self.radio.send(self.beacon())
                self.tx += 1
                self.last_beacon = now
            if now - self.last_gossip > GOSSIP_S:
                self.gossip()
                self.last_gossip = now
            for rssi, payload in self.radio.poll():
                self._handle(rssi, payload)
            time.sleep(0.1)


# ---------------------------------------------------------------- backhaul

def _http(url, data=None, timeout=5):
    """Tiny JSON HTTP helper — GET when data=None, POST otherwise."""
    if data is None:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


class BackhaulBridge(threading.Thread):
    """Connects the mesh to an internet-side community server.

    Outbound: mesh-delivered messages are POSTed to {URL}/inbox once.
    Inbound:  GET {URL}/outbox/{community} returns {to,text}[] which are
              injected into the mesh as new messages.

    The bridge node is just another mesh node — the server never talks
    LoRa, it talks HTTP to whichever node has real internet (LTE/sat).
    """

    def __init__(self, engine):
        super().__init__(daemon=True)
        self.engine = engine
        self.stop_event = threading.Event()
        self.reported = set()
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN uplinked INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()

    def run(self):
        while not self.stop_event.is_set():
            try:
                self._uplink()
                self._downlink()
            except Exception as e:
                print(f"[backhaul] {e}")
            self.stop_event.wait(BACKHAUL_S)

    def _uplink(self):
        rows = conn.execute(
            "SELECT id, from_node, to_node, text, ts FROM messages"
            " WHERE state='delivered' AND (uplinked=0 OR uplinked IS NULL)"
            " ORDER BY ts LIMIT 50").fetchall()
        for mid_, frm, to, text, ts in rows:
            _http(f"{BACKHAUL_URL}/inbox", {
                "id": mid_, "from": frm, "to": to, "text": text,
                "via": NODE_ID, "ts": ts})
            conn.execute("UPDATE messages SET uplinked=1 WHERE id=?", (mid_,))
            conn.commit()

    def _downlink(self):
        out = _http(f"{BACKHAUL_URL}/outbox/{COMMUNITY}")
        for m in out.get("messages", []):
            key = m.get("id", "")
            if key and key in self.reported:
                continue
            if key:
                self.reported.add(key)
            self.engine.send_msg(m.get("to", "*"), m.get("text", ""))


# ---------------------------------------------------------------- HTTP API

class Api(BaseHTTPRequestHandler):
    server_version = "ArcticChain/2.0"

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, body):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._json({"node": NODE_ID, "community": COMMUNITY,
                        "radio": RADIO_KIND, "uptime_s": round(time.time() - START, 1),
                        "tx": engine.tx, "rx": engine.rx})
        elif self.path == "/inbox":
            rows = inbox()
            self._json({"messages": [
                {"ts": r[0], "from": r[1], "to": r[2], "text": r[3],
                 "hops": r[4], "rssi": r[5], "cls": r[6]} for r in rows]})
        elif self.path == "/peers":
            rows = conn.execute(
                "SELECT node_id, last_seen, rssi, pos FROM neighbors"
                " ORDER BY last_seen DESC").fetchall()
            self._json({"peers": [
                {"node": r[0], "age_s": round(time.time() - r[1], 1),
                 "rssi": r[2],
                 "pos": json.loads(r[3]) if r[3] else None} for r in rows],
                "self_pos": [float(v) for v in POS.split(",")]
                if POS and "," in POS else None})
        elif self.path == "/queue":
            rows = all_pending()
            self._json({"pending": [
                {"id": r[0], "from": r[1], "to": r[2], "text": r[3],
                 "hops": r[4], "cls": r[5]} for r in rows]})
        elif self.path == "/stats":
            c = conn.execute(
                "SELECT state, COUNT(*) FROM messages GROUP BY state").fetchall()
            self._json({"by_state": {r[0]: r[1] for r in c},
                        "neighbors": conn.execute(
                            "SELECT COUNT(*) FROM neighbors").fetchone()[0],
                        "tx": engine.tx, "rx": engine.rx})
        elif self.path in ("/", "/dashboard"):
            self._html(DASHBOARD_HTML.replace("__NODE__", NODE_ID)
                       .replace("__COMMUNITY__", COMMUNITY))
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json({"error": "bad json"}, 400)
        if self.path in ("/send", "/message", "/broadcast"):
            to = data.get("to", "*")
            text = data.get("text", "")
            cls = data.get("cls", "alert" if to != "*" and "sos" in text.lower()
                           else "data")
            if not text:
                return self._json({"error": "empty text"}, 400)
            ok = engine.send_msg(to, text, cls)
            return self._json({"queued": ok, "to": to, "cls": cls,
                               "id": "see /queue"})
        if self.path == "/task":
            # swarm/coordinator tasking frame (PROTOCOL_v1 §3.3)
            to = data.get("to", "*")
            text = data.get("text", "")
            if not text:
                return self._json({"error": "empty text"}, 400)
            ok = engine.send_msg(to, text, "control")
            return self._json({"queued": ok, "to": to, "cls": "control"})
        self._json({"error": "not found"}, 404)

    def log_message(self, *a):
        pass


DASHBOARD_HTML = """<!doctype html><html><head><meta charset=utf-8>
<title>ArcticChain — __NODE__</title><meta name=viewport content="width=device-width">
<style>
body{font-family:system-ui;background:#0d1420;color:#dfe7f0;margin:0;padding:16px}
h1{font-size:20px}h2{font-size:14px;color:#7fb2e0;margin:18px 0 6px}
.card{background:#16202e;border:1px solid #2a3a50;border-radius:10px;padding:12px;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
td,th{padding:5px 8px;border-bottom:1px solid #24344a;text-align:left}
.msg{background:#101a28;border-left:3px solid #5eead4;padding:8px 10px;margin:6px 0;border-radius:4px;font-size:13px}
.dim{color:#7f92a8;font-size:12px}
.pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#1e3a5c}
form{display:flex;gap:8px;margin:10px 0}
input{flex:1;padding:8px;border-radius:6px;border:1px solid #2a3a50;background:#0d1420;color:#dfe7f0}
button{padding:8px 16px;border:0;border-radius:6px;background:#5eead4;color:#0d1420;font-weight:bold;cursor:pointer}
</style></head><body>
<h1>◈ ArcticChain <span class=pill>__NODE__</span> <span class=dim>community: __COMMUNITY__</span></h1>
<div class=card id=health>loading…</div>
<h2>Send message</h2>
<form onsubmit="send(event)"><input id=t placeholder="message to mesh (broadcast if no 'to')"><input id=to placeholder="to: node-id or *" style="max-width:160px"><button>send</button></form>
<h2>Mesh map</h2><div class=card><svg id=map width="100%" height="220" viewBox="0 0 600 220"
 style="background:#0a1018;border-radius:8px"></svg>
 <div class=dim id=mapnote>set ARCTIC_POS=lat,lon on nodes to plot positions</div></div>
<h2>Inbox</h2><div id=inbox></div>
<h2>Peers</h2><div id=peers></div>
<h2>Pending queue</h2><div id=queue></div>
<script>
async function j(u,o){let r=await fetch(u,o);return r.json()}
const CLSC={alert:'#ff6b6b',control:'#ffd166',data:'#5eead4',telemetry:'#7f92a8'};
function clsBadge(c){return '<span class=pill style="background:'+(CLSC[c]||'#1e3a5c')+'22;color:'+(CLSC[c]||'#7f92a8')+'">'+(c||'data')+'</span>'}
function drawMap(p){
 let pts=[];
 if(p.self_pos)pts.push({n:'__NODE__',pos:p.self_pos,self:1});
 p.peers.forEach(x=>{if(x.pos)pts.push({n:x.node,pos:x.pos,rssi:x.rssi})});
 let svg=document.getElementById('map'),note=document.getElementById('mapnote');
 if(pts.length<2){svg.innerHTML='';note.textContent='need ≥2 positioned nodes (ARCTIC_POS=lat,lon)';return}
 note.textContent=pts.length+' positioned nodes';
 let lats=pts.map(q=>q.pos[0]),lons=pts.map(q=>q.pos[1]);
 let a0=Math.min(...lats),a1=Math.max(...lats),o0=Math.min(...lons),o1=Math.max(...lons);
 let pad=30, W=600,H=220;
 // equirectangular approx — fine at community scale
 let kx=(W-2*pad)/Math.max(o1-o0,1e-6), ky=(H-2*pad)/Math.max(a1-a0,1e-6), k=Math.min(kx,ky);
 let X=lo=>(lo-o0)*k+(W-(o1-o0)*k)/2, Y=la=>H-((la-a0)*k+(H-(a1-a0)*k)/2);
 let html='';
 // links: draw line self->each peer (star approx of gossip domain)
 let sp=pts.find(q=>q.self);
 pts.forEach(q=>{if(q===sp)return;
  html+='<line x1="'+X(sp.pos[1])+'" y1="'+Y(sp.pos[0])+'" x2="'+X(q.pos[1])+'" y2="'+Y(q.pos[0])+'" stroke="#2a3a50" stroke-width="1"/>'});
 pts.forEach(q=>{
  let x=X(q.pos[1]),y=Y(q.pos[0]);
  html+='<circle cx="'+x+'" cy="'+y+'" r="'+(q.self?9:6)+'" fill="'+(q.self?'#ffd166':'#5eead4')+'"/>';
  html+='<text x="'+(x+10)+'" y="'+(y+4)+'" fill="#dfe7f0" font-size="11">'+q.n+'</text>'});
 svg.innerHTML=html;
}
async function refresh(){
 let h=await j('/health');
 document.getElementById('health').innerHTML=
  'uptime <b>'+h.uptime_s+'s</b> · radio <b>'+h.radio+'</b> · tx <b>'+h.tx+'</b> · rx <b>'+h.rx+'</b>';
 let ib=await j('/inbox');
 document.getElementById('inbox').innerHTML=ib.messages.map(m=>
  '<div class=msg><b>'+m.from+'</b> → '+m.to+' '+clsBadge(m.cls)+' · '+new Date(m.ts*1000).toLocaleTimeString()+
  ' <span class=dim>rssi '+m.rssi+'</span><br>'+m.text+'</div>').join('')||'<div class=dim>empty</div>';
 let p=await j('/peers'); drawMap(p);
 document.getElementById('peers').innerHTML='<table><tr><th>node</th><th>age</th><th>rssi</th><th>pos</th></tr>'+
  p.peers.map(x=>'<tr><td>'+x.node+'</td><td>'+x.age_s+'s</td><td>'+x.rssi+'</td><td>'+(x.pos?x.pos.join(', '):'—')+'</td></tr>').join('')+'</table>';
 let q=await j('/queue');
 document.getElementById('queue').innerHTML='<table><tr><th>id</th><th>class</th><th>from→to</th><th>text</th><th>hops</th></tr>'+
  q.pending.map(x=>'<tr><td>'+x.id+'</td><td>'+clsBadge(x.cls)+'</td><td>'+x.from+'→'+x.to+'</td><td>'+x.text+'</td><td>'+x.hops+'</td></tr>').join('')+'</table>';
}
async function send(e){e.preventDefault();
 await j('/send',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({to:document.getElementById('to').value||'*',text:document.getElementById('t').value})});
 document.getElementById('t').value='';refresh()}
refresh();setInterval(refresh,3000);
</script></body></html>"""


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    if RADIO_KIND == "virtual":
        radio = VirtualRadio(VPORT)
    else:
        radio = LoRaRadio()
        radio.open()
    engine = Engine(radio)
    engine.start()
    if BACKHAUL_URL:
        bridge = BackhaulBridge(engine)
        bridge.start()
        print(f"[backhaul] bridging mesh <-> {BACKHAUL_URL} every {BACKHAUL_S}s")
    server = HTTPServer(("0.0.0.0", HTTP_PORT), Api)
    print(f"[arcticchain] v2 up — node={NODE_ID} community={COMMUNITY} "
          f"radio={RADIO_KIND} http=:{HTTP_PORT} db={DB_PATH}"
          f"{' signed' if COMMUNITY_KEY else ' UNSIGNED'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        engine.stop_event.set()
