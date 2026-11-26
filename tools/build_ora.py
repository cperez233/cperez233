"""Gráfica de contribuciones del README: cada contribución es un golpe de ORA ORA ORA.

Lee el calendario de GitHub (GraphQL) y lo dibuja con la misma tinta, trama y
trazos que el resto de piezas. Lo corre el workflow .github/workflows/ora.yml,
que publica el resultado en la rama `output`.

La animación depende de los datos: tres puños cruzan el calendario, cada día con
actividad recibe el golpe cuando el puño pasa por su columna, y la racha más
larga se encadena como un combo. El total rueda como un contador al cargar.

Si el año empezó vacío, la cuadrícula se acerca a las semanas con actividad (mínimo NMIN) y
marca dónde empieza la ráfaga; con celdas grandes, los días fuertes llevan su cifra dentro.
Cuando el año se llena, vuelve sola al calendario completo de 53 semanas.

Repos privados: el GITHUB_TOKEN de Actions solo ve lo público, salvo que el perfil tenga activado
"Private contributions". Con ORA_TOKEN (token personal de la cuenta, scope `repo`) la consulta se hace
como el propio usuario y el calendario trae también lo privado (solo conteos, nunca nombres de repos).

Además de los SVG escribe contributions.json, que lee el tablero 3D de portfolio-web.

    ORA_TOKEN=... .venv/bin/python tools/build_ora.py --user cperez233 --out dist
    .venv/bin/python tools/build_ora.py --sample --out .preview   # datos falsos, solo para probar el diseño
    .venv/bin/python tools/build_ora.py --json contributions.json --out .preview   # datos reales ya publicados
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

QUERY = """query($login: String!) { user(login: $login) { contributionsCollection {
  contributionYears restrictedContributionsCount
  contributionCalendar { totalContributions weeks { contributionDays { date weekday contributionCount contributionLevel } } } } } }"""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
}

# Barrage: cada 9 s tres puños cruzan la gráfica (de T0 a T0+DUR). Los días con actividad
# reciben el golpe justo cuando el puño pasa por su columna.
# Los puños entran desde fuera del cuadro (borde delantero en FRONT0 < 0), cruzan a velocidad constante y
# salen por la derecha sin desvanecerse: TRAVEL deja incluso la estela fuera del lienzo.
CYCLE, T0, DUR, TRAVEL, FRONT0, LEAD = 10.0, 0.3, 8.0, 1600, -20, 10
# Cuadrícula: como mínimo NMIN semanas a lo ancho; las filas miden como mucho PMAX px
NMIN, PMAX = 16, 44


def graphql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "build_ora"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if body.get("errors") or not (body.get("data") or {}).get("user"):
        raise SystemExit(f"GitHub devolvió un error: {body.get('errors') or 'usuario no encontrado'}")
    return body["data"]["user"]


def fetch_calendar(user, token):
    coll = graphql(QUERY, {"login": user}, token)["contributionsCollection"]
    cal = coll["contributionCalendar"]
    cal["restricted"] = coll["restrictedContributionsCount"]
    # Totales por año calendario (el tablero 3D del portfolio los lista)
    years = sorted(coll["contributionYears"])
    parts = " ".join(f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
                     "{ contributionCalendar { totalContributions } }" for y in years)
    data = graphql(f"query($login: String!) {{ user(login: $login) {{ {parts} }} }}", {"login": user}, token) if years else {}
    cal["years"] = {str(y): data[f"y{y}"]["contributionCalendar"]["totalContributions"] for y in years}
    return cal


def write_json(cal, path, private):
    """Mismo formato que data/github-snapshot.json de portfolio-web: solo días con actividad."""
    days = [[d["date"], d["contributionCount"]] for w in cal["weeks"] for d in w["contributionDays"] if d["contributionCount"]]
    path.write_text(json.dumps({
        "fetchedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "total": cal["totalContributions"], "includesPrivate": private,
        "totals": cal.get("years", {}), "days": days,
    }, separators=(",", ":")), encoding="utf-8")


def calendar_from_json(path):
    """Rehace el calendario desde un contributions.json ya publicado (solo para previsualizar)."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    counts = dict(data["days"])
    last = datetime.datetime.fromisoformat(data["fetchedAt"]).date()
    day = last.replace(year=last.year - 1)
    nz = sorted(c for c in counts.values() if c)
    q = [nz[int(len(nz) * f)] for f in (.25, .5, .75)] if nz else [1, 1, 1]
    names = ["FIRST", "SECOND", "THIRD", "FOURTH"]
    weeks, cur = [], []
    while day <= last:
        n = counts.get(day.isoformat(), 0)
        lvl = "NONE" if not n else names[sum(n > v for v in q)] + "_QUARTILE"
        wd = (day.weekday() + 1) % 7
        if wd == 0 and cur:
            weeks.append({"contributionDays": cur})
            cur = []
        cur.append({"date": day.isoformat(), "weekday": wd, "contributionCount": n, "contributionLevel": lvl})
        day += datetime.timedelta(days=1)
    weeks.append({"contributionDays": cur})
    return {"totalContributions": data["total"], "weeks": weeks, "years": data.get("totals", {}),
            "private": data.get("includesPrivate", False)}


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
    # (columna, fila) de cada día: la primera semana del calendario puede venir incompleta
    pos = [(c, d["weekday"]) for c, w in enumerate(cal["weeks"]) for d in w["contributionDays"]]
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
    first_at = next((i for i, c in enumerate(counts) if c), None)
    return dict(days=days, pos=pos, first_at=first_at, cur_span=(end - current + 1, end) if current else None, total=cal["totalContributions"], active=sum(1 for c in counts if c), top=top, streak=best,
                current=current, span=best_span, top_at=counts.index(top) if top else None,
                first=datetime.date.fromisoformat(days[0]["date"]), last=datetime.date.fromisoformat(days[-1]["date"]))


def hit_time(x):
    """Segundo del ciclo en que el puño líder llega a la coordenada `x`."""
    return T0 + (x - LEAD - FRONT0) / (TRAVEL / DUR)


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
    shake_len = (1200 + 100 - FRONT0) / (TRAVEL / DUR)  # mientras algún puño está dentro del lienzo
    p0, p1 = T0 / CYCLE * 100, (T0 + shake_len) / CYCLE * 100
    steps, n = [], int(shake_len / .08)
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


def window(cal, st):
    """Semanas que se dibujan. Si el año empezó vacío, la cuadrícula se acerca a donde hay golpes
    (desde una semana antes del primero, mínimo NMIN semanas): así no queda medio cuadro vacío."""
    n_all = len(cal["weeks"])
    if st["first_at"] is None:
        return 0
    first_col = st["pos"][st["first_at"]][0]
    return max(0, min(first_col - 1, n_all - NMIN))


def odometer(face, s, x, y, size, fill, cid, tracking=0.0, delay=.25):
    """El total como un contador que rueda hasta su cifra (una vuelta entera y luego el dígito).
    La cifra final queda en su sitio sin animación: con prefers-reduced-motion se ve quieta."""
    step, parts, keys, xx = size * 1.25, [], [], x
    digits = [i for i, ch in enumerate(s) if ch.isdigit()]
    for i, ch in enumerate(s):
        w = face.width(ch, size)
        if ch.isdigit():
            seq = list(range(10)) + list(range(int(ch) + 1))
            n = len(seq)
            strip = "".join(face.text(str(k), xx + w / 2, y - (n - 1 - j) * step, size, fill, anchor="middle")
                            for j, k in enumerate(seq))
            k = digits.index(i)
            parts.append(f'<g class="odo" style="animation-name:odo{k};animation-delay:{delay + k * .14:.2f}s">{strip}</g>')
            keys.append(f"@keyframes odo{k}{{from{{transform:translateY({(n - 1) * step:.0f}px)}}}}")
        else:
            parts.append(face.text(ch, xx, y, size, fill))
        xx += w + tracking
    clip = (f'<defs><clipPath id="{cid}"><rect x="{x - 12}" y="{y - size * .92:.0f}" width="{xx - x + 24:.0f}" '
            f'height="{size * .97:.0f}"/></clipPath></defs>')
    return clip + f'<g clip-path="url(#{cid})">{"".join(parts)}</g>', "".join(keys)


def ora(cal, t, lang, anton, dela, arch, arch_r):
    st = stats(cal)
    private = cal.get("private", False)
    W = 1200
    ink, acc, bg = t["ink"], t["accent"], t["bg"]
    copy = {
        "en": dict(title="CONTRIBUTIONS", year="contributions in the last year", since="contributions since {d}",
                   in_days="in {n} days", in_day="today", labels=["ACTIVE DAYS", "BEST DAY", "PER ACTIVE DAY"],
                   pct="{p}% of the days", avg="on average", rush="THE RUSH BEGINS", less="Less", more="More",
                   note="Public and private repos. Private work counts here; its code stays private."
                   if private else "GitHub only counts what it can see; most client work stays in private repos."),
        "es": dict(title="CONTRIBUCIONES", year="contribuciones en el último año", since="contribuciones desde el {d}",
                   in_days="en {n} días", in_day="hoy", labels=["DÍAS ACTIVOS", "MEJOR DÍA", "POR DÍA ACTIVO"],
                   pct="{p}% de los días", avg="en promedio", rush="EMPIEZA LA RÁFAGA", less="Menos", more="Más",
                   note="Repos públicos y privados. Lo privado cuenta aquí; su código sigue privado."
                   if private else "GitHub solo cuenta lo que ve; casi todo el trabajo de clientes está en repos privados."),
    }[lang]
    m = MONTHS[lang]
    days, pos = st["days"], st["pos"]

    # Ventana y geometría: columnas que llenan el ancho, filas de como mucho PMAX px
    w0 = window(cal, st)
    weeks = cal["weeks"][w0:]
    n = len(weeks)
    px = (W - 88) / n
    py = min(px, PMAX)
    gap = max(4, round(py * .12))
    cw, ch = px - gap, py - gap
    big = py >= 30  # celdas grandes: número dentro, trazos más gruesos
    since = st["first_at"] is not None and st["first_at"] > 30
    GX, GY = 44, 330 if since else 312
    grid_bottom = GY + 7 * py - gap

    def xy(i):
        c, wd = pos[i]
        return GX + (c - w0) * px, GY + wd * py

    # Desde el primer golpe (si el año empezó vacío) o el año entero
    first_d = datetime.date.fromisoformat(days[st["first_at"]]["date"]) if st["first_at"] is not None else st["first"]
    win_first = datetime.date.fromisoformat(weeks[0]["contributionDays"][0]["date"])
    span = (f'{m[win_first.month - 1]} {win_first.year} – ' if win_first.year != st["last"].year else f'{m[win_first.month - 1]} – ')
    span += f'{m[st["last"].month - 1]} {st["last"].year}'

    b = [f'<rect width="{W}" height="{{H}}" fill="{bg}"/>', halftone(t, "ho", 1030, 110, 300)]
    b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{ink}"/>')
    b.append(anton.text(copy["title"], 44, 58, 24, acc, tracking=3))
    b.append(dela.text("オラオラ", 44 + anton.width(copy["title"], 24, 3) + 20, 57, 17, t["muted"], tracking=3))
    b.append(arch_r.text(span, 1156, 58, 16, t["muted"], anchor="end"))

    # El total rueda como un contador de golpes
    total_s = num(st["total"], lang)
    odo, odo_keys = odometer(anton, total_s, 40, 184, 120, ink, f"odo{lang}{t['bg'][1:]}", tracking=1)
    b.append(odo)
    b.append(f'<rect x="44" y="202" width="56" height="4" fill="{acc}"/>')
    if since:
        n_days = (st["last"] - first_d).days + 1
        b.append(arch.text(copy["since"].format(d=fmt_day(first_d, lang)), 44, 238, 21, ink))
        b.append(arch_r.text(copy["in_days"].format(n=n_days) if n_days > 1 else copy["in_day"], 44, 264, 17, t["muted"]))
    else:
        n_days = len(days)
        b.append(arch.text(copy["year"], 44, 238, 21, ink))

    # Tres cifras: días activos, mejor día y golpes por día activo
    avg = st["total"] / max(st["active"], 1)
    avg_s = num(round(avg), lang) if avg >= 10 else f"{avg:.1f}".replace(".", "," if lang == "es" else ".")
    best_d = fmt_day(datetime.date.fromisoformat(days[st["top_at"]]["date"]), lang) if st["top_at"] is not None else "—"
    vals = [num(st["active"], lang), num(st["top"], lang), avg_s]
    subs = [copy["pct"].format(p=round(100 * st["active"] / max(n_days, 1))), best_d, copy["avg"]]
    for i, (v, label, sub) in enumerate(zip(vals, copy["labels"], subs)):
        x = 560 + i * 210
        b.append(f'<g class="pop" style="animation-delay:{.35 + i * .15:.2f}s">{anton.text(v, x, 158, 88, acc)}</g>')
        b.append(f'<rect x="{x}" y="174" width="44" height="3" fill="{ink}"/>')
        b.append(arch.text(label, x, 204, 14, ink, tracking=1.4))
        b.append(arch_r.text(sub, x, 228, 15, t["muted"]))

    # Meses arriba de la cuadrícula (sin pisarse)
    size_m = 16 if big else 13
    marks, last_month = [], None
    for c, week in enumerate(weeks):
        mo = datetime.date.fromisoformat(week["contributionDays"][0]["date"]).month
        if mo != last_month:
            x = GX + c * px
            if GX + n * px - x >= 40:
                if marks and x - marks[-1][0] < 56:
                    marks.pop()
                marks.append((x, m[mo - 1]))
            last_month = mo
    b += [arch.text(name, x, GY - 14, size_m, t["muted"]) for x, name in marks]

    # Empieza la ráfaga: línea en el primer golpe cuando hay semanas vacías antes
    if st["first_at"] is not None:
        fx0, fy0 = xy(st["first_at"])
        if fx0 - GX >= px * .9:
            lx = fx0 - gap / 2
            label = f'{copy["rush"]} · {fmt_day(first_d, lang).upper()}'
            lw = anton.width(label, 15, 2)
            tx = min(lx + 10, GX + n * px - lw)
            b.append(f'<path d="M{lx:.1f} {GY - 54}V{grid_bottom + 6}" stroke="{acc}" stroke-width="2" stroke-dasharray="5 4"/>')
            b.append(f'<path d="M{lx - 6:.1f} {GY - 54}h12" stroke="{acc}" stroke-width="2.5"/>')
            b.append(anton.text(label, tx, GY - 41, 15, acc, tracking=2))

    # Cuadrícula: cada columna entra como una ráfaga; los días fuertes llevan su cifra
    fills = {1: (acc, .35), 2: (acc, .65), 3: (acc, 1), 4: (ink, 1)}
    s0, s1 = st["span"]
    combo = st["streak"] >= 3
    sw = 3 if big else 2
    cols = [[] for _ in range(n)]
    fx = []
    for i, d in enumerate(days):
        c = pos[i][0] - w0
        if c < 0:
            continue
        x, y = xy(i)
        lvl = LEVELS.get(d["contributionLevel"], 0)
        if lvl == 0:
            cols[c].append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" height="{ch:.1f}" fill="{ink}" fill-opacity=".08"/>')
            continue
        f, op = fills[lvl]
        edge = f' stroke="{ink}" stroke-width="{sw}"' if lvl >= 3 else ""
        hit = hit_time(x)
        cls = "p2" if combo and s0 <= i <= s1 else "p"
        inner = f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" height="{ch:.1f}" fill="{f}" fill-opacity="{op}"{edge}/>'
        if big and lvl >= 3:
            fs = min(ch * .56, cw * .5)
            inner += anton.text(str(d["contributionCount"]), x + cw / 2, y + ch / 2 + fs * .37, fs, bg, anchor="middle")
        cols[c].append(f'<g class="{cls}" style="animation-delay:{hit:.2f}s">{inner}</g>')
        k = min(cw, ch) / 16
        fx.append(f'<polygon class="ix" style="animation-delay:{hit:.2f}s" points="{star(x + cw / 2, y + ch / 2, 15 * k, 6 * k)}" fill="{ink}"/>')
        if lvl >= 3:  # aura: pulso lento que sale del cuadro
            fx.append(f'<rect class="au" style="animation-delay:{i % 11 * .21:.2f}s" x="{x:.1f}" y="{y:.1f}" '
                      f'width="{cw:.1f}" height="{ch:.1f}" fill="none" stroke="{acc}" stroke-width="{sw}"/>')
    cells = [f'<g class="col" style="animation-delay:{c * (0.025 if n > 30 else .06):.3f}s">{"".join(col)}</g>' for c, col in enumerate(cols)]
    b.append(f'<g class="shake">{"".join(cells)}{"".join(fx)}</g>')

    # Mejor día: marco discontinuo que respira
    if st["top_at"] is not None and pos[st["top_at"]][0] >= w0:
        x, y = xy(st["top_at"])
        o = 4 if not big else 6
        b.append(f'<rect class="bd" x="{x - o:.1f}" y="{y - o:.1f}" width="{cw + 2 * o:.1f}" height="{ch + 2 * o:.1f}" '
                 f'fill="none" stroke="{ink}" stroke-width="2" stroke-dasharray="4 3"/>')

    # Combo: llave bajo la racha más larga
    if combo and pos[s0][0] >= w0:
        x0 = xy(s0)[0]
        x1 = xy(s1)[0] + cw
        yb = grid_bottom + 12
        label = f'COMBO X{st["streak"]}'
        half = anton.width(label, 18, 2) / 2
        mid = min(max((x0 + x1) / 2, GX + half), GX + n * px - half)
        b.append(f'<path d="M{x0:.1f} {yb - 6}V{yb}H{x1:.1f}V{yb - 6}" fill="none" stroke="{acc}" stroke-width="2.5" stroke-linejoin="round"/>')
        b.append(f'<g class="cb" style="animation-delay:{hit_time(xy(s1)[0]):.2f}s">{anton.text(label, mid, yb + 24, 18, ink, tracking=2, anchor="middle")}</g>')

    # Los puños van encima de la cuadrícula: ráfagas en tres filas, el líder marca el ritmo
    glyphs = "オラオラ"
    gw = dela.width(glyphs, 22, 2)
    sc = min(1.5, max(1, py / 26))
    for k, row in enumerate((1, 3, 5)):
        y = GY + row * py + ch / 2
        x = FRONT0 - 8 * sc - k * 40 * sc
        lines = "".join(f'<rect x="{-58 - gw - 70 + j * 18:.0f}" y="{-8 + j * 8}" width="{62 - j * 14}" height="2.5" '
                        f'fill="{acc}" fill-opacity=".7"/>' for j in range(3))
        glyph = (f'<path d="{dela.path(glyphs, -58, 8, 22, 2, anchor="end")}" fill="{acc}" stroke="{bg}" '
                 f'stroke-width="3.5" stroke-linejoin="round" paint-order="stroke"/>')
        b.append(f'<g transform="translate({x:.1f} {y:.1f}) scale({sc:.2f})"><g class="sw" style="animation-name:sweep{k}"><g class="ln">{lines}</g>'
                 f'<g class="bob" style="animation-delay:-{k * .11:.2f}s">{glyph}{fist(t)}</g></g></g>')

    # Leyenda y nota
    ly = grid_bottom + 58
    H = ly + 40
    b.append(arch_r.text(copy["note"], 44, ly + 12, 14, t["muted"]))
    lx = 1156 - 5 * 20 - arch_r.width(copy["more"], 14) - 14

    def key_square(x, lvl):
        if lvl == 0:
            return f'<rect x="{x}" y="{ly}" width="16" height="16" fill="{ink}" fill-opacity=".08"/>'
        f, op = fills[lvl]
        edge = f' stroke="{ink}" stroke-width="2"' if lvl >= 3 else ""
        return f'<rect x="{x}" y="{ly}" width="16" height="16" fill="{f}" fill-opacity="{op}"{edge}/>'

    b.append(arch_r.text(copy["more"], 1156, ly + 12, 14, t["muted"], anchor="end"))
    b += [key_square(lx + lvl * 20, lvl) for lvl in range(5)]
    b.append(arch_r.text(copy["less"], lx - 10, ly + 12, 14, t["muted"], anchor="end"))
    b[0] = b[0].replace("{H}", f"{H:.0f}")

    p0, p1 = T0 / CYCLE * 100, (T0 + DUR) / CYCLE * 100
    # Cada fila de puños se escala distinto: el recorrido en su sistema de coordenadas se compensa
    sweeps = "".join(f"@keyframes sweep{k}{{0%,{p0:.2f}%{{transform:translateX(0)}}{p1:.2f}%,100%{{transform:translateX({TRAVEL / sc:.0f}px)}}}}"
                     for k in range(3))
    style = (
        ".col{transform-box:fill-box;transform-origin:bottom;animation:col .5s cubic-bezier(.2,.9,.2,1.2) both}"
        "@keyframes col{from{opacity:0;transform:translateX(-10px) scaleY(.4)}}"
        ".odo{animation-duration:1.7s;animation-timing-function:cubic-bezier(.12,.8,.18,1);animation-fill-mode:both}" + odo_keys +
        ".pop{transform-box:fill-box;transform-origin:left bottom;animation:pop .6s cubic-bezier(.2,.9,.2,1.4) both}"
        "@keyframes pop{from{opacity:0;transform:scale(.4) rotate(-6deg)}}"
        # golpe normal, golpe de combo, destello de impacto y aura
        f".p,.p2{{transform-box:fill-box;transform-origin:center;animation:punch {CYCLE}s linear infinite}}"
        ".p2{animation-name:punch2}"
        # celdas grandes: golpe más corto, que no tape a las vecinas
        f"@keyframes punch{{0%,5%,100%{{transform:none}}1.2%{{transform:scale({1.22 if big else 1.55}) rotate(-{4 if big else 8}deg)}}"
        f"2.6%{{transform:scale(.86) rotate(3deg)}}3.8%{{transform:scale(1.06)}}}}"
        f"@keyframes punch2{{0%,6%,100%{{transform:none}}1.2%{{transform:scale({1.38 if big else 2}) rotate(-{6 if big else 12}deg)}}"
        f"2.8%{{transform:scale(.8) rotate(5deg)}}4.4%{{transform:scale(1.12)}}}}"
        f".ix{{opacity:0;transform-box:fill-box;transform-origin:center;animation:ix {CYCLE}s linear infinite}}"
        "@keyframes ix{0%,5%,100%{opacity:0;transform:scale(.3)}.4%{opacity:.95;transform:scale(.7)}"
        "2.2%{opacity:0;transform:scale(1.5)}}"
        ".au{opacity:0;transform-box:fill-box;transform-origin:center;animation:au 2.4s ease-out infinite}"
        "@keyframes au{0%{opacity:.75;transform:scale(1)}100%{opacity:0;transform:scale(1.5)}}"
        ".bd{animation:bd 1.6s ease-in-out infinite}@keyframes bd{0%,100%{opacity:1}50%{opacity:.3}}"
        f".cb{{transform-box:fill-box;transform-origin:center;animation:cb {CYCLE}s linear infinite}}"
        "@keyframes cb{0%,8%,100%{transform:none}1.5%{transform:scale(1.7)}3.5%{transform:scale(.9)}5%{transform:scale(1.15)}}"
        # puños y temblor
        f".sw{{animation-duration:{CYCLE}s;animation-timing-function:linear;animation-iteration-count:infinite}}" + sweeps +
        # vaivén de golpe del puño y estela de líneas que parpadea
        ".bob{transform-box:fill-box;transform-origin:center;animation:bob .32s ease-in-out infinite alternate}"
        "@keyframes bob{from{transform:translateY(-2px) rotate(-3deg)}to{transform:translateY(2px) rotate(3deg)}}"
        ".ln{animation:ln .14s steps(2,end) infinite alternate}"
        "@keyframes ln{from{opacity:.35;transform:translateX(-6px)}to{opacity:1;transform:translateX(5px)}}"
        f".shake{{animation:shake {CYCLE}s steps(1,end) infinite}}" + shake_keyframes()
    )
    since_txt = {"en": f" since {fmt_day(first_d, 'en')}", "es": f" desde el {fmt_day(first_d, 'es')}"}[lang] if since else ""
    label = {
        "en": f'Contribution graph: {st["total"]} contributions{since_txt or " in the last year"}, {st["active"]} active days, '
              f'best day {st["top"]}, longest streak {st["streak"]} days, current streak {st["current"]}.',
        "es": f'Gráfica de contribuciones: {st["total"]} contribuciones{since_txt or " en el último año"}, {st["active"]} días activos, '
              f'mejor día {st["top"]}, racha más larga de {st["streak"]} días, racha actual de {st["current"]}.',
    }[lang]
    return svg(W, int(H), label, "".join(b), style)


def fmt_day(d, lang):
    mo = MONTHS[lang][d.month - 1]
    return f"{mo} {d.day}" if lang == "en" else f"{d.day} {mo}"


def span_text(days, span, lang):
    a, z = (datetime.date.fromisoformat(days[i]["date"]) for i in span)
    return fmt_day(a, lang) if a == z else f"{fmt_day(a, lang)} – {fmt_day(z, lang)}"


FLAME = ("M0 -15C3 -9 10 -5 10 3C10 10 5 15 0 15C-5 15 -10 10 -10 3C-10 -1 -7 -4 -5 -7C-4 -4 -2 -3 0 -4C1 -8 0 -11 0 -15Z")


def streak_card(cal, t, lang, anton, dela, arch, arch_r):
    """Rachas: la actual en un anillo (lleno = igualar el récord), la más larga en grande con la
    intensidad de cada día debajo, y los últimos 30 días en una tira."""
    st = stats(cal)
    days = st["days"]
    W, H = 1200, 262
    ink, acc, bg = t["ink"], t["accent"], t["bg"]
    copy = {
        "en": ("CURRENT STREAK", "LONGEST STREAK", "LAST 30 DAYS", "DAYS", "No active streak", "active days",
               "{n} more to beat the record", "NEW RECORD", "contributions", "today"),
        "es": ("RACHA ACTUAL", "RACHA MÁS LARGA", "ÚLTIMOS 30 DÍAS", "DÍAS", "Sin racha activa", "días activos",
               "{n} más para batir el récord", "NUEVO RÉCORD", "contribuciones", "hoy"),
    }[lang]
    counts = [d["contributionCount"] for d in days]
    b = [f'<rect width="{W}" height="{H}" fill="{bg}"/>', halftone(t, "hk", 600, 120, 420)]
    b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{ink}"/>')
    for x in (420, 820):
        b.append(f'<rect x="{x}" y="44" width="1.5" height="170" fill="{ink}" fill-opacity=".22"/>')

    # A · racha actual: anillo que se llena según la racha más larga, con llama arriba
    cx, cy, r = 232, 112, 64
    circ = 2 * math.pi * r
    frac = min(1, st["current"] / max(st["streak"], 1))
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ink}" stroke-opacity=".12" stroke-width="10"/>')
    if st["current"]:
        b.append(f'<circle class="ring" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{acc}" stroke-width="10" stroke-linecap="butt" '
                 f'stroke-dasharray="{circ * frac:.1f} {circ:.1f}" transform="rotate(-90 {cx} {cy})" style="--len:{circ * frac:.1f}"/>')
    b.append(f'<circle cx="{cx}" cy="{cy - r}" r="22" fill="{bg}"/>')
    b.append(f'<g transform="translate({cx} {cy - r})"><g class="fl"><path d="{FLAME}" fill="{acc}" stroke="{ink}" stroke-width="2.5" stroke-linejoin="round"/>'
             f'<path d="M0 3C3 6 4 9 0 12C-4 9 -3 6 0 3Z" fill="{bg}"/></g></g>')
    b.append(anton.text(str(st["current"]), cx, cy + 26, 76, ink, anchor="middle"))
    b.append(anton.text(copy[0], cx, 216, 21, acc, tracking=2.5, anchor="middle"))
    sub = span_text(days, st["cur_span"], lang) if st["cur_span"] else copy[4]
    if st["current"] and st["current"] >= st["streak"]:
        # la racha actual es la más larga: sello de récord junto al anillo
        rec = copy[7]
        rw = anton.width(rec, 15, 2) + 20
        b.append(f'<g class="rec" transform="translate({cx + r + 8} {cy - 26}) rotate(-8)"><rect x="0" y="-14" width="{rw:.0f}" '
                 f'height="26" fill="{acc}" stroke="{ink}" stroke-width="2"/>{anton.text(rec, 10, 6, 15, bg, tracking=2)}</g>')
    elif st["current"]:
        sub += " · " + copy[6].format(n=st["streak"] - st["current"] + 1)
    b.append(arch_r.text(sub, cx, 241, 15, t["muted"], anchor="middle"))

    # B · racha más larga, en grande
    mx = 620
    num_s = str(st["streak"])
    nw, uw = anton.width(num_s, 128, 1), anton.width(copy[3], 26, 2)
    x0 = mx - (nw + 16 + uw) / 2
    b.append(anton.text(num_s, x0, 150, 128, ink, tracking=1))
    b.append(anton.text(copy[3], x0 + nw + 16, 150, 26, acc, tracking=2))
    b.append(anton.text(copy[1], mx, 216, 21, acc, tracking=2.5, anchor="middle"))
    if st["streak"]:
        # una barra por día de la racha, alta según cuántos golpes hubo ese día
        run = counts[st["span"][0]:st["span"][1] + 1][-40:]
        top = max(run)
        bw = min(16, (240 - 3 * (len(run) - 1)) / len(run))
        bx = mx - (len(run) * (bw + 3) - 3) / 2
        for j, c in enumerate(run):
            h = 3 + 15 * c / top
            fill = ink if c == top else acc
            b.append(f'<rect class="bar" style="animation-delay:{.3 + j * .05:.2f}s" x="{bx + j * (bw + 3):.1f}" y="{186 - h:.1f}" '
                     f'width="{bw:.1f}" height="{h:.1f}" fill="{fill}"/>')
        hits = sum(run)
        b.append(arch_r.text(f'{span_text(days, st["span"], lang)} · {num(hits, lang)} {copy[8]}', mx, 241, 15, t["muted"], anchor="middle"))
    else:
        b.append(f'<rect x="{mx - 22}" y="168" width="44" height="3" fill="{ink}"/>')

    # C · últimos 30 días: 3 filas × 10, el hoy es el último cuadro
    last = days[-30:]
    cur = set(range(len(days) - 30, len(days))) & (set(range(st["cur_span"][0], st["cur_span"][1] + 1)) if st["cur_span"] else set())
    cell, pitch = 26, 32
    gx0, gy0 = 988 - (10 * pitch - 6) / 2, 62
    levels = {1: (acc, .35), 2: (acc, .65), 3: (acc, 1), 4: (ink, 1)}
    for i, d in enumerate(last):
        lvl = LEVELS.get(d["contributionLevel"], 0)
        x, y = gx0 + (i % 10) * pitch, gy0 + (i // 10) * pitch
        if lvl == 0:
            rect = f'<rect x="{x:.0f}" y="{y}" width="{cell}" height="{cell}" fill="{ink}" fill-opacity=".08"/>'
        else:
            f, op = levels[lvl]
            edge = f' stroke="{ink}" stroke-width="2.2"' if (len(days) - 30 + i) in cur else ""
            rect = f'<rect x="{x:.0f}" y="{y}" width="{cell}" height="{cell}" fill="{f}" fill-opacity="{op}"{edge}/>'
        b.append(f'<g class="dot" style="animation-delay:{i * .03:.2f}s">{rect}</g>')
    # hoy: el último cuadro late
    x, y = gx0 + 9 * pitch, gy0 + 2 * pitch
    b.append(f'<rect class="today" x="{x - 4:.0f}" y="{y - 4}" width="{cell + 8}" height="{cell + 8}" fill="none" '
             f'stroke="{acc}" stroke-width="2" stroke-dasharray="4 3"/>')
    b.append(arch_r.text(copy[9], x + cell / 2, y + cell + 22, 13, t["muted"], anchor="middle"))
    active = sum(1 for d in last if d["contributionCount"])
    month_hits = sum(d["contributionCount"] for d in last)
    b.append(anton.text(copy[2], 988, 216, 21, acc, tracking=2.5, anchor="middle"))
    b.append(arch_r.text(f"{active} {copy[5]} · {num(month_hits, lang)} {copy[8]}", 988, 241, 15, t["muted"], anchor="middle"))

    style = (
        ".fl{transform-box:fill-box;transform-origin:50% 100%;animation:fl 1.1s ease-in-out infinite}"
        "@keyframes fl{0%,100%{transform:scale(1,1)}50%{transform:scale(.92,1.1) rotate(-3deg)}}"
        ".ring{animation:ring 1.4s cubic-bezier(.2,.8,.2,1) both .2s}"
        "@keyframes ring{from{stroke-dasharray:0 1000}}"
        ".dot{transform-box:fill-box;transform-origin:center;animation:dot .45s cubic-bezier(.2,.9,.2,1.3) both}"
        "@keyframes dot{from{opacity:0;transform:scale(.3)}}"
        ".bar{transform-box:fill-box;transform-origin:bottom;animation:bar .5s cubic-bezier(.2,.9,.2,1.3) both}"
        "@keyframes bar{from{transform:scaleY(0)}}"
        ".today{animation:bd 1.6s ease-in-out infinite}@keyframes bd{0%,100%{opacity:1}50%{opacity:.25}}"
        ".rec{animation:rec 2.4s ease-in-out infinite}@keyframes rec{0%,100%{opacity:1}50%{opacity:.75}}"
    )
    label = {
        "en": f'Streaks: current {st["current"]} days, longest {st["streak"]} days. {active} active days in the last 30.',
        "es": f'Rachas: actual de {st["current"]} días, más larga de {st["streak"]} días. {active} días activos en los últimos 30.',
    }[lang]
    return svg(W, H, label, "".join(b), style)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "cperez233"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--sample", action="store_true", help="datos inventados para probar el diseño")
    ap.add_argument("--json", help="rehace el calendario desde un contributions.json (previsualizar con datos reales)")
    args = ap.parse_args()

    if args.json:
        cal = calendar_from_json(args.json)
    elif args.sample:
        cal = sample_calendar()
        cal["private"] = True
    else:
        own = os.environ.get("ORA_TOKEN")
        token = own or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Falta ORA_TOKEN o GITHUB_TOKEN (o usa --sample para probar el diseño).")
        cal = fetch_calendar(args.user, token)
        # Con el token propio la consulta ve lo privado; con GITHUB_TOKEN solo si el perfil lo comparte.
        cal["private"] = bool(own) or cal["restricted"] > 0
        print(f'{cal["totalContributions"]} contribuciones en el último año '
              f'({"incluye privadas" if cal["private"] else "solo públicas"}; ocultas al token: {cal["restricted"]})')
        if not cal["private"]:
            print("::warning::La gráfica solo cuenta repos públicos. Activa \"Private contributions\" en el perfil "
                  "o guarda un token personal en el secreto ORA_TOKEN.")

    fetch_fonts()
    anton, dela = Face("Anton-Regular.ttf"), Face("DelaGothicOne-Regular.ttf")
    arch, arch_r = Face("Archivo.ttf", wght=600, wdth=100), Face("Archivo.ttf", wght=400, wdth=100)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_json(cal, out / "contributions.json", cal.get("private", False))
    for lang in ("en", "es"):
        for mode, t in THEMES.items():
            for name, build in (("ora", ora), ("streak", streak_card)):
                path = out / f"{name}{'' if lang == 'en' else '-es'}-{mode}.svg"
                path.write_text(build(cal, t, lang, anton, dela, arch, arch_r), encoding="utf-8")
                print(f"{path}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
