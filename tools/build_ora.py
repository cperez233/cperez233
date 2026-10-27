"""Gráfica de contribuciones del README: cada contribución es un golpe de ORA ORA ORA.

Lee el calendario de GitHub (GraphQL) y lo dibuja con la misma tinta, trama y
trazos que el resto de piezas. Lo corre el workflow .github/workflows/ora.yml,
que publica el resultado en la rama `output`.

    GITHUB_TOKEN=... .venv/bin/python tools/build_ora.py --user cperez233 --out dist
    .venv/bin/python tools/build_ora.py --sample --out .preview   # datos falsos, solo para probar el diseño
"""

import argparse
import datetime
import json
import os
import pathlib
import random
import urllib.request

from build_assets import GO_CSS, THEMES, Face, fetch_fonts, halftone, svg

QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date weekday contributionCount contributionLevel } } } } } }"""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
}


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
    rnd, day = random.Random(7), datetime.date.today() - datetime.timedelta(days=364)
    day -= datetime.timedelta(days=(day.weekday() + 1) % 7)  # arranca en domingo
    weeks, total = [], 0
    for _ in range(53):
        days = []
        for wd in range(7):
            n = 0 if rnd.random() < .35 else int(rnd.expovariate(.28))
            total += n
            days.append({"date": day.isoformat(), "weekday": wd, "contributionCount": n,
                         "contributionLevel": "NONE" if n == 0 else ["FIRST", "SECOND", "THIRD", "FOURTH"][min(3, n // 4)] + "_QUARTILE"})
            day += datetime.timedelta(days=1)
        weeks.append({"contributionDays": days})
    return {"totalContributions": total, "weeks": weeks}


def num(n, lang):
    s = f"{n:,}"
    return s if lang == "en" else s.replace(",", ".")


def stats(cal):
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    counts = [d["contributionCount"] for d in days]
    best = run = 0
    for c in counts:
        run = run + 1 if c else 0
        best = max(best, run)
    return dict(total=cal["totalContributions"], active=sum(1 for c in counts if c), top=max(counts), streak=best,
                first=datetime.date.fromisoformat(days[0]["date"]), last=datetime.date.fromisoformat(days[-1]["date"]))


def ora(cal, t, lang, anton, dela, arch, arch_r):
    st = stats(cal)
    W, H = 1200, 490
    ink, acc, bg = t["ink"], t["accent"], t["bg"]
    copy = {
        "en": ("CONTRIBUTIONS", "contributions in the last year", ["ACTIVE DAYS", "BEST DAY", "LONGEST STREAK"],
               "Less", "More", "GitHub only counts what it can see; most client work stays in private repos."),
        "es": ("CONTRIBUCIONES", "contribuciones en el último año", ["DÍAS ACTIVOS", "MEJOR DÍA", "RACHA MÁS LARGA"],
               "Menos", "Más", "GitHub solo cuenta lo que ve; casi todo el trabajo de clientes está en repos privados."),
    }[lang]
    m = MONTHS[lang]
    span = f'{m[st["first"].month - 1]} {st["first"].year} – {m[st["last"].month - 1]} {st["last"].year}'

    b = [f'<rect width="{W}" height="{H}" fill="{bg}"/>', halftone(t, "ho", 1030, 110, 300)]
    b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{ink}"/>')
    b.append(anton.text(copy[0], 44, 58, 24, acc, tracking=3))
    b.append(arch_r.text(span, 1156, 58, 16, t["muted"], anchor="end"))

    # El número grande, como el contador de golpes
    big = num(st["total"], lang)
    b.append(anton.text(big, 40, 178, 128, ink, tracking=1))
    bw = anton.width(big, 128, 1)
    b.append(f'<rect x="44" y="196" width="56" height="4" fill="{ink}"/>')
    b.append(arch.text(copy[1], 44, 232, 21, ink))

    # Tres cifras al lado
    x0 = max(590, 40 + bw + 330)
    vals = [num(st["active"], lang), str(st["top"]), f'{st["streak"]}']
    for i, (v, label) in enumerate(zip(vals, copy[2])):
        x = x0 + i * 200
        b.append(anton.text(v, x, 150, 66, acc))
        b.append(f'<rect x="{x}" y="164" width="36" height="3" fill="{ink}"/>')
        b.append(arch.text(label, x, 192, 14, t["muted"], tracking=1.2))

    # El barrage: オラ latiendo detrás de las cifras
    for i, (x, y, size, rot) in enumerate([(330, 104, 54, -10), (410, 160, 70, -4), (470, 96, 42, 9)]):
        d = dela.path("オラ", x, y, size, anchor="middle")
        b.append(f'<g transform="rotate({rot} {x} {y - size / 2})"><path class="go" '
                 f'style="animation-delay:-{i * 0.37:.2f}s;animation-duration:.5s" fill="{acc}" fill-opacity=".9" d="{d}"/></g>')

    # Cuadrícula: 53 semanas × 7 días, cada columna entra como una ráfaga
    gx, gy, pitch, cell = 70, 276, 20, 16
    cells, marks, last_month = [], [], None
    fills = {1: (acc, .35), 2: (acc, .65), 3: (acc, 1), 4: (ink, 1)}

    def square(x, y, lvl):
        if lvl == 0:
            return f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{ink}" fill-opacity=".08"/>'
        f, op = fills[lvl]
        edge = f' stroke="{ink}" stroke-width="2"' if lvl >= 3 else ""
        return f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{f}" fill-opacity="{op}"{edge}/>'

    for c, week in enumerate(cal["weeks"]):
        first = week["contributionDays"][0]
        mo = datetime.date.fromisoformat(first["date"]).month
        if mo != last_month:
            if c <= len(cal["weeks"]) - 3:
                if marks and c - marks[-1][0] < 3:
                    marks.pop()
                marks.append((c, m[mo - 1]))
            last_month = mo
        col = []
        for d in week["contributionDays"]:
            col.append(square(gx + c * pitch, gy + d["weekday"] * pitch, LEVELS.get(d["contributionLevel"], 0)))
        cells.append(f'<g class="col" style="animation-delay:{c * 0.025:.3f}s">{"".join(col)}</g>')
    labels = [arch.text(name, gx + c * pitch, gy - 12, 13, t["muted"]) for c, name in marks]
    b += labels + cells

    # Leyenda y nota
    ly = gy + 7 * pitch + 32
    b.append(arch_r.text(copy[5], 44, ly + 12, 14, t["muted"]))
    lx = 1156 - 5 * pitch - arch_r.width(copy[4], 14) - 14
    b.append(arch_r.text(copy[4], 1156, ly + 12, 14, t["muted"], anchor="end"))
    for lvl in range(5):
        b.append(square(lx + lvl * pitch, ly, lvl))
    b.append(arch_r.text(copy[3], lx - 10, ly + 12, 14, t["muted"], anchor="end"))

    style = (
        GO_CSS
        + ".col{transform-box:fill-box;transform-origin:bottom;animation:col .5s cubic-bezier(.2,.9,.2,1.2) both}"
        "@keyframes col{from{opacity:0;transform:translateX(-10px) scaleY(.4)}}"
    )
    label = {
        "en": f'Contribution graph: {st["total"]} contributions in the last year, {st["active"]} active days, longest streak {st["streak"]} days.',
        "es": f'Gráfica de contribuciones: {st["total"]} contribuciones en el último año, {st["active"]} días activos, racha más larga de {st["streak"]} días.',
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
