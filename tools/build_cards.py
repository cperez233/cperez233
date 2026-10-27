"""Tarjetas de proyecto del README: paneles de manga con la captura del sitio.

Cada tarjeta es un HTML que Chromium en modo headless convierte a JPG,
en claro/oscuro y EN/ES. Las capturas viven en tools/shots.

    .venv/bin/pip install pillow
    .venv/bin/python tools/build_cards.py
"""

import os
import pathlib
import subprocess
import tempfile

from PIL import Image

from build_assets import FONTS, THEMES, fetch_fonts

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tools" / "shots"
OUT = ROOT / "assets" / "cards"
SCALE = 1.5
# Va en el nombre de cada tarjeta: subirlo cuando cambian las capturas, porque
# GitHub y el navegador guardan en cache la imagen vieja si el nombre no cambia.
VERSION = 4

FEATURED = [
    dict(
        key="tostrivia", shot="tostrivia.jpg", kana="クイズ", title="TOSTRIVIA", side="left",
        kicker={"en": "Trivia game · play solo or with friends", "es": "Juego de trivia · solo o con amigos"},
        desc={
            "en": "Spin the wheel and answer against the clock: anime, games, series and movies. Guess an opening "
                  "from its sound or a poster from a blur. Rooms of up to 10 players, each on their own phone.",
            "es": "Gira la ruleta y responde contra el reloj: anime, juegos, series y películas. Adivina un opening "
                  "por su sonido o un póster desde el desenfoque. Salas de hasta 10 jugadores, cada uno en su celular.",
        },
        stat=("5,300+", {"en": "questions, in English and Spanish", "es": "preguntas, en inglés y español"}),
        cta={"en": "Play it now", "es": "Jugar ahora"},
        meta="React · Vite · PeerJS (WebRTC) · Vercel",
    ),
    dict(
        key="radar-kpop", shot="radar-kpop.jpg", kana="レーダー", title="RADAR K-POP", side="right",
        kicker={"en": "Fan site · K-pop tours", "es": "Página de fans · giras de K-pop"},
        desc={
            "en": "Where do ten K-pop groups play next? Each one stands on its next tour stop on a small 3D globe, "
                  "drawn as chibis, with a countdown, the distance to you and a pastel map of the venue.",
            "es": "¿Dónde tocan después diez grupos de K-pop? Cada uno aparece en su próxima parada de gira en un "
                  "globo 3D, dibujado como chibis, con cuenta regresiva, distancia a ti y un mapa pastel del recinto.",
        },
        stat=("68", {"en": "hand-made chibi stickers", "es": "chibis hechos a mano"}),
        cta={"en": "Open the radar", "es": "Abrir el radar"},
        meta="JavaScript · MapLibre · GitHub Actions · PWA",
    ),
    dict(
        key="carpy", shot="carpy.jpg", kana="カーピー", title="CARPY", side="left",
        kicker={"en": "Software studio · co-founder", "es": "Estudio de software · cofundador"},
        desc={
            "en": "A software studio with a small team. We build custom software, websites, integrations and "
                  "security audits for businesses in Colombia and abroad, from the first call to the deploy.",
            "es": "Un estudio de software con un equipo pequeño. Hacemos software a la medida, páginas web, "
                  "integraciones y auditorías para negocios en Colombia y afuera, desde la primera llamada hasta el despliegue.",
        },
        stat=None,
        cta={"en": "Quotes open · carpy.tech", "es": "Cotizaciones abiertas · carpy.tech"},
        meta="React 19 · Vite · Framer Motion",
    ),
    dict(
        key="cruz-blanca", shot="cruz-blanca.jpg", kana="レストラン", title="CRUZ BLANCA", side="right",
        kicker={"en": "Restaurant · Girón, Santander", "es": "Restaurante · Girón, Santander"},
        desc={
            "en": "Restaurant, café, ice-cream parlor and cocktail bar across from the Basílica Menor. A full menu "
                  "you can order from, table bookings, promos and the night menu, all landing on their WhatsApp.",
            "es": "Restaurante, café, heladería y coctelería frente a la Basílica Menor. Carta completa para pedir "
                  "desde la página, reservas de mesa, promos y la carta de noche, todo directo a su WhatsApp.",
        },
        stat=("260+", {"en": "dishes on the menu", "es": "platos en la carta"}),
        cta={"en": "See the site", "es": "Ver la página"},
        meta="React · Vite · Tailwind · Framer Motion · SSR",
    ),
    dict(
        key="content", shot="content-social.jpg", kana="バズ", title={"en": "CONTENT", "es": "CONTENIDO"}, side="left",
        kicker={"en": "Tostu · @criscx1905", "es": "Tostu · @criscx1905"},
        desc={
            "en": "Short videos, edits and live streams. I write, record and edit my own content, and I bring "
                  "the same eye to the brands I build websites for.",
            "es": "Videos cortos, edición y directos. Escribo, grabo y edito mi propio contenido, y llevo ese "
                  "mismo ojo a las marcas a las que les hago páginas.",
        },
        stat=("32K+", {"en": "followers on TikTok", "es": "seguidores en TikTok"}),
        cta={"en": "See it on TikTok", "es": "Verlo en TikTok"},
        meta="After Effects · OBS · TikTok · Instagram · YouTube · Twitch",
    ),
]

GRID = [
    dict(key="jovis-gioielli", shot="joyeria.jpg", title="JOVI'S GIOIELLI", domain="joyeria-liart.vercel.app",
         line={"en": "Jewelry store in Italy, with a live engraving preview",
               "es": "Joyería en Italia, con vista previa del grabado en vivo"}),
    dict(key="sammy-partyboom", shot="sammy.jpg", title="SAMMY PARTYBOOM", domain={"en": "Kids' parties · Bucaramanga", "es": "Fiestas infantiles · Bucaramanga"},
         line={"en": "Kids' party entertainers with a WhatsApp quote builder",
               "es": "Animación de fiestas infantiles con cotizador por WhatsApp"}),
    dict(key="hotel-logistico", shot="hotel-logistico.jpg", title="HOTEL LOGÍSTICO", domain="hotellogistico.com",
         line={"en": "Hotel in Santa Marta with bookings over WhatsApp",
               "es": "Hotel en Santa Marta con reservas por WhatsApp"}),
    dict(key="master-service-quality", shot="msq.jpg", title="MASTER SERVICE QUALITY", domain="carros-2.vercel.app",
         line={"en": "Truck rental with monthly quotes, Barrancabermeja",
               "es": "Renta de camionetas con cotización mensual, Barrancabermeja"}),
    dict(key="groomers-house", shot="groomers.jpg", title="THE GROOMER'S HOUSE", domain="the-groomers-house.vercel.app",
         line={"en": "Dog grooming in Floridablanca, appointments over WhatsApp",
               "es": "Peluquería canina en Floridablanca, citas por WhatsApp"}),
    dict(key="leons", shot="leons.jpg", title="LEONS FOOTWEAR", domain="calzadoleons.com",
         line={"en": "Footwear factory with a wholesale catalog", "es": "Fábrica de calzado con catálogo mayorista"}),
    dict(key="louloz", shot="louloz.jpg", title="LOULOZ", domain="louloz.com",
         line={"en": "Online shoe store", "es": "Tienda online de calzado"}),
    dict(key="rincon-del-bebe", shot="rincon.jpg", title="EL RINCÓN DEL BEBÉ", domain="elrincondelbebebga.com",
         line={"en": "Baby store with nationwide delivery", "es": "Tienda de bebés con envíos a todo el país"}),
    dict(key="m10-drinks", shot="m10.jpg", title="M10 DRINKS", domain="m10drinkslicorera.com",
         line={"en": "Liquor store with 24/7 delivery in Floridablanca", "es": "Licorera con domicilio 24/7 en Floridablanca"}),
    dict(key="passguard", shot="passguard.jpg", title="PASSGUARD", domain="pass-guard-omega.vercel.app",
         line={"en": "Password generator and auditor that never leaves the browser",
               "es": "Generador y auditor de contraseñas que no sale del navegador"}),
    dict(key="pairsync", shot="pairsync-session.jpg", title="PAIRSYNC", domain={"en": "Thesis · finished", "es": "Tesis · terminada"},
         line={"en": "Pair programming with an AI tutor and grades synced to Moodle",
               "es": "Pair programming con tutor de IA y notas sincronizadas con Moodle"}),
    dict(key="portfolio", shot="portfolio.jpg", title="CRISTIANPEREZ.ME", domain="cristianperez.me",
         line={"en": "My portfolio: bilingual, with a free site audit", "es": "Mi portafolio: bilingüe, con auditoría web gratis"}),
    dict(key="actas-fcv", shot="fcv-buscador.jpg", title="ACTAS FCV", domain="Fundación Cardiovascular de Colombia",
         line={"en": "OCR pipeline for handwritten forms, 746 records indexed",
               "es": "Pipeline de OCR para actas manuscritas, 746 actas indexadas"}),
    dict(key="guardenv", shot="guardenv.jpg", title="GUARDENV", domain={"en": "Open source · security", "es": "Código abierto · seguridad"},
         line={"en": "Secret scanner with 48 vendor signatures and Shannon entropy",
               "es": "Escáner de secretos con 48 firmas de proveedores y entropía de Shannon"}),
]


def pick(v, lang):
    return v[lang] if isinstance(v, dict) else v


def base_css(t):
    return f"""
@font-face{{font-family:Anton;src:url('{(FONTS / "Anton-Regular.ttf").as_uri()}')}}
@font-face{{font-family:Dela;src:url('{(FONTS / "DelaGothicOne-Regular.ttf").as_uri()}')}}
@font-face{{font-family:Archivo;src:url('{(FONTS / "Archivo.ttf").as_uri()}');font-weight:100 900}}
*{{box-sizing:border-box;margin:0}}
html,body{{background:{t["bg"]};overflow:hidden}}
.card{{position:relative;overflow:hidden;background:{t["bg"]};border:4px solid {t["ink"]};font-family:Archivo;color:{t["ink"]}}}
.tone{{position:absolute;inset:0;background-image:radial-gradient({t["ink"]}29 1.6px,transparent 1.8px);background-size:9px 9px;
  -webkit-mask-image:radial-gradient(circle at var(--tx) var(--ty),#000 0,transparent 55%)}}
.panel{{position:absolute;background:{t["ink"]}}}
.panel img{{position:absolute;inset:5px;width:calc(100% - 10px);height:calc(100% - 10px);object-fit:cover;object-position:top left}}
.go{{position:absolute;font-family:Dela;color:{t["accent"]};line-height:1;
  text-shadow:3px 3px 0 {t["bg"]},-3px 3px 0 {t["bg"]},3px -3px 0 {t["bg"]},-3px -3px 0 {t["bg"]}}}
.title{{font-family:Anton;line-height:.95;letter-spacing:.5px;color:{t["ink"]}}}
.kana{{font-family:Dela;color:{t["accent"]};letter-spacing:2px}}
.muted{{color:{t["muted"]}}}
"""


def featured_html(p, t, lang):
    W, H = 1200, 540
    left = p["side"] == "left"
    cut = "polygon(0 0,100% 0,86% 100%,0 100%)" if left else "polygon(0 0,100% 0,100% 100%,14% 100%)"
    panel = f"left:24px;top:24px;bottom:24px;width:690px;clip-path:{cut}" if left else \
        f"right:24px;top:24px;bottom:24px;width:690px;clip-path:{cut}"
    copy = "left:676px;right:44px" if left else "left:44px;right:676px"
    stat = ""
    if p["stat"]:
        stat = (f'<div style="display:flex;align-items:baseline;gap:14px;margin-top:22px">'
                f'<span class="title" style="font-size:62px;color:{t["accent"]}">{p["stat"][0]}</span>'
                f'<span class="muted" style="font-size:18px;font-weight:600">{p["stat"][1][lang]}</span></div>')
    body = f"""
<div class="card" style="width:{W}px;height:{H}px;--tx:{'92%' if left else '8%'};--ty:15%">
  <div class="tone"></div>
  <div class="panel" style="{panel}"><img src="{(SHOTS / p['shot']).as_uri()}" style="clip-path:{cut}"></div>
  <div style="position:absolute;{copy};top:0;bottom:0;display:flex;flex-direction:column;justify-content:center;
       {'padding-left:40px' if left else 'padding-right:40px'}">
    <div class="muted" style="font-size:17px;font-weight:600">{p['kicker'][lang]}</div>
    <div class="kana" style="font-size:18px;margin-top:14px">{p['kana']}</div>
    <div class="title" style="font-size:70px;margin-top:6px">{pick(p['title'], lang)}</div>
    <p style="font-size:18.5px;line-height:1.5;margin-top:16px;opacity:.86">{p['desc'][lang]}</p>
    {stat}
    <div style="margin-top:{18 if p['stat'] else 26}px;font-size:15px;font-weight:600" class="muted">{p['meta']}</div>
    <div style="margin-top:14px;font-size:18px;font-weight:700;color:{t['accent']}">{p['cta'][lang]} &nbsp;→</div>
  </div>
</div>"""
    return W, H, body


def grid_html(p, t, lang):
    """Tarjeta chica para la cuadrícula de 3 columnas (~285 px en GitHub, de ahí el lienzo de 420)."""
    W, H = 420, 372
    cut = "polygon(0 0,100% 0,100% 88%,0 100%)"
    body = f"""
<div class="card" style="width:{W}px;height:{H}px;border-width:3px;--tx:90%;--ty:92%">
  <div class="tone"></div>
  <div class="panel" style="left:14px;right:14px;top:14px;height:208px;clip-path:{cut}">
    <img src="{(SHOTS / p['shot']).as_uri()}" style="clip-path:{cut}"></div>
  <div style="position:absolute;left:22px;right:22px;top:236px">
    <div class="title" style="font-size:31px">{p['title']}</div>
    <div style="font-size:15.5px;line-height:1.35;margin-top:7px;opacity:.86">{p['line'][lang]}</div>
    <div style="font-size:13.5px;font-weight:700;margin-top:7px;color:{t['accent']}">{pick(p['domain'], lang)}</div>
  </div>
</div>"""
    return W, H, body


def render(W, H, body, t, target):
    html = f"<!doctype html><meta charset=utf-8><style>{base_css(t)}</style>{body}"
    with tempfile.TemporaryDirectory(dir=ROOT / "tools") as tmp:
        page = pathlib.Path(tmp) / "card.html"
        png = pathlib.Path(tmp) / "card.png"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [os.environ.get("CHROMIUM", "chromium"), "--headless=new", "--no-sandbox", "--hide-scrollbars", f"--window-size={W},{H}",
             f"--force-device-scale-factor={SCALE}", "--virtual-time-budget=3000",
             f"--screenshot={png}", page.as_uri()],
            check=True, capture_output=True,
        )
        Image.open(png).convert("RGB").save(target, "JPEG", quality=84, optimize=True, progressive=True)


def main():
    fetch_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    for items, build in ((FEATURED, featured_html), (GRID, grid_html)):
        for p in items:
            for lang in ("en", "es"):
                for mode, t in THEMES.items():
                    target = OUT / f"{p['key']}{'' if lang == 'en' else '-es'}-{mode}-v{VERSION}.jpg"
                    render(*build(p, t, lang), t, target)
                    print(f"{target.relative_to(ROOT)}  {target.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
