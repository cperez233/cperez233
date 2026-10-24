"""Cuenta líneas de código por lenguaje en una carpeta con clones de mis repos.

    python tools/language_stats.py CARPETA_CON_CLONES [-x repo ...] > tools/languages.json

Ignora dependencias, builds, lockfiles y archivos minificados o generados.
Solo cuenta lenguajes de programación y de interfaz (HTML y CSS incluidos);
JSON, Markdown y YAML quedan fuera.
"""

import argparse
import json
import pathlib
import datetime

LANGS = {
    "TypeScript": {".ts", ".tsx", ".mts", ".cts"},
    "JavaScript": {".js", ".jsx", ".mjs", ".cjs"},
    "Python": {".py"},
    "PHP": {".php"},
    "Java": {".java"},
    "HTML": {".html", ".htm"},
    "CSS": {".css", ".scss", ".sass", ".less"},
    "SQL": {".sql"},
    "Shell": {".sh", ".bash"},
}
EXT = {e: lang for lang, exts in LANGS.items() for e in exts}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next", ".nuxt", "out", "coverage", "__pycache__",
             ".venv", "venv", "env", "target", ".gradle", "storage", "bootstrap/cache", ".vercel", "public/build", ".cache"}
SKIP_NAMES = ("package-lock", "yarn.lock", "pnpm-lock", "composer.lock")


def count(repo: pathlib.Path):
    totals = {}
    for f in repo.rglob("*"):
        if not f.is_file() or any(part in SKIP_DIRS for part in f.relative_to(repo).parts[:-1]):
            continue
        lang = EXT.get(f.suffix.lower())
        if not lang or f.name.endswith((".min.js", ".min.css", ".d.ts")) or f.name.startswith(SKIP_NAMES):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        # un archivo de una sola línea gigante es casi seguro minificado o generado
        if lines and max(map(len, lines)) > 1000:
            continue
        n = sum(1 for l in lines if l.strip())
        totals[lang] = totals.get(lang, 0) + n
    return totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=pathlib.Path)
    ap.add_argument("-x", "--exclude", action="append", default=[])
    a = ap.parse_args()
    repos, total = {}, {}
    for d in sorted(p for p in a.root.iterdir() if (p / ".git").exists() and p.name not in a.exclude):
        c = count(d)
        repos[d.name] = c
        for k, v in c.items():
            total[k] = total.get(k, 0) + v
    out = {"date": datetime.date.today().isoformat(), "unit": "non-blank lines", "repos": len(repos),
           "languages": dict(sorted(total.items(), key=lambda kv: -kv[1])), "by_repo": repos}
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
