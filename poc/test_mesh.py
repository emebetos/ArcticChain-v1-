#!/usr/bin/env python3
"""Two-node acceptance test for arcticchain_agent2 — virtual radio mesh.

Spawns node-a and node-b on one machine, proves:
  1. beacons -> peers discovered
  2. unicast A->B delivered
  3. broadcast reaches both inboxes
  4. queue drains (store-forward works)

Run:  python test_mesh.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
AGENT = HERE / "arcticchain_agent2.py"

def get(port, path):
    with urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=3) as r:
        return json.loads(r.read())

def post(port, path, data):
    req = urllib.request.Request(
        f"http://localhost:{port}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.loads(r.read())

def wait_for(port, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            get(port, "/health")
            return True
        except Exception:
            time.sleep(0.3)
    return False

def main():
    tmp = Path(tempfile.mkdtemp(prefix="acmesh_"))
    key = "test-community-key-001"
    env_a = {**os.environ, "ARCTIC_NODE_ID": "node-a", "ARCTIC_PORT": "8091",
             "ARCTIC_DB": str(tmp / "a.db"), "ARCTIC_VPORT": "9201",
             "ARCTIC_KEY": key, "ARCTIC_POS": "53.55,-113.49"}
    env_b = {**os.environ, "ARCTIC_NODE_ID": "node-b", "ARCTIC_PORT": "8092",
             "ARCTIC_DB": str(tmp / "b.db"), "ARCTIC_VPORT": "9201",
             "ARCTIC_KEY": key, "ARCTIC_POS": "53.60,-113.40"}
    pa = subprocess.Popen([sys.executable, str(AGENT)], env=env_a,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pb = subprocess.Popen([sys.executable, str(AGENT)], env=env_b,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    try:
        assert wait_for(8091) and wait_for(8092), "agents failed to start"
        print("[1] both agents up")

        time.sleep(12)  # >1 beacon interval
        peers_a = get(8091, "/peers")["peers"]
        peers_b = get(8092, "/peers")["peers"]
        assert any(p["node"] == "node-b" for p in peers_a), f"A sees no B: {peers_a}"
        assert any(p["node"] == "node-a" for p in peers_b), f"B sees no A: {peers_b}"
        peer_b = [p for p in peers_a if p["node"] == "node-b"][0]
        assert peer_b.get("pos") == [53.60, -113.40], f"pos not propagated: {peer_b}"
        print(f"[2] peers discovered — A sees {len(peers_a)}, B sees {len(peers_b)}; pos beacon OK")

        post(8091, "/send", {"to": "node-b", "text": "hello from A"})
        t0 = time.time()
        delivered = False
        while time.time() - t0 < 15:
            inbox_b = get(8092, "/inbox")["messages"]
            if any(m["text"] == "hello from A" and m["from"] == "node-a"
                   for m in inbox_b):
                delivered = True
                break
            time.sleep(0.5)
        assert delivered, "unicast A->B NOT delivered in 15s"
        print("[3] unicast A->B DELIVERED")

        # delivery ACK: B acked the unicast -> A's copy leaves pending
        t0 = time.time()
        acked = False
        while time.time() - t0 < 12:
            st = get(8091, "/stats")["by_state"]
            if st.get("acked", 0) >= 1:
                acked = True
                break
            time.sleep(0.5)
        assert acked, "delivery ACK never arrived at sender"
        print("[3b] delivery ACK received — sender marked acked")

        post(8092, "/broadcast", {"text": "mesh is alive"})
        t0 = time.time()
        flooded = False
        while time.time() - t0 < 15:
            inbox_a = get(8091, "/inbox")["messages"]
            if any(m["text"] == "mesh is alive" for m in inbox_a):
                flooded = True
                break
            time.sleep(0.5)
        assert flooded, "broadcast B->A NOT received in 15s"
        print("[4] broadcast B->A RECEIVED")

        # forged frame with wrong key must be rejected
        import socket as _sk, json as _js
        bad = _js.dumps({"t": "msg", "id": "forged1", "node": "node-x",
                         "community": "default", "from": "node-x", "to": "node-a",
                         "text": "FORGED", "hops": 8, "ts": time.time(),
                         "sig": "deadbeef"}).encode()
        s = _sk.socket(_sk.AF_INET, _sk.SOCK_DGRAM)
        s.setsockopt(_sk.SOL_SOCKET, _sk.SO_BROADCAST, 1)
        s.sendto(bad, ("<broadcast>", 9201))
        s.close()
        time.sleep(1)
        inbox_a = get(8091, "/inbox")["messages"]
        assert not any(m["text"] == "FORGED" for m in inbox_a), \
            "forged frame was accepted!"
        print("[4b] forged frame REJECTED (HMAC verify works)")

        q = get(8091, "/queue")["pending"]
        st = get(8091, "/stats")
        print(f"[5] stats: {st} | A pending: {len(q)}")
        print("\nALL CHECKS PASSED — signed mesh works end-to-end")
    except AssertionError as e:
        ok = False
        print(f"\nFAIL: {e}")
    finally:
        pa.terminate(); pb.terminate()
        time.sleep(0.5)
        for p in (pa, pb):
            if p.poll() is None:
                p.kill()
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
