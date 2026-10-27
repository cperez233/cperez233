"""Gráfica de contribuciones del README: cada contribución es un golpe de ORA ORA ORA.

Lee el calendario de GitHub (GraphQL) y lo dibuja con la misma tinta, trama y
trazos que el resto de piezas. Lo corre el workflow .github/workflows/ora.yml,
que publica el resultado en la rama `output`.

La animación depende de los datos: tres puños cruzan el calendario, cada día con
actividad recibe el golpe cuando el puño pasa por su columna, y la racha más
larga se encadena como un combo.

    GITHUB_TOKEN=... .venv/bin/python tools/build_ora.py --user cperez233 --out dist
    .venv/bin/python tools/build_ora.py --sample --out .preview   # datos falsos, solo para probar el diseño
"""

import argparse
import datetime
import json
import math
import os
import pathlib
import random
import urllib.request

from build_assets import THEMES, Face, fetch_fonts, halftone, svg

QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date weekday contributionCount contributionLevel } } } } } }"""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
}

# Barrage: cada 9 s tres puños cruzan la gráfica (de T0 a T0+DUR). Los días con actividad
# reciben el golpe justo cuando el puño pasa por su columna.
CYCLE, T0, DUR, TRAVEL, LEAD = 9.0, 0.5, 5.6, 1100, 20
GX, GY, PITCH, CELL = 70, 276, 20, 16


def fetch_calendar(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "build_ora"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if body.get("errors") or not body["data"]["user"]:
        raise SystemExit(f"GitHub devolvió un error: {body.get('errors') or 'usuario no encontrado'}")
    return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def sample_calendar():
    """Calendario inventado, solo para ver el diseño. Nunca se publica."""
    rnd, day = random.Random(11), datetime.date.today() - datetime.timedelta(days=364)
    day -= datetime.timedelta(days=(day.weekday() + 1) % 7)  # arranca en domingo
    weeks, total, i = [], 0, 0
    for _ in range(53):
        days = []
        for wd in range(7):
            burst = 190 <= i <= 200 or 280 <= i <= 286 or i >= 352  # rachas largas y el final activo
            n = int(rnd.expovariate(.3)) + 1 if burst else (0 if rnd.random() < .55 else int(rnd.expovariate(.4)) + 1)
            total += n
            days.append({"date": day.isoformat(), "weekday": wd, "contributionCount": n,
                         "contributionLevel": "NONE" if n == 0 else ["FIRST", "SECOND", "THIRD", "FOURTH"][min(3, n // 3)] + "_QUARTILE"})
            day += datetime.timedelta(days=1)
            i += 1
        weeks.append({"contributionDays": days})
    return {"totalContributions": total, "weeks": weeks}


def num(n, lang):
    s = f"{n:,}"
    return s if lang == "en" else s.replace(",", ".")


def stats(cal):
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    counts = [d["contributionCount"] for d in days]
    # racha más larga (como índices de `days`) y racha actual (hoy puede estar vacío todavía)
    best, run, best_span = 0, 0, (0, -1)
    for i, c in enumerate(counts):
        run = run + 1 if c else 0
        if run > best:
            best, best_span = run, (i - run + 1, i)
    end = len(counts) - 1 - (1 if counts and counts[-1] == 0 else 0)
    current = 0
    while end - current >= 0 and counts[end - current]:
        current += 1
    top = max(counts)
    return dict(total=cal["totalContributions"], active=sum(1 for c in counts if c), top=top, streak=best,
                current=current, span=best_span, top_at=counts.index(top) if top else None,
                first=datetime.date.fromisoformat(days[0]["date"]), last=datetime.date.fromisoformat(days[-1]["date"]))


def hit_time(col):
    """Segundo del ciclo en que el puño líder llega a la columna `col`."""
    return T0 + (col * PITCH + LEAD) / (TRAVEL / DUR)


def star(cx, cy, r_out=15, r_in=6, n=8):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi * i / n - math.pi / 2
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


def shake_keyframes():
    """La cuadrícula tiembla mientras pasan los puños: saltos de ~1 px cada 80 ms."""
    offs = [(1.2, 0), (-1, .8), (.8, -1), (-1.2, 0), (0, 1), (1, -.6)]
    p0, p1 = T0 / CYCLE * 100, (T0 + DUR) / CYCLE * 100
    steps, n = [], int(DUR / .08)
    for i in range(n):
        x, y = offs[i % len(offs)]
        steps.append(f"{p0 + (p1 - p0) * i / n:.2f}%{{transform:translate({x}px,{y}px)}}")
    return f"@keyframes shake{{0%,{p0:.2f}%{{transform:none}}{''.join(steps)}{p1:.2f}%,100%{{transform:none}}}}"


def fist(t):
    """Puño de Star Platinum de perfil, mirando a la derecha; el borde delantero queda en x = 8."""
    ink, acc = t["ink"], t["accent"]
    hand = (f'<path d="M-34 -6Q-34 -12 -28 -12H2Q8 -12 8 -6V6Q8 12 2 12H-28Q-34 12 -34 6Z" '
            f'fill="{acc}" stroke="{ink}" stroke-width="2.5" stroke-linejoin="round"/>')
    knuckles = "".join(f'<path d="M-4 {y}H8" stroke="{ink}" stroke-width="2" stroke-linecap="round"/>' for y in (-5, 0.5, 6))
    thumb = f'<rect x="-26" y="3" width="22" height="9" rx="4.5" fill="{acc}" stroke="{ink}" stroke-width="2.2"/>'
    cuff = f'<rect x="-48" y="-9" width="14" height="18" rx="2" fill="{ink}"/>'
    ghost = f'<g opacity=".28" transform="translate(-16 0)">{hand}</g>'
    return ghost + cuff + hand + knuckles + thumb


def ora(cal, t, lang, anton, dela, arch, arch_r):
    st = stats(cal)
    W, H = 1200, 510
    ink, acc, bg = t["ink"], t["accent"], t["bg"]
    copy = {
        "en": ("CONTRIBUTIONS", "contributions in the last year", ["ACTIVE DAYS", "BEST DAY", "LONGEST STREAK", "CURRENT STREAK"],
               "Less", "More", "GitHub only counts what it can see; most client work stays in private repos."),
        "es": ("CONTRIBUCIONES", "contribuciones en el último año", ["DÍAS ACTIVOS", "MEJOR DÍA", "RACHA MÁS LARGA", "RACHA ACTUAL"],
               "Menos", "Más", "GitHub solo cuenta lo que ve; casi todo el trabajo de clientes está en repos privados."),
    }[lang]
    m = MONTHS[lang]
    span = f'{m[st["first"].month - 1]} {st["first"].year} – {m[st["last"].month - 1]} {st["last"].year}'
    weeks = cal["weeks"]

    b = [f'<rect width="{W}" height="{H}" fill="{bg}"/>', halftone(t, "ho", 1030, 110, 300)]
    b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{ink}"/>')
    b.append(anton.text(copy[0], 44, 58, 24, acc, tracking=3))
    b.append(dela.text("オラオラ", 44 + anton.width(copy[0], 24, 3) + 20, 57, 17, t["muted"], tracking=3))
    b.append(arch_r.text(span, 1156, 58, 16, t["muted"], anchor="end"))

    # El número grande, como el contador de golpes
    big = num(st["total"], lang)
    b.append(anton.text(big, 40, 180, 116, ink, tracking=1))
    b.append(f'<rect x="44" y="196" width="56" height="4" fill="{ink}"/>')
    b.append(arch.text(copy[1], 44, 232, 21, ink))

    # Cuatro cifras
    vals = [num(st["active"], lang), str(st["top"]), str(st["streak"]), str(st["current"])]
    for i, (v, label) in enumerate(zip(vals, copy[2])):
        x = 482 + i * 175
        b.append(anton.text(v, x, 150, 66, acc))
        b.append(f'<rect x="{x}" y="164" width="36" height="3" fill="{ink}"/>')
        b.append(arch.text(label, x, 192, 13, t["muted"], tracking=1.2))

    # Cuadrícula: 53 semanas × 7 días, cada columna entra como una ráfaga
    fills = {1: (acc, .35), 2: (acc, .65), 3: (acc, 1), 4: (ink, 1)}
    s0, s1 = st["span"]
    combo = st["streak"] >= 3

    cells, fx, marks, last_month = [], [], [], None
    for c, week in enumerate(weeks):
        mo = datetime.date.fromisoformat(week["contributionDays"][0]["date"]).month
        if mo != last_month:
            if c <= len(weeks) - 3:
                if marks and c - marks[-1][0] < 3:
                    marks.pop()
                marks.append((c, m[mo - 1]))
            last_month = mo
        col = []
        for d in week["contributionDays"]:
            wd, lvl = d["weekday"], LEVELS.get(d["contributionLevel"], 0)
            x, y = GX + c * PITCH, GY + wd * PITCH
            if lvl == 0:
                col.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{ink}" fill-opacity=".08"/>')
                continue
            f, op = fills[lvl]
            edge = f' stroke="{ink}" stroke-width="2"' if lvl >= 3 else ""
            hit = hit_time(c)
            cls = "p2" if combo and s0 <= c * 7 + wd <= s1 else "p"
            col.append(f'<rect class="{cls}" style="animation-delay:{hit:.2f}s" x="{x}" y="{y}" width="{CELL}" '
                       f'height="{CELL}" fill="{f}" fill-opacity="{op}"{edge}/>')
            fx.append(f'<polygon class="ix" style="animation-delay:{hit:.2f}s" points="{star(x + CELL / 2, y + CELL / 2)}" fill="{ink}"/>')
            if lvl >= 3:  # aura: pulso lento que sale del cuadro
                fx.append(f'<rect class="au" style="animation-delay:{(c * 7 + wd) % 11 * .21:.2f}s" x="{x}" y="{y}" '
                          f'width="{CELL}" height="{CELL}" fill="none" stroke="{acc}" stroke-width="2"/>')
        cells.append(f'<g class="col" style="animation-delay:{c * 0.025:.3f}s">{"".join(col)}</g>')

    b += [arch.text(name, GX + c * PITCH, GY - 12, 13, t["muted"]) for c, name in marks]
    b.append(f'<g class="shake">{"".join(cells)}{"".join(fx)}</g>')

    # Mejor día: marco discontinuo que respira
    if st["top_at"] is not None:
        c, wd = divmod(st["top_at"], 7)
        b.append(f'<rect class="bd" x="{GX + c * PITCH - 4}" y="{GY + wd * PITCH - 4}" width="{CELL + 8}" height="{CELL + 8}" '
                 f'fill="none" stroke="{ink}" stroke-width="2" stroke-dasharray="4 3"/>')

    # Combo: llave bajo la racha más larga
    if combo:
        c0, c1 = s0 // 7, s1 // 7
        x0, x1 = GX + c0 * PITCH, GX + c1 * PITCH + CELL
        yb = GY + 7 * PITCH + 10
        label = f'COMBO X{st["streak"]}'
        half = anton.width(label, 18, 2) / 2
        mid = min(max((x0 + x1) / 2, GX + half), GX + 53 * PITCH - half)
        b.append(f'<path d="M{x0} {yb - 6}V{yb}H{x1}V{yb - 6}" fill="none" stroke="{acc}" stroke-width="2.5" stroke-linejoin="round"/>')
        b.append(f'<g class="cb" style="animation-delay:{hit_time(c1):.2f}s">{anton.text(label, mid, yb + 24, 18, ink, tracking=2, anchor="middle")}</g>')

    # Los puños van encima de la cuadrícula: ráfagas en tres filas, el líder marca el ritmo
    glyphs = "オラオラ"
    gw = dela.width(glyphs, 22, 2)
    for k, row in enumerate((1, 3, 5)):
        y = GY + row * PITCH + CELL / 2
        x = GX - LEAD - 8 - k * 40
        lines = "".join(f'<rect x="{-58 - gw - 70 + j * 18:.0f}" y="{-8 + j * 8}" width="{62 - j * 14}" height="2.5" '
                        f'fill="{acc}" fill-opacity=".7"/>' for j in range(3))
        glyph = (f'<path d="{dela.path(glyphs, -58, 8, 22, 2, anchor="end")}" fill="{acc}" stroke="{bg}" '
                 f'stroke-width="3.5" stroke-linejoin="round" paint-order="stroke"/>')
        b.append(f'<g transform="translate({x} {y})"><g class="sw">{lines}{glyph}{fist(t)}</g></g>')

    # Leyenda y nota
    ly = GY + 7 * PITCH + 56
    b.append(arch_r.text(copy[5], 44, ly + 12, 14, t["muted"]))
    lx = 1156 - 5 * PITCH - arch_r.width(copy[4], 14) - 14

    def key_square(x, lvl):
        if lvl == 0:
            return f'<rect x="{x}" y="{ly}" width="{CELL}" height="{CELL}" fill="{ink}" fill-opacity=".08"/>'
        f, op = fills[lvl]
        edge = f' stroke="{ink}" stroke-width="2"' if lvl >= 3 else ""
        return f'<rect x="{x}" y="{ly}" width="{CELL}" height="{CELL}" fill="{f}" fill-opacity="{op}"{edge}/>'

    b.append(arch_r.text(copy[4], 1156, ly + 12, 14, t["muted"], anchor="end"))
    b += [key_square(lx + lvl * PITCH, lvl) for lvl in range(5)]
    b.append(arch_r.text(copy[3], lx - 10, ly + 12, 14, t["muted"], anchor="end"))

    p0, p1 = T0 / CYCLE * 100, (T0 + DUR) / CYCLE * 100
    style = (
        ".col{transform-box:fill-box;transform-origin:bottom;animation:col .5s cubic-bezier(.2,.9,.2,1.2) both}"
        "@keyframes col{from{opacity:0;transform:translateX(-10px) scaleY(.4)}}"
        # golpe normal, golpe de combo, destello de impacto y aura
        f".p,.p2{{transform-box:fill-box;transform-origin:center;animation:punch {CYCLE}s linear infinite}}"
        ".p2{animation-name:punch2}"
        "@keyframes punch{0%,5%,100%{transform:none}1.2%{transform:scale(1.55) rotate(-8deg)}"
        "2.6%{transform:scale(.8) rotate(4deg)}3.8%{transform:scale(1.12)}}"
        "@keyframes punch2{0%,6%,100%{transform:none}1.2%{transform:scale(2) rotate(-12deg)}"
        "2.8%{transform:scale(.7) rotate(6deg)}4.4%{transform:scale(1.2)}}"
        f".ix{{opacity:0;transform-box:fill-box;transform-origin:center;animation:ix {CYCLE}s linear infinite}}"
        "@keyframes ix{0%,5%,100%{opacity:0;transform:scale(.3)}.4%{opacity:.95;transform:scale(.7)}"
        "2.2%{opacity:0;transform:scale(1.5)}}"
        ".au{opacity:0;transform-box:fill-box;transform-origin:center;animation:au 2.4s ease-out infinite}"
        "@keyframes au{0%{opacity:.75;transform:scale(1)}100%{opacity:0;transform:scale(1.9)}}"
        ".bd{animation:bd 1.6s ease-in-out infinite}@keyframes bd{0%,100%{opacity:1}50%{opacity:.3}}"
        f".cb{{transform-box:fill-box;transform-origin:center;animation:cb {CYCLE}s linear infinite}}"
        "@keyframes cb{0%,8%,100%{transform:none}1.5%{transform:scale(1.7)}3.5%{transform:scale(.9)}5%{transform:scale(1.15)}}"
        # puños y temblor
        f".sw{{opacity:0;animation:sweep {CYCLE}s linear infinite}}"
        f"@keyframes sweep{{0%,{p0:.2f}%{{opacity:0;transform:translateX(0)}}{p0 + .6:.2f}%{{opacity:1}}"
        f"{p1 - .6:.2f}%{{opacity:1}}{p1:.2f}%,100%{{opacity:0;transform:translateX({TRAVEL}px)}}}}"
        f".shake{{animation:shake {CYCLE}s steps(1,end) infinite}}" + shake_keyframes()
    )
    label = {
        "en": f'Contribution graph: {st["total"]} contributions in the last year, {st["active"]} active days, '
              f'longest streak {st["streak"]} days, current streak {st["current"]}.',
        "es": f'Gráfica de contribuciones: {st["total"]} contribuciones en el último año, {st["active"]} días activos, '
              f'racha más larga de {st["streak"]} días, racha actual de {st["current"]}.',
    }[lang]
    return svg(W, H, label, "".join(b), style)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "cperez233"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--sample", action="store_true", help="datos inventados para probar el diseño")
    args = ap.parse_args()

    if args.sample:
        cal = sample_calendar()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Falta GITHUB_TOKEN (o usa --sample para probar el diseño).")
        cal = fetch_calendar(args.user, token)

    fetch_fonts()
    anton, dela = Face("Anton-Regular.ttf"), Face("DelaGothicOne-Regular.ttf")
    arch, arch_r = Face("Archivo.ttf", wght=600, wdth=100), Face("Archivo.ttf", wght=400, wdth=100)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for lang in ("en", "es"):
        for mode, t in THEMES.items():
            path = out / f"ora{'' if lang == 'en' else '-es'}-{mode}.svg"
            path.write_text(ora(cal, t, lang, anton, dela, arch, arch_r), encoding="utf-8")
            print(f"{path}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
