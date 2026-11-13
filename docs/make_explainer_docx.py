# -*- coding: utf-8 -*-
"""ArcticChain — plain-language explainer document (.docx)

Not a pitch. An explanation for someone who has never heard of it:
what it is, why it exists, how each piece works, what's real today.
"""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

for section in doc.sections:
    section.top_margin = Inches(0.85)
    section.bottom_margin = Inches(0.85)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)

def h(text, level=1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.color.rgb = RGBColor(0x1a, 0x2a, 0x3a)
    return p

def para(text, bold=False, italic=False, size=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    return p

def bullet(text):
    return doc.add_paragraph(text, style='List Bullet')

def numbered(text):
    return doc.add_paragraph(text, style='List Number')

# ============================ TITLE ============================
t = doc.add_heading('ARCTICCHAIN', 0)
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('What it is, why it exists, and how it works — explained plainly')
r.italic = True
r.font.size = Pt(13)
r.font.color.rgb = RGBColor(0x55, 0x66, 0x77)

para('Prepared by Surafel Negussie, Planner/Maker — Emebet Inc. (emebetos.ca), '
     'sole proprietary owner. This document explains; it does not sell.')
para('Status note: this describes a real, partially-built system. Section 9 '
     'is an honest list of what exists today versus what is still planned.')

# ============================ 1. THE SHORT VERSION ============================
h('1. The short version')
para('Most of Canada has good cell service. The rest — farms, cabins, '
     'fly-in communities, wilderness, the North — often has nothing, or one '
     'expensive bar of signal that disappears the moment you leave the '
     'mailbox. The big carriers will not build towers there because the '
     'math does not work: too few customers per kilometre of cable.')
para('ArcticChain is a different approach. Instead of one company building '
     'giant towers and selling access, each community builds its own small '
     'network out of simple, cheap, repairable devices that talk to each '
     'other directly — like a group chat that works with no phone signal at '
     'all. Messages hop from device to device until they reach who they are '
     'for, and wait patiently if the path is temporarily broken.')
para('The same network also carries sensor data: small solar-powered "bees" '
     'that perch in trees and watch for wildfire smoke, measure air quality, '
     'track floods — and can physically move toward whatever they are '
     'watching. Eventually the plan grows into community-owned satellite '
     'services for the places on Earth that still have no communications.')

# ============================ 2. THE PROBLEM ============================
h('2. The problem, concretely')
para('Imagine you live on a gravel road two hours from the nearest town. '
     'Today, realistically:')
bullet('Your phone shows "No Service" most of the day. In an emergency you '
       'cannot call 911 unless you drive to the one hill with a bar.')
bullet('The clinic cannot send lab results or do a video visit when the '
       'tower is down — which in wildfire season is exactly when you need it.')
bullet('There is no warning system for the forest around you. Wildfires '
       'are detected by aircraft and cameras that may be hundreds of '
       'kilometres away and hours late.')
bullet('School kids do homework on paper because there is no internet to '
       'bring home. Elders cannot video-call family.')
bullet('If a company did offer service, it would be expensive, it would '
       'belong to a corporation on another continent, and your data would '
       'travel through systems you cannot see or control.')
para('This is not a niche problem. It is tens of thousands of square '
     'kilometres of Canada — and similar gaps exist across the circumpolar '
     'world, which is why the long-term plan looks beyond Canada.')

# ============================ 3. THE CORE IDEA ============================
h('3. The core idea: a network that belongs to the community')
para('Normal cell networks work like this: your phone talks to a tower; the '
     'tower talks to the carrier\'s core network; the carrier decides what '
     'you can do and what it costs. If the tower is not there, nothing works.')
para('ArcticChain works differently at every level:')
bullet('Devices talk to each other directly over a licence-free radio band '
       '(915 MHz in Canada — the same band used by many farm and industrial '
       'radios). No tower required for local communication.')
bullet('Messages do not need a continuous path. If the route is broken, the '
       'message waits in a queue on the last device that had it, and moves '
       'on the next time a neighbour comes into range. This is called '
       'store-and-forward, and it is the single most important idea in the '
       'system.')
bullet('The network belongs to the community that hosts it. Traffic stays '
       'on local hardware first; the internet is used only when the '
       'community\'s own gateway chooses to use it — for example to reach '
       'a hospital or a provincial emergency system.')
bullet('Every device is identical in kind: a brick on a mailbox post, a '
       'bee in a tree, a phone in a pocket — all run the same signed mesh '
       'protocol. Adding a device makes the network better for everyone.')

# ============================ 4. HOW A MESSAGE TRAVELS ============================
h('4. How a message actually travels (worked example)')
para('Say a hunter falls and presses the SOS button on an ArcticPhone at '
     'the edge of the valley. Here is what happens:')
numbered('The phone wraps the SOS alert in a signed, encrypted envelope '
         'addressed to the community\'s emergency node. It cannot reach '
         'the emergency node directly — they are 12 km apart through trees.')
numbered('The phone broadcasts the envelope over LoRa. A Mite bee perched '
         '800 m away hears it and stores a copy.')
numbered('The bee cannot reach the emergency node either, but it can reach '
         'an L1 Brick on a nearby ridge — 4 km away, line of sight. It '
         'forwards the envelope.')
numbered('The Brick relays it to the community Totem, which is the node '
         'with the satellite/LTE backhaul. The alert reaches the emergency '
         'coordinator — total elapsed time maybe 90 seconds, zero cell '
         'towers involved.')
numbered('If the hunter moves deeper into a dead zone, the message simply '
         'waits in queues across the mesh until connectivity returns. '
         'Nothing is lost; it is late, not gone.')
para('Two properties matter here: every envelope is cryptographically '
     'signed (only devices holding the community key can originate or '
     'alter traffic — tested: forged frames are rejected), and every hop '
     'is logged, so the system can show the path a message took.')

# ============================ 5. THE FLEET ============================
h('5. The fleet — what each device is')
para('There are seven hardware shapes, all nodes on the same mesh. They '
     'range from "buildable today from a parts list" to "honest research '
     'concept" — the drawings mark which is which.')

h('L1 Brick — the workhorse node', 2)
para('A sealed box roughly the size of a large paperback: a Raspberry Pi '
     'Compute Module, a LoRa radio, an optional LTE modem, an E-Ink '
     'display, four 18650 batteries, and a solar panel. It mounts on a '
     'fence post or building. It is a mailbox (message store), a repeater '
     '(extends the mesh), a bulletin board (shows community notices on '
     'paper-like e-ink), an SOS beacon, and optionally the internet '
     'gateway. Bill of materials is roughly $335–525 in parts; the '
     'blueprints include the real wiring and assembly steps.')

h('S Mite — the swarm bee', 2)
para('A 90 mm solar-powered puck that clips onto a branch. It carries '
     'small sensors (temperature, humidity, air quality, optional thermal '
     'or camera payloads), a LoRa radio, and a battery. Bees are meant to '
     'be cheap enough to deploy in groups of dozens or hundreds. They do '
     'not need to be individually smart — the swarm is the sensor. See '
     'section 6.')

h('E Totem — the community board', 2)
para('A pole-mounted E-Ink display plus a mesh node. It shows free clinic '
     'days, road closures, emergency alerts, community notices — readable '
     'by anyone, no smartphone required. It is the public face of the '
     'network in a village.')

h('A Anchor — the charging station', 2)
para('A solar-powered dock that charges Mites and phones, acts as a relay '
     'and backhaul point. Think of it as the swarm\'s gas station and the '
     'community\'s cell-tower substitute in one box.')

h('P ArcticPhone — the phone', 2)
para('A rugged phone designed for rural Canada: mesh radio built in (every '
     'phone extends the network), satellite SOS as a standard feature '
     'rather than a premium tier, offline-first apps (maps, manuals, '
     'forms work with zero bars), glove-friendly interface, repairable '
     'with ordinary tools, and a module bay for add-ons like thermal '
     'cameras or extra battery. This is a concept with a full blueprint '
     'set — not yet a product you can buy.')

h('D Seed — degradable sensor mote', 2)
para('A printed-electronics mote small enough to scatter over an area — '
     'think "computational dust". The honest status: this is research '
     'grade (technology readiness ~2). The idea is seasonal sensors you '
     'seed before fire season and which degrade harmlessly afterward. It '
     'is documented so the research path exists, but nobody should plan '
     'around it working yet.')

h('H Meridian — the satellite payload concept', 2)
para('A smallsat designed to be the space segment of the same mesh — '
     'the ground devices are already the user terminals. This is a '
     'mission concept, not a launched satellite.')

# ============================ 6. THE SWARM ============================
h('6. The swarm — why bees matter')
para('One bee with a temperature sensor is a thermometer. Forty bees '
     'that can move are a *system*. The design intent:')
bullet('The swarm is the sensor, not any individual unit. Each bee '
       'carries a partial payload; the collective covers an area no '
       'fixed camera or tower could.')
bullet('Bees are mobile. They normally perch (cheap, solar-powered, '
       'long battery life), but when a mission arrives — a fire '
       'detection, a flood watch, a research target — the coordinator '
       'sends a tasking message and the relevant bees physically relocate '
       'toward the event while relaying data back through the mesh.')
bullet('Roles are specialized but interchangeable: SENSOR bees measure, '
       'EYE bees add thermal/visual confirmation, RELAY bees extend '
       'radio range, CHARGER bees form the docked recharge network.')
bullet('Missions are multi-purpose, not just fire: wildfire detection, '
       'flood and snowpack monitoring, air-quality and pollution plume '
       'mapping, permafrost and ecological research, beetle surveillance, '
       'post-fire recovery studies, and research in places humans cannot '
       'safely go (collapsed mines, radiation zones, active fire lines, '
       'polar ice).')
bullet('The simulator in the repo demonstrates this: when an ignition '
       'event fires, tasking messages propagate over the mesh and the '
       'swarm converges — 7 of 10 bees on station while message delivery '
       'stays at 100%.')
para('Energy honesty: bees are designed around perch-and-report duty '
     'cycling — measure, transmit, sleep, repeat — not continuous '
     'flight. Solar keeps them alive indefinitely in season; chargers '
     'replenish them. This is deliberately low-tech so units survive '
     'Canadian winters and bear country.')

# ============================ 7. THE PHONE & OFFLINE DIGNITY ============================
h('7. The phone — and "offline dignity"')
para('The most important word in the product vocabulary is dignity: the '
     'system should be *useful*, not merely *present*, when everything '
     'else fails. That means:')
bullet('A phone that shows maps, first-aid guides, government forms, '
       'schoolwork, and community messages with literally zero signal.')
bullet('Messaging that works phone-to-phone over the mesh even when '
       'there is no tower, no satellite pass, and no internet.')
bullet('An SOS that works because it has three independent paths — mesh, '
       'cellular, satellite — and picks whichever exists.')
bullet('A community notice board (the Totem) that works for people who '
       'will never own a smartphone.')
para('The phone itself is still a concept — but the protocol it will '
     'speak is already built and tested in Rust (signed link-state '
     'routing, encrypted envelopes, 46 passing tests), and the node '
     'software it will run is already working on ordinary computers '
     'today.')

# ============================ 8. THE LONG GAME — SPACE ============================
h('8. The long game — from ground mesh to orbit')
para('The stated ambition is global rural/remote communications — '
     'ultimately a sovereign Canadian network that can stand beside '
     'Starlink in the places Starlink does not economically serve. The '
     'honest staging:')
numbered('NOW — ground mesh for unserved communities (hardware exists, '
         'software works, pilots are the next step).')
numbered('NEAR — borrow satellite capacity (existing L-band messengers, '
         'Starlink/Iridium as backhaul) so remote nodes get an internet '
         'path without owning satellites.')
numbered('MID — ArcticChain smallsats: a modest constellation of '
         'polar-leaning satellites handling alerts and IoT data. This '
         'needs kilobytes of capacity, not megabits — far fewer '
         'satellites than a broadband constellation, which is what makes '
         'it fundable.')
numbered('FAR — sovereign NGSO broadband and, separately, helping '
         'catalyze Canadian orbital launch capability. This is a '
         'decade-scale goal and is described as such everywhere in the '
         'plan.')
para('The strategic point often missed: Starlink\'s economics require '
     'dense, paying subscribers. Polar regions, boreal forest, remote '
     'industry, and Indigenous communities are structurally unprofitable '
     'for them. A Canadian polar constellation owns a market the '
     'incumbent cannot copy without abandoning its own model. That — '
     'not "beat Starlink at bandwidth" — is the credible version of the '
     'ambition, and it is the version used in every pitch document.')

# ============================ 9. WHAT IS REAL TODAY ============================
h('9. What is real today — the honest inventory')
para('Because this project lives or dies on credibility, here is exactly '
     'what exists versus what is planned:')

h('Working and tested', 2)
bullet('Mesh protocol in Rust — signed routing, encrypted envelopes, '
       '46 passing tests.')
bullet('Node agent (Python) — store-and-forward, peer discovery, '
       'HMAC-signed frames (forged frames verified rejected), '
       'internet backhaul bridge, live dashboard on :8080.')
bullet('Two-node acceptance test — passes end-to-end on one machine '
       'using the virtual radio; the same code path targets real LoRa '
       'hardware.')
bullet('Mesh simulator — range-limited model with mobile bees and swarm '
       'tasking; produces delivery/latency/coverage reports.')
bullet('33-sheet ANSI B blueprint set — every fleet member, electronics, '
       'power, assembly, finish/materials, component decision matrices. '
       'Audit-verified, zero layout collisions.')
bullet('Five printable-part STLs generated from parametric Python — '
       'perch clip, battery tray, Totem and Anchor shells.')
bullet('Mite firmware sketch for ESP32-S3 + SX1262 — written to the '
       'pin map, needs hardware to validate.')
bullet('Field-test checklist for the first two-node deployment.')

h('Designed but not yet built', 2)
bullet('Physical L1 Brick and Mite prototypes (BOM exists; parts are '
       'orderable; assembly is the next milestone).')
bullet('ArcticPhone (concept + blueprints + spec; no prototype hardware).')
bullet('Seed motes (research concept, TRL ~2 — printed transient '
       'electronics are not field-ready).')
bullet('Meridian satellite (mission concept only).')

h('Explicitly not claimed', 2)
bullet('No global broadband exists today. No satellites are launched. '
       'No Starlink-equivalent capacity exists. The ground network is '
       'the product; space is the staged path.')

# ============================ 10. BUSINESS & OWNERSHIP ============================
h('10. Who owns it and how it could sustain itself')
para('Emebet Inc. (emebetos.ca, Edmonton) is the company and sole '
     'proprietary owner. Surafel Negussie is planner and maker. The '
     'business model, briefly: sell node hardware at healthy margin over '
     'BOM, charge communities for software/services, sell managed '
     'monitoring (wildfire, agriculture, assets) as recurring revenue, '
     'and fund the space program from demonstrated demand. The '
     '16-week student build program doubles as recruiting and public '
     'relations — every cohort is a pipeline of trained technicians.')
para('The pitch documents (ARCTICCHAIN_PITCH.docx / _v2.docx in docs/) '
     'cover the investor/government/university versions of this story.')

# ============================ 11. GLOSSARY ============================
h('11. Glossary — terms used above')
gloss = [
    ('Mesh', 'A network where each device forwards traffic for others, so '
             'no single tower or hub is required.'),
    ('Store-and-forward', 'Messages are saved and retried until a path '
             'exists — delivery may be late but is not lost.'),
    ('LoRa / SX1262', 'A licence-free long-range radio chip; ~5–15 km '
             'per hop in good conditions at 915 MHz.'),
    ('E-Ink / E-Paper', 'A display that looks like paper, needs power only '
             'when the image changes — readable in sunlight, months on '
             'a battery.'),
    ('Perch-and-report', 'The bee energy model: sleep, measure, transmit, '
             'sleep — solar keeps it alive indefinitely.'),
    ('Backhaul', 'The link from the local mesh to the wider internet — '
             'LTE, fibre, or satellite, owned by the community.'),
    ('NGSO', 'Non-geostationary orbit — satellites that move, enabling '
             'lower-latency global coverage (Starlink/OneWeb class).'),
    ('TRL', 'Technology readiness level; 2 = concept formulated, 9 = '
             'proven in operation.'),
]
for term, definition in gloss:
    p = doc.add_paragraph()
    r = p.add_run(term + ' — ')
    r.bold = True
    p.add_run(definition)

# ============================ FOOTER ============================
doc.add_paragraph()
para('— End of explainer —', italic=True)
para('ArcticChain · Emebet Inc. · Proprietary & Confidential · '
     'SURAFEL NEGUSSIE — Planner/Maker', size=9)

out = 'ARCTICCHAIN_EXPLAINER.docx'
doc.save(out)
print('saved', out)
