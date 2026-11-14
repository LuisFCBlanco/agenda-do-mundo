# Agenda do Mundo

Calendários assináveis com o que acontece no mundo ao redor de cada região: o céu, a natureza, a economia, as culturas, a saúde e a história, para 47 cidades. A pessoa escolhe as áreas no site e assina cada uma no Google Agenda, iPhone ou Outlook. Ninguém faz login e nada é gravado na agenda de ninguém.

## Como funciona

- `gerar.py` monta um `.ics` por região e área dentro de `docs/feeds/`, e o `docs/catalogo.json` que o site lê.
- O GitHub Actions (`.github/workflows/diario.yml`) roda esse script todo dia às 5h17 e publica o resultado.
- O GitHub Pages serve a pasta `docs/` como site.
- Lua, céu, sol e feriados são calculados, sem internet. Economia, clima e aves buscam a fonte; se ela falhar, o calendário mantém os dados anteriores em vez de ficar vazio.

## Colocar no ar (uma vez)

1. Crie uma conta em github.com.
2. Crie um repositório **público** chamado `agenda-do-mundo`, vazio.
3. Envie estes arquivos para ele.
4. Em **Settings > Pages**, escolha "Deploy from a branch", branch `main`, pasta `/docs`.
5. Em **Actions**, abra "Gerar calendários" e toque em **Run workflow** para a primeira geração.
6. O site fica em `https://SEU-USUARIO.github.io/agenda-do-mundo/`.

Aves: crie uma chave gratuita em ebird.org/api/keygen e salve em **Settings > Secrets and variables > Actions** com o nome `EBIRD_KEY`. Sem a chave, a área de aves só não aparece.

## Mudar regiões e áreas

`config.json` lista as regiões (nome, coordenadas, estado) e as áreas. Uma região nova é uma linha nova com latitude e longitude.

## Pontos em aberto

- Banco Central, Open-Meteo e eBird foram testados com respostas no formato documentado de cada um, não contra os servidores reais. O primeiro "Run workflow" é o teste real.
- O link "Assinar no Google" usa um formato que o Google não documenta oficialmente, mas que é amplamente usado. "Copiar link" funciona sempre.
- Em repositório público, o GitHub pode pausar tarefas agendadas depois de 60 dias sem atividade. Se chegar um e-mail avisando, basta reativar em Actions.

## Textos escritos pelo Claude

As áreas de natureza, safra, cultura regional, história, materiais, esporte, telas, energia e agro vêm de `textos/<escopo>/*.json` (`brasil` ou uma das cinco regiões), escritos por quatro tarefas agendadas do Claude que pesquisam na web. As regras estão em `tarefas/REGRAS.md`, o passo a passo em `tarefas/PROCEDIMENTO.md`, e `validar.py` confere cada arquivo antes do commit.

## Escopos

- **local** (cada cidade de `config.json`): Lua, céu, sol, estações, clima, qualidade do ar, aves do eBird, feriados, calendário védico, Ayurveda.
- **regional** (Norte, Nordeste, Centro-Oeste, Sudeste, Sul): natureza, safra, cultura.
- **nacional** (`brasil`): economia, investidor, agro, energia, culturas do mundo, saúde pública, história, materiais, datas, esporte, telas.
