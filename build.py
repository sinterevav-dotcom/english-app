"""Собирает контент курса из content/*.txt, проверяет его и вшивает в приложение.
Запуск: python3 build.py  ->  dist/english.html и dist/content.json
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent
LEVEL_FILES = [
    ("A1", "Beginner", ["content/a1.txt"]),
    ("A2", "Elementary", ["content/a2-1.txt", "content/a2-2.txt"]),
    ("B1", "Intermediate", ["content/b1-1.txt", "content/b1-2.txt"]),
    ("B2", "Upper-Intermediate", ["content/b2-1.txt", "content/b2-2.txt"]),
]
errors, warnings = [], []


def split(rest):
    return [p.strip() for p in rest.split("|")]


def parse_level(code, name, paths):
    level = {"id": code, "name": name, "modules": []}
    mod = unit = None
    for path in paths:
        if not (ROOT / path).exists():
            return None
        for n, raw in enumerate((ROOT / path).read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            tag, _, rest = line.partition(" ")
            where = f"{path}:{n}"
            if tag == "M":
                mid, title, colors = split(rest)
                mod = {"id": mid, "title": title, "colors": colors.split(","),
                       "grammar": {"title": "", "text": "", "ex": [], "drills": []}, "units": [], "text": None}
                level["modules"].append(mod)
            elif tag == "G":
                mod["grammar"]["title"] = rest.strip()
            elif tag == "T":
                mod["grammar"]["text"] = rest.strip()
            elif tag == "E":
                en, ru = [p.strip() for p in rest.split(" = ")]
                mod["grammar"]["ex"].append([en, ru])
            elif tag == "D":
                q, opts = rest.split(" = ", 1)
                parts = split(opts)
                hint, right, wrong = parts[0], parts[1], parts[2:]
                if "___" not in q:
                    errors.append(f"{where}: в упражнении нет пропуска ___")
                if right in wrong or len(wrong) < 2:
                    errors.append(f"{where}: проблема с вариантами ответа")
                mod["grammar"]["drills"].append({"q": q.strip(), "ru": hint, "right": right, "wrong": wrong})
            elif tag == "U":
                uid, utag, title, sub = split(rest)
                unit = {"id": uid, "tag": utag, "title": title, "sub": sub, "words": []}
                mod["units"].append(unit)
            elif tag == "W":
                parts = split(rest)
                if len(parts) == 4:
                    parts.insert(1, "")
                if len(parts) != 5 or not all(p for i, p in enumerate(parts) if i != 1):
                    errors.append(f"{where}: у слова должно быть 4 или 5 заполненных полей")
                    continue
                en, tr, ru, ex_en, ex_ru = parts
                unit["words"].append({"id": f"{unit['id']}_{len(unit['words'])}", "en": en, "tr": tr,
                                      "ru": ru, "exEn": ex_en, "exRu": ex_ru})
                stem = re.sub(r"[^a-z]", "", en.lower().split()[0])[:4]
                if stem and stem not in re.sub(r"[^a-z]", "", ex_en.lower()):
                    warnings.append(f"{where}: пример не содержит слово «{en}»")
            elif tag == "X":
                title, sub = split(rest)
                mod["text"] = {"title": title, "sub": sub, "paras": [], "qs": []}
            elif tag == "P":
                mod["text"]["paras"].append(rest.strip())
            elif tag == "Q":
                q, right, *wrong = split(rest)
                if right in wrong or len(wrong) < 2:
                    errors.append(f"{where}: проблема с вариантами ответа")
                mod["text"]["qs"].append({"q": q, "right": right, "wrong": wrong})
            else:
                errors.append(f"{where}: неизвестная строка")
    return level


SIZES = {"A1": 10, "A2": 10, "B1": 12, "B2": 15}


def check(level, seen):
    for m in level["modules"]:
        g = m["grammar"]
        if not (g["title"] and g["text"] and len(g["ex"]) >= 3 and len(g["drills"]) >= 8):
            errors.append(f"{m['id']}: грамматика заполнена не полностью")
        if level["id"] != "A1" and (not m["text"] or len(m["text"]["qs"]) < 4):
            errors.append(f"{m['id']}: нет текста с вопросами")
        for u in m["units"]:
            letters = u["id"].startswith("a1s")
            if not letters and len(u["words"]) != SIZES[level["id"]]:
                errors.append(f"{u['id']}: {len(u['words'])} слов вместо {SIZES[level['id']]}")
            for w in u["words"]:
                key = w["en"].lower()
                if letters:
                    continue
                if key in seen:
                    errors.append(f"дубль «{w['en']}»: {seen[key]} и {u['id']}")
                seen[key] = u["id"]


def parse_map():
    levels, cur = [], None
    for line in (ROOT / "content/map.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("L "):
            code, name, words = split(line[2:])
            cur = {"id": code, "name": name, "words": int(words), "modules": []}
            levels.append(cur)
        elif line.startswith("M "):
            title, grammar = split(line[2:])
            cur["modules"].append({"title": title, "grammar": grammar})
    return levels


levels, seen = [], {}
for code, name, paths in LEVEL_FILES:
    lv = parse_level(code, name, paths)
    if lv:
        check(lv, seen)
        levels.append(lv)
ready = {l["id"] for l in levels}
planned = [p for p in parse_map() if p["id"] not in ready]
data = {"levels": levels, "planned": planned}

for w in warnings:
    print("ВНИМАНИЕ", w)
for e in errors:
    print("ОШИБКА", e)
for lv in levels:
    ws = sum(len(u["words"]) for m in lv["modules"] for u in m["units"])
    us = sum(len(m["units"]) for m in lv["modules"])
    print(f"{lv['id']}: модулей {len(lv['modules'])}, юнитов {us}, слов {ws}")
print("Всего слов:", len(seen))
if errors:
    sys.exit(1)

(ROOT / "dist").mkdir(exist_ok=True)
js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
(ROOT / "dist/content.json").write_text(js, encoding="utf-8")
html = (ROOT / "app.html").read_text(encoding="utf-8")
html = html.replace("/*__BASECSS__*/", (ROOT / "style.css").read_text(encoding="utf-8"))
html = html.replace("/*__COURSE__*/null", js)
(ROOT / "dist/english.html").write_text(html, encoding="utf-8")
(ROOT / "dist/telegram").mkdir(exist_ok=True)
title, rest = html.split("\n", 1)
tg = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
      '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
      + title + '\n<style>html,body{margin:0}</style>\n<script src="https://telegram.org/js/telegram-web-app.js"></script>\n</head>\n<body>\n'
      + rest + '\n</body>\n</html>\n')
(ROOT / "dist/telegram/index.html").write_text(tg, encoding="utf-8")
print("Собрано: dist/english.html и dist/telegram/index.html")
