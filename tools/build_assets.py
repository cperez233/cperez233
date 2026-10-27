"""Genera los SVG del README (portada, tarjeta de Stand y banner de contacto).

El texto se convierte a trazos, así GitHub los muestra igual en cualquier
navegador sin cargar fuentes. Cada pieza sale en claro/oscuro y en EN/ES.

    python -m venv .venv && .venv/bin/pip install fonttools
    .venv/bin/python tools/build_assets.py
"""

import json
import datetime
import math
import pathlib
import urllib.request

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONTS = pathlib.Path(__file__).resolve().parent / ".fonts"
GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
SOURCES = {
    "Anton-Regular.ttf": "anton/Anton-Regular.ttf",
    "DelaGothicOne-Regular.ttf": "delagothicone/DelaGothicOne-Regular.ttf",
    "Archivo.ttf": "archivo/Archivo%5Bwdth,wght%5D.ttf",
}

THEMES = {
    "dark": dict(bg="#111013", ink="#ece6d8", muted="#9a948a", accent="#e3b341", line="#2a272c"),
    "light": dict(bg="#f1ebdf", ink="#161418", muted="#6b655c", accent="#9a6a0c", line="#d9d1c2"),
}


def fetch_fonts():
    FONTS.mkdir(exist_ok=True)
    for name, src in SOURCES.items():
        target = FONTS / name
        if not target.exists():
            urllib.request.urlretrieve(GF + src, target)


class Face:
    def __init__(self, file, **axes):
        font = TTFont(FONTS / file)
        if axes:
            font = instancer.instantiateVariableFont(font, axes)
        self.glyphs = font.getGlyphSet()
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"]
        self.upm = font["head"].unitsPerEm

    def width(self, text, size, tracking=0.0):
        s = size / self.upm
        return sum(self.hmtx[self.cmap[ord(c)]][0] * s + tracking for c in text) - tracking

    def path(self, text, x, y, size, tracking=0.0, anchor="start"):
        s = size / self.upm
        if anchor != "start":
            w = self.width(text, size, tracking)
            x -= w if anchor == "end" else w / 2
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for c in text:
            name = self.cmap[ord(c)]
            self.glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
            x += self.hmtx[name][0] * s + tracking
        return pen.getCommands()

    def text(self, text, x, y, size, fill, tracking=0.0, anchor="start", extra=""):
        return f'<path{extra} fill="{fill}" d="{self.path(text, x, y, size, tracking, anchor)}"/>'


def wrap(face, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if face.width(trial, size) > max_w and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def svg(w, h, label, body, style=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{label}"><title>{label}</title>'
        f"<style>{style}@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}</style>"
        f"{body}</svg>"
    )


def halftone(t, pid, cx, cy, r):
    return (
        f'<defs><pattern id="{pid}" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">'
        f'<circle cx="4.5" cy="4.5" r="1.6" fill="{t["ink"]}" fill-opacity=".16"/></pattern>'
        f'<radialGradient id="{pid}g" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="{pid}m"><circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{pid}g)"/></mask></defs>'
        f'<rect width="100%" height="100%" fill="url(#{pid})" mask="url(#{pid}m)"/>'
    )


def menacing(face, t, spots, cls="go"):
    """ゴゴゴ: el sonido de la amenaza. Cada una late con su propio retraso."""
    out = []
    for i, (x, y, size, rot) in enumerate(spots):
        d = face.path("ゴ", x, y, size, anchor="middle")
        out.append(
            f'<g transform="rotate({rot} {x} {y - size / 2})"><path class="{cls}" '
            f'style="animation-delay:-{i * 0.37:.2f}s" fill="{t["accent"]}" d="{d}"/></g>'
        )
    return "".join(out)


GO_CSS = (
    ".go{transform-box:fill-box;transform-origin:center;animation:go 1.5s ease-in-out infinite}"
    "@keyframes go{0%,100%{transform:scale(1) translate(0,0)}25%{transform:scale(1.07) translate(-1.5px,1px)}"
    "50%{transform:scale(1) translate(1px,-1px)}75%{transform:scale(1.05) translate(0,1.5px)}}"
)


# --- Portada: el time stop de ZA WARUDO -------------------------------------

def cover(t, lang, anton, dela, arch, arch_r):
    W, H = 1200, 540
    cx, cy, R = 922, 262, 168
    copy = {
        "en": ("Bucaramanga, Colombia", "Full-stack developer · Content creator",
               "Systems Engineer, UNAB · Co-founder of Carpy"),
        "es": ("Bucaramanga, Colombia", "Desarrollador full-stack · Creador de contenido",
               "Ingeniero de Sistemas, UNAB · Cofundador de Carpy"),
    }[lang]

    b = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>', halftone(t, "ht", cx, cy, 330)]

    # Nombre y rol
    b.append(arch.text(copy[0], 64, 96, 19, t["muted"]))
    b.append(anton.text("CRIS", 58, 244, 160, t["ink"], tracking=2))
    b.append(anton.text("PÉREZ", 58, 424, 160, t["accent"], tracking=2))
    b.append(f'<rect x="64" y="448" width="56" height="4" fill="{t["ink"]}"/>')
    b.append(arch.text(copy[1], 64, 488, 23, t["ink"]))
    b.append(arch_r.text(copy[2], 64, 518, 18, t["muted"]))

    # Reloj
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="{t["bg"]}" stroke="{t["ink"]}" stroke-width="4"/>')
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{R - 14}" fill="none" stroke="{t["ink"]}" stroke-width="1.2"/>')
    for i in range(60):
        a = math.radians(i * 6)
        big = i % 15 == 0
        mid = i % 5 == 0
        r1 = R - 14 - (26 if big else 16 if mid else 7)
        sw = 7 if big else 3.5 if mid else 1.2
        x1, y1 = cx + r1 * math.sin(a), cy - r1 * math.cos(a)
        x2, y2 = cx + (R - 14) * math.sin(a), cy - (R - 14) * math.cos(a)
        b.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{t["ink"]}" stroke-width="{sw}"/>')
    # 10:10, horas y minutos quietos; el segundero hace el trabajo
    b.append(f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - 78}" stroke="{t["ink"]}" stroke-width="9" stroke-linecap="square" transform="rotate(-55 {cx} {cy})"/>')
    b.append(f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - 118}" stroke="{t["ink"]}" stroke-width="6" stroke-linecap="square" transform="rotate(60 {cx} {cy})"/>')
    b.append(f'<g class="sec"><line x1="{cx}" y1="{cy + 26}" x2="{cx}" y2="{cy - 136}" stroke="{t["accent"]}" stroke-width="3"/></g>')
    b.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="{t["accent"]}"/>')

    b.append(menacing(dela, t, [(612, 150, 60, -14), (650, 240, 76, -8), (622, 344, 94, -16),
                                (666, 452, 68, -6), (1134, 476, 56, 10)]))

    # La esfera: se expande desde el reloj e invierte todo lo que toca
    b.append(f'<circle class="za" cx="{cx}" cy="{cy}" r="1" fill="#fff"/>')
    # Solo se ve con el tiempo detenido (encima de la inversión, por eso usa el fondo como tinta)
    stop = "".join(dela.text(ch, 1142, 92 + i * 60, 50, t["bg"], anchor="middle") for i, ch in enumerate("時よ止まれ"))
    b.append(f'<g class="stop">{stop}</g>')

    # 16 s: 6 tics, se detiene el tiempo ~4 s, 6 tics más. 12 × 30° = vuelta completa.
    ticks = [0, 1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16]
    kf = "".join(f"{s / 16 * 100:.2f}%{{transform:rotate({i * 30}deg)}}" for i, s in enumerate(ticks))
    style = (
        GO_CSS
        + f".sec{{transform-origin:{cx}px {cy}px;animation:sec 16s steps(1,end) infinite}}@keyframes sec{{{kf}}}"
        + ".za{transform-box:fill-box;transform-origin:center;transform:scale(0);mix-blend-mode:difference;"
        "animation:za 16s cubic-bezier(.7,0,.3,1) infinite}"
        "@keyframes za{0%,37.5%{transform:scale(0)}41.5%,61%{transform:scale(1050)}65%,100%{transform:scale(0)}}"
        ".stop{opacity:0;animation:stop 16s linear infinite}"
        "@keyframes stop{0%,42%{opacity:0}43%,60%{opacity:1}60.5%,100%{opacity:0}}"
    )
    label = {
        "en": "Cris Pérez — full-stack developer and content creator, Bucaramanga, Colombia. A clock where time stops, JoJo style.",
        "es": "Cris Pérez — desarrollador full-stack y creador de contenido, Bucaramanga, Colombia. Un reloj donde el tiempo se detiene, al estilo JoJo.",
    }[lang]
    return svg(W, H, label, "".join(b), style)


# --- Tarjeta de Stand --------------------------------------------------------

STATS = [("破壊力", "C"), ("スピード", "B"), ("射程距離", "A"), ("持続力", "A"), ("精密動作性", "A"), ("成長性", "A")]
GRADE = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}


def stand(t, lang, anton, dela, arch, arch_r):
    W, H = 1200, 600
    cx, cy, R = 858, 296, 148
    copy = {
        "en": ("STAND USER", "Stand user — Cristian Pérez",
               "Builds software, websites and apps that businesses actually use, and makes content that "
               "goes viral. Has a cybersecurity streak: checks the locks before handing over the keys.",
               "Power · Speed · Range · Stamina · Precision · Potential"),
        "es": ("USUARIO DEL STAND", "Usuario del Stand — Cristian Pérez",
               "Construye software, páginas web y apps que los negocios usan de verdad, y crea contenido que "
               "se vuelve viral. Tiene aires de ciberseguridad: revisa las cerraduras antes de entregar las llaves.",
               "Poder · Velocidad · Alcance · Resistencia · Precisión · Potencial"),
    }[lang]

    b = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>', halftone(t, "hs", cx, cy, 300)]
    b.append(f'<rect x="24" y="24" width="{W - 48}" height="{H - 48}" fill="none" stroke="{t["ink"]}" stroke-width="3"/>')

    part_label = "PART 1" if lang == "en" else "PARTE 1"
    b.append(anton.text(part_label, 72, 98, 26, t["accent"], tracking=3))
    b.append(arch.text(copy[0], 72 + anton.width(part_label, 26, 3) + 18, 97, 17, t["muted"], tracking=3))
    b.append(dela.text("「", 58, 190, 64, t["accent"]))
    b.append(anton.text("PARANOID", 118, 180, 84, t["ink"], tracking=1))
    b.append(anton.text("ANDROID", 118, 268, 84, t["ink"], tracking=1))
    b.append(dela.text("」", 118 + anton.width("ANDROID", 84, 1) + 8, 286, 64, t["accent"]))
    b.append(dela.text("パラノイド・アンドロイド", 74, 322, 20, t["accent"], tracking=2))
    b.append(arch.text(copy[1], 72, 382, 22, t["ink"]))
    for i, line in enumerate(wrap(arch_r, copy[2], 19, 460)):
        b.append(arch_r.text(line, 72, 426 + i * 29, 19, t["muted"]))

    def pt(i, r):
        a = math.radians(-90 + i * 60)
        return cx + r * math.cos(a), cy + r * math.sin(a)

    for ring in range(1, 6):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, R * ring / 5) for i in range(6)))
        b.append(f'<polygon points="{pts}" fill="none" stroke="{t["ink"]}" stroke-opacity="{.25 if ring < 5 else 1}" stroke-width="{1 if ring < 5 else 2.5}"/>')
    for i in range(6):
        x, y = pt(i, R)
        b.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{t["ink"]}" stroke-opacity=".25"/>')
    vals = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, R * GRADE[g] / 5) for i, (_, g) in enumerate(STATS)))
    b.append(f'<polygon class="val" points="{vals}" fill="{t["accent"]}" fill-opacity=".38" stroke="{t["accent"]}" stroke-width="3" stroke-linejoin="round"/>')

    for i, (jp, g) in enumerate(STATS):
        x, y = pt(i, R + 44)
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="25" fill="{t["bg"]}" stroke="{t["ink"]}" stroke-width="2.5"/>')
        b.append(anton.text(g, x, y + 12, 34, t["accent"], anchor="middle"))
        lx, ly = pt(i, R + 44)
        ly += -40 if i == 0 else 50 if i == 3 else 0
        off = 0 if i in (0, 3) else (34 if i in (1, 2) else -34)
        anchor = "middle" if i in (0, 3) else ("start" if i in (1, 2) else "end")
        b.append(dela.text(jp, lx + off, ly + 7, 18, t["ink"], anchor=anchor))
    b.append(arch_r.text(copy[3], 72, H - 50, 15, t["muted"]))

    style = (
        f".val{{transform-origin:{cx}px {cy}px;animation:val 1.4s cubic-bezier(.2,.9,.2,1.15) both .3s}}"
        "@keyframes val{from{transform:scale(0) rotate(-40deg)}to{transform:none}}"
    )
    label = {
        "en": "JoJo-style Stand card. Stand: Paranoid Android. User: Cristian Pérez. Power C, Speed B, Range A, Stamina A, Precision A, Potential A.",
        "es": "Tarjeta de Stand estilo JoJo. Stand: Paranoid Android. Usuario: Cristian Pérez. Poder C, Velocidad B, Alcance A, Resistencia A, Precisión A, Potencial A.",
    }[lang]
    return svg(W, H, label, "".join(b), style)


# --- Contacto: "Oh? You're approaching me?" -----------------------------------

def approach(t, lang, anton, dela, arch, arch_r):
    W, H = 1200, 250
    line, sub = {
        "en": ("OH? YOU'RE APPROACHING ME?", "Websites, apps and custom software for your business."),
        "es": ("¿OH? ¿TE ACERCAS A MÍ?", "Páginas web, apps y software a la medida para tu negocio."),
    }[lang]
    size = 80
    b = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>', halftone(t, "ha", 1040, 125, 260)]
    b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{t["ink"]}"/>')
    b.append(anton.text(("PART 5" if lang == "en" else "PARTE 5"), 44, 58, 24, t["accent"], tracking=3))
    b.append(anton.text(line, 40, 150, size, t["ink"], tracking=1))
    b.append(arch_r.text(sub, 44, 202, 20, t["muted"]))
    b.append(menacing(dela, t, [(1020, 112, 52, -10), (1084, 150, 66, -4), (1148, 110, 54, 8)]))
    label = {"en": "Oh? You're approaching me? — contact", "es": "¿Oh? ¿Te acercas a mí? — contacto"}[lang]
    return svg(W, H, label, "".join(b), GO_CSS)


# --- Encabezados de sección: cada parte, como las partes de JoJo ---------------

PARTS = {
    "part-2": (2, {"en": "SELECTED WORK", "es": "TRABAJO SELECCIONADO"}, "作品集"),
    "part-3": (3, {"en": "ARSENAL", "es": "ARSENAL"}, "武器"),
    "part-4": (4, {"en": "ORA ORA ORA", "es": "ORA ORA ORA"}, "オラオラ"),
}


def part(key):
    num, title, kana = PARTS[key]

    def build(t, lang, anton, dela, arch, arch_r):
        W, H = 1200, 132
        b = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>', halftone(t, "hp", 1060, 66, 220)]
        b.append(anton.text(f'{"PART" if lang == "en" else "PARTE"} {num}', 44, 40, 22, t["accent"], tracking=3))
        b.append(anton.text(title[lang], 40, 104, 66, t["ink"], tracking=1))
        b.append(dela.text(kana, 1156, 104, 24, t["accent"], tracking=4, anchor="end"))
        b.append(f'<rect x="44" y="118" width="{W - 88}" height="4" fill="{t["ink"]}"/>')
        label = f'{"Part" if lang == "en" else "Parte"} {num} — {title[lang].title()}'
        return svg(W, H, label, "".join(b))

    return build


# --- Arsenal: el stack, en tinta ------------------------------------------------

ICONS = pathlib.Path(__file__).resolve().parent / "icons"
ARSENAL = [
    ({"en": "LANGUAGES", "es": "LENGUAJES"}, "言語",
     [("python", "Python"), ("typescript", "TypeScript"), ("javascript", "JavaScript"), ("java-plain", "Java"), ("php", "PHP")]),
    ({"en": "FRONT END", "es": "FRONT END"}, "フロント",
     [("react", "React"), ("nextdotjs", "Next.js"), ("vite", "Vite"), ("tailwindcss", "Tailwind"), ("framer", "Framer Motion")]),
    ({"en": "BACK END", "es": "BACK END"}, "バックエンド",
     [("laravel", "Laravel"), ("nodedotjs", "Node.js"), ("postgresql", "PostgreSQL"), ("langchain", "LangChain"), ("docker", "Docker")]),
    ({"en": "DEPLOY", "es": "DESPLIEGUE"}, "デプロイ",
     [("git", "Git"), ("githubactions", "GitHub Actions"), ("vercel", "Vercel"), ("azure-plain", "Azure"), ("linux", "Linux")]),
    ({"en": "SECURITY", "es": "SEGURIDAD"}, "セキュリティ",
     [("kalilinux", "Kali Linux"), ("burpsuite", "Burp Suite"), ("wireshark", "Wireshark"), ("owasp", "OWASP")]),
    ({"en": "CONTENT", "es": "CONTENIDO"}, "コンテンツ",
     [("aftereffects-plain", "After Effects"), ("obsstudio", "OBS"), ("tiktok", "TikTok"), ("instagram", "Instagram"),
      ("youtube", "YouTube"), ("twitch", "Twitch")]),
]


def icon(file, x, y, size, fill):
    import re
    src = (ICONS / f"{file}.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()]
    paths = "".join(f'<path d="{d}"/>' for d in re.findall(r'<path[^>]*?\sd="([^"]+)"', src))
    s = size / max(vb[2], vb[3])
    return f'<g fill="{fill}" transform="translate({x} {y}) scale({s:.4f}) translate({-vb[0]} {-vb[1]})">{paths}</g>'


def arsenal(t, lang, anton, dela, arch, arch_r):
    W, row_h, top = 1200, 104, 24
    H = top * 2 + row_h * len(ARSENAL)
    b = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>', halftone(t, "hr", 1100, 80, 320)]
    for r, (label, kana, items) in enumerate(ARSENAL):
        y = top + r * row_h
        if r:
            b.append(f'<rect x="44" y="{y}" width="{W - 88}" height="1.5" fill="{t["ink"]}" fill-opacity=".22"/>')
        b.append(f'<g class="row" style="animation-delay:{r * 0.12:.2f}s">')
        b.append(anton.text(label[lang], 44, y + 56, 34, t["ink"], tracking=1.5))
        b.append(dela.text(kana, 46, y + 84, 14, t["accent"], tracking=2))
        for i, (file, name) in enumerate(items):
            cx = 380 + i * 150
            b.append(icon(file, cx - 20, y + 18, 40, t["ink"]))
            b.append(arch.text(name, cx, y + 86, 15, t["muted"], anchor="middle"))
        b.append("</g>")
    style = ".row{animation:row .7s cubic-bezier(.2,.8,.2,1) both}@keyframes row{from{opacity:0;transform:translateX(-16px)}}"
    label = {"en": "Stack", "es": "Stack"}[lang] + ": " + "; ".join(
        f'{l[lang].title()}: {", ".join(n for _, n in items)}' for l, _, items in ARSENAL)
    return svg(W, H, label, "".join(b), style)


# --- Lenguajes: el pastel, en tinta ---------------------------------------------

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
LANG_STATS = pathlib.Path(__file__).resolve().parent / "languages.json"


def languages(t, lang, anton, dela, arch, arch_r):
    """Dona con las líneas de código por lenguaje (tools/language_stats.py)."""
    data = json.loads(LANG_STATS.read_text())
    shown = {k: v for k, v in data["languages"].items() if v / sum(data["languages"].values()) >= 0.01}
    total = sum(shown.values())
    W, H = 1200, 400
    cx, cy, R, r = 250, 206, 150, 82
    ink, acc, bg = t["ink"], t["accent"], t["bg"]
    fills = [(acc, 1), (ink, 1), (acc, .55), (ink, .6), ("tone", 1), (acc, .3), (ink, .35), (ink, .18)]
    copy = {
        "en": ("BY THE NUMBERS", "数字", "From the interface to the server.",
               f'{data["repos"]} repositories · lines of code · {datetime.date.fromisoformat(data["date"]).strftime("%b %Y")}',
               "LINES OF CODE", "Languages"),
        "es": ("EN NÚMEROS", "数字", "De la interfaz al servidor.",
               f'{data["repos"]} repositorios · líneas de código · {MESES[datetime.date.fromisoformat(data["date"]).month - 1]} {datetime.date.fromisoformat(data["date"]).year}',
               "LÍNEAS DE CÓDIGO", "Lenguajes"),
    }[lang]

    def paint(i):
        color, op = fills[i]
        return ('url(#tone)', "") if color == "tone" else (color, f' fill-opacity="{op}"')

    b = [f'<rect width="{W}" height="{H}" fill="{bg}"/>', halftone(t, "hl", 1060, 110, 260)]
    b.append(
        f'<defs><pattern id="tone" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">'
        f'<rect width="7" height="7" fill="{bg}"/><circle cx="3.5" cy="3.5" r="1.9" fill="{ink}"/></pattern></defs>'
    )
    b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{ink}"/>')

    # Dona
    wedges, a0 = [], -math.pi / 2
    for i, (name, n) in enumerate(shown.items()):
        a1 = a0 + 2 * math.pi * n / total
        big = 1 if a1 - a0 > math.pi else 0
        x0, y0, x1, y1 = cx + R * math.cos(a0), cy + R * math.sin(a0), cx + R * math.cos(a1), cy + R * math.sin(a1)
        x2, y2, x3, y3 = cx + r * math.cos(a1), cy + r * math.sin(a1), cx + r * math.cos(a0), cy + r * math.sin(a0)
        fill, extra = paint(i)
        wedges.append(
            f'<path d="M{x0:.1f} {y0:.1f}A{R} {R} 0 {big} 1 {x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}A{r} {r} 0 {big} 0 {x3:.1f} {y3:.1f}Z" '
            f'fill="{fill}"{extra} stroke="{bg}" stroke-width="4" stroke-linejoin="round"/>'
        )
        a0 = a1
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{R + 12}" fill="none" stroke="{ink}" stroke-width="3"/>')
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{r - 12}" fill="none" stroke="{ink}" stroke-width="1.5" stroke-opacity=".5"/>')
    b.append(f'<g class="pie">{"".join(wedges)}</g>')
    b.append(anton.text(f"{round(total / 1000)}K", cx, cy + 14, 52, ink, anchor="middle", tracking=1))
    b.append(arch.text(copy[4], cx, cy + 40, 13, t["muted"], anchor="middle", tracking=1.5))

    # Título
    b.append(anton.text(copy[0], 540, 76, 44, ink, tracking=1))
    b.append(dela.text(copy[1], 1156, 76, 22, acc, tracking=4, anchor="end"))
    b.append(f'<rect x="544" y="92" width="56" height="4" fill="{ink}"/>')
    b.append(arch.text(copy[2], 540, 128, 20, t["muted"]))

    # Leyenda: dos columnas de cuatro
    for i, (name, n) in enumerate(shown.items()):
        col, row = divmod(i, 4)
        x, y = 544 + col * 320, 156 + row * 56
        fill, extra = paint(i)
        b.append(f'<g class="row" style="animation-delay:{i * 0.08:.2f}s">')
        b.append(f'<rect x="{x}" y="{y}" width="30" height="30" fill="{fill}"{extra} stroke="{ink}" stroke-width="2"/>')
        b.append(arch.text(name, x + 46, y + 22, 21, ink))
        b.append(anton.text(f"{n / total * 100:.0f}%" if n / total >= .095 else f"{n / total * 100:.1f}%",
                            x + 288, y + 26, 32, acc, anchor="end"))
        b.append(f'<rect x="{x}" y="{y + 40}" width="288" height="1.5" fill="{ink}" fill-opacity=".22"/>')
        b.append("</g>")
    b.append(arch_r.text(copy[3], 544, H - 22, 15, t["muted"]))

    style = (
        GO_CSS
        + f".pie{{transform-origin:{cx}px {cy}px;animation:pie 1.2s cubic-bezier(.2,.9,.2,1.1) both .2s}}"
        "@keyframes pie{from{transform:rotate(-140deg) scale(.55);opacity:0}}"
        ".row{animation:row .7s cubic-bezier(.2,.8,.2,1) both}@keyframes row{from{opacity:0;transform:translateX(-16px)}}"
    )
    label = f'{copy[5]}: ' + ", ".join(f"{k} {v / total * 100:.0f}%" for k, v in shown.items())
    return svg(W, H, label, "".join(b), style)


# --- Botones: enlaces como paneles inclinados, con sombra dura de manga ----------

BTN_INK, BTN_CREAM, BTN_GOLD = "#161418", "#ece6d8", "#e3b341"
SKEW = 10  # desplazamiento horizontal de la inclinación (≈ 12°)
BUTTONS = [
    # clave, etiqueta {en, es}, subtítulo, ícono
    ("web", {"en": "WEB", "es": "WEB"}, "cristianperez.me", "vercel"),
    ("email", {"en": "EMAIL", "es": "CORREO"}, "crisperezm879@gmail.com", "gmail"),
    ("linkedin", {"en": "LINKEDIN", "es": "LINKEDIN"}, "cristianperez879m", "linkedin"),
    ("tiktok", {"en": "TIKTOK", "es": "TIKTOK"}, "@criscx1905 · 32K+", "tiktok"),
    ("instagram", {"en": "INSTAGRAM", "es": "INSTAGRAM"}, "@criscx1905", "instagram"),
    ("youtube", {"en": "YOUTUBE", "es": "YOUTUBE"}, "Tostu", "youtube"),
    ("twitch", {"en": "TWITCH", "es": "TWITCH"}, "tostu", "twitch"),
    ("linktree", {"en": "LINKTREE", "es": "LINKTREE"}, "crxscx", "linktree"),
    ("carpy", {"en": "CARPY", "es": "CARPY"}, "carpy.tech", None),
    ("quote", {"en": "REQUEST A QUOTE", "es": "PEDIR COTIZACIÓN"}, None, "gmail"),
]


def button(label, sub, icon_file, primary, anton, arch, arch_r):
    """Panel inclinado: pestaña con el ícono a la izquierda, texto a la derecha."""
    H, tab, pad = 40, 46, 16
    body_fill, edge = (BTN_GOLD, BTN_INK) if primary else (BTN_INK, BTN_GOLD)
    tab_fill, tab_ink = (BTN_INK, BTN_GOLD) if primary else (BTN_GOLD, BTN_INK)
    text_ink, sub_ink = (BTN_INK, BTN_INK) if primary else (BTN_CREAM, "#b9b2a4")
    label_w = anton.width(label, 18, 1.4)
    sub_w = arch_r.width(sub, 11.5) if sub else 0
    W = int(tab + pad + max(label_w, sub_w) + pad + SKEW)
    sh = 3  # sombra dura

    def para(x0, x1):
        return f"{x0 + SKEW},0 {x1},0 {x1 - SKEW},{H} {x0},{H}"

    shadow = (f'fill="{BTN_INK}" stroke="{BTN_GOLD}" stroke-width="1.5"' if primary
              else f'fill="{BTN_GOLD}" fill-opacity=".9"')
    b = [
        f'<polygon points="{para(0, W)}" transform="translate({sh} {sh})" {shadow}/>',
        f'<polygon points="{para(0, W)}" fill="{body_fill}" stroke="{edge}" stroke-width="2.5" stroke-linejoin="miter"/>',
        f'<polygon points="{para(0, tab + SKEW)}" fill="{tab_fill}"/>',
    ]
    cx, cy = (tab + SKEW) / 2 + 1, H / 2
    if icon_file:
        b.append(icon(icon_file, cx - 10, cy - 10, 20, tab_ink))
    else:  # flecha ↗ para enlaces sin marca
        b.append(f'<path d="M{cx - 7} {cy + 7}L{cx + 7} {cy - 7}M{cx - 3} {cy - 7}H{cx + 7}V{cy + 3}" fill="none" '
                 f'stroke="{tab_ink}" stroke-width="3" stroke-linecap="square"/>')
    tx = tab + SKEW + pad - 4
    if sub:
        b.append(anton.text(label, tx, 18, 18, text_ink, tracking=1.4))
        b.append(arch_r.text(sub, tx, 33, 11.5, sub_ink))
    else:
        b.append(anton.text(label, tx, 26, 18, text_ink, tracking=1.4))
    return W + sh, H + sh, "".join(b)


def build_buttons(anton, arch, arch_r):
    made = []
    for key, labels, sub, icon_file in BUTTONS:
        for lang in ("en", "es"):
            if lang == "es" and labels["es"] == labels["en"] and key != "quote":
                continue
            w, h, body = button(labels[lang], sub, icon_file, key == "quote", anton, arch, arch_r)
            name = f"btn-{key}{'' if lang == 'en' else '-es'}.svg"
            alt = labels[lang].title() + (f" — {sub}" if sub else "")
            (OUT / name).write_text(svg(w, h, alt, body), encoding="utf-8")
            made.append((name, (OUT / name).stat().st_size))
    for name, size in made:
        print(f"assets/{name}  {size} B")


# --- Final: To Be Continued ------------------------------------------------------

def to_be_continued(t, lang, anton, dela, arch, arch_r):
    W, H = 1200, 190
    pts = "70,95 150,30 150,58 640,58 640,132 150,132 150,160"
    b = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>']
    b.append('<g class="tbc">')
    b.append(f'<polygon points="{pts}" fill="{t["accent"]}" stroke="{t["ink"]}" stroke-width="5" stroke-linejoin="round"/>')
    b.append(f'<g transform="skewX(-12) translate(22 0)">{anton.text("TO BE CONTINUED", 395, 118, 50, t["bg"], tracking=2, anchor="middle")}</g>')
    b.append("</g>")
    bye = "Arrivederci." if lang == "en" else "Arrivederci."
    b.append(arch.text(bye, 1156, 106, 24, t["ink"], anchor="end"))
    b.append(arch_r.text("— Cris", 1156, 136, 18, t["muted"], anchor="end"))
    style = (".tbc{animation:tbc 9s cubic-bezier(.2,.9,.25,1) infinite}"
             "@keyframes tbc{0%{transform:translateX(620px)}9%,92%{transform:none;opacity:1}100%{transform:none;opacity:0}}")
    return svg(W, H, "To Be Continued — Arrivederci.", "".join(b), style)


def main():
    fetch_fonts()
    anton = Face("Anton-Regular.ttf")
    dela = Face("DelaGothicOne-Regular.ttf")
    arch = Face("Archivo.ttf", wght=600, wdth=100)
    arch_r = Face("Archivo.ttf", wght=400, wdth=100)
    OUT.mkdir(exist_ok=True)
    pieces = [("cover", cover), ("stand", stand), ("approach", approach), ("arsenal", arsenal), ("languages", languages),
              ("tbc", to_be_continued)] + [(k, part(k)) for k in PARTS]
    for name, build in pieces:
        for lang in ("en", "es"):
            for mode, t in THEMES.items():
                suffix = "" if lang == "en" else "-es"
                path = OUT / f"{name}{suffix}-{mode}.svg"
                path.write_text(build(t, lang, anton, dela, arch, arch_r), encoding="utf-8")
                print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")
    build_buttons(anton, arch, arch_r)


if __name__ == "__main__":
    main()
