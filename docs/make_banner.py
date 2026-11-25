"""Generate docs/banner.svg: an animated sequence diagram of the BE-03 auth flow (pure SVG + CSS, loops)."""
import sys

OUT = sys.argv[1]
W, H = 1280, 640
LOOP = 14.0  # seconds

# lifelines (x) inside the right-hand card
CX, AX, SX = 770, 960, 1150
LANES = {"C": CX, "A": AX, "S": SX}

# (from, to, label, kind)  kind: req | ok | bad | sup
MSGS = [
    ("C", "A", "POST /auth/login", "req"),
    ("A", "S", "sign_in_with_password()", "sup"),
    ("S", "A", "signed JWT", "ok"),
    ("A", "C", "200 · access_token", "ok"),
    ("C", "A", "GET /protected/profile + Bearer", "req"),
    ("A", "S", "get_user(token)", "sup"),
    ("S", "A", "valid ✓", "ok"),
    ("A", "C", "200 · { id, email }", "ok"),
    ("C", "A", "Bearer eyJ…X  (one char changed)", "bad"),
    ("A", "C", "401 · Invalid or expired token", "bad"),
]
COLORS = {"req": "#8FB8FF", "sup": "#B9D3C8", "ok": "#6FDCA4", "bad": "#FF8A8E"}
Y0, DY = 214, 37
STEP = 8.4          # % of the loop between messages
START = 3.0         # % before the first message
FADE_OUT = (93.0, 98.0)

css, body = [], []

for i, (a, b, label, kind) in enumerate(MSGS):
    x1, x2 = LANES[a], LANES[b]
    y = Y0 + i * DY
    s = START + i * STEP
    col = COLORS[kind]
    d = 1 if x2 > x1 else -1
    # arrow + label fade in
    css.append(f"@keyframes m{i}{{0%,{s:.1f}%{{opacity:0}}{s + 2.6:.1f}%,{FADE_OUT[0]}%{{opacity:1}}{FADE_OUT[1]}%,100%{{opacity:0}}}}")
    css.append(f".m{i}{{animation:m{i} {LOOP}s linear infinite}}")
    # travelling dot
    css.append(f"@keyframes d{i}{{0%,{s:.1f}%{{transform:translateX(0);opacity:0}}{s + 0.3:.1f}%{{opacity:1}}"
               f"{s + 2.6:.1f}%{{transform:translateX({x2 - x1 - d * 8}px);opacity:1}}{s + 3.2:.1f}%,100%{{transform:translateX({x2 - x1 - d * 8}px);opacity:0}}}}")
    css.append(f".d{i}{{animation:d{i} {LOOP}s cubic-bezier(.4,0,.2,1) infinite}}")
    tip = x2 - d * 6
    lx = (x1 + x2) / 2
    anchor = "middle"
    # long labels on the client<->api lane would cover the lifeline; keep them centred above the arrow
    body.append(
        f'<g class="m{i} anim">'
        f'<line x1="{x1 + d * 6}" y1="{y}" x2="{tip - d * 6}" y2="{y}" stroke="{col}" stroke-width="2"'
        f'{" stroke-dasharray=\"5 4\"" if kind in ("ok", "bad") and a != "C" else ""}/>'
        f'<path d="M{tip},{y} l{-d * 10},-5 v10 z" fill="{col}"/>'
        f'<text x="{lx}" y="{y - 8}" text-anchor="{anchor}" class="lbl" fill="{col}">{label}</text>'
        f'</g>'
        f'<circle class="d{i} anim" cx="{x1 + d * 8}" cy="{y}" r="5" fill="{col}"/>'
    )

# API node flashes green on the 200, red on the 401
s_ok, s_bad = START + 7 * STEP, START + 9 * STEP
css.append(f"@keyframes okf{{0%,{s_ok:.1f}%{{opacity:0}}{s_ok + 1.5:.1f}%{{opacity:.9}}{s_ok + 6:.1f}%,100%{{opacity:0}}}}")
css.append(f"@keyframes badf{{0%,{s_bad:.1f}%{{opacity:0}}{s_bad + 1.5:.1f}%{{opacity:.9}}{s_bad + 6:.1f}%,100%{{opacity:0}}}}")
css.append(f".okf{{animation:okf {LOOP}s linear infinite}}.badf{{animation:badf {LOOP}s linear infinite}}")
# padlock shackle closes when the guard is checking
css.append(f"@keyframes blink{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}.blink{{animation:blink 1.6s ease-in-out infinite}}")
# accessibility: no motion -> show the whole diagram, static
css.append("@media (prefers-reduced-motion: reduce){.anim,.okf,.badf,.blink{animation:none!important}"
           + "".join(f".m{i}{{opacity:1}}" for i in range(len(MSGS)))
           + "".join(f".d{i}{{opacity:0}}" for i in range(len(MSGS))) + ".okf,.badf{opacity:0}}")

def node(x, title, sub, accent):
    return (f'<rect x="{x - 78}" y="128" width="156" height="52" rx="10" fill="#0B2B2D" stroke="{accent}" stroke-width="1.5"/>'
            f'<text x="{x}" y="151" text-anchor="middle" class="node">{title}</text>'
            f'<text x="{x}" y="169" text-anchor="middle" class="nsub">{sub}</text>'
            f'<line x1="{x}" y1="182" x2="{x}" y2="{Y0 + (len(MSGS) - 1) * DY + 22}" stroke="#2B4A44" stroke-width="1.5" stroke-dasharray="3 5"/>')

flash = (f'<rect class="okf" x="{AX - 82}" y="124" width="164" height="60" rx="12" fill="none" stroke="#6FDCA4" stroke-width="4" opacity="0"/>'
         f'<rect class="badf" x="{AX - 82}" y="124" width="164" height="60" rx="12" fill="none" stroke="#FF8A8E" stroke-width="4" opacity="0"/>')

lock = (f'<g class="blink" transform="translate({AX + 58},132)">'
        f'<path d="M3 9 V6 a5 5 0 0 1 10 0 V9" fill="none" stroke="#6FDCA4" stroke-width="2"/>'
        f'<rect x="0" y="9" width="16" height="12" rx="2" fill="#6FDCA4"/></g>')

chips = ""
x = 72
for text, bg, outline in [("POST", "#1FA971", False), ("GET", "#2F80ED", False), ("401", "#E5484D", False),
                          ("Supabase", "#6FDCA4", True), ("JWT", "#6FDCA4", True)]:
    w = 18 + 11 * len(text)
    if outline:
        chips += f'<rect x="{x}" y="372" width="{w}" height="36" rx="8" fill="none" stroke="{bg}" stroke-width="2"/>'
        chips += f'<text x="{x + w / 2}" y="396" text-anchor="middle" class="chip" fill="{bg}">{text}</text>'
    else:
        chips += f'<rect x="{x}" y="372" width="{w}" height="36" rx="8" fill="{bg}"/>'
        chips += f'<text x="{x + w / 2}" y="396" text-anchor="middle" class="chip" fill="#fff">{text}</text>'
    x += w + 10

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"
 aria-labelledby="t d">
<title id="t">Auth API: login and protect with Supabase Auth</title>
<desc id="d">Animated sequence diagram. The client logs in through the FastAPI server, Supabase returns a signed JWT,
the client calls /protected/profile with the bearer token and gets 200 after the server verifies it with Supabase;
a token with one character changed gets 401 Invalid or expired token.</desc>
<defs>
 <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
  <path d="M40 0H0V40" fill="none" stroke="#FFFFFF" stroke-opacity=".035"/>
 </pattern>
 <radialGradient id="g1" cx="85%" cy="15%" r="45%"><stop offset="0" stop-color="#2ECC80" stop-opacity=".18"/><stop offset="1" stop-color="#2ECC80" stop-opacity="0"/></radialGradient>
 <radialGradient id="g2" cx="10%" cy="95%" r="50%"><stop offset="0" stop-color="#1A7A4A" stop-opacity=".35"/><stop offset="1" stop-color="#1A7A4A" stop-opacity="0"/></radialGradient>
 <style>
  text{{font-family:"Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif}}
  .eyebrow{{font-size:17px;letter-spacing:3px;font-weight:600;fill:#6FDCA4}}
  .h1{{font-size:88px;font-weight:800;fill:#fff;letter-spacing:-2px}}
  .sub{{font-size:25px;fill:#B9D3C8}}
  .chip{{font-family:Consolas,"SF Mono",Menlo,monospace;font-size:17px;font-weight:700}}
  .name{{font-size:22px;font-weight:600;fill:#fff}}
  .node{{font-size:18px;font-weight:700;fill:#fff}}
  .nsub{{font-family:Consolas,"SF Mono",Menlo,monospace;font-size:12px;fill:#6E8F85}}
  .lbl{{font-family:Consolas,"SF Mono",Menlo,monospace;font-size:13.5px;font-weight:600}}
  .cap{{font-family:Consolas,"SF Mono",Menlo,monospace;font-size:13px;fill:#6E8F85}}
  {"".join(css)}
 </style>
</defs>
<rect width="{W}" height="{H}" fill="#051F21"/>
<rect width="{W}" height="{H}" fill="url(#g2)"/><rect width="{W}" height="{H}" fill="url(#g1)"/>
<rect width="{W}" height="{H}" fill="url(#grid)"/>

<text x="72" y="98" class="eyebrow">FLYRANK AI INTERNSHIP · BE-03 · A4</text>
<text x="66" y="196" class="h1">Auth API</text>
<text x="72" y="252" class="sub">Login &amp; protect with Supabase Auth.</text>
<text x="72" y="288" class="sub">One guard verifies every bearer token:</text>
<text x="72" y="324" class="sub">valid → 200, tampered → 401.</text>
{chips}
<text x="72" y="560" class="name">Azizul Abedin Azmi</text>
<circle cx="292" cy="553" r="3" fill="#4C7A6B"/>
<rect x="308" y="533" width="352" height="38" rx="19" fill="#fff"/>
<text x="332" y="558" font-size="17" font-weight="700" fill="#1A7A4A">✓</text>
<text x="352" y="558" font-size="16" font-weight="700" fill="#051F21">FlyRank verified</text>
<line x1="490" y1="543" x2="490" y2="561" stroke="#E4EAED"/>
<text x="500" y="557" class="chip" font-size="13" font-weight="400" fill="#6E7F84">FR-D1-A84A9-AB526</text>

<rect x="680" y="64" width="560" height="530" rx="18" fill="#020E0F" fill-opacity=".78" stroke="#6FDCA4" stroke-opacity=".22"/>
<circle cx="706" cy="88" r="6" fill="#2B4A44"/><circle cx="726" cy="88" r="6" fill="#2B4A44"/><circle cx="746" cy="88" r="6" fill="#2B4A44"/>
<text x="1214" y="93" text-anchor="end" class="cap">the trust triangle, live</text>
{node(CX, "Client", "curl · Swagger", "#8FB8FF")}
{node(AX, "FastAPI", "Depends(current_user)", "#6FDCA4")}
{node(SX, "Supabase", "Auth · IdP", "#B9D3C8")}
{flash}
{lock}
{"".join(body)}
</svg>
'''
open(OUT, "w", encoding="utf-8", newline="\n").write(svg)
print("wrote", OUT, len(svg), "bytes")

