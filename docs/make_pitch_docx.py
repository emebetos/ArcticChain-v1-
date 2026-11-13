# -*- coding: utf-8 -*-
"""Generate ArcticChain pitch document as .docx"""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# Page setup — letter
for section in doc.sections:
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)

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

# ---- Title ----
t = doc.add_heading('ARCTICCHAIN', 0)
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run('Sovereign Rural Connectivity for Canada')
r.bold = True
r.font.size = Pt(14)
r.font.color.rgb = RGBColor(0x2a, 0x5a, 0x8a)

meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = meta.add_run('Prepared by Surafel Negussie — Emebet Inc. · emebetos.ca\nPROPRIETARY & CONFIDENTIAL')
r.font.size = Pt(9)
r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

# ---- One-liner ----
h('The One-Liner', 1)
para('Starlink sells internet to people who can already afford it and see the sky. '
     'ArcticChain gives a community its own network — messages, alerts, sensors, and '
     'services — that works when nothing else does, and gets better every time a '
     'neighbour joins.', bold=True)

para('Today that network is a ground mesh. The endgame is a sovereign Canadian '
     'constellation — ArcticChain becomes the space-based network for rural and '
     'remote places around the globe: reliable communications where towers do not '
     'exist and sky view is not guaranteed.', bold=True)

para('You are not building a phone company. You are building the connectivity '
     'layer for the last 10–20% of Canada first — and eventually for unserved '
     'regions worldwide. The ground mesh funds and proves the demand; the '
     'constellation scales it to the planet.')

# ---- Problem ----
h('The Problem', 1)
para('Rogers, Bell, and Telus will not economically serve rural and remote Canada — '
     'the math does not work at low density. Starlink covers some of it but costs '
     '~$400 hardware plus monthly fees, needs clear sky, and is foreign-owned '
     'infrastructure with foreign data routing. Meanwhile:')
for b in [
    'Wildfires threaten communities with zero warning because there is no sensor grid.',
    'Clinics cannot send lab results or get telehealth triage when towers fail.',
    'Hunters, workers, and remote residents have no SOS path off-grid.',
    'First Nations communities often have no service at all — a sovereignty issue, '
    'not just a tech gap.',
]:
    doc.add_paragraph(b, style='List Bullet')

# ---- Product ----
h('The Product — A Fleet, Not a Device', 1)
para('The key insight: it is a platform, not a product. Every device is a node on the '
     'same signed mesh. Seven hardware shapes in the blueprint set:')

tbl = doc.add_table(rows=1, cols=3)
tbl.style = 'Light Grid Accent 1'
hdr = tbl.rows[0].cells
hdr[0].text = 'Device'
hdr[1].text = 'What it is'
hdr[2].text = 'Price class'
rows = [
    ('L1 Brick', 'Field node — handheld mailbox, mesh repeater, E-Ink bulletin board, '
     'SOS beacon. CM5 + LoRa + LTE + e-paper + solar. Buildable today with a real BOM.',
     '~$600–1,200'),
    ('S Mite', 'The "bee" — 90 mm perchable swarm unit. Solar-powered, clips to branches, '
     'forms a collective mobile sensor field for wildfire/flood/beetle surveillance.',
     '~$60–110/unit'),
    ('E Totem', 'Community public board — pole-mounted E-Ink display + mesh node. '
     'Free clinic days, road closures, emergency alerts — no smartphone needed.',
     'hub-scale'),
    ('A Anchor', 'Charging station — docks Mites/phones, solar + LiFePO4, LTE/satellite '
     'backhaul. The infrastructure backbone.',
     'station-scale'),
    ('P ArcticPhone', 'Rural-first phone: tri-radio (LoRa mesh + LTE + satellite SOS), '
     'every phone is a repeater, offline dignity suite, repairable with hand tools, '
     'swappable mission modules.',
     'concept'),
    ('D Seed', 'Degradable sensor motes — printed-electronics "computational dust" '
     'seeded over a fuel break for fire season, then dissolves. Honest R&D.',
     'research'),
    ('H Meridian', 'Satellite payload concept — the mesh IS the ground segment. Borrow '
     'capacity now, launch your own smallsats later.',
     'vision'),
]
for name, what, price in rows:
    c = tbl.add_row().cells
    c[0].text = name
    c[1].text = what
    c[2].text = price
    for cell in c:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(9.5)

# ---- How it works ----
h('How It Actually Works', 1)
para('The technical core is already real, not vaporware:', bold=True)
for b in [
    'Signed mesh protocol — Ed25519 link-state routing, X25519 + ChaCha20-Poly1305 '
    'end-to-end encryption. Government/emergency-grade security, 46 Rust tests passing.',
    'Store-and-forward agent — SQLite-backed, works days offline, syncs opportunistically. '
    'Messages, alerts, and sensor data flow when connectivity exists — no bars required.',
    '915 MHz LoRa — unlicensed Canadian ISM band, 5–15 km range per hop, mesh repeats '
    'it further. Zero spectrum licensing cost.',
    'Solar-first power — duty-cycled nodes sip microwatts; a perched Mite harvests '
    'more sun than it burns.',
    'Offline-first everything — the phone works fully with zero bars; the Totem needs '
    'no internet; data stays on community infrastructure.',
]:
    doc.add_paragraph(b, style='List Bullet')

# ---- Moat ----
h('Why ArcticChain Wins — The Moat', 1)
for i, (t_, d_) in enumerate([
    ('Network effects', 'Every phone/node sold adds a repeater. The 100th user has better '
     'coverage than the 1st. Competitors cannot copy deployed density.'),
    ('Community ownership', 'The mesh belongs to the town, not a carrier. That is a '
     'procurement argument AND a loyalty argument.'),
    ('Data sovereignty', 'Traffic routes community mesh first. Regulators and Indigenous '
     'communities both want this.'),
    ('Applications flywheel', 'Every new use (wildfire, agriculture, health, emergency) is '
     'another app on the same mesh. The platform is the product.'),
    ('Open hardware + training', 'The BOM is a 16-week student build program. Every cohort '
     'is recruiting and PR.'),
], 1):
    p = doc.add_paragraph()
    r = p.add_run(f'{t_}: ')
    r.bold = True
    p.add_run(d_)

# ---- Business model ----
h('Business Model', 1)
tbl2 = doc.add_table(rows=1, cols=2)
tbl2.style = 'Light Grid Accent 1'
hdr = tbl2.rows[0].cells
hdr[0].text = 'Stream'
hdr[1].text = 'Anchor'
for s_, a_ in [
    ('Hardware', 'Node kits $600–1,200 · hubs $5–15K — healthy margin on a $335–525 BOM'),
    ('Software', 'ArcticChain OS dashboards/alerts — $10–40/node/month or community license'),
    ('Services', 'Managed wildfire/ag/asset monitoring — $2–10K/site/year'),
    ('Emergency retainers', 'Annual contracts with municipalities/counties'),
    ('Training', 'Student cohorts, technician certification'),
    ('Space (later)', 'Satellite services, launch ecosystem — the long game'),
]:
    c = tbl2.add_row().cells
    c[0].text = s_
    c[1].text = a_
    for cell in c:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(9.5)

para('Capital efficiency is the pitch point: no tower capex, no licensed spectrum — '
     'the two cost structures that kill rural telecom do not apply to ArcticChain.')

# ---- Roadmap ----
h('Roadmap (Honest Gates)', 1)
for b in [
    'Now — build 2 L1 Bricks (~$670–1,050), prove the mesh end-to-end.',
    'Year 1 — Tier-1 deployments + Totem/Anchor + first paying wildfire/ag pilot.',
    'Year 2 — ArcticPhone + Mite swarm pilots (fire season) + ArcticChain OS.',
    'Year 3–4 — Indigenous sovereignty programs, emergency backbone contracts, '
    'first ArcticChain smallsats (borrowed launch).',
    'Year 5+ — sovereign polar constellation for messaging/IoT globally, '
    'NGSO broadband path, Canadian launch ecosystem — the ignition.',
]:
    doc.add_paragraph(b, style='List Bullet')

# ---- The endgame ----
h('The Endgame — A New Space Network', 1)
para('The satellite layer is not a pivot — it is the destination the ground network '
     'was built to reach:', bold=True)
for b in [
    'S1 — ArcticChain smallsats (yr 2–4): polar-inclination CubeSats and smallsats '
    'doing store-and-forward messaging and IoT for Canada and partner regions. '
    'Polar orbits cover what Starlink\u2019s 53\u00b0 shells thin out on — the North.',
    'S2 — Sovereign NGSO broadband (yr 5+): the constellation grows into a genuine '
    'competitor for rural/remote global coverage — the places where "as good '
    'communications" means reliable, not gigabit.',
    'S3 — Canadian launch (yr 5+): the constellation becomes the anchor payload '
    'demand that justifies domestic orbital launch — the flywheel that ignites '
    'a Canadian space program.',
]:
    doc.add_paragraph(b, style='List Bullet')
para('Physics note for technical reviewers: higher orbits win for latency-tolerant '
     'store-forward (coverage per satellite, fewer satellites needed); LEO wins for '
     'broadband. ArcticChain\u2019s messaging/IoT constellation deliberately exploits '
     'the orbit economics Starlink ignores — and that is the defensible wedge.',
     italic=True)

# ---- Audience angles ----
h('Pitch Angles by Audience', 1)
for t_, d_ in [
    ('Government / grants', 'Community-owned critical infrastructure for the unserved — '
     'complements Starlink, does not compete. Wildfire mesh is the flagship wedge.'),
    ('Investors', 'The picks-and-shovels layer of rural Canada — hardware margin + '
     'software subscription + network effects, with a defensible protocol already built.'),
    ('Universities', '16-week build kit + research programs (swarm sensing, degradable '
     'electronics, mesh protocols) — students build real deployable nodes.'),
    ('Indigenous communities', 'Your network, your data, your jobs — sovereignty as a '
     'feature, not a slogan.'),
    ('Industry (ag, resource)', 'Connectivity where towers are not — telemetry, tracking, '
     'alerts, at node prices.'),
]:
    p = doc.add_paragraph()
    r = p.add_run(f'{t_}: ')
    r.bold = True
    p.add_run(d_)

# ---- Close ----
h('The Close', 1)
para('You are not asking anyone to believe a vision — you are showing them a working '
     'protocol, a buildable BOM, a printed blueprint set, a market the giants '
     'abandoned on the ground, and a credible path to the sky. The pitch is not '
     '"we will beat Starlink at bandwidth." It is: rural and remote places deserve '
     'communications as good as anyone\u2019s — and ArcticChain is building the '
     'network that gets there, community-owned, Canadian, and inevitable.', bold=True)

doc.save(r'C:\Users\user\New folder\arcticchain\docs\ARCTICCHAIN_PITCH_v2.docx')
print('saved')
