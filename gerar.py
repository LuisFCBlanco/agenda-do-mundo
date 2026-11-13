"""Agenda do Mundo: gera calendários assináveis (.ics) por região e área.

Roda todo dia no GitHub Actions. Áreas calculadas (Lua, céu, sol, feriados) não
precisam de internet; áreas com dados ao vivo (economia, clima, aves) buscam a
fonte e, se ela falhar, mantêm os eventos que já estavam publicados.
"""
import json, math, os, sys, unicodedata, urllib.request, urllib.parse
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import ephem, holidays
from icalendar import Calendar, Event

RAIZ = Path(__file__).parent
CFG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(CFG["fuso"])
SAIDA = RAIZ / "docs" / "feeds"
AGORA = datetime.now(timezone.utc)
HOJE = AGORA.astimezone(TZ).date()
INI = HOJE - timedelta(days=CFG["janela_dias_passado"])
FIM = HOJE + timedelta(days=CFG["janela_dias_futuro"])
LOG = []


def log(msg):
    LOG.append(msg)
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------- utilidades
def hm(dt):
    return f"{dt.hour}h{dt.minute:02d}"


def br(n, casas=2):
    return f"{n:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def local(ed):
    """ephem.Date (UTC) -> datetime no fuso da região."""
    return ephem.Date(ed).datetime().replace(tzinfo=timezone.utc).astimezone(TZ)


def ev(uid, titulo, inicio, fim=None, descricao="", dia_todo=False):
    if dia_todo:
        d = inicio if isinstance(inicio, date) and not isinstance(inicio, datetime) else inicio.date()
        return {"uid": uid, "titulo": titulo, "dia_todo": True, "inicio": d.isoformat(),
                "fim": (d + timedelta(days=1)).isoformat(), "descricao": descricao}
    inicio = inicio.replace(second=0, microsecond=0)
    fim = (fim or inicio + timedelta(minutes=15)).replace(second=0, microsecond=0)
    return {"uid": uid, "titulo": titulo, "dia_todo": False, "inicio": inicio.isoformat(),
            "fim": fim.isoformat(), "descricao": descricao}


def dias():
    d = INI
    while d <= FIM:
        yield d
        d += timedelta(days=1)


RUMOS = ["norte", "nordeste", "leste", "sudeste", "sul", "sudoeste", "oeste", "noroeste"]


def rumo(az_rad):
    return RUMOS[int((math.degrees(az_rad) + 22.5) % 360 // 45)]


def altura_txt(alt_graus):
    if alt_graus < 15:
        return "bem baixo"
    if alt_graus < 35:
        return "baixo"
    if alt_graus < 60:
        return "a meia altura"
    return "alto"


def observador(reg, horizonte="0"):
    o = ephem.Observer()
    o.lat, o.lon, o.elevation = str(reg["lat"]), str(reg["lon"]), reg.get("alt", 0)
    o.horizon = horizonte
    return o


def meio_dia_utc(d):
    return datetime(d.year, d.month, d.day, 12, tzinfo=TZ).astimezone(timezone.utc)


def crepusculo(reg, d, tarde=True):
    """Fim do crepúsculo civil à tarde (ou começo, de manhã): sol 6° abaixo do horizonte."""
    o = observador(reg, "-6")
    o.date = meio_dia_utc(d)
    sol = ephem.Sun()
    try:
        return o.next_setting(sol, use_center=True) if tarde else o.previous_rising(sol, use_center=True)
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        return None


# ---------------------------------------------------------------- Lua
FASES = [
    ("Lua nova", ephem.next_new_moon,
     "Noite sem Lua: a semana mais escura do mês, a melhor para ver estrelas fracas e a Via Láctea longe das luzes. "
     "A Lua está entre a Terra e o Sol, com o lado iluminado virado para longe de nós."),
    ("Quarto crescente", ephem.next_first_quarter_moon,
     "A Lua aparece meio iluminada à tarde e no começo da noite e se põe por volta da meia-noite. "
     "Com binóculo, a linha entre luz e sombra mostra as crateras em relevo, porque ali o sol bate rasante."),
    ("Lua cheia", ephem.next_full_moon,
     "A Lua nasce no leste quando o Sol se põe e atravessa a noite inteira. "
     "A Terra está entre os dois, então vemos o lado iluminado de frente; a claridade apaga as estrelas fracas."),
    ("Quarto minguante", ephem.next_last_quarter_moon,
     "A Lua nasce por volta da meia-noite e fica no céu de manhã. Quem acorda cedo vê a metade iluminada a oeste."),
]


def area_lua(reg):
    out = []
    for nome, fn, texto in FASES:
        t = ephem.Date(datetime.combine(INI, datetime.min.time()))
        while True:
            t = fn(t)
            quando = local(t)
            if quando.date() > FIM:
                break
            o = observador(reg)
            lua, sol = ephem.Moon(), ephem.Sun()
            # hora boa de olhar: cheia e minguante quando a Lua nasce (o nascer mais próximo do momento da fase);
            # crescente no pôr do sol; nova quando o céu fica totalmente escuro (Sol 18° abaixo do horizonte)
            try:
                if nome in ("Lua cheia", "Quarto minguante"):
                    o.date = ephem.Date(t - 0.5)
                    ver = local(o.next_rising(lua))
                    dica = f"Nasce às {hm(ver)} de {ver:%d/%m}, a {rumo(lua.az)}."
                elif nome == "Quarto crescente":
                    o.date = meio_dia_utc(quando.date())
                    o.date = o.next_setting(sol)
                    ver = local(o.date)
                    lua.compute(o)
                    dica = f"Ao pôr do sol ({hm(ver)}) ela já está {altura_txt(math.degrees(lua.alt))}, a {rumo(lua.az)}."
                else:
                    o.horizon = "-18"
                    o.date = meio_dia_utc(quando.date())
                    ver = local(o.next_setting(sol, use_center=True))
                    dica = f"Céu totalmente escuro a partir das {hm(ver)}."
            except (ephem.AlwaysUpError, ephem.NeverUpError):
                ver, dica = quando, ""
            desc = f"{texto}\n\n{dica}\nMomento exato da fase: {quando.strftime('%d/%m')} às {hm(quando)}.\n\nBase: posição calculada com a biblioteca PyEphem para {reg['nome']}."
            out.append(ev(f"lua-{nome}-{quando:%Y%m%d}", nome, ver, ver + timedelta(minutes=30), desc))
            t = ephem.Date(t + 1)
    return out


# ---------------------------------------------------------------- Céu
PLANETAS = [("Mercúrio", ephem.Mercury), ("Vênus", ephem.Venus), ("Marte", ephem.Mars),
            ("Júpiter", ephem.Jupiter), ("Saturno", ephem.Saturn)]

CHUVAS = [
    (4, 22, "Líridas", "Radiante baixo no norte: daqui do Sudeste aparecem poucos meteoros. Melhor depois das 3h."),
    (5, 6, "Eta Aquáridas", "Uma das melhores chuvas para o hemisfério sul. Olhe para o leste nas duas horas antes do amanhecer. São grãos deixados pelo cometa Halley."),
    (7, 30, "Delta Aquáridas do Sul", "Favorecida no hemisfério sul. Melhor depois da meia-noite, com o radiante alto."),
    (8, 12, "Perseidas", "Famosa no hemisfério norte; daqui o radiante fica muito baixo e se vê pouco."),
    (10, 21, "Oriônidas", "Outra chuva de grãos do cometa Halley. Melhor depois da meia-noite, olhando para o leste."),
    (11, 17, "Leônidas", "O radiante nasce de madrugada a leste. A taxa costuma ser baixa, mas os meteoros são rápidos."),
    (12, 14, "Geminídeas", "A chuva mais forte do ano. O radiante nasce no nordeste por volta das 22h; o melhor é depois da meia-noite. Vem do asteroide Faetonte, não de um cometa."),
]


def visiveis(reg, quando_ed):
    o = observador(reg)
    o.date = quando_ed
    vis = []
    for nome, cls in PLANETAS:
        p = cls()
        p.compute(o)
        alt = math.degrees(p.alt)
        if alt > 8:
            vis.append((nome, alt, rumo(p.az), p.mag, p))
    return o, vis


def area_ceu(reg):
    out = []
    for d in dias():
        tarde = crepusculo(reg, d, True)
        manha = crepusculo(reg, d, False)
        # resumo semanal às segundas
        if d.weekday() == 0:
            for quando, rot, chave in ((tarde, "ao anoitecer", "noite"), (manha, "antes do amanhecer", "manha")):
                if quando is None:
                    continue
                _, vis = visiveis(reg, quando)
                hora = local(quando)
                if vis:
                    linhas = [f"{n}: {altura_txt(a)} ({a:.0f}°), a {r}, brilho {br(m,1)}" for n, a, r, m, _ in sorted(vis, key=lambda x: x[3])]
                    titulo = f"Planetas {rot}: " + ", ".join(v[0] for v in sorted(vis, key=lambda x: x[3]))
                    desc = (f"Às {hm(hora)} desta semana:\n" + "\n".join(linhas) +
                            "\n\nBrilho em magnitude: quanto menor o número, mais brilhante (Vênus chega perto de -4, as estrelas mais fracas a olho nu ficam em torno de 6). "
                            "Planeta não pisca como estrela porque é um disco, não um ponto.")
                else:
                    titulo = f"Nenhum planeta brilhante {rot} esta semana"
                    desc = "Os cinco planetas visíveis a olho nu estão perto demais do Sol ou abaixo do horizonte neste horário."
                out.append(ev(f"ceu-planetas-{chave}-{d:%Y%m%d}", titulo, hora, hora + timedelta(minutes=30),
                              desc + f"\n\nBase: posições calculadas com PyEphem para {reg['nome']}."))
        # Lua perto de planeta
        for quando, rot in ((tarde, "ao anoitecer"), (manha, "antes do amanhecer")):
            if quando is None:
                continue
            o, vis = visiveis(reg, quando)
            lua = ephem.Moon(); lua.compute(o)
            if math.degrees(lua.alt) < 8:
                continue
            for nome, alt, r, m, p in vis:
                sep = math.degrees(ephem.separation(lua, p))
                if sep < 6:
                    hora = local(quando)
                    out.append(ev(f"ceu-conj-{nome}-{hora:%Y%m%d%H}", f"Lua perto de {nome}", hora, hora + timedelta(minutes=30),
                                  f"{rot.capitalize()}, {nome} fica a {br(sep,1)}° da Lua, a {r}, {altura_txt(alt)}. "
                                  f"Um punho fechado com o braço esticado cobre uns 10° de céu, então os dois cabem dentro dele.\n\n"
                                  f"A Lua anda cerca de 13° por noite contra as estrelas; amanhã ela já estará longe.\n\nBase: PyEphem."))
    # chuvas de meteoros
    for ano in {INI.year, FIM.year}:
        for mes, dia, nome, texto in CHUVAS:
            d = date(ano, mes, dia)
            if not (INI <= d <= FIM):
                continue
            t2 = datetime(ano, mes, dia, 2, tzinfo=TZ) + timedelta(days=1)
            lua = ephem.Moon(); lua.compute(ephem.Date(t2.astimezone(timezone.utc)))
            ilum = round(lua.phase)
            cond = "Lua quase ausente, boa noite para ver." if ilum < 30 else ("Lua forte atrapalha bastante." if ilum > 70 else "Lua atrapalha um pouco.")
            out.append(ev(f"ceu-chuva-{nome}-{ano}", f"Pico das {nome}", d, descricao=
                          f"{texto}\n\nLua {ilum}% iluminada na madrugada seguinte: {cond}\n"
                          f"Data de pico aproximada: varia cerca de um dia de ano para ano.\n\nBase: calendário de chuvas da International Meteor Organization; Lua calculada com PyEphem.",
                          dia_todo=True))
    return out


# ---------------------------------------------------------------- Sol e estações
def area_sol(reg):
    out = []
    sol = ephem.Sun()
    duracao_ant = None
    for d in [INI - timedelta(days=1)] + list(dias()):
        o = observador(reg, "-0:34")
        o.date = meio_dia_utc(d) - timedelta(hours=12)
        try:
            nasce = o.next_rising(sol); sol.compute(o); az_n = sol.az
            o.date = nasce
            poe = o.next_setting(sol); sol.compute(o); az_p = sol.az
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            continue
        n, p = local(nasce), local(poe)
        dur = (p - n).total_seconds() / 60
        if d < INI:
            duracao_ant = dur
            continue
        h, m = divmod(round(dur), 60)
        dif = "" if duracao_ant is None else f" ({'+' if dur >= duracao_ant else '−'}{abs(dur - duracao_ant):.1f} min em relação a ontem)".replace(".", ",")
        out.append(ev(f"sol-nasce-{d:%Y%m%d}", f"Sol nasce · dia de {h}h{m:02d}", n, n + timedelta(minutes=10),
                      f"Nascer às {hm(n)}, a {math.degrees(az_n):.0f}° ({rumo(az_n)}). Dia de {h}h{m:02d}{dif}.\n"
                      f"O ponto do horizonte onde o Sol nasce anda para o sul até o solstício de dezembro e volta para o norte até o de junho.\n\nBase: PyEphem, com refração atmosférica padrão."))
        out.append(ev(f"sol-poe-{d:%Y%m%d}", "Pôr do sol", p, p + timedelta(minutes=10),
                      f"Pôr às {hm(p)}, a {math.degrees(az_p):.0f}° ({rumo(az_p)}). Uns 25 minutos depois acaba o crepúsculo civil e as primeiras estrelas aparecem."))
        duracao_ant = dur
    marcos = [(ephem.next_vernal_equinox, "Equinócio: começa o outono",
               "Dia e noite com quase a mesma duração. Daqui em diante os dias encurtam até o solstício de junho."),
              (ephem.next_summer_solstice, "Solstício: começa o inverno",
               "Noite mais longa do ano no hemisfério sul. O Sol do meio-dia fica no ponto mais baixo do ano."),
              (ephem.next_autumnal_equinox, "Equinócio: começa a primavera",
               "Dia e noite com quase a mesma duração. Daqui em diante os dias crescem até o solstício de dezembro."),
              (ephem.next_winter_solstice, "Solstício: começa o verão",
               "Dia mais longo do ano no hemisfério sul. O Sol do meio-dia passa quase a pino no Trópico de Capricórnio, que corta o estado de São Paulo.")]
    for fn, titulo, texto in marcos:
        t = fn(ephem.Date(datetime.combine(INI, datetime.min.time())))
        q = local(t)
        if q.date() <= FIM:
            out.append(ev(f"sol-marco-{q:%Y%m%d}", titulo, q, q + timedelta(minutes=30),
                          f"{texto}\nMomento exato: {q.strftime('%d/%m/%Y')} às {hm(q)}.\n\nA causa é a inclinação de 23,4° do eixo da Terra, não a distância ao Sol: a Terra fica mais perto do Sol em janeiro, no nosso verão, e o hemisfério norte está no inverno nessa mesma época.\n\nBase: PyEphem."))
    return out


# ---------------------------------------------------------------- Feriados
def area_feriados(reg):
    anos = list(range(INI.year, FIM.year + 1))
    est = holidays.Brazil(subdiv=reg["uf"], years=anos, language="pt_BR")
    nac = holidays.Brazil(years=anos)
    out = []
    for d, nome in sorted(est.items()):
        if INI <= d <= FIM:
            tipo = "Feriado nacional" if d in nac else f"Feriado estadual ({reg['uf']})"
            out.append(ev(f"feriado-{d:%Y%m%d}", nome, d, descricao=f"{tipo}. Feriados municipais ainda não entram nesta agenda.\n\nBase: biblioteca holidays (python-holidays).", dia_todo=True))
    return out


# ---------------------------------------------------------------- dados ao vivo
def busca_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "agenda-do-mundo/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def sgs(serie, n):
    return busca_json(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json")


def dbr(s):
    return datetime.strptime(s, "%d/%m/%Y").date()


def area_economia(reg):
    out = []
    selic = sgs(432, 1)[-1]
    seg = HOJE + timedelta(days=(7 - HOJE.weekday()) % 7)
    t = datetime(seg.year, seg.month, seg.day, 9, tzinfo=TZ)
    out.append(ev(f"eco-selic-{seg:%Y%m%d}", f"Selic em vigor: {br(float(selic['valor']))}% ao ano", t, t + timedelta(minutes=15),
                  f"Meta da taxa Selic definida pelo Copom, em vigor desde o último dado publicado ({selic['data']}).\n"
                  "É a taxa que o Banco Central usa para puxar os juros da economia: quando sobe, crédito fica mais caro e o consumo esfria, o que segura a inflação.\n\n"
                  "Base: Banco Central do Brasil, SGS série 432."))
    dol = sgs(1, 5)
    vals = [(dbr(x["data"]), float(x["valor"])) for x in dol]
    ult = vals[-1][0]
    t = datetime(ult.year, ult.month, ult.day, 18, tzinfo=TZ)
    ini, fim_ = vals[0][1], vals[-1][1]
    var = (fim_ / ini - 1) * 100
    out.append(ev(f"eco-dolar-{ult:%G%V}", f"Dólar na semana: R$ {br(fim_, 4)} ({'+' if var >= 0 else '−'}{br(abs(var))}%)", t, t + timedelta(minutes=15),
                  "PTAX de venda, dia a dia:\n" + "\n".join(f"{d:%d/%m}: R$ {br(v, 4)}" for d, v in vals) +
                  f"\n\nMínima R$ {br(min(v for _, v in vals), 4)}, máxima R$ {br(max(v for _, v in vals), 4)}.\n"
                  "A PTAX é a média das cotações que o Banco Central coleta ao longo do dia; serve de referência para contratos.\n\n"
                  "Base: Banco Central do Brasil, SGS série 1."))
    return out


WMO = {0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado", 45: "nevoeiro", 48: "nevoeiro com geada",
       51: "garoa fraca", 53: "garoa", 55: "garoa forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
       80: "pancadas fracas", 81: "pancadas", 82: "pancadas fortes", 95: "trovoadas", 96: "trovoadas com granizo", 99: "trovoadas com granizo"}


def area_clima(reg):
    q = urllib.parse.urlencode({"latitude": reg["lat"], "longitude": reg["lon"], "timezone": CFG["fuso"], "forecast_days": 7,
                                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,uv_index_max,weather_code"})
    j = busca_json("https://api.open-meteo.com/v1/forecast?" + q)["daily"]
    feito = AGORA.astimezone(TZ)
    out = []
    for i, dia in enumerate(j["time"]):
        d = date.fromisoformat(dia)
        tmax, tmin = j["temperature_2m_max"][i], j["temperature_2m_min"][i]
        pp, mm, uv = j["precipitation_probability_max"][i], j["precipitation_sum"][i], j["uv_index_max"][i]
        cond = WMO.get(j["weather_code"][i], "tempo variável")
        titulo = f"{tmax:.0f}° / {tmin:.0f}° · chuva {pp or 0}% · {cond}"
        uvtxt = "" if uv is None else f" Índice UV máximo {br(uv,0)}{' (muito alto: sombra entre 10h e 16h)' if uv >= 8 else ''}."
        out.append(ev(f"clima-{d:%Y%m%d}", titulo, d, dia_todo=True, descricao=
                      f"Máxima {tmax:.0f} °C, mínima {tmin:.0f} °C. Chance de chuva {pp or 0}%, {br(mm or 0,1)} mm previstos.{uvtxt}\n\n"
                      f"Previsão feita em {feito:%d/%m às %Hh%M}. O Google relê este calendário a cada 12 a 24 horas, então a previsão pode estar um dia atrasada.\n\n"
                      "Base: Open-Meteo, modelos meteorológicos nacionais combinados."))
    return out


def area_aves(reg):
    chave = os.environ.get("EBIRD_KEY")
    if not chave:
        raise RuntimeError("sem EBIRD_KEY")
    base = "https://api.ebird.org/v2/data/obs/geo/recent"
    p = urllib.parse.urlencode({"lat": reg["lat"], "lng": reg["lon"], "dist": 25, "back": 7, "sppLocale": "pt_BR", "maxResults": 300})
    h = {"X-eBirdApiToken": chave}
    obs = busca_json(f"{base}?{p}", h)
    raros = busca_json(f"{base}/notable?{p}", h)
    out = []
    seg = HOJE - timedelta(days=HOJE.weekday())
    t = datetime(seg.year, seg.month, seg.day, 6, tzinfo=TZ)
    obs.sort(key=lambda x: x.get("obsDt", ""), reverse=True)
    linhas = [f"{x['comName']} ({x.get('locName','')}, {x.get('obsDt','')[8:10]}/{x.get('obsDt','')[5:7]})" for x in obs[:40]]
    out.append(ev(f"aves-semana-{seg:%Y%m%d}", f"Aves por perto: {len(obs)} espécie{'s' if len(obs) != 1 else ''} na última semana", t, t + timedelta(minutes=30),
                  f"Espécies registradas por observadores num raio de 25 km de {reg['nome']} nos últimos 7 dias, das mais recentes para as mais antigas:\n\n" +
                  "\n".join(linhas) + ("\n..." if len(obs) > 40 else "") +
                  "\n\nRegistro depende de haver alguém observando: lugar sem observador não aparece, mesmo cheio de aves.\n\nBase: eBird, Cornell Lab of Ornithology."))
    vistos = set()
    for x in raros:
        k = (x["speciesCode"], x.get("obsDt", "")[:10])
        if k in vistos:
            continue
        vistos.add(k)
        d = date.fromisoformat(x["obsDt"][:10])
        out.append(ev(f"aves-raro-{x['speciesCode']}-{d:%Y%m%d}", f"Registro incomum: {x['comName']}", d, dia_todo=True, descricao=
                      f"{x['comName']} ({x.get('sciName','')}) registrado em {x.get('locName','')} em {d:%d/%m}. "
                      "O eBird marca como incomum o que foge do esperado para a região ou a época.\n\nBase: eBird, Cornell Lab of Ornithology."))
    return out


AREAS = {"lua": area_lua, "ceu": area_ceu, "sol": area_sol, "feriados": area_feriados,
         "economia": area_economia, "clima": area_clima, "aves": area_aves}
AO_VIVO = {"economia", "clima", "aves"}


# ---------------------------------------------------------------- saída
def para_ics(eventos, nome_cal, descricao):
    cal = Calendar()
    cal.add("prodid", "-//Agenda do Mundo//PT-BR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", nome_cal)
    cal.add("x-wr-caldesc", descricao)
    cal.add("x-wr-timezone", CFG["fuso"])
    cal.add("refresh-interval", timedelta(hours=12), parameters={"VALUE": "DURATION"})
    cal.add("x-published-ttl", "PT12H")
    for e in eventos:
        v = Event()
        uid = unicodedata.normalize("NFKD", e["uid"]).encode("ascii", "ignore").decode().replace(" ", "_")
        v.add("uid", uid + "@agenda-do-mundo")
        v.add("dtstamp", AGORA)
        v.add("summary", e["titulo"])
        v.add("description", e["descricao"])
        if e["dia_todo"]:
            v.add("dtstart", date.fromisoformat(e["inicio"]))
            v.add("dtend", date.fromisoformat(e["fim"]))
        else:
            v.add("dtstart", datetime.fromisoformat(e["inicio"]).astimezone(timezone.utc))
            v.add("dtend", datetime.fromisoformat(e["fim"]).astimezone(timezone.utc))
        v.add("transp", "TRANSPARENT")
        cal.add_component(v)
    return cal.to_ical()


def chave_ordem(e):
    s = e["inicio"]
    return s if "T" in s else s + "T00:00"


def main():
    catalogo = {"projeto": CFG["projeto"], "gerado_em": AGORA.astimezone(TZ).isoformat(timespec="minutes"),
                "regioes": CFG["regioes"], "areas": [], "feeds": {}, "avisos": []}
    for area in CFG["areas"]:
        catalogo["areas"].append({k: area[k] for k in ("id", "nome", "resumo", "fonte")})
    for reg in CFG["regioes"]:
        pasta = SAIDA / reg["id"]
        pasta.mkdir(parents=True, exist_ok=True)
        tudo = []
        catalogo["feeds"][reg["id"]] = {}
        for area in CFG["areas"]:
            aid = area["id"]
            arq_json = pasta / f"{aid}.json"
            antigos = json.loads(arq_json.read_text(encoding="utf-8")) if arq_json.exists() else []
            try:
                novos = AREAS[aid](reg)
                ok = True
            except Exception as ex:  # fonte fora do ar ou sem chave: mantém o que já estava publicado
                novos, ok = [], False
                log(f"[{reg['id']}/{aid}] não atualizou: {ex}")
                catalogo["avisos"].append(f"{reg['id']}/{aid}: {ex}")
            if aid in AO_VIVO:
                # dados ao vivo acumulam histórico: o mais novo substitui o mesmo uid, o resto fica até 30 dias
                limite = (HOJE - timedelta(days=30)).isoformat()
                junto = {e["uid"]: e for e in antigos if e["inicio"][:10] >= limite}
                junto.update({e["uid"]: e for e in novos})
                eventos = list(junto.values())
            else:
                eventos = novos if ok else antigos
            eventos.sort(key=chave_ordem)
            if not eventos and not ok:
                continue
            arq_json.write_text(json.dumps(eventos, ensure_ascii=False, indent=1), encoding="utf-8")
            (pasta / f"{aid}.ics").write_bytes(para_ics(eventos, f"{area['nome']} · {reg['nome']}", f"{area['resumo']} Agenda do Mundo."))
            tudo += [dict(e, titulo=f"{area['nome']}: {e['titulo']}") for e in eventos]
            prox = [e for e in eventos if e["inicio"][:10] >= HOJE.isoformat()]
            catalogo["feeds"][reg["id"]][aid] = {"n": len(eventos), "atualizado": ok,
                                                "proximos": [{"titulo": e["titulo"], "inicio": e["inicio"]} for e in prox[:3]]}
            log(f"[{reg['id']}/{aid}] {len(eventos)} eventos{'' if ok else ' (mantidos da última vez)'}")
        tudo.sort(key=chave_ordem)
        (pasta / "tudo.ics").write_bytes(para_ics(tudo, f"Agenda do Mundo · {reg['nome']}", "Todas as áreas da Agenda do Mundo."))
    (RAIZ / "docs" / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
