"""Agenda do Mundo: gera calendários assináveis (.ics) por região e área.

Roda todo dia no GitHub Actions. Áreas calculadas (Lua, céu, sol, feriados) não
precisam de internet; áreas com dados ao vivo (economia, clima, aves) buscam a
fonte e, se ela falhar, mantêm os eventos que já estavam publicados.
"""
import json, math, os, sys, unicodedata, urllib.error, urllib.request, urllib.parse
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import ephem, holidays
from icalendar import Calendar, Event

RAIZ = Path(__file__).parent
CFG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
FUSO_BR = "America/Sao_Paulo"
TZ = ZoneInfo(FUSO_BR)  # trocado a cada cidade em main(), para os horários do texto saírem no fuso dela
SAIDA = RAIZ / "docs" / "feeds"
AGORA = datetime.now(timezone.utc)
HOJE = AGORA.astimezone(TZ).date()
INI = HOJE - timedelta(days=CFG["janela_dias_passado"])
FIM = HOJE + timedelta(days=CFG["janela_dias_futuro"])
FIM_ANO = HOJE + timedelta(days=370)  # festas anuais: um ano à frente, para o calendário nunca ficar vazio
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


def dias(fim=None):
    d, fim = INI, fim or FIM
    while d <= fim:
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
            out.append(ev(f"ceu-chuva-{nome}-{ano}", f"Chuva de meteoros {nome}", d, descricao=
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
    return out


def area_estacoes(reg):
    out = []
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
        if q.date() <= FIM_ANO:
            out.append(ev(f"sol-marco-{q:%Y%m%d}", titulo, q, q + timedelta(minutes=30),
                          f"{texto}\nMomento exato: {q.strftime('%d/%m/%Y')} às {hm(q)}.\n\nA causa é a inclinação de 23,4° do eixo da Terra, não a distância ao Sol: a Terra fica mais perto do Sol em janeiro, no nosso verão, e o hemisfério norte está no inverno nessa mesma época.\n\nBase: PyEphem."))
    return out


# ---------------------------------------------------------------- Feriados
def area_feriados(reg):
    anos = list(range(INI.year, FIM_ANO.year + 1))
    est = holidays.Brazil(subdiv=reg["uf"], years=anos, language="pt_BR")
    nac = holidays.Brazil(years=anos)
    out = []
    for d, nome in sorted(est.items()):
        if INI <= d <= FIM_ANO:
            tipo = "Feriado nacional" if d in nac else f"Feriado estadual ({reg['uf']})"
            out.append(ev(f"feriado-{d:%Y%m%d}", nome, d, descricao=f"{tipo}. Feriados municipais ainda não entram nesta agenda.\n\nBase: biblioteca holidays (python-holidays).", dia_todo=True))
    return out




# ---------------------------------------------------------------- calendários de outras tradições
def _primeiro_dia(h, nomes_pt, desc_extra, prefixo):
    """Um evento por festa (primeiro dia de cada sequência com o mesmo nome)."""
    out, vistos = [], set()
    for d, nome in sorted(h.items()):
        base = nome.split(" (")[0].strip()
        ant = h.get(d - timedelta(days=1))
        if base.lower().endswith("eve") or (ant and ant.split(" (")[0].strip() == base):
            continue
        if not (INI <= d <= FIM_ANO):
            continue
        chave = next((k for k in nomes_pt if k.lower() in base.lower()), None)
        if chave is None:
            continue
        titulo, texto = nomes_pt[chave]
        vistos.add(base)
        out.append(ev(f"{prefixo}-{d:%Y%m%d}-{chave[:12]}", titulo, d, dia_todo=True, descricao=f"{texto}\n\n{desc_extra}"))
    return out


JUDAICO = [  # (mês hebraico, dia, título, texto) — Nisan=1 ... Tishrei=7, Kislev=9, Shevat=11, Adar=12 (Adar II=13 em ano bissexto)
    (7, 1, "Rosh Hashaná", "Ano-novo judaico. Abre os Dez Dias de Arrependimento; o shofar, um chifre de carneiro, é tocado na sinagoga."),
    (7, 10, "Yom Kipur", "Dia do Perdão, o mais solene do ano: 25 horas de jejum e oração."),
    (7, 15, "Sucot", "Festa das Cabanas: sete dias morando ou comendo em cabanas de teto aberto, lembrando os 40 anos no deserto e a colheita de outono em Israel."),
    (7, 22, "Simchat Torá", "Fim e recomeço da leitura anual da Torá, com dança nas sinagogas."),
    (9, 25, "Chanucá", "Festa das Luzes, oito noites acendendo uma vela a mais por noite, lembrando a reconsagração do Templo de Jerusalém no século 2 a.C."),
    (11, 15, "Tu BiShvat", "Ano-novo das árvores: no inverno de Israel, a seiva volta a subir nas amendoeiras, as primeiras a florir."),
    (1, 15, "Pessach", "Páscoa judaica, a saída do Egito. Oito dias sem pão fermentado; começa com o jantar do Sêder."),
    (3, 6, "Shavuot", "Festa das Semanas, 50 dias depois de Pessach: a entrega da Torá no Sinai e a colheita do trigo."),
]


def area_judaico(reg):
    from convertdate import hebrew
    out = []
    for ano_g in range(INI.year, FIM_ANO.year + 1):
        for ano_h in (ano_g + 3760, ano_g + 3761):
            itens = list(JUDAICO)
            purim_mes = 13 if hebrew.leap(ano_h) else 12
            itens.append((purim_mes, 14, "Purim", "Lembra a rainha Ester e a salvação dos judeus da Pérsia. Leitura do Livro de Ester, fantasias e troca de presentes de comida."))
            for mes, dia, titulo, texto in itens:
                try:
                    d = date(*hebrew.to_gregorian(ano_h, mes, dia))
                except ValueError:
                    continue
                if INI <= d <= FIM_ANO:
                    out.append(ev(f"jud-{titulo}-{d:%Y}", titulo, d, dia_todo=True, descricao=
                                  f"{texto}\n\nNo calendário judaico o dia começa ao pôr do sol, então a festa começa na noite anterior a esta data.\n"
                                  "O calendário é lunissolar: os meses seguem a Lua e um 13º mês entra 7 vezes a cada 19 anos para manter as festas na estação certa.\n\n"
                                  "Base: conversão do calendário hebraico (convertdate)."))
    return list({e["uid"]: e for e in out}.values())


ISLAMICO = [(1, 1, "Ano-novo islâmico", "Primeiro de Muharram, que marca a Hégira, a ida de Maomé de Meca para Medina em 622."),
            (1, 10, "Ashura", "Dia de jejum voluntário para sunitas; para xiitas, luto pela morte de Hussein em Karbala."),
            (3, 12, "Mawlid", "Nascimento do profeta Maomé, celebrado em boa parte do mundo muçulmano."),
            (9, 1, "Começa o Ramadã", "Mês de jejum do nascer ao pôr do sol. A refeição que quebra o jejum ao anoitecer se chama iftar."),
            (10, 1, "Eid al-Fitr", "Festa do fim do Ramadã: oração da manhã, roupas novas, visitas e doações."),
            (12, 10, "Eid al-Adha", "Festa do Sacrifício, no auge da peregrinação a Meca, lembrando Abraão."),]


def area_islamico(reg):
    from convertdate import islamic
    out = []
    a0 = islamic.from_gregorian(INI.year, INI.month, INI.day)[0]
    for ano_h in (a0, a0 + 1, a0 + 2):
        for mes, dia, titulo, texto in ISLAMICO:
            d = date(*islamic.to_gregorian(ano_h, mes, dia))
            if INI <= d <= FIM_ANO:
                out.append(ev(f"isl-{mes}-{dia}-{ano_h}", titulo, d, dia_todo=True, descricao=
                              f"{texto}\n\nO calendário islâmico é puramente lunar: 12 meses de 29 ou 30 dias, cerca de 11 dias mais curto que o nosso ano, "
                              "então cada festa anda pelas estações ao longo de 33 anos.\n"
                              "Data estimada pelo calendário tabular: o início real depende de avistar a Lua crescente e pode variar um ou dois dias conforme o país.\n\n"
                              "Base: calendário hijri tabular (convertdate)."))
    return out


TERMOS = ["Equinócio da primavera (Chunfen)", "Claridade pura (Qingming)", "Chuva dos grãos (Guyu)", "Início do verão (Lixia)",
          "Grão pequeno (Xiaoman)", "Grão com espiga (Mangzhong)", "Solstício de verão (Xiazhi)", "Calor pequeno (Xiaoshu)",
          "Calor grande (Dashu)", "Início do outono (Liqiu)", "Fim do calor (Chushu)", "Orvalho branco (Bailu)",
          "Equinócio de outono (Qiufen)", "Orvalho frio (Hanlu)", "Descida da geada (Shuangjiang)", "Início do inverno (Lidong)",
          "Neve pequena (Xiaoxue)", "Neve grande (Daxue)", "Solstício de inverno (Dongzhi)", "Frio pequeno (Xiaohan)",
          "Frio grande (Dahan)", "Início da primavera (Lichun)", "Água da chuva (Yushui)", "Despertar dos insetos (Jingzhe)"]


def lon_sol(t):
    s = ephem.Sun(); s.compute(ephem.Date(t))
    return math.degrees(ephem.Ecliptic(s, epoch=ephem.Date(t)).lon)


def cruzamentos(passo, desloc=0.0, ate=None):
    """Instantes em que a longitude do Sol (menos desloc) cruza múltiplos de 'passo' graus, na janela."""
    t, fim = ephem.Date(datetime.combine(INI, datetime.min.time())), ephem.Date(datetime.combine(ate or FIM, datetime.min.time()))
    out = []
    ant = int(((lon_sol(t) - desloc) % 360) // passo)
    while t < fim:
        t2 = ephem.Date(t + 0.5)
        k = int(((lon_sol(t2) - desloc) % 360) // passo)
        if k != ant:
            a, b = float(t), float(t2)
            for _ in range(30):
                m = (a + b) / 2
                if int(((lon_sol(m) - desloc) % 360) // passo) == ant:
                    a = m
                else:
                    b = m
            out.append((ephem.Date(b), k))
            ant = k
        t = t2
    return out


CHINA = {"Chinese New Year": ("Ano-novo chinês (Festa da Primavera)", "A maior festa da China: reuniões de família, envelopes vermelhos e fogos. Abre o novo ano do calendário lunissolar, na segunda Lua nova depois do solstício de dezembro."),
         "Tomb-Sweeping": ("Qingming, dia de varrer os túmulos", "Famílias limpam os túmulos dos antepassados e fazem passeios ao ar livre na primavera chinesa."),
         "Dragon Boat": ("Festa do Barco-Dragão", "Corridas de barcos e bolinhos de arroz em folha de bambu, no 5º dia do 5º mês lunar."),
         "Mid-Autumn": ("Festa do Meio do Outono", "Noite de Lua cheia de outono no hemisfério norte: famílias olham a Lua e comem bolos da Lua.")}


def area_chines(reg):
    out = []
    for t, k in cruzamentos(15, ate=FIM_ANO):
        q = local(t)
        nome = TERMOS[k]
        out.append(ev(f"chi-termo-{q:%Y%m%d}", nome, q, q + timedelta(minutes=30), descricao=
                      f"Começa uma das 24 estações solares do calendário chinês, a cada 15° que o Sol avança na eclíptica (agora em {k*15}°). "
                      "Os nomes descrevem o clima e o trabalho do campo na planície do rio Amarelo, no hemisfério norte; aqui no Brasil as estações estão invertidas. "
                      "Em 2016 a UNESCO reconheceu o sistema como patrimônio imaterial.\n"
                      f"Momento exato: {q:%d/%m} às {hm(q)}.\n\nBase: longitude do Sol calculada com PyEphem."))
    anos = list(range(INI.year, FIM_ANO.year + 1))
    out += _primeiro_dia(holidays.China(years=anos, language="en_US"), CHINA,
                         "Data oficial do calendário de feriados da China.\n\nBase: python-holidays.", "chi")
    return out


HINDU = {"Diwali": ("Diwali, a festa das luzes", "Lamparinas acesas em casas e templos celebram a vitória da luz sobre a escuridão; cai na Lua nova do mês de Kartika."),
         "Holi": ("Holi, a festa das cores", "Pó colorido e água jogados nas ruas celebram a chegada da primavera indiana, na Lua cheia de Phalguna."),
         "Maha Shivaratri": ("Maha Shivaratri", "A grande noite de Shiva: jejum e vigília noturna nos templos."),
         "Makar Sankranti": ("Makar Sankranti", "O Sol entra em Capricórnio sideral; festa da colheita com pipas no céu de vários estados indianos."),
         "Ram Navami": ("Rama Navami", "Nascimento de Rama, herói do Ramayana."),
         "Janmashtami": ("Krishna Janmashtami", "Nascimento de Krishna, celebrado à meia-noite."),
         "Ganesh Chaturthi": ("Ganesh Chaturthi", "Festa de Ganesha, o deus que remove obstáculos; estátuas levadas em procissão até a água."),
         "Dussehra": ("Dussehra", "Vitória de Rama sobre Ravana, o bem sobre o mal; encerra os nove dias de Navaratri."),
         "Navratri": ("Navaratri", "Nove noites dedicadas à deusa Durga, com danças em roda."),
         "Raksha Bandhan": ("Raksha Bandhan", "Irmãs amarram um fio no pulso dos irmãos, um laço de proteção mútua."),
         "Onam": ("Onam", "Festa da colheita em Kerala, com tapetes de flores."),
         "Pongal": ("Pongal", "Festa da colheita no sul da Índia, com arroz cozido no leite até transbordar."),
         "Guru Nanak": ("Aniversário de Guru Nanak", "Fundador do sikhismo; a data mais importante do calendário sikh."),
         "Chhath": ("Chhath Puja", "Oferendas ao Sol nascente e poente às margens dos rios.")}


def area_hindu(reg):
    anos = list(range(INI.year, FIM_ANO.year + 1))
    h = holidays.India(years=anos, language="en_US")
    try:
        h.update(holidays.India(years=anos, language="en_US", categories=("optional",)))
    except Exception:
        pass
    return _primeiro_dia(h, HINDU, "O calendário hindu é lunissolar, com meses que seguem a Lua; por isso a data muda a cada ano no nosso calendário. "
                         "Data do calendário oficial de feriados da Índia.\n\nBase: python-holidays.", "hin")


# ---------------------------------------------------------------- Védico e Ayurveda
NAKSHATRAS = ["Ashvini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
              "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula",
              "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
TITHIS = ["Pratipada", "Dvitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
          "Ekadashi", "Dvadashi", "Trayodashi", "Chaturdashi"]
RASHIS = ["Mesha (Áries)", "Vrishabha (Touro)", "Mithuna (Gêmeos)", "Karka (Câncer)", "Simha (Leão)", "Kanya (Virgem)",
          "Tula (Libra)", "Vrischika (Escorpião)", "Dhanu (Sagitário)", "Makara (Capricórnio)", "Kumbha (Aquário)", "Meena (Peixes)"]
RITUS = {9: "Shishira", 11: "Vasanta", 1: "Grishma", 3: "Varsha", 5: "Sharad", 7: "Hemanta"}  # rashi de entrada -> ritu
RITU_TXT = {"Shishira": "fim do inverno indiano, frio e seco", "Vasanta": "primavera indiana", "Grishma": "verão quente e seco da Índia",
            "Varsha": "monção, a estação das chuvas na Índia", "Sharad": "outono indiano, depois das chuvas", "Hemanta": "começo do inverno indiano"}


def ayanamsa(t):
    """Lahiri, aproximação linear: 23,853° em 2000 + 50,29\" por ano."""
    anos = (ephem.Date(t).datetime() - datetime(2000, 1, 1)).days / 365.25
    return 23.853 + anos * 50.29 / 3600


def lon_lua(t):
    m = ephem.Moon(); m.compute(ephem.Date(t))
    return math.degrees(ephem.Ecliptic(m, epoch=ephem.Date(t)).lon)


def tithi(t):
    return int(((lon_lua(t) - lon_sol(t)) % 360) // 12) + 1  # 1..30


def nome_tithi(n):
    if n == 15:
        return "Purnima (Lua cheia)"
    if n == 30:
        return "Amavasya (Lua nova)"
    return ("Shukla " if n < 15 else "Krishna ") + TITHIS[(n - 1) % 15]


def nascer(reg, d):
    o = observador(reg, "-0:34")
    o.date = meio_dia_utc(d) - timedelta(hours=12)
    return o.next_rising(ephem.Sun())


def area_vedico(reg):
    out, ant = [], None
    for d in [INI - timedelta(days=1)] + list(dias()):
        n = nascer(reg, d)
        tt = tithi(n)
        if d >= INI:
            nk = NAKSHATRAS[int(((lon_lua(n) - ayanamsa(n)) % 360) // (360 / 27))]
            q = local(n)
            out.append(ev(f"ved-dia-{d:%Y%m%d}", f"{nome_tithi(tt)} · {nk}", d, dia_todo=True, descricao=
                          f"No nascer do sol ({hm(q)}) o dia lunar é {nome_tithi(tt)} e a Lua está no nakshatra {nk}.\n\n"
                          "No panchang, o almanaque védico, o tithi é cada 12° que a Lua se afasta do Sol: são 30 por mês lunar, 15 crescentes (Shukla) e 15 minguantes (Krishna). "
                          "O nakshatra é uma das 27 mansões lunares, faixas de 13°20' do céu sideral por onde a Lua passa em cerca de um dia cada. "
                          "O dia védico é regido pelo tithi que está valendo no nascer do sol.\n\n"
                          "Base: posições do Sol e da Lua calculadas com PyEphem; zodíaco sideral com ayanamsa de Lahiri aproximado."))
            for alvo, lado in ((11, "Shukla"), (26, "Krishna")):
                if tt == alvo and ant != alvo or (ant is not None and ant < alvo < tt and tt - ant < 3):
                    out.append(ev(f"ved-ekadashi-{d:%Y%m%d}", f"Ekadashi ({lado})", d, dia_todo=True, descricao=
                                  "Décimo primeiro dia de cada metade do mês lunar, dia de jejum para muitos hindus, sobretudo devotos de Vishnu: "
                                  "a tradição evita grãos e feijões e reserva o dia para oração e quietude. Acontece duas vezes por mês.\n\n"
                                  "A ciência estudou o jejum intermitente em geral, com efeitos sobre a sensibilidade à insulina descritos em ensaios clínicos; "
                                  "não há estudo que ligue a fase da Lua a esses efeitos.\n\nBase: tithi no nascer do sol calculado com PyEphem."))
        ant = tt
    for t, k in cruzamentos(30, desloc=ayanamsa(datetime.combine(HOJE, datetime.min.time()))):
        q = local(t)
        ritu = RITUS.get(k)
        txt = f"O Sol entra em {RASHIS[k]} no zodíaco sideral, a Sankranti do mês. "
        if ritu:
            txt += f"Começa também o ritu {ritu}, {RITU_TXT[ritu]}, uma das seis estações do Ayurveda. "
        out.append(ev(f"ved-sankranti-{q:%Y%m%d}", f"Sankranti: Sol em {RASHIS[k].split(' ')[0]}", q, q + timedelta(minutes=30), descricao=
                      txt + "O zodíaco sideral é medido pelas estrelas fixas; o tropical, usado no Ocidente, pelos equinócios. "
                      "Hoje os dois estão cerca de 24° defasados por causa da precessão do eixo da Terra.\n"
                      f"Momento exato: {q:%d/%m} às {hm(q)}.\n\nBase: PyEphem, ayanamsa de Lahiri aproximado."))
    return out


def area_ayurveda(reg):
    out = []
    for d in dias():
        try:
            n = local(nascer(reg, d))
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            continue
        ini = n - timedelta(minutes=96)
        out.append(ev(f"ayu-brahma-{d:%Y%m%d}", "Brahma muhurta", ini, ini + timedelta(minutes=48), descricao=
                      f"Das {hm(ini)} às {hm(ini + timedelta(minutes=48))}, os 48 minutos que começam 96 minutos antes do nascer do sol ({hm(n)}).\n\n"
                      "Na tradição do Ayurveda e do yoga é a hora mais indicada para meditação, estudo e pranayama: o ar é calmo e a mente ainda não se encheu do dia. "
                      "O nome quer dizer 'a hora de Brahma'.\n\n"
                      "Pelo lado da ciência, o que se sabe é que horários regulares de acordar e a exposição à luz da manhã ajudam a manter o relógio circadiano estável; "
                      "a hora específica não foi testada.\n\nBase: nascer do sol calculado com PyEphem; horário tradicional do Ashtanga Hridaya."))
        if d.weekday() == 0:
            t6 = datetime(d.year, d.month, d.day, 6, tzinfo=TZ)
            out.append(ev(f"ayu-doshas-{d:%Y%m%d}", "Os doshas ao longo do dia", t6, t6 + timedelta(minutes=15), descricao=
                          "Para o Ayurveda, três forças regem o corpo e também as horas do dia: Kapha (terra e água, estabilidade) das 6h às 10h, "
                          "Pitta (fogo, digestão e foco) das 10h às 14h e Vata (ar, movimento e criatividade) das 14h às 18h; o ciclo se repete à noite. "
                          "Daí a recomendação tradicional de fazer a refeição principal perto do meio-dia, quando Pitta, o fogo digestivo, está no auge.\n\n"
                          "A cronobiologia confirma que digestão, temperatura do corpo e atenção variam ao longo do dia de forma previsível; "
                          "estudos de refeição em horário restrito indicam melhor resposta à glicose em refeições mais cedo. Os doshas em si não têm equivalente medido.\n\n"
                          "Base: Ashtanga Hridaya (Sutrasthana); Jakubowicz e colegas, Obesity (2013), sobre horário das refeições."))
    for d in (date(a, 6, 21) for a in range(INI.year, FIM_ANO.year + 1)):
        if INI <= d <= FIM_ANO:
            out.append(ev(f"ayu-yoga-{d:%Y}", "Dia Internacional do Yoga", d, dia_todo=True, descricao=
                          "Instituído pela ONU em 2014, a pedido da Índia, na data do solstício de junho.\n\nBase: Resolução 69/131 da Assembleia Geral da ONU."))
    return out


# ---------------------------------------------------------------- Saúde pública
MESES = {1: ("Janeiro Branco", "saúde mental"), 2: ("Fevereiro Roxo e Laranja", "lúpus, fibromialgia e Alzheimer; leucemia e doação de medula"),
         3: ("Março Lilás", "prevenção do câncer do colo do útero"), 4: ("Abril Azul", "conscientização sobre o autismo"),
         5: ("Maio Amarelo", "segurança no trânsito"), 6: ("Junho Vermelho", "doação de sangue"), 7: ("Julho Amarelo", "hepatites virais"),
         8: ("Agosto Dourado", "aleitamento materno"), 9: ("Setembro Amarelo", "prevenção do suicídio e valorização da vida"),
         10: ("Outubro Rosa", "prevenção do câncer de mama"), 11: ("Novembro Azul", "saúde do homem e câncer de próstata"),
         12: ("Dezembro Vermelho", "prevenção do HIV e da aids")}
DIAS_SAUDE = {(3, 24): "Dia Mundial de Combate à Tuberculose", (4, 7): "Dia Mundial da Saúde", (4, 25): "Dia Mundial da Malária",
              (5, 31): "Dia Mundial sem Tabaco", (6, 14): "Dia Mundial do Doador de Sangue", (7, 28): "Dia Mundial das Hepatites",
              (9, 10): "Dia Mundial de Prevenção do Suicídio", (10, 10): "Dia Mundial da Saúde Mental", (11, 14): "Dia Mundial do Diabetes",
              (12, 1): "Dia Mundial de Luta contra a Aids"}


def area_saude(reg):
    out = []
    for d in dias(FIM_ANO):
        if d.day == 1:
            nome, tema = MESES[d.month]
            out.append(ev(f"sau-mes-{d:%Y%m}", nome, d, dia_todo=True, descricao=
                          f"Mês de campanha sobre {tema}. As campanhas por cor do mês se espalharam no Brasil a partir do Outubro Rosa, que começou nos Estados Unidos nos anos 1990.\n\n"
                          "Base: calendário de campanhas do Ministério da Saúde."))
        if (d.month, d.day) in DIAS_SAUDE:
            out.append(ev(f"sau-dia-{d:%Y%m%d}", DIAS_SAUDE[(d.month, d.day)], d, dia_todo=True,
                          descricao="Data do calendário oficial de dias mundiais da Organização Mundial da Saúde.\n\nBase: OMS, World Health Days."))
    return out


# ---------------------------------------------------------------- dados ao vivo
def busca_json(url, headers=None):
    """Busca JSON com até 3 tentativas: fontes públicas às vezes demoram no aperto de mão TLS."""
    import time
    req = urllib.request.Request(url, headers={"User-Agent": "agenda-do-mundo/1.0", **(headers or {})})
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as ex:
            if isinstance(ex, urllib.error.HTTPError) and ex.code < 500 and ex.code != 429:
                raise
            if tentativa == 2:
                raise
            time.sleep(3 * (tentativa + 1))


def sgs(serie, n):
    return busca_json(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json")


def dbr(s):
    return datetime.strptime(s, "%d/%m/%Y").date()


def semana_moeda(serie, nome, simbolo):
    vals = [(dbr(x["data"]), float(x["valor"])) for x in sgs(serie, 5)]
    ult = vals[-1][0]
    t = datetime(ult.year, ult.month, ult.day, 18, tzinfo=TZ)
    ini, fim_ = vals[0][1], vals[-1][1]
    var = (fim_ / ini - 1) * 100
    return ev(f"eco-{simbolo}-{ult:%G%V}", f"{nome} na semana: R$ {br(fim_, 4)} ({'+' if var >= 0 else '−'}{br(abs(var))}%)", t, t + timedelta(minutes=15),
              f"PTAX de venda, dia a dia:\n" + "\n".join(f"{d:%d/%m}: R$ {br(v, 4)}" for d, v in vals) +
              f"\n\nMínima R$ {br(min(v for _, v in vals), 4)}, máxima R$ {br(max(v for _, v in vals), 4)}. "
              "A PTAX é a média das cotações que o Banco Central coleta ao longo do dia e serve de referência para contratos.\n\n"
              f"Base: Banco Central do Brasil, SGS série {serie}.")


MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def area_economia(reg):
    out = []
    selic = sgs(432, 1)[-1]
    seg = HOJE + timedelta(days=(7 - HOJE.weekday()) % 7)
    t = datetime(seg.year, seg.month, seg.day, 9, tzinfo=TZ)
    out.append(ev(f"eco-selic-{seg:%Y%m%d}", f"Selic em vigor: {br(float(selic['valor']))}% ao ano", t, t + timedelta(minutes=15),
                  f"Meta da taxa Selic definida pelo Copom. Valor em vigor no último dado publicado pelo Banco Central ({selic['data']}).\n"
                  "É a taxa que o Banco Central usa para puxar os juros da economia: quando sobe, o crédito fica mais caro e o consumo esfria, o que segura a inflação.\n\n"
                  "Base: Banco Central do Brasil, SGS série 432."))
    out.append(semana_moeda(1, "Dólar", "dolar"))
    out.append(semana_moeda(21619, "Euro", "euro"))
    ipca = sgs(433, 12)
    ref = dbr(ipca[-1]["data"])
    acum = 1.0
    for x in ipca:
        acum *= 1 + float(x["valor"]) / 100
    t = datetime(HOJE.year, HOJE.month, HOJE.day, 9, 30, tzinfo=TZ)
    out.append(ev(f"eco-ipca-{ref:%Y%m}", f"IPCA de {MESES_NOME[ref.month-1]}: {br(float(ipca[-1]['valor']))}%", t, t + timedelta(minutes=15),
                  f"Inflação oficial do mês de {MESES_NOME[ref.month-1]} de {ref.year}: {br(float(ipca[-1]['valor']))}%. "
                  f"Nos 12 meses até ele: {br((acum - 1) * 100)}%.\n"
                  "O IPCA mede a variação de preços de uma cesta de consumo de famílias com renda de 1 a 40 salários mínimos em 16 regiões; é o índice da meta de inflação.\n\n"
                  "Base: IBGE, via Banco Central do Brasil, SGS série 433."))
    return out


PARCIAIS = []  # fontes que falharam dentro de uma área que ainda teve outra fonte funcionando


def area_investidor(reg):
    out, erros = [], []
    try:
        out += _focus()
    except Exception as ex:
        erros.append(f"Focus (Banco Central): {type(ex).__name__}: {ex}")
    # o calendário do IBGE não responde aos servidores do GitHub (fora do Brasil): as datas de divulgação
    # entram pela tarefa semanal nacional, que pesquisa na web (tarefas/nacional.md, área investidor)
    if erros and not out:
        raise RuntimeError("; ".join(erros))
    PARCIAIS.extend(f"brasil/investidor, {e}" for e in erros)
    return out


def _focus():
    out = []
    q = urllib.parse.quote
    filtro = q("Indicador eq 'IPCA' or Indicador eq 'Selic' or Indicador eq 'Câmbio' or Indicador eq 'PIB Total'")
    url = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
           f"?$top=80&$format=json&$orderby=Data%20desc&$filter={filtro}&$select=Indicador,Data,DataReferencia,Mediana,baseCalculo")
    vals = busca_json(url)["value"]
    data = max(v["Data"] for v in vals)
    anos = [str(HOJE.year), str(HOJE.year + 1)]
    pega = {}
    for v in vals:
        if v["Data"] == data and v.get("baseCalculo", 0) == 0 and v["DataReferencia"] in anos:
            pega.setdefault((v["Indicador"], v["DataReferencia"]), v["Mediana"])
    ano = " e ".join(anos)
    d = date.fromisoformat(data)
    seg = d + timedelta(days=(7 - d.weekday()) % 7)
    t = datetime(seg.year, seg.month, seg.day, 8, 30, tzinfo=TZ)
    rot = {"IPCA": ("IPCA", "%"), "Selic": ("Selic no fim de", "% ao ano"), "Câmbio": ("Dólar no fim de", " reais"), "PIB Total": ("PIB", "%")}
    linhas = [f"{rot[k][0]} {a}: {br(float(v))}{rot[k][1]}" for (k, a), v in sorted(pega.items(), key=lambda x: (x[0][1], x[0][0])) if k in rot]
    out.append(ev(f"inv-focus-{d:%Y%m%d}", f"Focus: o que o mercado espera para {ano}", t, t + timedelta(minutes=15),
                  f"Mediana das projeções de cerca de cem bancos e consultorias, coletadas até {d:%d/%m}:\n" + "\n".join(linhas) +
                  "\n\nO Boletim Focus sai toda segunda às 8h25. Ele não é previsão do Banco Central, é o que o mercado acha; "
                  "a distância entre ele e a meta de inflação ajuda a entender as decisões do Copom.\n\nBase: Banco Central do Brasil, Sistema de Expectativas de Mercado."))
    return out


def _ibge():
    out = []
    cal = busca_json("https://servicodados.ibge.gov.br/api/v3/calendario/?qtd=200")
    itens = cal.get("items", cal) if isinstance(cal, dict) else cal
    for x in itens:
        s = str(x.get("data_inicio", ""))
        try:
            dt = datetime.strptime(s[:19], "%d/%m/%Y %H:%M:%S") if "/" in s else datetime.fromisoformat(s[:19])
        except ValueError:
            continue
        if not (INI <= dt.date() <= FIM) or "divulga" not in str(x.get("tipo", "")).lower():
            continue
        dt = dt.replace(tzinfo=TZ) if dt.hour else datetime(dt.year, dt.month, dt.day, 9, tzinfo=TZ)
        titulo = str(x.get("titulo") or x.get("produto") or "Divulgação do IBGE")[:110]
        out.append(ev(f"inv-ibge-{x.get('id', titulo)}", f"IBGE: {titulo}", dt, dt + timedelta(minutes=15), descricao=
                      f"{x.get('descricao') or ''}\n\nDivulgação do calendário oficial do IBGE.{(' ' + str(x.get('link'))) if x.get('link') else ''}\n\n"
                      "Base: IBGE, calendário de divulgações."))
    return out


WMO = {0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado", 45: "nevoeiro", 48: "nevoeiro com geada",
       51: "garoa fraca", 53: "garoa", 55: "garoa forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
       80: "pancadas fracas", 81: "pancadas", 82: "pancadas fortes", 95: "trovoadas", 96: "trovoadas com granizo", 99: "trovoadas com granizo"}


def area_clima(reg):
    q = urllib.parse.urlencode({"latitude": reg["lat"], "longitude": reg["lon"], "timezone": str(TZ), "forecast_days": 7,
                                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,uv_index_max,weather_code"})
    j = busca_json("https://api.open-meteo.com/v1/forecast?" + q)["daily"]
    feito = AGORA.astimezone(TZ)
    out = []
    for i, dia in enumerate(j["time"]):
        d = date.fromisoformat(dia)
        tmax, tmin = j["temperature_2m_max"][i], j["temperature_2m_min"][i]
        pp, mm, uv = j["precipitation_probability_max"][i], j["precipitation_sum"][i], j["uv_index_max"][i]
        cond = WMO.get(j["weather_code"][i], "tempo variável")
        uvtxt = "" if uv is None else f" Índice UV máximo {br(uv,0)}{' (muito alto: sombra entre 10h e 16h)' if uv >= 8 else ''}."
        calor = " Calor forte: beba água antes de sentir sede, porque a sede chega depois da desidratação começar." if tmax >= 34 else ""
        out.append(ev(f"clima-{d:%Y%m%d}", f"{tmax:.0f}° / {tmin:.0f}° · chuva {pp or 0}% · {cond}", d, dia_todo=True, descricao=
                      f"Máxima {tmax:.0f} °C, mínima {tmin:.0f} °C. Chance de chuva {pp or 0}%, {br(mm or 0,1)} mm previstos.{uvtxt}{calor}\n\n"
                      f"Previsão feita em {feito:%d/%m às %Hh%M}. O Google relê este calendário a cada 12 a 24 horas.\n\nBase: Open-Meteo."))
    return out


FAIXAS_AR = [(50, "bom", "Ar limpo, sem restrição."), (100, "moderado", "Pessoas muito sensíveis podem sentir; os demais, sem restrição."),
             (150, "ruim para grupos sensíveis", "Quem tem asma, doença cardíaca ou pulmonar, crianças e idosos devem reduzir esforço longo ao ar livre."),
             (200, "ruim", "Todos devem reduzir esforço intenso ao ar livre; grupos sensíveis, evitar."),
             (300, "muito ruim", "Evite atividade ao ar livre; mantenha janelas fechadas nos horários piores."),
             (10**9, "perigoso", "Fique em ambiente fechado.")]


def area_ar(reg):
    q = urllib.parse.urlencode({"latitude": reg["lat"], "longitude": reg["lon"], "timezone": str(TZ), "forecast_days": 5,
                                "hourly": "us_aqi,pm2_5,ozone"})
    j = busca_json("https://air-quality-api.open-meteo.com/v1/air-quality?" + q)["hourly"]
    por_dia = {}
    for t, aqi, pm in zip(j["time"], j["us_aqi"], j["pm2_5"]):
        if aqi is None:
            continue
        d = t[:10]
        if d not in por_dia or aqi > por_dia[d][0]:
            por_dia[d] = (aqi, pm, t[11:16])
    out = []
    for dia, (aqi, pm, hora) in sorted(por_dia.items()):
        nome, conselho = next((n, c) for lim, n, c in FAIXAS_AR if aqi <= lim)
        d = date.fromisoformat(dia)
        out.append(ev(f"ar-{d:%Y%m%d}", f"Ar {nome} (índice {aqi:.0f})", d, dia_todo=True, descricao=
                      f"Pior momento previsto por volta das {hora.replace(':', 'h')}, índice {aqi:.0f} na escala americana (EPA), "
                      f"com partículas finas PM2,5 em {br(pm or 0, 0)} µg/m³. {conselho}\n\n"
                      "As partículas finas entram fundo no pulmão e passam para o sangue; queimadas e trânsito são as fontes principais no Brasil. "
                      "Valor de modelo, não de estação de medição: serve para ver a tendência.\n\nBase: Open-Meteo, modelo CAMS do programa Copernicus."))
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
    seg = HOJE - timedelta(days=HOJE.weekday())
    t = datetime(seg.year, seg.month, seg.day, 6, tzinfo=TZ)
    obs.sort(key=lambda x: x.get("obsDt", ""), reverse=True)
    linhas = [f"{x['comName']} ({x.get('locName','')}, {x.get('obsDt','')[8:10]}/{x.get('obsDt','')[5:7]})" for x in obs[:40]]
    out = [ev(f"aves-semana-{seg:%Y%m%d}", f"Aves por perto: {len(obs)} espécie{'s' if len(obs) != 1 else ''} na última semana", t, t + timedelta(minutes=30),
              f"Espécies registradas por observadores num raio de 25 km de {reg['nome']} nos últimos 7 dias:\n\n" + "\n".join(linhas) +
              ("\n..." if len(obs) > 40 else "") + "\n\nLugar sem observador não aparece, mesmo cheio de aves.\n\nBase: eBird, Cornell Lab of Ornithology.")]
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


# ---------------------------------------------------------------- textos escritos pelo Claude (tarefas semanais)
SELO = {"sazonal": "", "agenda": "", "confirmar": "Data provável: confira antes de contar com ela."}


def textos(escopo, aid):
    """Eventos escritos pelas tarefas semanais em textos/<escopo>/*.json para a área aid."""
    pasta = RAIZ / "textos" / escopo
    out = []
    for arq in sorted(pasta.glob("*.json")) if pasta.exists() else []:
        try:
            itens = json.loads(arq.read_text(encoding="utf-8"))
        except ValueError as ex:
            log(f"[textos/{escopo}/{arq.name}] JSON inválido: {ex}")
            continue
        for i, x in enumerate(itens):
            try:
                if x.get("area") != aid or not x.get("titulo") or not x.get("descricao"):
                    continue
                d = date.fromisoformat(str(x["data"]))
                if not (INI <= d <= FIM):
                    continue
                selo = SELO.get(x.get("confianca"), "")
                desc = x["descricao"].strip() + (f"\n\n{selo}" if selo else "") + (f"\n\nFonte: {x['fonte']}" if x.get("fonte") else "") + \
                    "\n\nTexto do Claude (IA), com pesquisa."
                slug = unicodedata.normalize("NFKD", x["titulo"]).encode("ascii", "ignore").decode().lower()[:40]
                uid = f"txt-{aid}-{d:%Y%m%d}-" + "".join(c if c.isalnum() else "-" for c in slug)
                hora = str(x.get("hora") or "")
                if len(hora) == 5 and hora[2] == ":":
                    t = datetime(d.year, d.month, d.day, int(hora[:2]), int(hora[3:]), tzinfo=ZoneInfo(FUSO_BR))
                    out.append(ev(uid, x["titulo"][:120], t, t + timedelta(minutes=int(x.get("duracao_min") or 30)), desc))
                else:
                    out.append(ev(uid, x["titulo"][:120], d, descricao=desc, dia_todo=True))
            except (ValueError, KeyError, TypeError) as ex:
                log(f"[textos/{escopo}/{arq.name}] item {i} ignorado: {ex}")
    return out


CALC = {"lua": area_lua, "ceu": area_ceu, "sol": area_sol, "estacoes": area_estacoes, "feriados": area_feriados,
        "judaico": area_judaico, "islamico": area_islamico, "chines": area_chines, "hindu": area_hindu,
        "vedico": area_vedico, "ayurveda": area_ayurveda, "saude": area_saude,
        "economia": area_economia, "investidor": area_investidor, "clima": area_clima, "ar": area_ar, "aves": area_aves}
AO_VIVO = {"economia", "investidor", "clima", "ar", "aves"}  # acumulam histórico e mantêm o anterior se a fonte cair


# ---------------------------------------------------------------- saída
DTSTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)  # fixo: evita reescrever todos os arquivos todo dia


def para_ics(eventos, nome_cal, descricao):
    cal = Calendar()
    cal.add("prodid", "-//Agenda do Mundo//PT-BR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", nome_cal)
    cal.add("x-wr-caldesc", descricao)
    cal.add("x-wr-timezone", FUSO_BR)
    cal.add("refresh-interval", timedelta(hours=12), parameters={"VALUE": "DURATION"})
    cal.add("x-published-ttl", "PT12H")
    for e in eventos:
        v = Event()
        uid = unicodedata.normalize("NFKD", e["uid"]).encode("ascii", "ignore").decode().replace(" ", "_")
        v.add("uid", uid + "@agenda-do-mundo")
        v.add("dtstamp", DTSTAMP)
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


def gerar_area(area, lugar, escopo_textos, catalogo):
    """Calcula uma área para um lugar, junta os textos do Claude e grava .json e .ics. Devolve os eventos."""
    global TZ
    TZ = ZoneInfo(lugar.get("tz", FUSO_BR))
    aid = area["id"]
    pasta = SAIDA / lugar["id"]
    pasta.mkdir(parents=True, exist_ok=True)
    arq_json = pasta / f"{aid}.json"
    antigos = json.loads(arq_json.read_text(encoding="utf-8")) if arq_json.exists() else []
    ok, novos = True, []
    if aid in CALC:
        try:
            novos = CALC[aid](lugar)
        except Exception as ex:
            ok = False
            log(f"[{lugar['id']}/{aid}] não atualizou: {type(ex).__name__}: {ex}")
            catalogo["avisos"].append(f"{lugar['id']}/{aid}: {type(ex).__name__}: {ex}")
    extra = textos(escopo_textos, aid) if escopo_textos else []
    if aid in AO_VIVO or (aid not in CALC):
        limite = (HOJE - timedelta(days=30)).isoformat()
        junto = {e["uid"]: e for e in antigos if e["inicio"][:10] >= limite}
        junto.update({e["uid"]: e for e in novos + extra})
        eventos = list(junto.values())
    else:
        eventos = (novos if ok else antigos) + extra
    eventos.sort(key=chave_ordem)
    if not eventos:
        return []
    arq_json.write_text(json.dumps(eventos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (pasta / f"{aid}.ics").write_bytes(para_ics(eventos, f"{area['nome']} · {lugar['nome']}", f"{area['resumo']} Agenda do Mundo."))
    prox = [e for e in eventos if e["inicio"][:10] >= HOJE.isoformat()]
    catalogo["feeds"].setdefault(lugar["id"], {})[aid] = {"n": len(eventos), "atualizado": ok,
                                                          "proximos": [{"titulo": e["titulo"], "inicio": e["inicio"]} for e in prox[:3]]}
    return eventos


def main():
    catalogo = {"projeto": CFG["projeto"], "gerado_em": AGORA.astimezone(ZoneInfo(FUSO_BR)).isoformat(timespec="minutes"),
                "regioes": CFG["regioes"], "macros": CFG["macros"], "grupos": CFG["grupos"],
                "areas": [{k: a[k] for k in ("id", "nome", "grupo", "escopo", "resumo", "fonte")} for a in CFG["areas"]],
                "feeds": {}, "avisos": []}
    brasil = {"id": "brasil", "nome": "Brasil", "tz": FUSO_BR, "lat": -15.7797, "lon": -47.9297, "uf": "DF"}
    por_lugar = {}
    for area in [a for a in CFG["areas"] if a["escopo"] == "nacional"]:
        por_lugar.setdefault("brasil", {})[area["id"]] = gerar_area(area, brasil, "brasil", catalogo)
    for mid, mnome in CFG["macros"].items():
        lugar = {"id": mid, "nome": mnome, "tz": FUSO_BR}
        for area in [a for a in CFG["areas"] if a["escopo"] == "regional"]:
            por_lugar.setdefault(mid, {})[area["id"]] = gerar_area(area, lugar, mid, catalogo)
    for reg in CFG["regioes"]:
        tudo = []
        for area in CFG["areas"]:
            if area["escopo"] == "local":
                evs = gerar_area(area, reg, None, catalogo)
            else:
                evs = por_lugar.get("brasil" if area["escopo"] == "nacional" else reg["macro"], {}).get(area["id"], [])
            tudo += [dict(e, titulo=f"{area['nome']}: {e['titulo']}") for e in evs]
        tudo.sort(key=chave_ordem)
        (SAIDA / reg["id"] / "tudo.ics").write_bytes(para_ics(tudo, f"Agenda do Mundo · {reg['nome']}", "Todas as áreas da Agenda do Mundo."))
        log(f"[{reg['id']}] {len(tudo)} eventos no total")
    # avisos repetidos por cidade viram um só por área e tipo de erro
    vistos, avisos = set(), []
    for a in catalogo["avisos"]:
        lugar, resto = a.split("/", 1)
        if resto not in vistos:
            vistos.add(resto)
            avisos.append(a)
    catalogo["avisos"] = avisos + sorted(set(PARCIAIS))
    falhas = [a for a in catalogo["avisos"] if "sem EBIRD_KEY" not in a]
    (RAIZ / "falhas.txt").write_text("\n".join(falhas), encoding="utf-8")
    (RAIZ / "docs" / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
