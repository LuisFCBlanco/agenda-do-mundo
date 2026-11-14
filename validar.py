"""Confere um arquivo de textos antes do commit: python3 validar.py textos/sudeste/natureza.json

Sai com erro (código 1) e lista os problemas se algum item quebrar as regras de tarefas/REGRAS.md.
"""
import json, sys
from datetime import date

CFG = json.load(open("config.json", encoding="utf-8"))
AREAS = {a["id"]: a["escopo"] for a in CFG["areas"]}
PROIBIDO_TITULO = ("janela de", "período de", "periodo de", "início de", "inicio de", "pico de", "fim de")

problemas = []
for caminho in sys.argv[1:]:
    escopo = caminho.replace("\\", "/").split("/")[-2]
    itens = json.load(open(caminho, encoding="utf-8"))
    if not isinstance(itens, list):
        problemas.append(f"{caminho}: precisa ser uma lista JSON")
        continue
    for i, x in enumerate(itens):
        onde = f"{caminho} item {i} ({x.get('titulo', '?')})"
        area = x.get("area")
        if area not in AREAS:
            problemas.append(f"{onde}: área desconhecida {area!r}")
        elif AREAS[area] == "local":
            problemas.append(f"{onde}: área {area} é calculada por cidade e não aceita texto")
        elif (AREAS[area] == "nacional") != (escopo == "brasil"):
            problemas.append(f"{onde}: área {area} ({AREAS[area]}) no escopo errado {escopo}")
        for campo in ("titulo", "data", "descricao", "fonte", "confianca"):
            if not x.get(campo):
                problemas.append(f"{onde}: falta {campo}")
        try:
            date.fromisoformat(str(x.get("data")))
        except ValueError:
            problemas.append(f"{onde}: data inválida {x.get('data')!r}")
        h = x.get("hora")
        if h not in (None, "") and not (isinstance(h, str) and len(h) == 5 and h[2] == ":"):
            problemas.append(f"{onde}: hora deve ser HH:MM ou null")
        texto = f"{x.get('titulo', '')} {x.get('descricao', '')} {x.get('fonte', '')}"
        if "—" in texto or "–" in texto:
            problemas.append(f"{onde}: tem travessão")
        if str(x.get("titulo", "")).lower().startswith(PROIBIDO_TITULO):
            problemas.append(f"{onde}: título começa com expressão proibida")
        if x.get("confianca") not in ("sazonal", "agenda", "confirmar"):
            problemas.append(f"{onde}: confianca deve ser sazonal, agenda ou confirmar")

print("\n".join(problemas) if problemas else "ok")
sys.exit(1 if problemas else 0)
