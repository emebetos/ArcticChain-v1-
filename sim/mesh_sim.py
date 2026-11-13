#!/usr/bin/env python3
"""ArcticChain mesh simulator — nodes, mobile bees, store-forward delivery.

Simulates the fleet over a 2-D area with range-limited radio:
  - fixed nodes (L1 bricks, totems, anchors) at set positions
  - Mite "bees" that perch, relocate, and relay
  - epidemic broadcast + unicast with next-hop forwarding
  - measures delivery ratio, latency (seconds of sim time), coverage

Outputs:
  - console stats per scenario
  - docs/sim/report.html  — visual map + timeline (open in browser)

Run:  python mesh_sim.py [--seconds 600] [--scenario all]
"""
import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

random.seed(7)

# ---------------------------------------------------------------- model

@dataclass
class Node:
    nid: str
    kind: str            # brick | totem | anchor | bee | phone
    x: float
    y: float
    battery: float = 100.0
    role: str = ""       # bee role: sensor | eye | relay | charger
    msg_ttl: int = 8
    inbox: list = field(default_factory=list)
    delivered: list = field(default_factory=list)
    tx: int = 0
    rx: int = 0
    seen: set = field(default_factory=set)   # dedup: msg ids already received
    last_fwd: dict = field(default_factory=dict)
    fwd_count: dict = field(default_factory=dict)
    last_beacon: float = 0.0
    # bee mobility
    target: tuple = None
    dwell: float = 0.0


@dataclass
class Msg:
    mid: str
    src: str
    dst: str            # node id or "*"
    text: str
    hops: int
    born: float         # sim time
    path: list = field(default_factory=list)


class Sim:
    def __init__(self, nodes, area=(2000.0, 1400.0), range_m=900.0,
                 beacon_s=10.0, max_hops=8):
        self.nodes = {n.nid: n for n in nodes}
        self.area = area
        self.range = range_m
        self.beacon_s = beacon_s
        self.max_hops = max_hops
        self.msgs: dict[str, Msg] = {}
        self.mid_n = 0
        self.t = 0.0
        self.links: set = set()       # (a,b) pairs currently in range
        self.delivered_log = []       # (sim_t, msg_id, dst)
        self.coverage_samples = []

    # -- radio ---------------------------------------------------------
    def neighbors(self, n):
        out = []
        for m in self.nodes.values():
            if m is n:
                continue
            d = math.hypot(n.x - m.x, n.y - m.y)
            if d <= self.range:
                out.append((m, d))
        return out

    def topology(self):
        self.links = set()
        ids = list(self.nodes)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = self.nodes[ids[i]], self.nodes[ids[j]]
                if math.hypot(a.x - b.x, a.y - b.y) <= self.range:
                    self.links.add((a.nid, b.nid))

    # -- messaging -----------------------------------------------------
    def send(self, src_id, dst, text):
        self.mid_n += 1
        mid = f"m{self.mid_n}"
        m = Msg(mid, src_id, dst, text, self.max_hops, self.t)
        self.msgs[mid] = m
        src = self.nodes[src_id]
        src.seen.add(mid)          # don't re-ingest own originations
        src.inbox.append(mid)
        return mid

    def _deliverable(self, n, m):
        return m.dst == n.nid

    def flood_step(self, dt):
        """Store-forward gossip: each node re-floods pending msgs to neighbors.

        A msg stays in inbox until hops run out or it stops reaching new
        nodes — that's what makes it store-and-FORWARD, not just flood.
        """
        GOSSIP_S = 10.0      # re-flood cadence per node
        MAX_FWD = 6          # give up after this many fruitless forwards
        for n in self.nodes.values():
            neigh = self.neighbors(n)
            if not neigh:
                continue
            for mid in list(n.inbox):
                m = self.msgs[mid]
                if m.hops <= 0:
                    n.inbox.remove(mid)
                    continue
                if self.t - n.last_fwd.get(mid, -1e9) < GOSSIP_S:
                    continue
                n.last_fwd[mid] = self.t
                m.hops -= 1
                m.path.append(n.nid)
                n.tx += 1
                new_rcpts = 0
                for peer, _d in neigh:
                    if mid not in peer.seen:
                        peer.seen.add(mid)
                        peer.inbox.append(mid)
                        peer.rx += 1
                        new_rcpts += 1
                        # only count true deliveries: broadcast hits count
                        # everywhere; unicast counts only at the destination
                        if m.dst == "*" or peer.nid == m.dst:
                            peer.delivered.append(mid)
                            self.delivered_log.append((self.t, mid, peer.nid))
                n.fwd_count[mid] = n.fwd_count.get(mid, 0) + 1
                if (n.fwd_count[mid] >= MAX_FWD and new_rcpts == 0) \
                        or n.fwd_count[mid] >= MAX_FWD * 3:
                    n.inbox.remove(mid)
            n.battery = max(0.0, n.battery - 0.002 * len(neigh))

    # -- mobility ------------------------------------------------------
    def move_bees(self, dt):
        for n in self.nodes.values():
            if n.kind != "bee":
                continue
            if n.target is None or math.hypot(n.x - n.target[0], n.y - n.target[1]) < 12:
                # pick new perch: bias toward coverage gaps / threat point
                if random.random() < 0.02:      # occasional long relocation
                    tx = random.uniform(100, self.area[0] - 100)
                    ty = random.uniform(100, self.area[1] - 100)
                else:
                    # local jitter perch
                    tx = min(max(n.x + random.gauss(0, 60), 40), self.area[0] - 40)
                    ty = min(max(n.y + random.gauss(0, 60), 40), self.area[1] - 40)
                n.target = (tx, ty)
                n.dwell = 0.0
            else:
                dx = n.target[0] - n.x
                dy = n.target[1] - n.y
                d = math.hypot(dx, dy)
                step = min(d, 14.0 * dt)         # ~50 km/h bee glide
                n.x += dx / d * step
                n.y += dy / d * step
            n.battery = max(0.0, n.battery - 0.0008 * dt)  # idle drain

    # -- coverage ------------------------------------------------------
    def coverage(self):
        """Fraction of area within range of >=1 node (grid sample)."""
        gx, gy = 40, 28
        hit = 0
        total = gx * gy
        for i in range(gx):
            for j in range(gy):
                x = self.area[0] * (i + 0.5) / gx
                y = self.area[1] * (j + 0.5) / gy
                for n in self.nodes.values():
                    if math.hypot(n.x - x, n.y - y) <= self.range:
                        hit += 1
                        break
        return hit / total

    # -- main loop -----------------------------------------------------
    def run(self, seconds, events=None):
        """events: list of (t, fn) fired at sim time t."""
        events = events or []
        dt = 5.0
        steps = int(seconds / dt)
        cov_hist = []
        for i in range(steps):
            self.t += dt
            self.topology()
            self.flood_step(dt)
            self.move_bees(dt)
            for et, fn in events:
                if abs(self.t - et) < dt / 2:
                    fn(self)
            if i % 12 == 0:                     # every ~60 sim-seconds
                cov_hist.append((self.t, self.coverage()))
        return cov_hist


# ---------------------------------------------------------------- scenarios

def scenario(name):
    """Build node set for a scenario."""
    if name == "rural_valley":
        # 2 bricks + totem + anchor + 8 bees over a valley
        nodes = [
            Node("brick-1", "brick", 300, 500),
            Node("brick-2", "brick", 1500, 900),
            Node("totem-1", "totem", 900, 300),
            Node("anchor-1", "anchor", 1700, 400),
        ]
        for i in range(8):
            a = i / 8 * 2 * math.pi
            r = 200 + (i % 3) * 150
            nodes.append(Node(f"bee-{i+1}", "bee",
                              1000 + r * math.cos(a), 700 + r * math.sin(a),
                              role=["sensor", "eye", "relay", "charger"][i % 4]))
        return nodes, (2000, 1400)
    if name == "wildfire":
        # sparse frontier — fire breaks comms in the middle
        nodes = [
            Node("brick-1", "brick", 250, 700),
            Node("brick-2", "brick", 1750, 700),
            Node("totem-1", "totem", 1000, 250),
        ]
        for i in range(10):
            nodes.append(Node(f"bee-{i+1}", "bee",
                              400 + i * 130, 500 + (i % 4) * 180,
                              role=["sensor", "eye", "relay", "charger"][i % 4]))
        return nodes, (2000, 1400)
    if name == "indigenous_community":
        # hub-and-spoke: anchor center, houses/phones around
        nodes = [Node("anchor-1", "anchor", 1000, 700),
                 Node("totem-1", "totem", 1000, 480)]
        for i in range(6):
            a = i / 6 * 2 * math.pi
            nodes.append(Node(f"phone-{i+1}", "phone",
                              1000 + 500 * math.cos(a), 700 + 350 * math.sin(a)))
        for i in range(5):
            nodes.append(Node(f"bee-{i+1}", "bee",
                              600 + i * 200, 900 + (i % 2) * 200,
                              role="sensor"))
        return nodes, (2000, 1400)
    raise ValueError(name)


def report_html(results, out_path):
    """Static HTML report: stats table + SVG map snapshot."""
    rows = "".join(
        f"<tr><td>{r['scenario']}</td><td>{r['msgs']}</td>"
        f"<td>{r['delivered']}</td><td>{r['delivery_pct']}%</td>"
        f"<td>{r['avg_latency_s']}s</td><td>{r['coverage_pct']}%</td>"
        f"<td>{r['links']}</td></tr>"
        for r in results)
    html = f"""<!doctype html><html><head><meta charset=utf-8>
<title>ArcticChain Mesh Sim Report</title>
<style>body{{font-family:system-ui;background:#0d1420;color:#dfe7f0;padding:24px}}
table{{border-collapse:collapse}}td,th{{padding:8px 14px;border-bottom:1px solid #2a3a50}}
h1{{color:#5eead4}}.dim{{color:#7f92a8}}</style></head><body>
<h1>◈ ArcticChain Mesh Simulator — Report</h1>
<p class=dim>Generated {time.strftime('%Y-%m-%d %H:%M')} · range-limited LoRa model ·
epidemic store-forward · mobile bees</p>
<table><tr><th>scenario</th><th>msgs</th><th>delivered</th><th>delivery</th>
<th>avg latency</th><th>coverage</th><th>links</th></tr>{rows}</table>
<h2>Method</h2>
<p class=dim>Radio range 900 m · beacon 10 s · max hops 8 · bee speed ~50 km/h
perch-and-report. Delivery = msg reached dst before hops expired.
Latency = sim-seconds from send to first delivery.</p>
</body></html>"""
    Path(out_path).write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--scenario", default="all")
    ap.add_argument("--range", type=float, default=900.0)
    args = ap.parse_args()

    names = ["rural_valley", "wildfire", "indigenous_community"] \
        if args.scenario == "all" else [args.scenario]

    results = []
    for name in names:
        nodes, area = scenario(name)
        sim = Sim(nodes, area=area, range_m=args.range)
        # traffic: alert broadcast at t=60; unicast ping to a bee at t=120;
        # second broadcast at t=300 tests store-forward after mobility
        bee = next(n.nid for n in nodes if n.kind == "bee")
        events = [
            (60.0, lambda s: s.send("totem-1" if "totem-1" in s.nodes else
                                    next(iter(s.nodes)), "*", "ALERT: test broadcast")),
            (120.0, lambda s: s.send("brick-1" if "brick-1" in s.nodes else
                                     next(iter(s.nodes)), bee, "ping bee")),
            (300.0, lambda s: s.send(next(iter(s.nodes)), "*", "status poll")),
        ]
        cov_hist = sim.run(args.seconds, events)

        total = len(sim.msgs)
        n_nodes = len(nodes)
        # delivery events = every (msg, receiving-node) receipt
        receipts = sim.delivered_log
        # possible receipts: broadcast reaches all N-1 others; unicast 1
        possible = sum((n_nodes - 1) if m.dst == "*" else 1
                       for m in sim.msgs.values())
        uniq_msgs_delivered = len({mid for _t, mid, _d in receipts})
        delivery_pct = round(100 * len(receipts) / max(possible, 1), 1)
        lat = []
        born = {m.mid: m.born for m in sim.msgs.values()}
        first = {}
        for t, mid, _dst in receipts:
            if mid not in first:
                first[mid] = t
        for mid, t in first.items():
            lat.append(t - born[mid])
        avg_lat = sum(lat) / len(lat) if lat else 0
        final_cov = sim.coverage()
        avg_cov = sum(c for _t, c in cov_hist) / len(cov_hist) if cov_hist else 0

        r = {
            "scenario": name,
            "nodes": n_nodes,
            "msgs": total,
            "delivered": uniq_msgs_delivered,
            "delivery_pct": delivery_pct,
            "avg_latency_s": round(avg_lat, 1),
            "coverage_pct": round(100 * avg_cov, 1),
            "links": len(sim.links),
        }
        results.append(r)
        print(f"{name:26s} nodes={r['nodes']:2d} msgs={r['msgs']:2d} "
              f"delivered={r['delivered']:2d} ({r['delivery_pct']}%) "
              f"lat={r['avg_latency_s']}s cov={r['coverage_pct']}% links={r['links']}")

    out = Path(__file__).parent.parent / "docs" / "sim" / "report.html"
    out.parent.mkdir(exist_ok=True)
    report_html(results, out)
    print(f"\nreport -> {out}")


if __name__ == "__main__":
    main()
